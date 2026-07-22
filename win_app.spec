# -*- coding: utf-8 -*-
"""
win_app.spec — PyInstaller 打包配置（仅 Windows）

构建（在 Windows 上）：
  pyinstaller win_app.spec --noconfirm --clean --distpath dist --workpath build
  →  dist/证件照工作室/  (onedir，含模型，开箱即用)
  →  再 makensis build_win.nsi  →  证件照工作室_Setup.exe 安装向导

说明：
  - 此文件不含 macOS 的 BUNDLE 块，避免在 Windows 上构建报错。
  - 依赖需先装好：pip install -r requirements.txt  （build_win.bat 会自动做）。
  - 模型已随 weights/ 打进包内，安装后无需联网下载。
"""
import os
import sys

spec_path = next((a for a in sys.argv if a.endswith(".spec")), "win_app.spec")
HERE = os.path.dirname(os.path.abspath(spec_path))
block_cipher = None

ICON = os.path.join(HERE, "app.ico") if os.path.exists(os.path.join(HERE, "app.ico")) else None

# 仅收集存在的目录，避免 PyInstaller 因缺失目录报错
datas = [
    (os.path.join(HERE, "core"), "core"),
    (os.path.join(HERE, "ui"), "ui"),
    (os.path.join(HERE, "weights"), "weights"),
]
if os.path.isdir(os.path.join(HERE, "data")):
    datas.append((os.path.join(HERE, "data"), "data"))

a = Analysis(
    [os.path.join(HERE, "idphoto_studio.py")],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "core.idphoto_core", "ui.main_window",
        "onnxruntime", "PIL", "PySide6",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "PySide6.QtSvg", "PySide6.QtXml",
    ],
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
