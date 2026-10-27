#!/bin/sh
# 把 bilifetch 安装到 /usr/local/bin（便携版用法，需要管理员密码）
# 也支持自定义前缀：PREFIX=~/.local ./install.sh
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
PREFIX="${PREFIX:-/usr/local}"
BINDIR="$PREFIX/bin"
LIBDIR="$PREFIX/lib/bilifetch"

SRC_SCRIPT="$DIR/lib/bilifetch/bilifetch.py"
SRC_LAUNCHER="$DIR/bin/bilifetch"

for f in "$SRC_SCRIPT" "$SRC_LAUNCHER"; do
    if [ ! -f "$f" ]; then
        echo "install.sh: 缺少文件 $f" >&2
        exit 1
    fi
done

echo "==> 安装到 $PREFIX"

if ! mkdir -p "$BINDIR" "$LIBDIR" 2>/dev/null; then
    echo "    没有写入权限，请用: sudo $0" >&2
    exit 1
fi

cp "$SRC_SCRIPT" "$LIBDIR/bilifetch.py"
cp "$SRC_LAUNCHER" "$BINDIR/bilifetch"
chmod 755 "$BINDIR/bilifetch" "$LIBDIR/bilifetch.py"

# 顺手装个卸载脚本（路径写死成实际安装位置）
cat > "$BINDIR/bilifetch-uninstall" <<UNINSTALL
#!/bin/sh
rm -f "$BINDIR/bilifetch" "$BINDIR/bilifetch-uninstall"
rm -rf "$LIBDIR"
echo "bilifetch 已卸载"
UNINSTALL
chmod 755 "$BINDIR/bilifetch-uninstall"

echo "    已安装 $BINDIR/bilifetch"
echo ""
echo "完成。测试一下："
echo "  $BINDIR/bilifetch --help"
echo ""
echo "提示："
echo "  · 需要 ffmpeg：brew install ffmpeg"
echo "  · 需要 requests：pip3 install requests"
echo "  · 卸载：$BINDIR/bilifetch-uninstall"
