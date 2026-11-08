#!/usr/bin/env python3
"""用户专用：批准某一镜花钱。Codex 不得运行这个脚本。

  python film01/tools/approve.py S03_v1

脚本会显示报价单，要求你在终端里亲手输入金额上限，再输入“同意”，然后写入 approvals/S03_v1.json。
批准单绑定请求指纹：之后只要提示词、图片或参数有任何改动，批准就失效。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    clip = sys.argv[1]
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("必须由用户在终端里亲手运行。")
    plan_f = ROOT / "requests" / f"{clip}.plan.json"
    out = ROOT / "approvals" / f"{clip}.json"
    if not plan_f.exists():
        sys.exit(f"没有报价单 {plan_f}")
    if out.exists():
        sys.exit(f"{out} 已存在。重拍要用新版本号。")
    plan = json.loads(plan_f.read_text(encoding="utf-8"))
    p = plan["preview"]
    print(f"\n镜头     : {clip}")
    print(f"模型     : {p['model']}")
    print(f"参数     : {p['duration']}s {p['resolution']} {p['ratio']} 音频={p['generate_audio']}")
    for im in plan["images"]:
        print(f"{im['role']:<9}: {im['file']} {im['size']}")
    print(f"提示词   : {p['content'][0]['text'][:300]}{'…' if len(p['content'][0]['text']) > 300 else ''}")
    print(f"预估费用 : ¥{plan['estimate_cny']}（以账单为准）")
    print(f"请求指纹 : {plan['payload_sha256']}\n")
    raw = input("输入这一镜的金额上限（元），直接回车取消：").strip()
    if not raw:
        sys.exit("已取消")
    try:
        cap = float(raw)
    except ValueError:
        sys.exit("不是数字，已取消")
    if cap < plan["estimate_cny"]:
        sys.exit(f"上限 ¥{cap} 低于预估 ¥{plan['estimate_cny']}，已取消")
    if input("确认花钱提交，请输入“同意”：").strip() != "同意":
        sys.exit("已取消")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8") as f:
        json.dump({"clip": clip, "payload_sha256": plan["payload_sha256"], "max_cny": cap,
                   "estimate_cny": plan["estimate_cny"], "approved_by": "user",
                   "approved_at": datetime.now().astimezone().isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已写入 {out.relative_to(ROOT.parent)}。请 git add/commit/push，或者让 Codex 执行提交工单。")


if __name__ == "__main__":
    main()
