#!/usr/bin/env python3
"""Seedance 调用脚本。导演编写，Codex 只运行，不修改。

  python film01/tools/seedance.py plan   shots/S03_v1.json    # 不联网、不花钱：检查输入、生成请求预览和报价
  python film01/tools/seedance.py submit shots/S03_v1.json    # 花钱：必须有用户签的 approvals/S03_v1.json
  python film01/tools/seedance.py poll   S03_v1 [--wait 20]   # 查询任务；成功就下载到 video/S03_v1.mp4

退出码：0 成功；1 输入或检查不通过；2 接口或网络错误（不要重试，交给导演）；3 疑似欠费或额度问题（全项目停止提交）。
密钥只从环境变量 ARK_API_KEY 读取，任何情况下都不打印。

注意：请求体格式根据导演对火山方舟文档的理解编写，第一次真正提交前，要由 JOB-0002 对照官方文档核对。
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Windows 控制台或管道可能是 GBK 编码：遇到无法显示的字符就替换，不让脚本崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent  # film01/
BASE = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
TASKS = BASE + "/contents/generations/tasks"
STOP = ROOT / "STOP_BILLING"
BILLING_CODES = {"AccountOverdueError", "OperationDenied.ServiceOverdue"}
BILLING_WORDS = ("overdue", "arrear", "insufficient balance", "billing", "payment", "欠费", "余额不足")
# 限流和排队上限不是欠费（JOB-0002 核对的错误码）：这些情况只停下报告，不写 STOP_BILLING
LIMIT_CODES = {"QuotaExceeded", "TooManyRequests"}
TERMINAL = {"succeeded", "failed", "cancelled", "expired"}


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def die(msg, code=1):
    print(f"[停止] {msg}", file=sys.stderr)
    sys.exit(code)


def rel(p):
    """Spec paths are relative to film01/; accept 'film01/...' too."""
    p = Path(p)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == ROOT.name:
        p = Path(*p.parts[1:])
    return ROOT / p


def write_new(path, data):
    """Never overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_log(path, data):
    """API logs are the only files these scripts update in place (append-only history)."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_prices():
    return json.loads((ROOT / "tools" / "prices.json").read_text(encoding="utf-8-sig"))


def ratio_value(r):
    a, b = r.split(":")
    return float(a) / float(b)


def check_image(path, ratio):
    from PIL import Image
    if not path.exists():
        die(f"图片不存在: {path}")
    size = path.stat().st_size
    if size > 10 * 1024 * 1024:  # 官方上限 30MB，这里更严
        die(f"图片超过 10MB: {path} ({size} 字节)")
    with Image.open(path) as im:
        w, h = im.size
        fmt = (im.format or "").lower()
    if fmt not in ("png", "jpeg", "webp"):
        die(f"图片格式不支持: {path} ({fmt})")
    if min(w, h) < 300 or max(w, h) > 6000:
        die(f"图片尺寸超出官方范围 300–6000px: {path} {w}x{h}")
    if not 0.4 <= w / h <= 2.5:
        die(f"图片宽高比超出官方范围 0.4–2.5: {path} {w}x{h}")
    if ratio != "adaptive":
        want = ratio_value(ratio)
        if abs(w / h - want) / want > 0.02:
            die(f"图片比例 {w}x{h}（{w / h:.3f}）和镜头画幅 {ratio}（{want:.3f}）不符: {path}")
    mime = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}[fmt]
    return (w, h), mime


def build(spec_path):
    spec_path = rel(spec_path)
    if not spec_path.exists():
        die(f"镜头参数文件不存在: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    clip = spec.get("clip")
    if clip != spec_path.stem:
        die(f"clip 字段 {clip!r} 必须和文件名 {spec_path.stem!r} 一致")
    for k in ("model", "prompt_file", "first_frame", "duration", "ratio", "resolution"):
        if k not in spec:
            die(f"镜头参数缺少字段: {k}")
    prices = load_prices()
    model, res = spec["model"], spec["resolution"]
    m = prices["models"].get(model)
    if m is None:
        die(f"prices.json 里没有模型 {model}，无法报价，不提交")
    rate = m["cny_per_million_tokens"].get(res)
    if rate is None:
        die(f"{model} 不支持 {res}，或者 prices.json 里没有它的单价")
    dur = spec["duration"]
    if not isinstance(dur, int) or not 4 <= dur <= m["max_duration"]:
        die(f"{model} 的 duration 必须是 4 到 {m['max_duration']} 之间的整数，现在是 {dur!r}")
    need = m.get("first_last_frame_ratio")
    if need and spec.get("first_frame") and spec["ratio"] != need:
        die(f"{model} 做首帧/首尾帧任务时，ratio 只能是 {need}")
    for k in ("seed", "camera_fixed"):
        if spec.get(k) is not None:
            die(f"官方文档没写 {model} 支持 {k}，不传这个字段（JOB-0002）")

    prompt = rel(spec["prompt_file"]).read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    if not prompt:
        die("视频提示词为空")

    content = [{"type": "text", "text": prompt}]
    images_info = []
    sizes = []
    for role, key in (("first_frame", "first_frame"), ("last_frame", "last_frame")):
        if not spec.get(key):
            continue
        p = rel(spec[key])
        size, mime = check_image(p, spec["ratio"])
        sizes.append(size)
        raw = p.read_bytes()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"},
            "role": role,
        })
        images_info.append({"role": role, "file": p.relative_to(ROOT).as_posix(), "size": f"{size[0]}x{size[1]}",
                            "sha256": hashlib.sha256(raw).hexdigest()})
    if len(set(sizes)) > 1:
        die(f"首尾帧尺寸不一致: {sizes}")

    payload = {
        "model": model,
        "content": content,
        "ratio": spec["ratio"],
        "duration": dur,
        "resolution": res,
        "generate_audio": bool(spec.get("generate_audio", False)),
        "watermark": bool(spec.get("watermark", False)),
    }

    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(body) > 60 * 1024 * 1024:  # 官方上限 64MB
        die(f"请求体 {len(body) / 1e6:.1f}MB，接近或超过 64MB 上限")
    sha = hashlib.sha256(body).hexdigest()
    ow, oh = prices["output_size_16x9"][res]
    tokens = ow * oh * prices["fps"] * dur / 1024

    preview = json.loads(json.dumps(payload))
    for item, info in zip(preview["content"][1:], images_info):
        item["image_url"]["url"] = f"<{info['file']} sha256={info['sha256'][:12]}>"
    plan = {
        "clip": clip,
        "payload_sha256": sha,
        "estimate_cny": round(tokens * rate / 1e6 + 0.005, 2),
        "estimate_tokens": round(tokens),
        "cny_per_million_tokens": rate,
        "price_note": "按 token 公式估算（见 prices.json），实际以火山方舟账单为准",
        "prompt_chars": len(prompt),
        "images": images_info,
        "preview": preview,
    }
    return clip, body, plan


def cmd_plan(a):
    clip, body, plan = build(a.spec)
    out = ROOT / "requests" / f"{clip}.plan.json"
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8-sig"))
        if old["payload_sha256"] != plan["payload_sha256"]:
            die(f"{out.name} 已存在但输入变了（提示词、图片或参数被改过）。请导演开新版本号，不覆盖旧报价。")
        print(f"{out.name} 已存在，输入没变。")
    else:
        plan["created"] = now()
        write_new(out, plan)
        print(f"已写入 {out.relative_to(ROOT).as_posix()}")
    p = plan["preview"]
    print(f"clip      : {clip}")
    print(f"model     : {p['model']}")
    print(f"参数      : {p['duration']}s  {p['resolution']}  {p['ratio']}  audio={p['generate_audio']}  "
          f"watermark={p['watermark']}")
    for im in plan["images"]:
        print(f"{im['role']:<11}: {im['file']}  {im['size']}  sha256={im['sha256'][:12]}")
    print(f"提示词    : {plan['prompt_chars']} 字")
    print(f"请求指纹  : {plan['payload_sha256']}")
    print(f"预估费用  : ¥{plan['estimate_cny']}（约 {plan['estimate_tokens']} token × "
          f"¥{plan['cny_per_million_tokens']}/百万，以账单为准）")


def api(method, url, body=None):
    key = os.environ.get("ARK_API_KEY")
    if not key:
        die("环境变量 ARK_API_KEY 未设置", 1)
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(text)
        except ValueError:
            data = {"raw": text[:2000]}
        return e.code, data


def error_of(data):
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("code", "")), str(err.get("message", ""))
    return "", json.dumps(data, ensure_ascii=False)[:500]


def is_billing(code, msg, http=None):
    if code in LIMIT_CODES or "ratelimit" in code.lower() or code.endswith("LimitExceeded"):
        return False
    if code in BILLING_CODES or http == 402:
        return True
    s = f"{code} {msg}".lower()
    return any(w in s for w in BILLING_WORDS)


def stop_billing(clip, http, code, msg):
    STOP.write_text(f"时间: {now()}\nclip: {clip}\nHTTP: {http}\ncode: {code}\nmessage: {msg}\n"
                    "疑似欠费或额度问题。全项目停止提交。只有用户能删除这个文件。\n", encoding="utf-8")
    print(f"[欠费/额度] 已写入 {STOP.name}，全项目停止提交。", file=sys.stderr)
    sys.exit(3)


def cmd_submit(a):
    if STOP.exists():
        die(f"{STOP.name} 存在，禁止提交:\n{STOP.read_text(encoding='utf-8-sig')}", 3)
    clip, body, plan = build(a.spec)
    log = ROOT / "logs" / "api" / f"{clip}.json"
    if log.exists():
        die(f"{clip} 已经提交过（{log.relative_to(ROOT).as_posix()}）。重拍要由导演开新版本号。")
    pf = ROOT / "requests" / f"{clip}.plan.json"
    if not pf.exists():
        die("没有报价单，请先运行 plan")
    if json.loads(pf.read_text(encoding="utf-8-sig"))["payload_sha256"] != plan["payload_sha256"]:
        die("当前输入和报价单的指纹不一致，输入被改过，禁止提交")
    af = ROOT / "approvals" / f"{clip}.json"
    if not af.exists():
        die(f"没有用户批准单 {af.relative_to(ROOT).as_posix()}，禁止提交")
    ap = json.loads(af.read_text(encoding="utf-8-sig"))
    if ap.get("payload_sha256") != plan["payload_sha256"]:
        die("批准单上的指纹和当前请求不一致，禁止提交")
    if float(ap.get("max_cny", 0)) < plan["estimate_cny"]:
        die(f"预估 ¥{plan['estimate_cny']} 超过批准上限 ¥{ap.get('max_cny')}，禁止提交")
    if not os.environ.get("ARK_API_KEY"):
        die("环境变量 ARK_API_KEY 未设置")

    rec = {"clip": clip, "payload_sha256": plan["payload_sha256"], "estimate_cny": plan["estimate_cny"],
           "state": "submitting", "submitted_at": now(), "history": []}
    write_new(log, rec)  # 先落盘再发请求：即使中途崩溃，也不会重复提交
    try:
        http, data = api("POST", TASKS, body)
    except Exception as e:  # network failure: server may or may not have accepted it
        rec["state"] = "unknown_network_error"
        rec["error"] = repr(e)[:500]
        update_log(log, rec)
        die(f"网络错误，不确定服务端有没有收到：{e!r}\n不要重试。请用户到火山方舟控制台看有没有这条任务。", 2)
    if http >= 400 or "id" not in data:
        code, msg = error_of(data)
        rec.update(state="rejected", http=http, error={"code": code, "message": msg})
        update_log(log, rec)
        print(f"提交被拒：HTTP {http} {code} {msg}", file=sys.stderr)
        if is_billing(code, msg, http):
            stop_billing(clip, http, code, msg)
        sys.exit(2)
    rec.update(state="submitted", task_id=data["id"])
    update_log(log, rec)
    print(f"已提交 {clip}，task_id={data['id']}")


def cmd_poll(a):
    log = ROOT / "logs" / "api" / f"{a.clip}.json"
    if not log.exists():
        die(f"没有 {a.clip} 的提交记录")
    rec = json.loads(log.read_text(encoding="utf-8-sig"))
    tid = rec.get("task_id")
    if not tid:
        die(f"{a.clip} 没有 task_id（状态 {rec.get('state')}），无法查询")
    deadline = time.time() + a.wait * 60
    while True:
        try:
            http, data = api("GET", f"{TASKS}/{tid}")
        except Exception as e:
            die(f"查询网络错误：{e!r}（查询不花钱，稍后可以再查）", 2)
        if http >= 400:
            code, msg = error_of(data)
            die(f"查询失败：HTTP {http} {code} {msg}", 2)
        status = data.get("status", "?")
        rec["history"].append({"at": now(), "status": status})
        rec["status"] = status
        if data.get("usage"):
            rec["usage"] = data["usage"]
        for k in ("seed", "resolution", "ratio", "duration", "framespersecond"):
            if k in data:
                rec.setdefault("result", {})[k] = data[k]
        update_log(log, rec)
        print(f"{now()}  {a.clip}  {status}")
        if status in TERMINAL or time.time() >= deadline:
            break
        time.sleep(15)

    if status == "failed":
        code, msg = error_of(data)
        rec["error"] = {"code": code, "message": msg}
        update_log(log, rec)
        print(f"任务失败：{code} {msg}", file=sys.stderr)
        if is_billing(code, msg):
            stop_billing(a.clip, None, code, msg)
        sys.exit(2)
    if status != "succeeded":
        print("还没完成，稍后再运行 poll。")
        return

    url = (data.get("content") or {}).get("video_url")
    if not url:
        die("状态是 succeeded，但返回里没有 content.video_url", 2)
    rec["video_host"] = url.split("/")[2]
    out = ROOT / "video" / f"{a.clip}.mp4"
    if out.exists():
        print(f"{out.relative_to(ROOT).as_posix()} 已存在，不重复下载")
        update_log(log, rec)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    try:
        with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    except Exception as e:
        die(f"下载失败（链接约 24 小时内有效，可以再运行 poll）：{e!r}\n视频所在域名: {rec['video_host']}", 2)
    chk = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=codec_type", "-of", "csv=p=0", str(tmp)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if chk.returncode != 0 or "video" not in chk.stdout:
        bad = tmp.with_name(f"{a.clip}.download_{int(time.time())}.bad")
        tmp.rename(bad)
        die(f"下载的文件不是有效视频（{bad.stat().st_size} 字节），已存为 {bad.relative_to(ROOT).as_posix()}，交给导演。", 2)
    tmp.rename(out)
    raw = out.read_bytes()
    rec["video"] = {"file": out.relative_to(ROOT).as_posix(), "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(), "downloaded_at": now()}
    update_log(log, rec)
    print(f"已下载 {out.relative_to(ROOT).as_posix()}（{len(raw) / 1e6:.1f} MB）")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("spec"); p.set_defaults(f=cmd_plan)
    p = sub.add_parser("submit"); p.add_argument("spec"); p.set_defaults(f=cmd_submit)
    p = sub.add_parser("poll"); p.add_argument("clip"); p.add_argument("--wait", type=float, default=0)
    p.set_defaults(f=cmd_poll)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
