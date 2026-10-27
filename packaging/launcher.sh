#!/bin/sh
# bilifetch —— B 站视频下载器启动器
# 由 bilifetch.py 配套生成，通过软链接/真实路径找到同级的 ../lib/bilifetch/bilifetch.py
set -e

SELF="$0"
while [ -L "$SELF" ]; do
    LINK=$(readlink "$SELF")
    case "$LINK" in
        /*) SELF="$LINK" ;;
        *)  SELF="$(dirname "$SELF")/$LINK" ;;
    esac
done

BIN_DIR=$(cd "$(dirname "$SELF")" && pwd)
LIB_DIR="$BIN_DIR/../lib/bilifetch"

if [ ! -f "$LIB_DIR/bilifetch.py" ]; then
    echo "bilifetch: 找不到 $LIB_DIR/bilifetch.py" >&2
    exit 1
fi

PY="${BILIFETCH_PYTHON:-}"
if [ -z "$PY" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PY="python3"
    else
        # 访达双击启动时 PATH 很短，Homebrew / MacPorts 的目录不在里面
        for d in /opt/homebrew/bin /usr/local/bin /opt/local/bin /opt/miniconda3/bin; do
            if [ -x "$d/python3" ]; then PY="$d/python3"; break; fi
        done
    fi
fi
if [ -z "$PY" ]; then
    echo "bilifetch: 找不到 python3，请先安装 Python 3.7+" >&2
    exit 1
fi

exec "$PY" "$LIB_DIR/bilifetch.py" "$@"
