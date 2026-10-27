#!/bin/sh
# 把一张 1024×1024 的 PNG 切成 macOS 的 .icns
# 用法：sh packaging/app/make_iconset.sh <src.png> <out.icns>
set -e

SRC="$1"
OUT="$2"
TMP=$(mktemp -d /tmp/bdiconset.XXXXXX)
SET="$TMP/icon.iconset"
mkdir -p "$SET"

for s in 16 32 64 128 256 512; do
    sips -z $s $s "$SRC" --out "$SET/icon_${s}x${s}.png" >/dev/null 2>&1
    d=$((s * 2))
    sips -z $d $d "$SRC" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
done

iconutil -c icns "$SET" -o "$OUT"
rm -rf "$TMP"
echo "已生成 $OUT"
