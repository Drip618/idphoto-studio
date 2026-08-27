# -*- coding: utf-8 -*-
"""
app.spec — PyInstaller 打包配置（Win / Mac 通用）

构建：
  Mac :  pyinstaller app.spec --noconfirm   →  dist/证件照工作室.app
  Win :  pyinstaller app.spec --noconfirm   →  dist/证件照工作室/ (onedir)

说明：
  - PyInstaller 不能跨平台编译，需在目标系统本机构建。
  - Mac 上 BUNDLE 块生成 .app；Win 上 BUNDLE 被忽略，由 NSIS 再封成安装器。
  - 依赖需先装好：pip install -r requirements.txt
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

# 适配 `python -m PyInstaller` 与直接 `pyinstaller` 两种调用方式
spec_path = next((a for a in sys.argv if a.endswith(".spec")), "app.spec")
HERE = os.path.dirname(os.path.abspath(spec_path))
block_cipher = None

# 平台图标：Mac 用 .icns，Win 用 .ico
if sys.platform == "darwin":
    ICON = os.path.join(HERE, "app.icns") if os.path.exists(os.path.join(HERE, "app.icns")) else None
else:
    ICON = os.path.join(HERE, "app.ico") if os.path.exists(os.path.join(HERE, "app.ico")) else None

# 强制收集 onnxruntime 全部二进制（核心修复：之前 onnxruntime 没打进包，导致打包态 import 失败、抠图退化为原图裁切）
ort_datas, ort_bins, ort_hidden = collect_all("onnxruntime")
ort_bins += collect_dynamic_libs("onnxruntime")

# PySide6 也用 collect_all 确保插件齐全
ps_datas, ps_bins, ps_hidden = collect_all("PySide6")

extra_datas = ort_datas + ps_datas
extra_bins = ort_bins + ps_bins
extra_hidden = ort_hidden + ps_hidden + [
    "core.idphoto_core", "ui.main_window",
    "onnxruntime", "PIL", "PySide6",
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "PySide6.QtSvg", "PySide6.QtXml",
]

a = Analysis(
    [os.path.join(HERE, "idphoto_studio.py")],
    pathex=[HERE],
    binaries=extra_bins,
    datas=[
        (os.path.join(HERE, "core"), "core"),
        (os.path.join(HERE, "ui"), "ui"),
        (os.path.join(HERE, "data"), "data"),
        (os.path.join(HERE, "weights"), "weights"),
    ] + extra_datas,
    hiddenimports=extra_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="证件照工作室",
    icon=ICON,
    windowed=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="证件照工作室",
)

app = BUNDLE(
    coll,
    name="证件照工作室.app",
    icon=ICON,
    bundle_identifier="com.idphotostudio.desktop",
    info_plist={
        "CFBundleName": "证件照工作室",
        "CFBundleDisplayName": "证件照工作室",
        "CFBundleIdentifier": "com.idphotostudio.desktop",
        "CFBundleVersion": "2.0.0",
        "CFBundleShortVersionString": "2.0.0",
        "CFBundleIconFile": "app.icns",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    },
)
