#!/usr/bin/env python3
"""把图片裁成指定画幅（默认 16:9），另存新文件，不覆盖原图。

  python film01/tools/fit_ratio.py images/STYLE_a_v1.png
  python film01/tools/fit_ratio.py images/S01_first_v2.png --ratio 16:9 --y 0.4

输出：images/<原名>_16x9.png，以及同名 .json 说明。
--x / --y 控制裁切窗口的位置：0 表示贴左/贴上，0.5 表示居中（默认），1 表示贴右/贴下。
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent


def rel(p):
    p = Path(p)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == ROOT.name:
        p = Path(*p.parts[1:])
    return ROOT / p


def main():
    from PIL import Image
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--ratio", default="16:9")
    ap.add_argument("--x", type=float, default=0.5)
    ap.add_argument("--y", type=float, default=0.5)
    a = ap.parse_args()

    src = rel(a.image)
    if not src.exists():
        sys.exit(f"图片不存在: {src}")
    rw, rh = (int(v) for v in a.ratio.split(":"))
    tag = f"{rw}x{rh}"
    if src.stem.endswith("_" + tag):
        sys.exit("这张图已经裁过了")
    dst = src.with_name(f"{src.stem}_{tag}.png")
    if dst.exists():
        sys.exit(f"{dst.relative_to(ROOT).as_posix()} 已存在，不覆盖")

    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w * rh > h * rw:            # 太宽：裁左右
            cw, ch = round(h * rw / rh), h
        else:                          # 太高：裁上下
            cw, ch = w, round(w * rh / rw)
        cw -= cw % 2
        ch -= ch % 2
        left = round((w - cw) * min(max(a.x, 0), 1))
        top = round((h - ch) * min(max(a.y, 0), 1))
        out = im.crop((left, top, left + cw, top + ch))
        out.save(dst)

    meta = {
        "file": dst.relative_to(ROOT).as_posix(),
        "from": src.relative_to(ROOT).as_posix(),
        "from_size": f"{w}x{h}",
        "size": f"{cw}x{ch}",
        "crop_box": [left, top, left + cw, top + ch],
        "ratio": a.ratio,
        "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
        "made_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(dst.with_suffix(".json"), "x", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已裁切 {meta['from']} {w}x{h} -> {meta['file']} {cw}x{ch}（裁切框 {meta['crop_box']}）")


if __name__ == "__main__":
    main()
