#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 macOS App 图标。

素材：packaging/app/fox_source.png（透明背景的小狐狸）
输出：<输出目录>/icon_1024.png（1024×1024，macOS 图标网格）

macOS 图标要点：
  * 底形用「超椭圆」（squircle），不是普通圆角矩形 —— n≈5 的 |x|^n+|y|^n=1
  * 整张画布 1024×1024，squircle 几乎铺满，四周留一点点透明边
  * 主体（狐狸）在里面再留出呼吸空间，避免贴边

用法：python3 packaging/app/make_icon.py <输出目录> [背景方案]
      背景方案: brand | cream | peach
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "fox_source.png")
CANVAS = 1024

# 底色方案：(顶部色, 底部色)
BACKDROPS = {
    "brand": ((255, 236, 242), (223, 243, 253)),   # 品牌粉蓝，淡淡的
    "cream": ((255, 250, 240), (253, 244, 229)),   # 奶油
    "peach": ((255, 240, 233), (255, 228, 214)),   # 蜜桃
}


def squircle_mask(size, n=5.0, margin=0.0):
    """超椭圆遮罩（macOS 风格的连续圆角）。"""
    ss = 4                                    # 超采样，边缘更顺
    s = size * ss
    y, x = np.mgrid[0:s, 0:s]
    c = (s - 1) / 2.0
    r = (s / 2.0) * (1.0 - margin)
    d = (np.abs((x - c) / r) ** n + np.abs((y - c) / r) ** n) <= 1.0
    mask = Image.fromarray((d * 255).astype(np.uint8), "L").resize((size, size), Image.LANCZOS)
    return mask


def gradient(size, top, bottom):
    """竖向渐变。"""
    t = np.linspace(0, 1, size)[:, None]
    top_a, bot_a = np.array(top, float), np.array(bottom, float)
    col = (top_a * (1 - t) + bot_a * t)[:, None, :]
    arr = np.repeat(col[:, :, :], size, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def build(outdir, scheme="brand"):
    if not os.path.exists(SOURCE):
        raise SystemExit("缺少素材：%s" % SOURCE)
    top, bottom = BACKDROPS.get(scheme, BACKDROPS["brand"])

    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    bg = gradient(CANVAS, top, bottom).convert("RGBA")
    bg.putalpha(squircle_mask(CANVAS, margin=0.012))
    canvas.alpha_composite(bg)

    # 狐狸：按画布的 66% 居中，四周留白
    fox = Image.open(SOURCE).convert("RGBA")
    target = int(CANVAS * 0.66)
    scale = target / max(fox.size)
    fox = fox.resize((max(1, int(fox.width * scale)), max(1, int(fox.height * scale))),
                    Image.LANCZOS)
    # 略微上移，给下方留白更均匀
    off_x = (CANVAS - fox.width) // 2
    off_y = (CANVAS - fox.height) // 2 - int(CANVAS * 0.01)
    canvas.alpha_composite(fox, (off_x, off_y))

    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "icon_1024.png")
    canvas.save(path)
    return path


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    scheme = sys.argv[2] if len(sys.argv) > 2 else "brand"
    print("图标已生成：%s" % build(outdir, scheme))


if __name__ == "__main__":
    main()
