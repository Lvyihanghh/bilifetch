#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 macOS App 图标（.icns）。

素材是 packaging/app/icon_source.png（用图像模型生成的橘猫吉祥物），
按 macOS 图标规范排版：1024×1024 画布，主体缩到 824×824 居中（Big Sur 图标网格留边），
再切出各尺寸组成 iconset，最后 iconutil 转 .icns。

用法：
    python3 packaging/app/make_icon.py <输出目录>     # 输出 icon_1024.png
    sh packaging/app/make_iconset.sh <src.png> <out.icns>
"""

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "icon_source.png")

CANVAS = 1024          # macOS 图标画布
ART = 824              # 主体尺寸（Big Sur 网格留边约 10%）
SIZES = [16, 32, 64, 128, 256, 512]


def build_canvas():
    """把素材放进 1024 画布中央，输出 RGBA。"""
    if not os.path.exists(SOURCE):
        raise SystemExit("缺少素材：%s" % SOURCE)
    im = Image.open(SOURCE).convert("RGB")
    w, h = im.size
    if w != h:                      # 居中裁成正方形
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    im = im.resize((ART, ART), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(im, ((CANVAS - ART) // 2, (CANVAS - ART) // 2))
    return canvas


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "icon_1024.png")
    build_canvas().save(path)
    print("图标已生成：%s" % path)


if __name__ == "__main__":
    main()
