#!/usr/bin/env python3
"""用另一张对齐的图修补一小块区域（导演用；比如去掉多出来的饰物）。另存新文件，不覆盖原图。

  python film01/tools/patch_region.py --base images/K1_typing_v1_16x9.png --donor images/S04_first_v1_16x9.png \
      --box 670 270 790 360 --color-mask bow --out images/K1_typing_v2_16x9.png --note "去掉多出来的蓝色蝴蝶结"

--box：只在这个矩形里修补（x0 y0 x1 y1）。
--color-mask bow：只替换框内“亮天蓝色”的像素（蝴蝶结），膨胀几像素后羽化；不给就替换整个框（边缘羽化）。
两张图必须同尺寸、基本对齐（例如一张是在另一张基础上编辑出来的）。
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
    import numpy as np
    from PIL import Image, ImageFilter
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--donor", required=True)
    ap.add_argument("--box", type=int, nargs=4, required=True)
    ap.add_argument("--color-mask", choices=["bow"])
    ap.add_argument("--grow", type=int, default=6, help="蒙版向外扩几像素")
    ap.add_argument("--feather", type=float, default=3.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    base_p, donor_p, out_p = rel(a.base), rel(a.donor), rel(a.out)
    if out_p.exists():
        sys.exit(f"{out_p.relative_to(ROOT).as_posix()} 已存在，不覆盖")
    base = Image.open(base_p).convert("RGB")
    donor = Image.open(donor_p).convert("RGB")
    if base.size != donor.size:
        sys.exit(f"尺寸不同：{base.size} vs {donor.size}")
    x0, y0, x1, y1 = a.box
    W, H = base.size
    mask = np.zeros((H, W), dtype=np.uint8)
    if a.color_mask == "bow":
        px = np.asarray(base).astype(int)
        r, g, b = px[..., 0], px[..., 1], px[..., 2]
        sel = (b > 170) & (g > 110) & (r < 140) & (b - r > 70)   # 亮天蓝色；头发是更暗的深蓝
        region = np.zeros_like(sel)
        region[y0:y1, x0:x1] = True
        mask[sel & region] = 255
    else:
        mask[y0:y1, x0:x1] = 255
    n = int((mask > 0).sum())
    if n == 0:
        sys.exit("蒙版是空的：框里没有找到要替换的像素")
    m = Image.fromarray(mask).filter(ImageFilter.MaxFilter(2 * a.grow + 1)).filter(ImageFilter.GaussianBlur(a.feather))
    # 羽化不能越出框
    clip = Image.new("L", (W, H), 0)
    clip.paste(255, (x0, y0, x1, y1))
    m = Image.fromarray(np.minimum(np.asarray(m), np.asarray(clip.filter(ImageFilter.GaussianBlur(2)))))
    out = Image.composite(donor, base, m)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_p)
    meta = {
        "file": out_p.relative_to(ROOT).as_posix(),
        "derived_from": base_p.relative_to(ROOT).as_posix(),
        "donor": donor_p.relative_to(ROOT).as_posix(),
        "box": a.box, "color_mask": a.color_mask, "masked_pixels": n,
        "note": a.note, "made_by": "director (patch_region.py)",
        "size": f"{W}x{H}",
        "sha256": hashlib.sha256(out_p.read_bytes()).hexdigest(),
        "made_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(out_p.with_suffix(".json"), "x", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已生成 {meta['file']}（替换了约 {n} 个像素，来自 {meta['donor']}）")


if __name__ == "__main__":
    main()
