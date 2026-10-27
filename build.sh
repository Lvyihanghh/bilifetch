#!/bin/sh
# 构建 bilifetch 的安装包：macOS (.dmg + .pkg) 和 Linux (.deb)
#
# 两个注意点：
#  1. 打包用的目录一律放在本地临时盘（APFS）上。工作目录在 exFAT 上时，
#     拷文件会带出 ._* 旁挂文件、权限也被压成 700，这些都会混进安装包。
#  2. hdiutil 的卷名不能用含 "bilibili" 的字符串（本机会直接拒绝），
#     且输出目录不能是 exFAT（xar.heap 临时文件会失败）。
#     —— 换台正常机器的话，卷名可以改回 "BiliFetch"，只是本机沙箱会拦。
#  3. pkgbuild 生成的 BOM 里会带 ._xxx 条目 —— 那是 macOS 原生 pkg 格式的固有行为，
#     Installer 装的时候会自己剥掉，不是 bug。
#
# 产物都在本目录的 dist/ 下，不污染系统。
set -e

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

VERSION=$(python3 -c "import re;print(re.search(r'VERSION\s*=\s*\"([^\"]+)\"',open('bilifetch.py').read()).group(1))")
PKGNAME="bilifetch"
BUILD="build"
DIST="dist"

echo "==> 版本 $VERSION"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

# 所有打包中间产物都放本地盘，最后只把成品拷进 dist/
STAGE=$(mktemp -d /tmp/bilifetch-stage.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT

# ---------------------------------------------------------------- 公共 payload
# 只拷文件内容，不带 resource fork / 扩展属性
# （工作目录在 exFAT 上，直接 cp 会把 ._xxx 旁挂文件也带进安装包）
copyfile() {
    python3 -c "import shutil,sys; shutil.copyfile(sys.argv[1], sys.argv[2])" "$1" "$2"
}

echo "==> 准备 payload"
PAYLOAD="$STAGE/payload"
mkdir -p "$PAYLOAD/bin" "$PAYLOAD/lib/bilifetch"
copyfile bilifetch.py "$PAYLOAD/lib/bilifetch/bilifetch.py"
copyfile bilifetch_collection.py "$PAYLOAD/lib/bilifetch/bilifetch_collection.py"
copyfile bilifetch_collection_gui.py "$PAYLOAD/lib/bilifetch/bilifetch_collection_gui.py"
copyfile packaging/launcher.sh "$PAYLOAD/bin/bilifetch"
copyfile README.md "$PAYLOAD/README.md"
chmod 755 "$PAYLOAD/bin/bilifetch"
chmod 644 "$PAYLOAD/lib/bilifetch/bilifetch.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_collection.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_collection_gui.py" "$PAYLOAD/README.md"

# ---------------------------------------------------------------- macOS
if [ "$(uname)" = "Darwin" ]; then
    echo "==> 打包 macOS .app（PyInstaller，图形界面）"
    # 图标：橘猫吉祥物（图像模型生成的素材）→ macOS .icns
    ICON="$STAGE/icon.icns"
    if python3 -c "import PIL" >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
        python3 packaging/app/make_icon.py "$STAGE" >/dev/null
        sh packaging/app/make_iconset.sh "$STAGE/icon_1024.png" "$ICON" >/dev/null
    else
        echo "    跳过图标（缺 PIL 或 iconutil）"
    fi

    if python3 -c "import PyQt5, PyInstaller" >/dev/null 2>&1; then
        python3 -m PyInstaller --noconfirm --windowed \
            --name BiliFetch \
            ${ICON:+--icon "$ICON"} \
            --osx-bundle-identifier io.github.lvyihanghh.bilifetch \
            --distpath "$STAGE" --workpath "$STAGE/pyi-work" --specpath "$STAGE" \
            bilifetch_gui.py >"$STAGE/pyinstaller.log" 2>&1 || {
                echo "    PyInstaller 失败，日志在 $STAGE/pyinstaller.log"; exit 1; }
        echo "    $STAGE/BiliFetch.app ($(du -sh "$STAGE/BiliFetch.app" | cut -f1))"
    else
        echo "    跳过：当前 python 没有 PyQt5 / PyInstaller"
        echo "    装上再打包： pip3 install PyQt5 pyinstaller"
        exit 1
    fi

    echo "==> 打包 macOS .pkg（命令行版）"
    PKGROOT="$STAGE/pkg-root"
    mkdir -p "$PKGROOT/usr/local/bin" "$PKGROOT/usr/local/lib/bilifetch" \
             "$PKGROOT/usr/local/share/doc/bilifetch"
    cp "$PAYLOAD/bin/bilifetch" "$PKGROOT/usr/local/bin/bilifetch"
    cp "$PAYLOAD/lib/bilifetch/bilifetch.py" "$PKGROOT/usr/local/lib/bilifetch/bilifetch.py"
    cp "$PAYLOAD/lib/bilifetch/bilifetch_collection.py" "$PKGROOT/usr/local/lib/bilifetch/bilifetch_collection.py"
    cp "$PAYLOAD/README.md" "$PKGROOT/usr/local/share/doc/bilifetch/README.md"
    chmod 755 "$PKGROOT/usr/local/bin/bilifetch"
    chmod 644 "$PKGROOT/usr/local/lib/bilifetch/bilifetch.py" \
              "$PKGROOT/usr/local/lib/bilifetch/bilifetch_collection.py" \
              "$PKGROOT/usr/local/share/doc/bilifetch/README.md"

    # 脚本先拷到本地盘：直接从 exFAT 拷会带上 ._postinstall 之类的旁挂文件
    PKGSCRIPTS="$STAGE/pkg-scripts"
    mkdir -p "$PKGSCRIPTS"
    copyfile packaging/pkg-scripts/postinstall "$PKGSCRIPTS/postinstall"
    chmod 755 "$PKGSCRIPTS/postinstall"

    pkgbuild --root "$PKGROOT" \
             --install-location / \
             --identifier "io.github.lvyihanghh.bilifetch.cli" \
             --version "$VERSION" \
             --scripts "$PKGSCRIPTS" \
             --ownership recommended \
             "$STAGE/BiliFetch.pkg" >/dev/null
    PKG="$DIST/BiliFetch-$VERSION-cli.pkg"
    # ad-hoc 签名（没有 Developer ID 证书，只能到这一步）
    codesign --sign - --timestamp=none "$STAGE/BiliFetch.pkg" 2>/dev/null || true
    cp -X "$STAGE/BiliFetch.pkg" "$PKG"
    echo "    $PKG ($(du -h "$PKG" | cut -f1))"

    echo "==> 打包 macOS .dmg"
    DMGSTAGE="$STAGE/dmg"
    mkdir -p "$DMGSTAGE"
    # 1) 真正的 .app —— 拖进「应用程序」后，访达/启动台里能看见、能双击
    cp -R "$STAGE/BiliFetch.app" "$DMGSTAGE/"
    # 2) 经典的 /Applications 软链接（把 .app 拖到它上面就等于装好了）
    ln -s /Applications "$DMGSTAGE/Applications"
    # 3) .pkg（给习惯用 installer 的用户，装命令行版）
    cp -X "$STAGE/BiliFetch.pkg" "$DMGSTAGE/BiliFetch-$VERSION-cli.pkg"
    # 4) 便携版 + 说明
    mkdir -p "$DMGSTAGE/便携版/bin" "$DMGSTAGE/便携版/lib/bilifetch"
    cp "$PAYLOAD/lib/bilifetch/bilifetch.py" "$DMGSTAGE/便携版/lib/bilifetch/"
    cp "$PAYLOAD/bin/bilifetch" "$DMGSTAGE/便携版/bin/"
    cp "$PAYLOAD/README.md" "$DMGSTAGE/便携版/"
    copyfile packaging/install.sh "$DMGSTAGE/便携版/install.sh"
    copyfile packaging/使用说明.txt "$DMGSTAGE/使用说明.txt"
    # 5) 一键装命令行工具的 .command
    cat > "$DMGSTAGE/安装命令行工具.command" <<'CMD'
#!/bin/sh
cd "$(dirname "$0")"
sudo ./便携版/install.sh
echo ""
echo "按回车关闭窗口。"
read _
CMD
    chmod 755 "$DMGSTAGE/安装命令行工具.command" "$DMGSTAGE/便携版/install.sh" \
              "$DMGSTAGE/便携版/bin/bilifetch"

    DMG="$DIST/BiliFetch-$VERSION-macOS.dmg"
    hdiutil create -volname "BiliFetch" -srcfolder "$DMGSTAGE" -ov -fs HFS+J -format UDZO \
        "$STAGE/BiliFetch.dmg" >/dev/null
    cp -X "$STAGE/BiliFetch.dmg" "$DMG"
    echo "    $DMG ($(du -h "$DMG" | cut -f1))"
fi

# ---------------------------------------------------------------- Linux
echo "==> 打包 Linux .deb"
DEBROOT="$STAGE/deb-root"
mkdir -p "$DEBROOT/usr/bin" "$DEBROOT/usr/lib/bilifetch" "$DEBROOT/usr/share/doc/bilifetch" \
         "$DEBROOT/usr/share/applications" "$DEBROOT/usr/share/icons/hicolor/512x512/apps"
cp "$PAYLOAD/bin/bilifetch" "$DEBROOT/usr/bin/bilifetch"
cp "$PAYLOAD/lib/bilifetch/bilifetch.py" "$DEBROOT/usr/lib/bilifetch/bilifetch.py"
cp "$PAYLOAD/README.md" "$DEBROOT/usr/share/doc/bilifetch/README.md"
chmod 755 "$DEBROOT/usr/bin/bilifetch"
chmod 644 "$DEBROOT/usr/lib/bilifetch/bilifetch.py" "$DEBROOT/usr/share/doc/bilifetch/README.md"

# 图形界面（依赖系统的 python3-pyqt5）
if python3 -c "import PyQt5" >/dev/null 2>&1 || [ -f packaging/gui/bilifetch_gui.py ]; then
    cp bilifetch_gui.py "$DEBROOT/usr/lib/bilifetch/bilifetch_gui.py"
    cp bilifetch_collection.py "$DEBROOT/usr/lib/bilifetch/bilifetch_collection.py"
    cp bilifetch_collection_gui.py "$DEBROOT/usr/lib/bilifetch/bilifetch_collection_gui.py"
    chmod 644 "$DEBROOT/usr/lib/bilifetch/bilifetch_gui.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_collection.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_collection_gui.py"
    cat > "$DEBROOT/usr/bin/bilifetch-gui" <<'GUI'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/bilifetch/bilifetch_gui.py "$@"
GUI
    chmod 755 "$DEBROOT/usr/bin/bilifetch-gui"
    cat > "$DEBROOT/usr/share/applications/bilifetch.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=BiliFetch
Name[zh_CN]=BiliFetch 视频下载器
Comment=Download videos from Bilibili
Comment[zh_CN]=B 站视频下载器
Exec=bilifetch-gui
Icon=bilifetch
Terminal=false
Categories=Network;Video;Utility;
DESKTOP
    chmod 644 "$DEBROOT/usr/share/applications/bilifetch.desktop"
    # 图标
    if python3 -c "import PIL" >/dev/null 2>&1; then
        python3 packaging/app/make_icon.py "$STAGE/linuxicon" >/dev/null
        cp "$STAGE/linuxicon/icon_1024.png" "$DEBROOT/usr/share/icons/hicolor/512x512/apps/bilifetch.png"
        chmod 644 "$DEBROOT/usr/share/icons/hicolor/512x512/apps/bilifetch.png"
    fi
fi

sed "s/^Version: .*/Version: $VERSION/" packaging/control > "$STAGE/control"
DEB="$DIST/${PKGNAME}_${VERSION}_all.deb"
python3 packaging/make_deb.py --payload "$DEBROOT" --control "$STAGE/control" \
    --scripts packaging/deb-scripts --output "$STAGE/package.deb"
cp -X "$STAGE/package.deb" "$DEB"
echo "    $DEB ($(du -h "$DEB" | cut -f1))"

echo "==> 校验 .deb"
python3 packaging/verify_deb.py "$DEB"

# ---------------------------------------------------------------- 校验和
echo "==> 生成校验和"
( cd "$DIST" && shasum -a 256 ./*.dmg ./*.pkg ./*.deb > SHA256SUMS )
cat "$DIST/SHA256SUMS"

# ---------------------------------------------------------------- 收尾
# 打包中间目录（build/）用完就删，别留在工作目录里
if [ -d "$BUILD" ]; then
    rm -rf "$BUILD"
    echo "    清掉中间目录 $BUILD/"
fi

# 工作目录在 exFAT 上时，macOS 会给每个文件生成 ._xxx 旁挂文件（存 xattr）。
# 每次改动文件都会重新生成，所以打包完统一扫一遍整个工作目录清掉，
# 免得把垃圾文件传到 GitHub Release 上。
python3 - <<'PY'
import os

SKIP = ("BilibiliDown-6.41", ".git", "node_modules")
n = 0
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith("._")]
    for name in list(files):
        if name.startswith("._") or name == ".DS_Store":
            try:
                os.remove(os.path.join(root, name))
                n += 1
            except OSError:
                pass
print("    清掉 %d 个旁挂/元数据文件" % n)
PY

echo ""
echo "==> 完成，产物在 $ROOT/$DIST/"
ls -la "$DIST"
