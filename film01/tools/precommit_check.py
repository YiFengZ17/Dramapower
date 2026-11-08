#!/usr/bin/env python3
"""提交前检查已暂存的文件：不能有视频、密钥和超大文件。Windows、WSL、Linux 都能运行。

  python film01/tools/precommit_check.py

退出码 0 表示可以提交，1 表示有问题，不要提交。
"""
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

BAD_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".part", ".bad"}
MAX_BYTES = 20 * 1024 * 1024

r = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], capture_output=True)
if r.returncode != 0:
    sys.exit("git diff 失败：" + r.stderr.decode("utf-8", "replace"))
names = [n for n in r.stdout.decode("utf-8", "replace").split("\0") if n]
repo = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           encoding="utf-8").stdout.strip())
problems = []
for n in names:
    p = Path(n)
    low = p.name.lower()
    if p.suffix.lower() in BAD_EXT:
        problems.append(f"视频或临时文件：{n}")
    elif low == ".env" or low.endswith(".env") or "secret" in low or "apikey" in low:
        problems.append(f"疑似密钥文件：{n}")
    elif n.startswith("film01/approvals/") and not n.endswith(".gitkeep"):
        problems.append(f"批准单只能由用户提交，Codex 不得 add：{n}")
    full = repo / n
    if full.is_file() and full.stat().st_size > MAX_BYTES:
        problems.append(f"文件超过 20MB：{n}（{full.stat().st_size / 1e6:.1f} MB）")

print(f"已暂存 {len(names)} 个文件。")
if problems:
    print("不能提交：")
    for x in problems:
        print("  - " + x)
    print("用 git restore --staged <文件> 把它们移出暂存区，然后告诉用户。")
    sys.exit(1)
print("检查通过，可以提交。")
