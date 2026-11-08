#!/usr/bin/env python3
"""按剪辑表（EDL）把片段剪成一条成片。导演编写，Codex 在本地运行。

  python film01/tools/assemble.py story/T01_edl_v1.json            # 渲染成片（只在本地）+ 剪辑点检查包
  python film01/tools/assemble.py story/T01_edl_v1.json --dry-run  # 只检查剪辑表、打印时间线，不渲染

剪辑表格式（路径相对 film01/）：
{
  "name": "T01_cut_v1",           # 输出 video/T01_cut_v1.mp4；已存在就拒绝，不覆盖
  "size": [864, 480], "fps": 24,
  "fade_in": 0.3, "fade_out": 0.5, # 片头淡入、片尾淡出（秒），0 表示不要
  "segments": [ {"shot": "S01", "src": "video/S01_v1.mp4", "in": 1.0, "out": 3.5}, ... ]
}
检查包输出到 video_check/<name>/：cuts.jpg（每段第一帧和最后一帧）、timeline.md。这些要提交，mp4 不提交。
"""
import argparse
import json
import subprocess
import sys
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


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"命令失败: {' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r.stdout


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    edl = json.loads(rel(a.edl).read_text(encoding="utf-8-sig"))
    name, (W, H), fps = edl["name"], edl["size"], edl["fps"]
    segs = edl["segments"]
    for s in segs:  # 入点、出点对齐到整帧
        s["in"], s["out"] = round(s["in"] * fps) / fps, round(s["out"] * fps) / fps
    out = ROOT / "video" / f"{name}.mp4"
    chk = ROOT / "video_check" / name
    if not a.dry_run and (out.exists() or chk.exists()):
        sys.exit(f"{out.relative_to(ROOT).as_posix()} 或它的检查包已存在，不覆盖。请导演在剪辑表里改 name 开新版本。")

    # 检查每段
    lines, t, problems = [], 0.0, []
    for i, s in enumerate(segs):
        src = rel(s["src"])
        if not src.exists():
            problems.append(f"第 {i + 1} 段 {s['shot']}：找不到 {s['src']}")
            continue
        d = duration(src)
        if not (0 <= s["in"] < s["out"] <= d + 1e-3):
            problems.append(f"第 {i + 1} 段 {s['shot']}：入点/出点 {s['in']}–{s['out']} 超出素材长度 {d:.2f}s")
        seg = s["out"] - s["in"]
        lines.append(f"| {i + 1} | {s['shot']} | {s['src']} | {s['in']:.2f}–{s['out']:.2f} | {seg:.2f}s | {t:.2f}–{t + seg:.2f} |")
        t += seg
    head = ["| # | 镜头 | 素材 | 素材入/出点 | 时长 | 成片时间 |", "|---|---|---|---|---|---|"]
    print("\n".join(head + lines))
    print(f"总时长 {t:.2f}s")
    if problems:
        sys.exit("剪辑表有问题：\n" + "\n".join(problems))
    if a.dry_run:
        return

    # 渲染
    cmd = ["ffmpeg", "-v", "error"]
    for s in segs:
        cmd += ["-i", str(rel(s["src"]))]
    parts = []
    for i, s in enumerate(segs):
        parts.append(f"[{i}:v]trim=start={s['in']}:end={s['out']},setpts=PTS-STARTPTS,fps={fps},"
                     f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"  # 比例略有差别时裁掉一点，不加黑边
                     
                     f"setsar=1,format=yuv420p[v{i}]")
    chain = "".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0"
    fades = []
    if edl.get("fade_in"):
        fades.append(f"fade=t=in:st=0:d={edl['fade_in']}")
    if edl.get("fade_out"):
        fades.append(f"fade=t=out:st={t - edl['fade_out']:.3f}:d={edl['fade_out']}")
    chain += ("," + ",".join(fades) if fades else "") + "[out]"
    parts.append(chain)
    out.parent.mkdir(exist_ok=True)
    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]", "-c:v", "libx264", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    run(cmd)
    real = duration(out)
    print(f"已生成 {out.relative_to(ROOT).as_posix()}（{real:.2f}s，只在本地，不提交）")

    # 剪辑点检查包：每段的第一帧和最后一帧
    from PIL import Image, ImageDraw
    chk.mkdir(parents=True)
    tiles, t0 = [], 0.0
    for i, s in enumerate(segs):
        seg = s["out"] - s["in"]
        for label, ts in (("IN", t0 + 0.5 / fps), ("OUT", t0 + seg - 1.0 / fps)):
            f = chk / f"_{i}_{label}.png"
            run(["ffmpeg", "-v", "error", "-ss", f"{ts:.3f}", "-i", str(out), "-frames:v", "1", str(f)])
            tiles.append((f"{i + 1} {s['shot']} {label} {ts:.2f}s", Image.open(f).convert("RGB")))
        t0 += seg
    tw, th = 432, round(432 * H / W)
    sheet = Image.new("RGB", (tw * 2, (th + 22) * len(segs)), "white")
    d = ImageDraw.Draw(sheet)
    for k, (lab, im) in enumerate(tiles):
        x, y = (k % 2) * tw, (k // 2) * (th + 22)
        sheet.paste(im.resize((tw, th)), (x, y + 22))
        d.text((x + 4, y + 4), lab, fill="black")
    sheet.save(chk / "cuts.jpg", quality=85)
    for f in chk.glob("_*.png"):
        f.unlink()
    (chk / "timeline.md").write_text(f"# {name} 时间线\n\n" + "\n".join(head + lines) +
                                     f"\n\n总时长 {t:.2f}s（成片实测 {real:.2f}s）\n\n![cuts](cuts.jpg)\n",
                                     encoding="utf-8")
    print(f"检查包 {chk.relative_to(ROOT).as_posix()}/（cuts.jpg、timeline.md）")


if __name__ == "__main__":
    main()
