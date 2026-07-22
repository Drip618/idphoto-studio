# 证件照工作室 · 换底色 + 排版打印一体

参考开源标杆项目 **HivisionIDPhotos**（ONNX 抠图 + 尺寸库 + PyInstaller 打包）重新设计，
定位是一套能长期稳定使用、支持 Win / Mac 原生双击运行的桌面软件。

## 这版解决了什么

| 你的痛点 | 这版做法 |
|---|---|
| 只是脚本壳子，不方便 | PySide6 原生桌面程序，可打包成 `.exe` / `.app` 双击即用 |
| 排版尺寸太少、不全面 | 内置 **37 种证件照尺寸**（中国 / 美国 / 欧盟·申根 / 英俄 / 日韩 / 加澳新 / 东南亚 / 其他），覆盖护照·签证·驾照·通行证·简历等 |
| 预设不能自己加 | 内置「自定义预设」窗口，尺寸 / 打印纸 / 底色都能自助增删，存到 `~/.idphoto_studio/user_presets.json` |
| 排版格式单一 | 三种格式：① 按打印纸自动排满（5寸/6寸/A4/3R/4R…共 11 种）② 自定义行列 ③ 指定张数塞入纸张；并支持**行优先 / 列优先**序列排序 |
| 慢、卡 | 抠图换用 ONNX modnet（~25MB，CPU 毫秒级，比上版 rembg 快一个量级）；**处理放后台线程，界面不冻结**；模型懒加载 |
| 要长期稳定 | 数据驱动（尺寸/底色/纸张全在代码与 CSV，逻辑与界面解耦），纯 Python 核心可单测 |

## 快速开始

```bash
pip install -r requirements.txt
python idphoto_studio.py        # 启动图形界面
```

换底色需要抠图模型（一次性下载，约 25MB，存到 `~/.idphoto_studio/weights/`，**不打进安装包**）：

```bash
python download_models.py
```

> 不下载模型也能用：底色选「不换背景」即可纯排版，零外部依赖。把软件装到别的电脑后，首次用换底色功能前在该机跑一次上面的下载即可。

## 使用流程

1. 拖拽照片到右侧预览区，或点「选择照片」
2. 选证件照尺寸（可搜索，如「美国」「签证」「一寸」）
3. 选底色（白/红/蓝/深蓝/灰/不换）
4. 选排版格式 + 序列排序
5. 点「生成预览」→ 点「保存 PNG+JPG」（默认导出到 `output/`，300 DPI）

## 自助加预设（不用碰代码）

菜单里点「自定义预设…」→ 三个标签页：
- **证件照尺寸**：名称 / 类别 / 宽(mm) / 高(mm)
- **打印纸**：名称 / 宽(mm) / 高(mm)
- **底色**：名称 / Hex

保存后立即写入用户配置，所有下拉框下次启动生效。也可直接编辑导出的 `data/size_list.csv` 审阅全部尺寸。

## 排版格式说明

- **按打印纸自动排满**：选定纸张，自动算出能塞下的最大张数并居中，默认边距 3mm、间距 2mm。
- **自定义行列**：你定几行几列，纸张按内容自动撑满。
- **指定张数**：给定张数，自动取近似方形网格塞进选定纸张。
- **序列排序**：行优先 = 1→右→换行；列优先 = 1→下→换列。

## 打包成原生程序（免上架、可发给别人装）

PyInstaller 不能跨平台编译，需在对应系统上构建。构建前先 `pip install -r requirements.txt`。

**macOS（本机已验证）**
```bash
bash build_mac.sh
# 产出 dist/证件照工作室.app  以及  dist/证件照工作室.dmg
```
`.dmg` 就是安装盘：双击挂载 → 把「证件照工作室」拖进 Applications 即可。可直接把这个 `.dmg` 发给别的 Mac 用。

**Windows（在 Windows 机器上执行）**
```bat
build_win.bat
# 1) 先 pyinstaller 打包出 dist\证件照工作室\（onedir）
# 2) 若装了 NSIS，自动 makensis build_win.nsi 生成 证件照工作室_Setup.exe 安装向导
#    没装 NSIS 则跳过，手动运行 makensis build_win.nsi 即可
```
`Setup.exe` 带开始菜单 / 桌面快捷方式 + 卸载程序，双击按向导装好就能用。

### 关于「未签名」与信任提示（重要）
两个平台都不强制签名也能用，但操作系统会拦一下：
- **macOS**：从别处下载的 `.app`/`.dmg` 首次打开可能被 Gatekeeper 拦（「无法验证开发者」）。解决：右键 → 打开；或终端 `xattr -cr /Applications/证件照工作室.app`。仅首次，之后正常。
- **Windows**：`Setup.exe` 可能触发 SmartScreen「已保护你的电脑」。点「仍要运行」→「更多信息」→「仍要运行」即可。仅是未购买代码签名证书的提示，不影响功能。

若要彻底消除这些提示，需分别购买 Apple Developer 证书（macOS）和代码签名证书（Windows）做签名——属于额外步骤，按你需求再加。

### 这软件吃性能吗？
基本不吃：
- **纯排版（核心需求）**：只用 Pillow 做缩放 + 拼贴，CPU 占用极低，十几年前的办公本也流畅，内存几十 MB。
- **换底色**：ONNX modnet 模型仅 25MB，CPU 推理单张毫秒到几十毫秒级，不吃显卡，普通笔记本毫无压力。
- 比上一代用的 rembg(U2Net ~170MB) 轻一个量级；处理全程在后台线程，界面不卡。
- 打包后的 app/exe 是自包含的，不依赖目标机装 Python。

## 目录结构

```
idphoto-studio/
├── idphoto_studio.py     # 入口（启动 GUI）
├── core/idphoto_core.py  # 核心引擎：尺寸库/排版/预设/换底/合成（无 GUI 依赖，可单测）
├── ui/main_window.py     # PySide6 界面 + 自定义预设编辑器 + 后台处理线程
├── data/size_list.csv    # 尺寸库导出（审阅/编辑）
├── weights/              # （开发态）ONNX 模型放这里；打包后模型改存用户目录 ~/.idphoto_studio/weights/
├── download_models.py    # 模型下载
├── app.spec / build_mac.sh / build_win.bat  # 打包
└── requirements.txt
```

## 性能与稳定说明

- 抠图用 ONNX + CPU，modnet 权重 25MB，推理在毫秒级；首次会下载并缓存模型。
- 所有图像处理在后台线程执行，主界面不卡顿、不假死。
- 尺寸/排版为纯几何计算，确定性输出，可复现。
