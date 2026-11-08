#!/usr/bin/env python3
"""从本地视频抽帧，生成给导演看的检查包，视频本身不提交。

  python film01/tools/inspect_video.py S03_v1 [--frames 8] [--video 其他路径.mp4]

输出到 video_check/<clip>/（已存在就拒绝，不覆盖）：
  probe.json          ffprobe 原始信息
  f00_n0000.jpg ...   均匀抽的帧，第一帧和最后一帧都包含
  sheet.jpg           联系表（所有抽帧拼成一张图）
  summary.json/.md    时长、分辨率、帧率、有没有音轨、每帧亮度、和首尾帧原图的差异
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"命令失败: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout


def rel(p):
    p = Path(p)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == ROOT.name:
        p = Path(*p.parts[1:])
    return ROOT / p


def diff(a, b):
    """Mean absolute RGB difference on 64x36 thumbnails, 0 (identical) .. 255."""
    from PIL import Image, ImageChops, ImageStat
    sa = a.convert("RGB").resize((64, 36))
    sb = b.convert("RGB").resize((64, 36))
    return round(sum(ImageStat.Stat(ImageChops.difference(sa, sb)).mean) / 3, 1)


def main():
    from PIL import Image, ImageDraw, ImageStat
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--video")
    a = ap.parse_args()

    video = rel(a.video) if a.video else ROOT / "video" / f"{a.clip}.mp4"
    if not video.exists():
        sys.exit(f"视频不存在: {video}")
    out = ROOT / "video_check" / a.clip
    if out.exists():
        sys.exit(f"{out.relative_to(ROOT)} 已存在，不覆盖。要重抽就换一个 clip 名或用 --video 另起。")
    probe = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_format", "-show_streams",
                            "-of", "json", str(video)]))
    final = out
    out = final.with_name(f".{a.clip}.partial")  # 先写到临时目录，全部成功后再改名
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "probe.json").write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    nframes = int(vs.get("nb_read_frames") or vs.get("nb_frames"))
    num, den = (int(x) for x in vs["r_frame_rate"].split("/"))
    fps = num / den
    k = max(2, min(a.frames, nframes))
    idx = sorted({round(i * (nframes - 1) / (k - 1)) for i in range(k)})

    sel = "+".join(f"eq(n\\,{i})" for i in idx)
    tmp = out / "_f%03d.jpg"
    run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select='{sel}'", "-fps_mode", "vfr",
         "-q:v", "3", str(tmp)])
    files = []
    for j, i in enumerate(idx):
        src = out / f"_f{j + 1:03d}.jpg"
        dst = out / f"f{j:02d}_n{i:04d}.jpg"
        src.rename(dst)
        files.append(dst)

    frames = [Image.open(f) for f in files]
    lum = [round(ImageStat.Stat(f.convert("L")).mean[0], 1) for f in frames]
    step = [diff(frames[j], frames[j + 1]) for j in range(len(frames) - 1)]

    spec_f = ROOT / "shots" / f"{a.clip}.json"
    match = {}
    if spec_f.exists():
        spec = json.loads(spec_f.read_text(encoding="utf-8"))
        for key, fr in (("first_frame", frames[0]), ("last_frame", frames[-1])):
            if spec.get(key) and rel(spec[key]).exists():
                with Image.open(rel(spec[key])) as ref:
                    match[key] = {"file": spec[key], "mean_abs_diff": diff(fr, ref)}

    # contact sheet
    tw = 480
    th = round(tw * frames[0].height / frames[0].width)
    cols = 4
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 24)), "white")
    d = ImageDraw.Draw(sheet)
    for j, (f, i) in enumerate(zip(frames, idx)):
        x, y = (j % cols) * tw, (j // cols) * (th + 24)
        sheet.paste(f.convert("RGB").resize((tw, th)), (x, y + 24))
        d.text((x + 6, y + 6), f"#{j}  frame {i}  t={i / fps:.2f}s", fill="black")
    sheet.save(out / "sheet.jpg", quality=85)

    audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    summary = {
        "clip": a.clip,
        "video_file_local_only": str(video),
        "duration_s": float(probe["format"]["duration"]),
        "size": f"{vs['width']}x{vs['height']}",
        "fps": round(fps, 3),
        "frames": nframes,
        "codec": vs["codec_name"],
        "has_audio": bool(audio),
        "audio_codec": audio[0]["codec_name"] if audio else None,
        "bytes": int(probe["format"]["size"]),
        "sampled_frames": [f.name for f in files],
        "mean_luma": lum,
        "diff_between_samples": step,
        "match_with_keyframes": match,
        "note": "mean_abs_diff 范围 0–255，越小越接近原图；只是粗略指标，导演还要看图。",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [f"# {a.clip} 检查包", "",
          f"- 时长 {summary['duration_s']:.2f}s，{summary['size']}，{summary['fps']} fps，共 {nframes} 帧，{vs['codec_name']}",
          f"- 音轨：{'有（' + summary['audio_codec'] + '）' if audio else '无'}",
          f"- 抽帧亮度：{lum}", f"- 相邻抽帧差异：{step}"]
    for key, m in match.items():
        md.append(f"- 与 {key} 原图差异：{m['mean_abs_diff']}（{m['file']}）")
    md += ["", "![sheet](sheet.jpg)", ""]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    out.rename(final)
    print("\n".join(md))
    print(f"\n已写入 {final.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
