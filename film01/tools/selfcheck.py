#!/usr/bin/env python3
"""本地环境自检。不花钱，不打印密钥。Windows（PowerShell/cmd）、WSL、Linux 都能运行。

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

# Windows 控制台或管道可能是 GBK 编码：遇到无法显示的字符就替换，不让脚本崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

IS_WIN = os.name == "nt"
IS_WSL = "microsoft" in platform.release().lower()
REPO = Path(__file__).resolve().parents[2]
rows = []


def check(name, ok, detail="", optional=False):
    rows.append((name, ok, detail, optional))


def first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return ((r.stdout or r.stderr).strip().splitlines() or [""])[0]
    except Exception as e:
        return f"错误: {e!r}"


env = "Windows 原生" if IS_WIN else ("WSL" if IS_WSL else "Linux/macOS")
check("系统", True, f"{env}  {platform.platform()}")
check("仓库路径", True, str(REPO))
check("Python 3.9 以上", sys.version_info >= (3, 9), f"{sys.version.split()[0]}  {sys.executable}")
try:
    import PIL
    check("Pillow", True, PIL.__version__)
except ImportError:
    check("Pillow", False, "运行 python -m pip install pillow")

for tool in ("git", "ffmpeg", "ffprobe", "codex"):
    p = shutil.which(tool)
    flag = "-version" if tool in ("ffmpeg", "ffprobe") else "--version"
    check(tool, bool(p), first_line([tool, flag])[:90] if p else "未找到（需要加入 PATH）")

if shutil.which("ffmpeg"):
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    check("ffmpeg 带 libx264", "libx264" in enc)
    check("ffmpeg 带字幕滤镜(libass)", " subtitles " in flt)

if IS_WIN:
    fontdir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    found = [f for f in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc") if (fontdir / f).exists()]
    check("中文字体", bool(found), ", ".join(found) or f"{fontdir} 下没找到微软雅黑或黑体")
elif shutil.which("fc-list"):
    fonts = subprocess.run(["fc-list", ":lang=zh"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace").stdout.strip().splitlines()
    check("中文字体", bool(fonts), (fonts or ["未找到"])[0][:80])
else:
    check("中文字体", False, "无法检查（没有 fc-list）", optional=True)

codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
gi = codex_home / "generated_images"
check("Codex 生图目录", gi.exists(), f"{gi}" + ("" if gi.exists() else "（还没画过图时不存在，属于正常）"),
      optional=True)
check("ARK_API_KEY 已设置", bool(os.environ.get("ARK_API_KEY")), "不显示内容")

url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
try:
    urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=20)
    check("连得上火山方舟", True, "HTTP 200")
except urllib.error.HTTPError as e:
    check("连得上火山方舟", True, f"HTTP {e.code}（没带密钥，能返回错误码就说明网络通）")
except Exception as e:
    check("连得上火山方舟", False, repr(e)[:120])


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


if shutil.which("git"):
    br = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    check("git 分支是 main", br == "main", br)
    check("mp4 已被忽略", git("check-ignore", "-q", "film01/video/x.mp4").returncode == 0)
    eol = git("check-attr", "eol", "film01/prompts/x.txt").stdout.strip()
    check("提示词用 LF 换行", eol.endswith("lf"), eol)
    check("git 用户名已设置", bool(git("config", "user.name").stdout.strip()), git("config", "user.name").stdout.strip())

for name, ok, detail, optional in rows:
    mark = "[OK]  " if ok else ("[提示]" if optional else "[缺少]")
    print(f"{mark} {name}：{detail}")
bad = [name for name, ok, _, optional in rows if not ok and not optional]
print("\n全部通过。" if not bad else f"\n未通过：{'、'.join(bad)}")
sys.exit(1 if bad else 0)
