@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   证件照工作室 — Windows 一键打包
echo ============================================

REM 1) 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
  echo [错误] 未检测到 Python。
  echo   请先安装：https://www.python.org/downloads/
  echo   安装时务必勾选 "Add Python to PATH"，装完重开命令行再运行本文件。
  pause
  exit /b 1
)

REM 2) 虚拟环境
if not exist venv (
  echo [1/5] 创建虚拟环境...
  python -m venv venv
)
call venv\Scripts\activate.bat

REM 3) 装依赖
echo [2/5] 安装依赖（首次约 1-3 分钟）...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM 4) 打包 exe
echo [3/5] 打包为 exe（首次约 1-2 分钟）...
python -m PyInstaller win_app.spec --noconfirm --clean --distpath dist --workpath build

if not exist "dist\证件照工作室\证件照工作室.exe" (
  echo [失败] 未生成 exe，请把上面的报错贴给我，我来修。
  pause
  exit /b 1
)

REM 5) 封装安装包
echo [4/5] 封装安装包（如已安装 NSIS）...
where makensis >nul 2>nul
if %errorlevel%==0 (
  makensis build_win.nsi
  echo   已生成 证件照工作室_Setup.exe
) else (
  echo   未检测到 NSIS，跳过。可直接用 dist\证件照工作室\ 文件夹。
  echo   需要 setup.exe 请装 NSIS：https://nsis.sourceforge.io/
)

echo [5/5] 完成。
echo   免安装绿色版：dist\证件照工作室\
if exist "证件照工作室_Setup.exe" echo   安装向导版  ：证件照工作室_Setup.exe
pause
