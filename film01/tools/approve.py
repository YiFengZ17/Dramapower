#!/usr/bin/env python3
"""用户专用：批准花钱。Codex 不得运行这个脚本。

  python film01/tools/approve.py S02_v3 S04_v3 S06_v1 S05_v3     # 一次批准多个镜头
  python film01/tools/approve.py S01_v1                          # 也可以只批一个

脚本会列出每个镜头的报价和合计，要求你在终端里亲手输入这一批的总金额上限，再输入“同意”，
然后为每个镜头写一张 approvals/<镜头>.json。
每张批准单都绑定该镜头的请求指纹：之后只要提示词、图片或参数有任何改动，那一镜的批准就失效。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台或管道可能是 GBK 编码：遇到无法显示的字符就替换，不让脚本崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent


def estimate(clip):
    """用当前的 seedance.build() 重算指纹和报价，确保批准的就是现在要提交的内容。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import seedance
    spec = ROOT / "shots" / f"{clip}.json"
    if not spec.exists():
        sys.exit(f"没有镜头参数 {spec}")
    _, _, plan = seedance.build(str(spec))
    saved = ROOT / "requests" / f"{clip}.plan.json"
    if not saved.exists():
        sys.exit(f"没有报价单 {saved}，请先运行 seedance.py plan")
    if json.loads(saved.read_text(encoding="utf-8-sig"))["payload_sha256"] != plan["payload_sha256"]:
        sys.exit(f"{clip} 的输入和报价单不一致（文件被改过），不能批准")
    return plan


def main():
    clips = sys.argv[1:]
    if not clips:
        sys.exit(__doc__)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("必须由用户在终端里亲手运行。")
    if len(set(clips)) != len(clips):
        sys.exit("镜头名重复了")
    for c in clips:
        if (ROOT / "approvals" / f"{c}.json").exists():
            sys.exit(f"approvals/{c}.json 已存在。重拍要用新版本号。")

    plans = [estimate(c) for c in clips]
    total = round(sum(p["estimate_cny"] for p in plans), 2)
    print()
    for c, p in zip(clips, plans):
        v = p["preview"]
        files = "、".join(im["file"] for im in p["images"])
        print(f"{c:<8} {v['model']}  {v['duration']}s {v['resolution']} {v['ratio']} 音频={v['generate_audio']}  "
              f"约 ¥{p['estimate_cny']}")
        print(f"         首尾帧：{files}")
        print(f"         提示词：{v['content'][0]['text'][:80]}…")
    print(f"\n合计约 ¥{total}（以账单为准）\n")

    raw = input("输入这一批的总金额上限（元），直接回车取消：").strip()
    if not raw:
        sys.exit("已取消")
    try:
        cap = float(raw)
    except ValueError:
        sys.exit("不是数字，已取消")
    if cap < total:
        sys.exit(f"上限 ¥{cap} 低于合计 ¥{total}，已取消")
    if input(f"确认花钱提交这 {len(clips)} 个镜头，请输入“同意”：").strip() != "同意":
        sys.exit("已取消")

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    batch = f"batch-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    (ROOT / "approvals").mkdir(exist_ok=True)
    for c, p in zip(clips, plans):
        with open(ROOT / "approvals" / f"{c}.json", "x", encoding="utf-8") as f:
            json.dump({"clip": c, "payload_sha256": p["payload_sha256"], "max_cny": cap,
                       "estimate_cny": p["estimate_cny"], "batch": batch, "batch_clips": clips,
                       "batch_total_estimate_cny": total, "approved_by": "user", "approved_at": now},
                      f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已写入 approvals/{c}.json")
    print("完成。让 Codex 执行工单即可。")


if __name__ == "__main__":
    main()
