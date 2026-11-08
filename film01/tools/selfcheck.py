#!/usr/bin/env python3
"""本地环境自检。不花钱，不打印密钥。

  python film01/tools/selfcheck.py
"""
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

rows = []


def check(name, ok, detail=""):
    rows.append((name, ok, detail))


def ver(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception as e:
        return f"错误: {e}"


check("系统", True, f"{platform.platform()}  WSL={'microsoft' in platform.release().lower()}")
check("Python ≥ 3.9", sys.version_info >= (3, 9), sys.version.split()[0])
try:
    import PIL
    check("Pillow", True, PIL.__version__)
except ImportError:
    check("Pillow", False, "pip install pillow")
for tool in ("git", "ffmpeg", "ffprobe", "codex"):
    p = shutil.which(tool)
    flag = "-version" if tool in ("ffmpeg", "ffprobe") else "--version"
    check(tool, bool(p), ver([tool, flag]) if p else "未找到")
if shutil.which("ffmpeg"):
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    check("ffmpeg libx264", "libx264" in enc)
    check("ffmpeg 字幕滤镜(libass)", " subtitles " in flt)
fonts = subprocess.run(["fc-list", ":lang=zh"], capture_output=True, text=True).stdout if shutil.which("fc-list") else ""
check("中文字体", bool(fonts.strip()), (fonts.strip().splitlines() or ["未找到，字幕需要装字体，如 fonts-noto-cjk"])[0][:80])

codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
gi = codex_home / "generated_images"
check("Codex 生图目录", gi.exists(), str(gi) + ("" if gi.exists() else "（还没画过图时不存在，属于正常）"))
check("ARK_API_KEY 已设置", bool(os.environ.get("ARK_API_KEY")), "不显示内容")

url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
try:
    urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=20)
    check("连通火山方舟", True, "200")
except urllib.error.HTTPError as e:
    check("连通火山方舟", True, f"HTTP {e.code}（未带密钥，能返回错误码就说明网络通）")
except Exception as e:
    check("连通火山方舟", False, repr(e)[:120])

repo = Path(__file__).resolve().parents[2]
try:
    br = subprocess.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                        text=True).stdout.strip()
    ign = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "film01/video/x.mp4"]).returncode == 0
    check("git 分支", True, br)
    check("mp4 已被忽略", ign)
except Exception as e:
    check("git", False, repr(e))

for name, ok, detail in rows:
    print(f"{'✅' if ok else '❌'} {name:<22} {detail}")
OPTIONAL = {"Codex 生图目录"}
sys.exit(0 if all(ok for name, ok, _ in rows if name not in OPTIONAL) else 1)
