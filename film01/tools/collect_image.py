#!/usr/bin/env python3
"""把 Codex 刚画好的图归档进 film01/images/，版本号自动递增，不覆盖。

  python film01/tools/collect_image.py --name S03_first --since 1731050000 \
      --prompt prompts/S03_first_v1.txt --refs images/CHAR_a_v1.png --job JOB-0005

在 ~/.codex/generated_images/（或 $CODEX_HOME/generated_images/）下找修改时间晚于 --since 的图片：
正好 1 张就归档；0 张或多张就报错并列出来，不自己挑（多张时可以用 --source 指定）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def rel(p):
    p = Path(p)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == ROOT.name:
        p = Path(*p.parts[1:])
    return ROOT / p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="输出名，例如 S03_first（不带版本号）")
    ap.add_argument("--since", type=float, required=True, help="开始画图前的 date +%%s")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--refs", nargs="*", default=[])
    ap.add_argument("--job", default="")
    ap.add_argument("--source", help="多张候选时，明确指定其中一张")
    a = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_\-]+", a.name) or re.search(r"_v\d+$", a.name):
        sys.exit("--name 只能包含字母、数字、下划线和连字符，且不要自带 _v 版本号")
    gen = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "generated_images"
    if a.source:
        cands = [Path(a.source).expanduser()]
        if not cands[0].exists():
            sys.exit(f"--source 不存在: {cands[0]}")
    else:
        if not gen.exists():
            sys.exit(f"找不到 {gen}")
        cands = sorted((p for p in gen.rglob("*") if p.suffix.lower() in EXTS and p.stat().st_mtime > a.since),
                       key=lambda p: p.stat().st_mtime)
        if len(cands) != 1:
            print(f"在 {gen} 下找到 {len(cands)} 张晚于 {a.since} 的新图，要求正好 1 张：", file=sys.stderr)
            for p in cands[:20]:
                print(f"  {p}  {datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds')}",
                      file=sys.stderr)
            sys.exit(1)
    src = cands[0]
    src_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    for side in (ROOT / "images").glob("*.json"):
        try:
            if json.loads(side.read_text(encoding="utf-8")).get("sha256") == src_sha:
                sys.exit(f"这张图已经归档过了：{side.with_suffix('').name}（来源 {src}），不重复归档")
        except ValueError:
            pass
    prompt_p = rel(a.prompt)
    if not prompt_p.exists():
        sys.exit(f"提示词文件不存在: {prompt_p}")

    out_dir = ROOT / "images"
    out_dir.mkdir(exist_ok=True)
    n = 1
    while any((out_dir / f"{a.name}_v{n}{e}").exists() for e in EXTS):
        n += 1
    ext = ".jpg" if src.suffix.lower() == ".jpeg" else src.suffix.lower()
    dst = out_dir / f"{a.name}_v{n}{ext}"
    shutil.copy2(src, dst)  # 新文件名，不会覆盖

    from PIL import Image
    with Image.open(dst) as im:
        w, h = im.size
    raw = dst.read_bytes()
    meta = {
        "file": str(dst.relative_to(ROOT)),
        "version": n,
        "size": f"{w}x{h}",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source": str(src),
        "codex_session_dir": src.parent.name,
        "prompt_file": str(prompt_p.relative_to(ROOT)),
        "prompt_sha256": hashlib.sha256(prompt_p.read_bytes()).hexdigest(),
        "refs": a.refs,
        "job": a.job,
        "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(dst.with_suffix(".json"), "x", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已归档 {meta['file']}  {w}x{h}  sha256={meta['sha256'][:12]}  来源 {src}")


if __name__ == "__main__":
    main()
