#!/bin/bash
# build_mac.sh — macOS 打包为 .app + 生成 .dmg 分发盘
set -e
pip install -r requirements.txt
pyinstaller app.spec --noconfirm
echo "完成：dist/证件照工作室.app"

# 生成 DMG 安装盘（双击挂载，拖入 Applications 即可，可直接发给别的 Mac）
TMP=$(mktemp -d)
cp -R dist/证件照工作室.app "$TMP/"
ln -s /Applications "$TMP/Applications"
hdiutil create -volname 证件照工作室 -srcfolder "$TMP" -ov -format UDZO dist/证件照工作室.dmg
rm -rf "$TMP"
echo "完成：dist/证件照工作室.dmg"
