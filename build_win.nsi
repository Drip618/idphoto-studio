; build_win.nsi — NSIS 安装器脚本（Windows）
; 用法（在 Windows 上）：先 build_win.bat 打包出 dist\证件照工作室\，再 makensis build_win.nsi
; 产出：证件照工作室_Setup.exe（带开始菜单/桌面快捷方式 + 卸载程序）
Unicode true

!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "证件照工作室"
OutFile "证件照工作室_Setup.exe"
InstallDir "$LOCALAPPDATA\证件照工作室"
RequestExecutionLevel user
CRCCheck on

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "主程序" SEC01
  SetOutPath "$INSTDIR"
  ; 打包产物在 dist\证件照工作室\ 目录下
  File /r "dist\证件照工作室\*"

  CreateDirectory "$SMPROGRAMS\证件照工作室"
  CreateShortCut "$SMPROGRAMS\证件照工作室\证件照工作室.lnk" "$INSTDIR\证件照工作室.exe"
  CreateShortCut "$DESKTOP\证件照工作室.lnk" "$INSTDIR\证件照工作室.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\证件照工作室" "DisplayName" "证件照工作室"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\证件照工作室" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\证件照工作室" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\证件照工作室" "DisplayIcon" "$INSTDIR\证件照工作室.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\证件照工作室.lnk"
  RMDir /r "$SMPROGRAMS\证件照工作室"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\证件照工作室"
SectionEnd
