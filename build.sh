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
copyfile bilifetch_login.py "$PAYLOAD/lib/bilifetch/bilifetch_login.py"
copyfile bilifetch_login_gui.py "$PAYLOAD/lib/bilifetch/bilifetch_login_gui.py"
copyfile bilifetch_ui.py "$PAYLOAD/lib/bilifetch/bilifetch_ui.py"
copyfile packaging/launcher.sh "$PAYLOAD/bin/bilifetch"
copyfile README.md "$PAYLOAD/README.md"
chmod 755 "$PAYLOAD/bin/bilifetch"
chmod 644 "$PAYLOAD/lib/bilifetch/bilifetch.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_collection.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_collection_gui.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_login.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_login_gui.py" \
          "$PAYLOAD/lib/bilifetch/bilifetch_ui.py" "$PAYLOAD/README.md"

# ---------------------------------------------------------------- macOS
if [ "$(uname)" = "Darwin" ]; then
    echo "==> 打包 macOS .app（PyInstaller，图形界面）"
    # 图标：橘猫吉祥物（图像模型生成的素材）→ macOS .icns
    ICON="$STAGE/icon.icns"
    if python3 -c "import PIL" >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
        python3 packaging/app/make_icon.py "$STAGE" brand >/dev/null
        sh packaging/app/make_iconset.sh "$STAGE/icon_1024.png" "$ICON" >/dev/null
    else
        echo "    跳过图标（缺 PIL 或 iconutil）"
    fi

    if python3 -c "import PyQt5, PyInstaller" >/dev/null 2>&1; then
        # 排除用不到的大包：qrcode 的静态扫描会把 numpy/cryptography 一起拖进来（白涨 43MB）
        python3 -m PyInstaller --noconfirm --windowed \
            --name BiliFetch \
            --exclude-module numpy --exclude-module cryptography \
            --exclude-module matplotlib --exclude-module pandas --exclude-module scipy \
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
    cp bilifetch_login.py "$DEBROOT/usr/lib/bilifetch/bilifetch_login.py"
    cp bilifetch_login_gui.py "$DEBROOT/usr/lib/bilifetch/bilifetch_login_gui.py"
    cp bilifetch_ui.py "$DEBROOT/usr/lib/bilifetch/bilifetch_ui.py"
    chmod 644 "$DEBROOT/usr/lib/bilifetch/bilifetch_gui.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_collection.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_collection_gui.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_login.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_login_gui.py" \
              "$DEBROOT/usr/lib/bilifetch/bilifetch_ui.py"
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

echo "==> 打包通用 Linux 发行版归档 (.tar.gz)"
LINUXTAR_DIR="$STAGE/BiliFetch-$VERSION-Linux"
mkdir -p "$LINUXTAR_DIR/bin" "$LINUXTAR_DIR/lib/bilifetch" "$LINUXTAR_DIR/share"
copyfile bilifetch.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch.py"
copyfile bilifetch_gui.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_gui.py"
copyfile bilifetch_collection.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_collection.py"
copyfile bilifetch_collection_gui.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_collection_gui.py"
copyfile bilifetch_login.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_login.py"
copyfile bilifetch_login_gui.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_login_gui.py"
copyfile bilifetch_ui.py "$LINUXTAR_DIR/lib/bilifetch/bilifetch_ui.py"
copyfile packaging/launcher.sh "$LINUXTAR_DIR/bin/bilifetch"
cat > "$LINUXTAR_DIR/bin/bilifetch-gui" <<'LGUI'
#!/bin/sh
SELF=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
DIR=$(cd "$(dirname "$SELF")" && pwd)
exec python3 "$DIR/../lib/bilifetch/bilifetch_gui.py" "$@"
LGUI
cat > "$LINUXTAR_DIR/install.sh" <<'LINST'
#!/bin/sh
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
PREFIX="${PREFIX:-/usr/local}"
mkdir -p "$PREFIX/bin" "$PREFIX/lib/bilifetch" "$PREFIX/share/applications" "$PREFIX/share/icons/hicolor/512x512/apps"
install -m 755 "$DIR/bin/bilifetch" "$PREFIX/bin/bilifetch"
install -m 755 "$DIR/bin/bilifetch-gui" "$PREFIX/bin/bilifetch-gui"
install -m 644 "$DIR/lib/bilifetch/"*.py "$PREFIX/lib/bilifetch/"
if [ -f "$DIR/share/bilifetch.png" ]; then
    install -m 644 "$DIR/share/bilifetch.png" "$PREFIX/share/icons/hicolor/512x512/apps/bilifetch.png"
fi
cat > "$PREFIX/share/applications/bilifetch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BiliFetch
Name[zh_CN]=BiliFetch 视频下载器
Comment=Download videos from Bilibili
Comment[zh_CN]=B 站视频下载器
Exec=$PREFIX/bin/bilifetch-gui
Icon=bilifetch
Terminal=false
Categories=Network;Video;Utility;
EOF
echo "BiliFetch 已安装到 $PREFIX （运行 bilifetch-gui 打开图形界面，或运行 bilifetch 使用命令行）"
LINST
chmod 755 "$LINUXTAR_DIR/bin/bilifetch" "$LINUXTAR_DIR/bin/bilifetch-gui" "$LINUXTAR_DIR/install.sh"
if [ -f "$STAGE/linuxicon/icon_1024.png" ]; then
    cp "$STAGE/linuxicon/icon_1024.png" "$LINUXTAR_DIR/share/bilifetch.png"
    cp "$STAGE/linuxicon/icon_1024.png" "$LINUXTAR_DIR/lib/bilifetch/icon_1024.png"
fi
copyfile README.md "$LINUXTAR_DIR/README.md"
LINUX_TAR="$DIST/BiliFetch-$VERSION-Linux.tar.gz"
tar -C "$STAGE" -czf "$STAGE/linux.tar.gz" "BiliFetch-$VERSION-Linux"
cp -X "$STAGE/linux.tar.gz" "$LINUX_TAR"
echo "    $LINUX_TAR ($(du -h "$LINUX_TAR" | cut -f1))"

# ---------------------------------------------------------------- Windows
echo "==> 打包 Windows 发行包 (.zip)"
WIN_DIR="$STAGE/BiliFetch-$VERSION-Windows"
mkdir -p "$WIN_DIR"
for f in bilifetch.py bilifetch_gui.py bilifetch_collection.py bilifetch_collection_gui.py \
         bilifetch_login.py bilifetch_login_gui.py bilifetch_ui.py README.md LICENSE; do
    copyfile "$f" "$WIN_DIR/$f"
done
copyfile bilifetch_gui.py "$WIN_DIR/BiliFetch.pyw"
if [ -f "$STAGE/linuxicon/icon.ico" ]; then
    cp "$STAGE/linuxicon/icon.ico" "$WIN_DIR/icon.ico"
elif [ -f "$STAGE/icon.ico" ]; then
    cp "$STAGE/icon.ico" "$WIN_DIR/icon.ico"
fi
cat > "$WIN_DIR/启动BiliFetch图形界面.vbs" <<'WVBS'
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir
On Error Resume Next
shell.Run "pythonw.exe """ & dir & "\BiliFetch.pyw""", 0, False
If Err.Number <> 0 Then
    Err.Clear
    shell.Run "pyw.exe """ & dir & "\BiliFetch.pyw""", 0, False
End If
WVBS
cat > "$WIN_DIR/bilifetch.bat" <<'WBAT'
@echo off
chcp 65001 >nul
python "%~dp0bilifetch.py" %*
WBAT
cat > "$WIN_DIR/一键安装依赖与桌面快捷方式.bat" <<'WINST'
@echo off
chcp 65001 >nul
echo [1/2] 正在安装 Python 依赖 (PyQt5, requests, qrcode, pillow)...
python -m pip install --upgrade PyQt5 requests qrcode pillow
echo [2/2] 正在创建桌面快捷方式...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BiliFetch.lnk'); ^
   $s.TargetPath='wscript.exe'; ^
   $s.Arguments='\"%~dp0启动BiliFetch图形界面.vbs\"'; ^
   $s.WorkingDirectory='%~dp0'; ^
   if (Test-Path '%~dp0icon.ico') { $s.IconLocation='%~dp0icon.ico' }; ^
   $s.Save()"
echo.
echo 安装完成！双击桌面上的 BiliFetch 图标即可打开图形界面。
echo 如需安装 ffmpeg，可在终端运行：winget install Gyan.FFmpeg
pause
WINST
cat > "$WIN_DIR/打包独立exe.bat" <<'WEXE'
@echo off
chcp 65001 >nul
echo 正在使用 PyInstaller 打包独立免安装 BiliFetch.exe ...
python -m pip install --upgrade PyQt5 requests qrcode pillow pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name BiliFetch ^
  --icon "%~dp0icon.ico" --add-data "%~dp0icon.ico;." ^
  --exclude-module numpy --exclude-module cryptography --exclude-module matplotlib ^
  "%~dp0bilifetch_gui.py"
echo 打包完成，产物在 dist\BiliFetch.exe
pause
WEXE
WIN_ZIP="$DIST/BiliFetch-$VERSION-Windows.zip"
( cd "$STAGE" && zip -qr "$STAGE/windows.zip" "BiliFetch-$VERSION-Windows" )
cp -X "$STAGE/windows.zip" "$WIN_ZIP"
echo "    $WIN_ZIP ($(du -h "$WIN_ZIP" | cut -f1))"

# ---------------------------------------------------------------- 校验和
echo "==> 生成校验和"
( cd "$DIST" && shasum -a 256 ./*.dmg ./*.pkg ./*.deb ./*.tar.gz ./*.zip > SHA256SUMS )
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

# .git 里的也要清：exFAT 存不了 POSIX 权限位，macOS 会给 0755/0444 的文件生成
# ._ 旁挂文件；git 的 pack 文件正好是 0444，git 会把旁挂误当成 pack 索引去读，
# 于是报 "non-monotonic index .git/objects/pack/._pack-xxx.idx"。
find .git -name '._*' -type f -delete 2>/dev/null || true

echo ""
echo "==> 完成，产物在 $ROOT/$DIST/"
ls -la "$DIST"
