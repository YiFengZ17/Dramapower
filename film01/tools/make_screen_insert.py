#!/usr/bin/env python3
"""S03 屏幕特写：完全用代码生成，不花钱。

  python film01/tools/make_screen_insert.py                   # 生成 video/S03_insert_v1.mp4（只在本地）
  python film01/tools/make_screen_insert.py --stills-only     # 只出 3 张静帧到 inserts/，给导演和用户看
  python film01/tools/make_screen_insert.py --version 2 --duration 3.5

画面：终端里运行着本地千问（ollama run qwen3），大肥鱼让它代写全部需求；
右边代码自动滚动；底部状态栏写着“摸鱼中”；屏幕玻璃上粘着几粒米饭；镜头缓慢推近。
不覆盖已有文件：同一版本号的输出已存在就拒绝。
"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 720

CJK_FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/System/Library/Fonts/PingFang.ttc"]
MONO_FONTS = ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/CascadiaMono.ttf",
              "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/System/Library/Fonts/Menlo.ttc"]

BG = (12, 16, 34)
PANEL = (20, 27, 52)
TITLE = (30, 39, 72)
SKY = (110, 198, 255)
WHITE = (236, 242, 255)
GRAY = (122, 136, 170)
GREEN = (126, 220, 160)
YELLOW = (255, 214, 120)
PINK = (255, 150, 190)

USER_MSG = "帮我把今天的需求全写完，我去吃口饭～"
REPLY = "好的！交给我吧，你慢慢吃～"
CODE = [
    ("kw", "def 今天的需求():"),
    ("", "    写代码()        # 千问在写"),
    ("", "    修bug()         # 千问在修"),
    ("", "    写周报()        # 千问在编"),
    ("", "    开会()          # 千问替她去"),
    ("", "    return \"下班\""),
    ("", ""),
    ("kw", "def 大肥鱼():"),
    ("", "    while True:"),
    ("", "        吃饭(碗=\"超大\")"),
    ("", "        假装敲键盘()"),
    ("", ""),
    ("kw", "def 补注释(n):"),
] + [("", f"    # 第 {i} 行：千问写的，别问") for i in range(1, 40)]


def find_font(cands, size):
    for c in cands:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    sys.exit(f"找不到字体，候选：{cands}")


class Fonts:
    def __init__(self):
        self.cjk = {s: find_font(CJK_FONTS, s) for s in (22, 26, 30, 34)}
        self.mono = {s: find_font(MONO_FONTS, s) for s in (22, 26, 30, 34)}


def text_mixed(d, xy, text, fonts, size, fill):
    """ASCII 用等宽字体，其他字符用中文字体。返回结束位置的 x 坐标。"""
    x, y = xy
    run, is_ascii = "", None
    for ch in text + "\0":
        a = ch.isascii()
        if ch != "\0" and (is_ascii is None or a == is_ascii):
            run += ch
            is_ascii = a
            continue
        if run:
            f = fonts.mono[size] if is_ascii else fonts.cjk[size]
            d.text((x, y + (0 if is_ascii else -2)), run, font=f, fill=fill)
            x += d.textlength(run, font=f)
        run, is_ascii = ch, a
    return x


def window(d, box, title, fonts):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, 14, fill=PANEL)
    d.rounded_rectangle((x0, y0, x1, y0 + 40), 14, fill=TITLE)
    d.rectangle((x0, y0 + 26, x1, y0 + 40), fill=TITLE)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((x0 + 16 + i * 24, y0 + 13, x0 + 30 + i * 24, y0 + 27), fill=c)
    text_mixed(d, (x0 + 100, y0 + 7), title, fonts, 22, GRAY)


def rice(layer, cx, cy, ang, scale=1.0):
    g = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    gd.ellipse((18, 24, 18 + 22 * scale, 24 + 12 * scale), fill=(250, 250, 244, 255), outline=(205, 205, 196, 255))
    gd.ellipse((22, 26, 30, 30), fill=(255, 255, 255, 255))
    g = g.rotate(ang, resample=Image.BICUBIC)
    layer.alpha_composite(g, (int(cx - 30), int(cy - 30)))


def frame(t, dur, fonts):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # 左：终端
    window(d, (40, 30, 700, 580), "终端 — ollama", fonts)
    y = 88
    text_mixed(d, (66, y), "$ ollama run qwen3", fonts, 26, GREEN)
    y += 50
    text_mixed(d, (66, y), ">>> ", fonts, 30, SKY)
    text_mixed(d, (66, y + 44), USER_MSG, fonts, 30, WHITE)
    y += 120
    n = max(0, min(len(REPLY), int((t - 0.25) / 0.9 * len(REPLY)))) if t > 0.25 else 0
    text_mixed(d, (66, y), "千问：", fonts, 26, YELLOW)
    xe = text_mixed(d, (66, y + 40), REPLY[:n], fonts, 30, WHITE)
    if n < len(REPLY) or int(t * 3) % 2 == 0:
        d.rectangle((xe + 4, y + 44, xe + 18, y + 76), fill=SKY)
    if t > 1.4:
        text_mixed(d, (66, y + 110), "正在生成 需求.py ……", fonts, 26, GRAY)

    # 右：编辑器，代码自动滚动
    window(d, (730, 30, 1240, 580), "需求.py", fonts)
    lines_done = t * 4.6  # 慢一点，让好笑的几行代码一直留在画面里
    lh, top, bottom = 34, 84, 566
    visible = (bottom - top) // lh
    start = max(0, int(lines_done) - visible + 1)
    for i in range(start, min(len(CODE), int(lines_done) + 1)):
        kind, s = CODE[i]
        if i == int(lines_done):
            s = s[: int((lines_done % 1) * len(s))]
        yy = top + (i - start) * lh
        text_mixed(d, (748, yy), f"{i + 1:>2}", fonts, 22, (70, 82, 120))
        color = PINK if kind == "kw" else (GRAY if s.strip().startswith("#") else WHITE)
        if "#" in s and kind != "kw":
            code, cmt = s.split("#", 1)
            text_mixed(d, (790, yy), code.rstrip(), fonts, 22, WHITE)
            text_mixed(d, (1010, yy), "#" + cmt, fonts, 22, GRAY)  # 注释对齐到固定列
        else:
            text_mixed(d, (790, yy), s, fonts, 22, color)

    # 底部状态栏
    d.rounded_rectangle((40, 596, 1240, 652), 14, fill=TITLE)
    bob = math.sin(t * 6) * 3
    text_mixed(d, (64, 607 + bob), "><((°>", fonts, 26, SKY)
    text_mixed(d, (170, 606), "状态：摸鱼中", fonts, 26, YELLOW if int(t * 2) % 2 == 0 else WHITE)
    p = 0.12 + 0.75 * min(1, t / dur)
    text_mixed(d, (640, 609), "千问干活进度", fonts, 22, GRAY)
    d.rounded_rectangle((800, 612, 1120, 636), 8, fill=(14, 19, 38))
    d.rounded_rectangle((800, 612, 800 + 320 * p, 636), 8, fill=SKY)
    text_mixed(d, (1135, 609), f"{round(p * 100)}%", fonts, 22, WHITE)

    # 屏幕玻璃上的米粒（静止，粘在屏幕上）
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for cx, cy, a in [(1150, 290, 20), (1185, 312, -35), (1120, 330, 70), (330, 520, 10)]:
        rice(over, cx, cy, a)
    im = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")

    # 镜头缓慢推近，并加一点屏幕光晕和暗角
    z = 1.0 + 0.04 * (t / dur)
    cw, ch = W / z, H / z
    cx, cy = W * 0.5, H * 0.47
    left = min(max(cx - cw / 2, 0), W - cw)
    top_ = min(max(cy - ch / 2, 0), H - ch)
    im = im.resize((W, H), Image.LANCZOS, box=(left, top_, left + cw, top_ + ch))
    glow = im.filter(ImageFilter.GaussianBlur(18))
    im = Image.blend(im, glow, 0.12)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), vig)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--duration", type=float, default=3.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--stills-only", action="store_true")
    a = ap.parse_args()

    fonts = Fonts()
    name = f"S03_insert_v{a.version}"
    sdir = ROOT / "inserts"
    sdir.mkdir(exist_ok=True)
    stills = [sdir / f"{name}_t{t:.1f}.png" for t in (0.0, a.duration / 2, a.duration)]
    if not any(p.exists() for p in stills):
        for p, t in zip(stills, (0.0, a.duration / 2, a.duration - 1 / a.fps)):
            frame(t, a.duration, fonts).save(p)
            print(f"静帧 {p.relative_to(ROOT).as_posix()}")
    else:
        print("静帧已存在，跳过")
    if a.stills_only:
        return

    out = ROOT / "video" / f"{name}.mp4"
    if out.exists():
        sys.exit(f"{out.relative_to(ROOT).as_posix()} 已存在，不覆盖。要改就用 --version 开新版本。")
    out.parent.mkdir(exist_ok=True)
    n = round(a.duration * a.fps)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                           "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame(i / a.fps, a.duration, fonts).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg 失败")
    print(f"已生成 {out.relative_to(ROOT).as_posix()}（{n} 帧，{a.duration}s，{a.fps}fps，只在本地，不提交）")


if __name__ == "__main__":
    main()
