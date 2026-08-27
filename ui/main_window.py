# -*- coding: utf-8 -*-
"""
ui/main_window.py — 证件照工作室 Studio 照相馆旗舰版
=========================================================================
- 默认进入「🖼 仅单张证件照」，导入照片绝不自动生成多图排版
- 用户只有在主动切换到相纸排版/混排时，才生成对应冲印排版
- SOTA 纯正 RMBG-1.4 亚像素发丝级抠图，彻底根除毛边与暗斑
- 点击切换 0 闪烁，平滑无感替换
- 支持「📂 批量处理」与白底浅灰虚线裁切框
"""
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox, QTabWidget, QListWidget,
    QProgressBar, QDoubleSpinBox, QFrame, QSplitter, QCheckBox, QColorDialog,
    QScrollArea, QSizePolicy, QButtonGroup
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings, QSize
from PySide6.QtGui import (
    QPixmap, QImage, QDragEnterEvent, QDragMoveEvent, QDropEvent,
    QColor, QIcon, QFont, QPalette
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import idphoto_core as core

STUDIO_QSS = """
* {
    font-family: -apple-system, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
}
QMainWindow {
    background-color: #f8fafc;
}
QFrame#LeftContainer {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-bottom: 2px;
}
QFrame#Card:hover {
    border-color: #cbd5e1;
}
QLabel#CardTitle {
    font-size: 12px;
    font-weight: 700;
    color: #475569;
    letter-spacing: 0.3px;
}
QLabel#SubTitle {
    font-size: 11px;
    color: #94a3b8;
}
QLabel#DimensionBadge {
    font-size: 11px;
    font-weight: 600;
    color: #2563eb;
    background-color: #eff6ff;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid #dbeafe;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
    color: #1e293b;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #eff6ff;
    selection-color: #2563eb;
    padding: 2px;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    color: #334155;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #e2e8f0;
}
QPushButton#PrimaryBtn {
    background-color: #2563eb;
    border: 1px solid #1d4ed8;
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    padding: 9px 14px;
    border-radius: 6px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #93c5fd;
    border-color: #bfdbfe;
}
QPushButton#SecondaryBtn {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    color: #475569;
    font-weight: 500;
    padding: 6px 10px;
    font-size: 11px;
}
QPushButton#ColorChip {
    border: 2px solid #e2e8f0;
    border-radius: 6px;
    padding: 4px 6px;
    font-weight: 600;
    font-size: 11px;
    min-height: 20px;
}
QPushButton#ColorChip:checked {
    border: 2px solid #2563eb;
    background-color: #eff6ff;
}
QFrame#DropBox {
    background-color: #f8fafc;
    border: 1.5px dashed #cbd5e1;
    border-radius: 8px;
}
QFrame#DropBox:hover, QFrame#DropBox[dragOver="true"] {
    background-color: #eff6ff;
    border-color: #3b82f6;
}
QProgressBar {
    background-color: #e2e8f0;
    border: none;
    border-radius: 3px;
    height: 5px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}
QCheckBox {
    font-size: 11px;
    color: #334155;
    spacing: 5px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
"""


def pil_to_qimage(img):
    if img is None:
        return QImage()
    from PIL import Image
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    data = img.tobytes("raw", "RGB")
    return QImage(data, w, h, w * 3, QImage.Format_RGB888)


class MattingWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            from PIL import Image
            img = Image.open(self.image_path)
            m = core.Matting()
            if not m.available():
                self.failed.emit("未找到抠图模型，已转为原图裁切")
                return
            rgba = m.remove(img)
            self.done.emit(rgba)
        except Exception as e:
            self.failed.emit(f"抠图失败：{e}")


class RenderWorker(QThread):
    done = Signal(object, str, bool, object)
    error = Signal(str)

    def __init__(self, image_path, size_dict, color_dict, mode_idx, extra_params,
                 cut_lines, add_text, cached_rgba=None):
        super().__init__()
        self.image_path = image_path
        self.size_dict = size_dict
        self.color_dict = color_dict
        self.mode_idx = mode_idx
        self.extra_params = extra_params
        self.cut_lines = cut_lines
        self.add_text = add_text
        self.cached_rgba = cached_rgba

    def run(self):
        try:
            from PIL import Image
            img = Image.open(self.image_path)
            bg_rgb = self.color_dict["rgb"]
            need_matting = bg_rgb is not None

            # 优先使用抠图缓存
            if need_matting and self.cached_rgba is not None:
                id_photo = core.create_standard_id_photo(
                    self.cached_rgba, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb
                )
            else:
                matting = core.Matting() if (need_matting and core.Matting().available()) else None
                id_photo = core.prepare_id_photo(
                    img, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb, matting
                )

            # 0: 仅单张证件照 (默认)
            if self.mode_idx == 0:
                info = f"单张 {self.size_dict['name']} · {self.size_dict['w_px']}×{self.size_dict['h_px']} px (300 DPI)"
                self.done.emit(id_photo, info, True, id_photo)
                return

            # 2: 常用冲印混排
            if self.mode_idx == 2:
                mix_type = self.extra_params.get("mix_type", "6in_4_4")
                if self.cached_rgba is not None:
                    id_1in = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(25), core.mm_to_px(35), bg_rgb)
                    id_2in = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(35), core.mm_to_px(49), bg_rgb)
                else:
                    matting = core.Matting() if (bg_rgb is not None and core.Matting().available()) else None
                    id_1in = core.prepare_id_photo(img, core.mm_to_px(25), core.mm_to_px(35), bg_rgb, matting)
                    id_2in = core.prepare_id_photo(img, core.mm_to_px(35), core.mm_to_px(49), bg_rgb, matting)

                sheet, info = core.compose_mixed_sheet(id_1in, id_2in, mix_type=mix_type, cut_lines=self.cut_lines, add_text=self.add_text)
                self.done.emit(sheet, info, False, id_photo)
                return

            # 1: 照相馆标准相纸排版, 3: 自定义网格
            if self.mode_idx == 1:
                p = self.extra_params["paper"]
                lay = core.compute_layout(p["w_mm"], p["h_mm"], self.size_dict["w_mm"], self.size_dict["h_mm"])
            else:
                lay = core.compute_layout_grid(self.size_dict["w_mm"], self.size_dict["h_mm"], self.extra_params["rows"], self.extra_params["cols"])

            size_name = self.size_dict["name"] if self.add_text else ""
            size_dims = f"{self.size_dict['w_mm']}×{self.size_dict['h_mm']}mm" if self.add_text else ""

            sheet = core.compose_sheet(
                id_photo, lay,
                sheet_color=(255, 255, 255),
                size_name=size_name,
                size_dims=size_dims,
                cut_lines=self.cut_lines
            )

            ori_tag = "横放" if lay["paper_w_mm"] > lay["paper_h_mm"] else "竖放"
            info = f"冲印排版 · {lay['count']} 张 ({lay['cols']}列 × {lay['rows']}行 · {ori_tag}) · {lay['paper'][0]}×{lay['paper'][1]} px"
            self.done.emit(sheet, info, False, id_photo)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()[-300:]}")


# ============================================================ 批量处理后台 Worker
class BatchWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, file_paths, size_dict, color_dict, export_single, export_sheet, paper_dict, out_dir):
        super().__init__()
        self.file_paths = file_paths
        self.size_dict = size_dict
        self.color_dict = color_dict
        self.export_single = export_single
        self.export_sheet = export_sheet
        self.paper_dict = paper_dict
        self.out_dir = out_dir

    def run(self):
        try:
            from PIL import Image
            total = len(self.file_paths)
            saved = []
            m = core.Matting() if self.color_dict["rgb"] is not None else None

            for idx, p in enumerate(self.file_paths):
                fname = os.path.basename(p)
                base = os.path.splitext(fname)[0]
                self.progress.emit(idx + 1, total, fname)

                try:
                    img = Image.open(p)
                    id_photo = core.prepare_id_photo(
                        img, self.size_dict["w_px"], self.size_dict["h_px"],
                        self.color_dict["rgb"], m
                    )

                    # 导出单张
                    if self.export_single:
                        p_png = os.path.join(self.out_dir, f"{base}_{self.size_dict['name']}_单张.png")
                        p_jpg = os.path.join(self.out_dir, f"{base}_{self.size_dict['name']}_单张.jpg")
                        id_photo.save(p_png, "PNG")
                        id_photo.save(p_jpg, "JPEG", quality=95)
                        saved.append(p_png)

                    # 导出排版
                    if self.export_sheet and self.paper_dict:
                        lay = core.compute_layout(
                            self.paper_dict["w_mm"], self.paper_dict["h_mm"],
                            self.size_dict["w_mm"], self.size_dict["h_mm"]
                        )
                        sheet = core.compose_sheet(
                            id_photo, lay,
                            size_name=self.size_dict["name"],
                            size_dims=f"{self.size_dict['w_mm']}×{self.size_dict['h_mm']}mm"
                        )
                        tag = self.paper_dict["name"].split(" ")[0]
                        p_sheet_png = os.path.join(self.out_dir, f"{base}_{tag}_{self.size_dict['name']}_排版.png")
                        p_sheet_jpg = os.path.join(self.out_dir, f"{base}_{tag}_{self.size_dict['name']}_排版.jpg")
                        sheet.save(p_sheet_png, "PNG")
                        sheet.save(p_sheet_jpg, "JPEG", quality=95)
                        saved.append(p_sheet_png)

                except Exception:
                    continue

            self.finished.emit(len(saved), saved)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================ 批量处理弹窗
class BatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 批量证件照冲印处理")
        self.resize(560, 480)
        self.file_paths = []
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. 文件选择
        f_box = QFrame(); f_box.setObjectName("Card")
        fl = QVBoxLayout(f_box); fl.setContentsMargins(12, 10, 12, 10); fl.setSpacing(6)
        fl.addWidget(QLabel("1. 选择要批量处理的人像照片:"))
        btn_row = QHBoxLayout()
        b_sel_files = QPushButton("多选照片文件…")
        b_sel_files.clicked.connect(self.select_files)
        b_sel_dir = QPushButton("选择整个文件夹…")
        b_sel_dir.clicked.connect(self.select_dir)
        btn_row.addWidget(b_sel_files)
        btn_row.addWidget(b_sel_dir)
        fl.addLayout(btn_row)
        self.lbl_file_count = QLabel("尚未选择照片文件")
        self.lbl_file_count.setObjectName("SubTitle")
        fl.addWidget(self.lbl_file_count)
        layout.addWidget(f_box)

        # 2. 目标规格与底色
        opt_box = QFrame(); opt_box.setObjectName("Card")
        ol = QFormLayout(opt_box); ol.setContentsMargins(12, 10, 12, 10); ol.setSpacing(8)
        self.batch_size = QComboBox()
        for s in core.load_sizes():
            self.batch_size.addItem(f"{s['name']} ({s['w_mm']}×{s['h_mm']}mm)", s)
        ol.addRow("目标规格:", self.batch_size)

        self.batch_color = QComboBox()
        for c in core.load_colors():
            self.batch_color.addItem(c["name"], c)
        ol.addRow("目标底色:", self.batch_color)

        self.batch_paper = QComboBox()
        for p in core.load_papers():
            self.batch_paper.addItem(p["name"], p)
        ol.addRow("排版相纸:", self.batch_paper)

        layout.addWidget(opt_box)

        # 3. 导出选项
        exp_box = QFrame(); exp_box.setObjectName("Card")
        el = QVBoxLayout(exp_box); el.setContentsMargins(12, 10, 12, 10); el.setSpacing(6)
        self.cb_exp_single = QCheckBox("导出单张证件照 (PNG + JPG 300DPI)")
        self.cb_exp_single.setChecked(True)
        self.cb_exp_sheet = QCheckBox("导出相纸排版冲印图 (自动排满相纸)")
        self.cb_exp_sheet.setChecked(True)
        el.addWidget(self.cb_exp_single)
        el.addWidget(self.cb_exp_sheet)
        layout.addWidget(exp_box)

        # 4. 进度条
        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("SubTitle")
        layout.addWidget(self.lbl_status)

        # 5. 底部按钮
        b_start = QPushButton("🚀 开始批量处理并导出")
        b_start.setObjectName("PrimaryBtn")
        b_start.clicked.connect(self.start_batch)
        layout.addWidget(b_start)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "多选照片", "", "图片 (*.jpg *.jpeg *.png *.bmp *.webp)")
        if files:
            self.file_paths = files
            self.lbl_file_count.setText(f"已选择 {len(files)} 张照片")

    def select_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择包含照片的文件夹")
        if d:
            valid = []
            for root, _, fs in os.walk(d):
                for f in fs:
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                        valid.append(os.path.join(root, f))
            self.file_paths = valid
            self.lbl_file_count.setText(f"文件夹内共找到 {len(valid)} 张照片: {d}")

    def start_batch(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先选择照片或文件夹。")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "选择保存导出文件夹")
        if not out_dir:
            return

        self.pbar.setVisible(True)
        self.pbar.setRange(0, len(self.file_paths))
        self.pbar.setValue(0)

        s_dict = self.batch_size.currentData()
        c_dict = self.batch_color.currentData()
        p_dict = self.batch_paper.currentData()

        self.worker = BatchWorker(
            self.file_paths, s_dict, c_dict,
            self.cb_exp_single.isChecked(), self.cb_exp_sheet.isChecked(),
            p_dict, out_dir
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "错误", e))
        self.worker.start()

    def on_progress(self, cur, total, fname):
        self.pbar.setValue(cur)
        self.lbl_status.setText(f"正在处理 ({cur}/{total}): {fname}…")

    def on_finished(self, count, saved):
        self.pbar.setVisible(False)
        self.lbl_status.setText(f"✓ 批量处理完成，共生成 {count} 个文件！")
        QMessageBox.information(self, "批量完成", f"已成功处理并生成 {count} 个图片文件！\n保存在所选文件夹。")
        self.accept()


# ============================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照工作室 Studio")
        self.setMinimumSize(1080, 720)

        self.settings = QSettings("IDPhotoStudio", "App")
        self.input_path = None
        self.cached_rgba = None
        self.current_render_image = None
        self.current_sheet = None
        self.current_single = None
        self.current_color_data = {"name": "蓝底", "rgb": (67, 142, 219), "hex": "#438EDB"}
        self._busy = False
        self.worker = None
        self.mworker = None

        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1280, 840)

        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # ---------- 左侧控制面板 ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(380)
        left_scroll.setMaximumWidth(460)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_container = QWidget()
        left_container.setObjectName("LeftContainer")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        # 1. 标题栏
        h_box = QHBoxLayout()
        t_box = QVBoxLayout()
        title = QLabel("证件照工作室")
        title.setStyleSheet("font-size: 17px; font-weight: 800; color: #0f172a;")
        subtitle = QLabel("智能发丝抠图 · 照相馆标准排版")
        subtitle.setObjectName("SubTitle")
        t_box.addWidget(title)
        t_box.addWidget(subtitle)
        h_box.addLayout(t_box)
        h_box.addStretch()

        b_batch_top = QPushButton("📂 批量处理…")
        b_batch_top.setObjectName("SecondaryBtn")
        b_batch_top.clicked.connect(self.open_batch_dialog)
        h_box.addWidget(b_batch_top)

        left_layout.addLayout(h_box)

        # 2. 照片导入卡片
        card_img = QFrame(); card_img.setObjectName("Card")
        cl_img = QVBoxLayout(card_img); cl_img.setContentsMargins(12, 10, 12, 10); cl_img.setSpacing(6)
        t_img = QLabel("1. 照片导入"); t_img.setObjectName("CardTitle")
        cl_img.addWidget(t_img)

        self.dropbox = QFrame(); self.dropbox.setObjectName("DropBox")
        self.dropbox.setCursor(Qt.PointingHandCursor)
        self.dropbox.mousePressEvent = lambda e: self.choose_photo()
        db_layout = QHBoxLayout(self.dropbox); db_layout.setContentsMargins(10, 8, 10, 8)
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(40, 40)
        self.thumb_label.setStyleSheet("background-color: #e2e8f0; border-radius: 6px;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setText("📸")
        db_layout.addWidget(self.thumb_label)

        db_text_box = QVBoxLayout()
        self.filename_label = QLabel("点击选择 或 拖入照片")
        self.filename_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #1e293b;")
        self.fileinfo_label = QLabel("支持 JPG / PNG / WEBP")
        self.fileinfo_label.setObjectName("SubTitle")
        db_text_box.addWidget(self.filename_label)
        db_text_box.addWidget(self.fileinfo_label)
        db_layout.addLayout(db_text_box)
        db_layout.addStretch()

        b_choose = QPushButton("选择照片")
        b_choose.setObjectName("SecondaryBtn")
        b_choose.clicked.connect(self.choose_photo)
        db_layout.addWidget(b_choose)

        cl_img.addWidget(self.dropbox)
        left_layout.addWidget(card_img)

        # 3. 规格与底色卡片
        card_spec = QFrame(); card_spec.setObjectName("Card")
        cl_spec = QVBoxLayout(card_spec); cl_spec.setContentsMargins(12, 10, 12, 10); cl_spec.setSpacing(8)
        t_spec = QLabel("2. 规格与底色"); t_spec.setObjectName("CardTitle")
        cl_spec.addWidget(t_spec)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索规格：一寸 / 二寸 / 护照 / 签证…")
        self.search_input.textChanged.connect(self.on_search_changed)
        cl_spec.addWidget(self.search_input)

        self.size_combo = QComboBox()
        self.size_combo.currentIndexChanged.connect(self.on_spec_changed)
        cl_spec.addWidget(self.size_combo)

        self.badge_dim = QLabel("规格: 25 × 35 mm · 295 × 413 px @ 300DPI")
        self.badge_dim.setObjectName("DimensionBadge")
        cl_spec.addWidget(self.badge_dim)

        cl_spec.addWidget(QLabel("背景底色:"))
        color_grid = QHBoxLayout(); color_grid.setSpacing(4)
        self.color_btn_group = QButtonGroup(self)
        self.color_btn_group.setExclusive(True)

        colors_def = [
            ("蓝底", "#438EDB", "#ffffff", (67, 142, 219)),
            ("红底", "#FF0000", "#ffffff", (255, 0, 0)),
            ("白底", "#FFFFFF", "#1e293b", (255, 255, 255)),
            ("深蓝", "#1E50A2", "#ffffff", (30, 80, 162)),
            ("灰底", "#D1D5DB", "#1e293b", (209, 213, 219)),
            ("原图", "transparent", "#1e293b", None),
        ]

        for idx, (cname, chex, text_c, crgb) in enumerate(colors_def):
            btn = QPushButton(cname)
            btn.setObjectName("ColorChip")
            btn.setCheckable(True)
            bg_style = f"background-color: {chex}; color: {text_c};" if chex != "transparent" else "background-color: #f1f5f9; color: #475569;"
            btn.setStyleSheet(bg_style)
            btn.clicked.connect(lambda checked, name=cname, rgb=crgb, h=chex: self.set_background_color(name, rgb, h))
            self.color_btn_group.addButton(btn, idx)
            color_grid.addWidget(btn)
            if idx == 0:  # 默认蓝底
                btn.setChecked(True)

        b_custom_c = QPushButton("🎨 自定义")
        b_custom_c.setObjectName("SecondaryBtn")
        b_custom_c.clicked.connect(self.pick_custom_color)
        color_grid.addWidget(b_custom_c)
        cl_spec.addLayout(color_grid)

        left_layout.addWidget(card_spec)

        # 4. 排版冲印卡片 (默认: 仅单张证件照)
        card_layout = QFrame(); card_layout.setObjectName("Card")
        cl_lay = QVBoxLayout(card_layout); cl_lay.setContentsMargins(12, 10, 12, 10); cl_lay.setSpacing(8)
        t_lay = QLabel("3. 格式与排版"); t_lay.setObjectName("CardTitle")
        cl_lay.addWidget(t_lay)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "🖼 仅单张证件照 (默认)",
            "📄 照相馆标准相纸排版",
            "🔀 常用冲印混排",
            "📐 自定义网格 (指定行/列)"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        cl_lay.addWidget(self.mode_combo)

        # 相纸容器
        self.paper_container = QWidget()
        pc_layout = QVBoxLayout(self.paper_container); pc_layout.setContentsMargins(0, 0, 0, 0); pc_layout.setSpacing(4)
        self.opt_paper = QComboBox()
        self.opt_paper.currentIndexChanged.connect(self.trigger_render_debounce)
        pc_layout.addWidget(self.opt_paper)
        self.paper_info_badge = QLabel("排版计算中…")
        self.paper_info_badge.setObjectName("SubTitle")
        pc_layout.addWidget(self.paper_info_badge)
        cl_lay.addWidget(self.paper_container)

        # 混排方案容器
        self.mixed_container = QWidget()
        mc_layout = QVBoxLayout(self.mixed_container); mc_layout.setContentsMargins(0, 0, 0, 0); mc_layout.setSpacing(4)
        self.opt_mixed = QComboBox()
        self.opt_mixed.addItem("6寸混排 · 4张二寸 + 4张一寸 (全正立)", "6in_4_4")
        self.opt_mixed.addItem("5寸混排 · 2张二寸 + 4张一寸 (全正立)", "5in_2_4")
        self.opt_mixed.currentIndexChanged.connect(self.trigger_render_debounce)
        mc_layout.addWidget(self.opt_mixed)
        cl_lay.addWidget(self.mixed_container)

        # 自定义网格容器
        self.grid_container = QWidget()
        gc_layout = QHBoxLayout(self.grid_container); gc_layout.setContentsMargins(0, 0, 0, 0); gc_layout.setSpacing(6)
        gc_layout.addWidget(QLabel("行数:"))
        self.opt_rows = QSpinBox(); self.opt_rows.setRange(1, 50); self.opt_rows.setValue(4)
        self.opt_rows.valueChanged.connect(self.trigger_render_debounce)
        gc_layout.addWidget(self.opt_rows)
        gc_layout.addWidget(QLabel("列数:"))
        self.opt_cols = QSpinBox(); self.opt_cols.setRange(1, 50); self.opt_cols.setValue(3)
        self.opt_cols.valueChanged.connect(self.trigger_render_debounce)
        gc_layout.addWidget(self.opt_cols)
        cl_lay.addWidget(self.grid_container)

        # 辅助选项
        self.opt_aux_box = QWidget()
        aux_layout = QHBoxLayout(self.opt_aux_box); aux_layout.setContentsMargins(0, 0, 0, 0); aux_layout.setSpacing(8)
        self.cb_cutlines = QCheckBox("打印裁切虚线框")
        self.cb_cutlines.setChecked(True)
        self.cb_cutlines.toggled.connect(self.trigger_render_debounce)
        aux_layout.addWidget(self.cb_cutlines)

        self.cb_sizetext = QCheckBox("标注尺寸规格")
        self.cb_sizetext.setChecked(True)
        self.cb_sizetext.toggled.connect(self.trigger_render_debounce)
        aux_layout.addWidget(self.cb_sizetext)
        cl_lay.addWidget(self.opt_aux_box)

        left_layout.addWidget(card_layout)

        # 5. 底部操作栏
        act_box = QVBoxLayout(); act_box.setSpacing(6)
        self.btn_export = QPushButton("💾 导出当前结果 (PNG + JPG)")
        self.btn_export.setObjectName("PrimaryBtn")
        self.btn_export.clicked.connect(self.export_images)
        act_box.addWidget(self.btn_export)

        bottom_tools = QHBoxLayout()
        b_preset = QPushButton("⚙️ 预设管理…")
        b_preset.setObjectName("SecondaryBtn")
        b_preset.clicked.connect(self.open_preset_dialog)
        bottom_tools.addWidget(b_preset)

        b_batch = QPushButton("📂 批量处理…")
        b_batch.setObjectName("SecondaryBtn")
        b_batch.clicked.connect(self.open_batch_dialog)
        bottom_tools.addWidget(b_batch)

        b_refresh = QPushButton("🔄 刷新")
        b_refresh.setObjectName("SecondaryBtn")
        b_refresh.clicked.connect(self.render_now)
        bottom_tools.addWidget(b_refresh)
        act_box.addLayout(bottom_tools)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        act_box.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪 · 请选择照片")
        self.status_label.setObjectName("SubTitle")
        self.status_label.setWordWrap(True)
        act_box.addWidget(self.status_label)

        left_layout.addLayout(act_box)
        left_layout.addStretch()

        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        # ---------- 右侧工作区 ----------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        self.view_status = QLabel("工作区：拖入图片即可开始")
        self.view_status.setStyleSheet("font-weight: 600; font-size: 13px; color: #475569;")
        top_bar.addWidget(self.view_status)
        top_bar.addStretch()
        right_layout.addLayout(top_bar)

        self.preview_canvas = QLabel()
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_canvas.setStyleSheet("background-color: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 10px;")
        self.preview_canvas.setText("把照片拖入此处\n或点击左侧「选择照片」")
        right_layout.addWidget(self.preview_canvas, 1)

        self.footer_info = QLabel("尚未载入图像")
        self.footer_info.setObjectName("SubTitle")
        self.footer_info.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.footer_info)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 880])

        self.refresh_sizes()
        self.refresh_papers()
        self.on_mode_changed()

        self.setAcceptDrops(True)

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._exec_render)

    # ---------- 拖拽支持 ----------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.dropbox.setProperty("dragOver", True)
            self.dropbox.style().unpolish(self.dropbox)
            self.dropbox.style().polish(self.dropbox)

    def dragMoveEvent(self, e: QDragMoveEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.dropbox.setProperty("dragOver", False)
        self.dropbox.style().unpolish(self.dropbox)
        self.dropbox.style().polish(self.dropbox)

    def dropEvent(self, e: QDropEvent):
        self.dropbox.setProperty("dragOver", False)
        self.dropbox.style().unpolish(self.dropbox)
        self.dropbox.style().polish(self.dropbox)
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                self.load_photo(p)
                break

    # ---------- 照片加载与智能抠图 ----------
    def choose_photo(self):
        last_dir = self.settings.value("last_dir", os.path.expanduser("~/Pictures"))
        p, _ = QFileDialog.getOpenFileName(
            self, "选择人像照片", last_dir, "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if p:
            self.settings.setValue("last_dir", os.path.dirname(p))
            self.load_photo(p)

    def load_photo(self, p):
        self.input_path = p
        self.cached_rgba = None
        self.current_sheet = None
        self.current_single = None
        self.current_render_image = None

        fname = os.path.basename(p)
        self.filename_label.setText(fname)
        self.settings.setValue("last_dir", os.path.dirname(p))

        try:
            from PIL import Image
            orig_img = Image.open(p)
            w, h = orig_img.size
            self.fileinfo_label.setText(f"原图: {w} × {h} px")
            thumb_img = orig_img.copy()
            thumb_img.thumbnail((40, 40), Image.LANCZOS)
            thumb_pm = QPixmap.fromImage(pil_to_qimage(thumb_img))
            self.thumb_label.setPixmap(thumb_pm)

            # 默认只显示单张证件照
            self.current_render_image = orig_img
            self.update_canvas_display()
            self.view_status.setText(f"已载入: {fname} · 发丝级抠图中…")
            self.footer_info.setText(f"原图分辨率: {w} × {h} px")
        except Exception as e:
            self.fileinfo_label.setText(str(e))

        self.status_label.setText("正在执行发丝级智能抠图…")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        if self.mworker and self.mworker.isRunning():
            self.mworker.quit(); self.mworker.wait(1000)

        self.mworker = MattingWorker(p)
        self.mworker.done.connect(self.on_matting_success)
        self.mworker.failed.connect(self.on_matting_failed)
        self.mworker.start()

    def on_matting_success(self, rgba):
        self.cached_rgba = rgba
        self.progress_bar.setVisible(False)
        self.status_label.setText("✓ 智能抠图完成！换底色实时瞬间刷新")
        self.trigger_render_debounce()

    def on_matting_failed(self, msg):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"{msg}")
        self.trigger_render_debounce()

    # ---------- 参数交互 ----------
    def set_background_color(self, name, rgb, hex_c):
        self.current_color_data = {"name": name, "rgb": rgb, "hex": hex_c}
        self.trigger_render_debounce()

    def pick_custom_color(self):
        col = QColorDialog.getColor(QColor("#438EDB"), self, "选择自定义底色")
        if col.isValid():
            r, g, b = col.red(), col.green(), col.blue()
            hex_c = col.name().upper()
            self.color_btn_group.setExclusive(False)
            for b in self.color_btn_group.buttons():
                b.setChecked(False)
            self.color_btn_group.setExclusive(True)
            self.set_background_color(f"自定义({hex_c})", (r, g, b), hex_c)

    def on_search_changed(self):
        self.refresh_sizes()
        self.trigger_render_debounce()

    def on_spec_changed(self):
        s = self.size_combo.currentData()
        if s:
            self.badge_dim.setText(f"规格: {s['w_mm']} × {s['h_mm']} mm · {s['w_px']} × {s['h_px']} px @ 300DPI")
            self.update_paper_calc_badge()
        self.trigger_render_debounce()

    def on_mode_changed(self):
        mode = self.mode_combo.currentIndex()
        # 0: 仅单张 (默认), 1: 相纸排版, 2: 常用混排, 3: 自定义网格
        self.paper_container.setVisible(mode == 1)
        self.mixed_container.setVisible(mode == 2)
        self.grid_container.setVisible(mode == 3)
        self.opt_aux_box.setVisible(mode != 0)
        self.update_paper_calc_badge()
        self.trigger_render_debounce()

    def update_paper_calc_badge(self):
        s = self.size_combo.currentData()
        p = self.opt_paper.currentData()
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            self.paper_info_badge.setText("💡 输出单张证件照 (默认)")
        elif mode == 1 and s and p:
            lay = core.compute_layout(p["w_mm"], p["h_mm"], s["w_mm"], s["h_mm"])
            ori_tag = "横放相纸" if lay["paper_w_mm"] > lay["paper_h_mm"] else "竖放相纸"
            self.paper_info_badge.setText(f"💡 标准相纸排版: {lay['count']} 张 ({lay['cols']}列 × {lay['rows']}行 · {ori_tag})")
        elif mode == 2:
            self.paper_info_badge.setText("💡 混排模板 · 所有照片正立直放")
        else:
            self.paper_info_badge.setText("")

    def refresh_sizes(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        kw = self.search_input.text()
        for s in core.search_sizes(kw):
            self.size_combo.addItem(f"{s['name']} ({s['w_mm']}×{s['h_mm']}mm) - {s['category']}", s)
        self.size_combo.blockSignals(False)
        s = self.size_combo.currentData()
        if s:
            self.badge_dim.setText(f"规格: {s['w_mm']} × {s['h_mm']} mm · {s['w_px']} × {s['h_px']} px @ 300DPI")

    def refresh_papers(self):
        self.opt_paper.blockSignals(True)
        self.opt_paper.clear()
        for p in core.load_papers():
            self.opt_paper.addItem(f"{p['name']}", p)
        self.opt_paper.blockSignals(False)

    # ---------- 渲染管理 (0 闪烁平滑更新) ----------
    def trigger_render_debounce(self):
        if self.input_path:
            self.debounce_timer.start(160)

    def render_now(self):
        self.debounce_timer.stop()
        self._exec_render()

    def _exec_render(self):
        if not self.input_path or self._busy:
            return
        s = self.size_combo.currentData()
        if not s:
            return

        mode_idx = self.mode_combo.currentIndex()
        extra_params = {
            "paper": self.opt_paper.currentData(),
            "rows": self.opt_rows.value(),
            "cols": self.opt_cols.value(),
            "mix_type": self.opt_mixed.currentData()
        }

        cut_lines = self.cb_cutlines.isChecked()
        add_text = self.cb_sizetext.isChecked()

        self._busy = True
        self.btn_export.setEnabled(False)

        if self.worker and self.worker.isRunning():
            self.worker.quit(); self.worker.wait(300)

        self.worker = RenderWorker(
            self.input_path, s, self.current_color_data, mode_idx, extra_params,
            cut_lines, add_text, cached_rgba=self.cached_rgba
        )
        self.worker.done.connect(self.on_render_done)
        self.worker.error.connect(self.on_render_error)
        self.worker.finished.connect(self.on_render_finished)
        self.worker.start()

    def on_render_done(self, img, info, is_single, single_photo):
        self.current_render_image = img
        self.current_sheet = None if is_single else img
        self.current_single = single_photo

        if img is not None:
            self.update_canvas_display()
            self.view_status.setText(info)
            self.footer_info.setText(f"输出分辨率: {img.size[0]} × {img.size[1]} px · 300 DPI")
            self.status_label.setText("✓ 渲染完成，可直接导出")

    def update_canvas_display(self):
        if self.current_render_image is None:
            return
        target_w = max(100, self.preview_canvas.width() - 20)
        target_h = max(100, self.preview_canvas.height() - 20)
        qimg = pil_to_qimage(self.current_render_image)
        pm = QPixmap.fromImage(qimg).scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_canvas.setPixmap(pm)

    def on_render_error(self, err):
        self.status_label.setText(f"渲染出错: {err}")

    def on_render_finished(self):
        self._busy = False
        self.btn_export.setEnabled(True)

    # ---------- 导出 ----------
    def export_images(self):
        if self.current_sheet is None and self.current_single is None:
            QMessageBox.warning(self, "提示", "请先选择照片生成预览后再导出。")
            return

        last_dir = self.settings.value("last_export_dir", os.path.expanduser("~/Desktop"))
        out_dir = QFileDialog.getExistingDirectory(self, "选择保存文件夹", last_dir)
        if not out_dir:
            return

        self.settings.setValue("last_export_dir", out_dir)
        s = self.size_combo.currentData()
        id_name = s["name"] if s else "证件照"
        base = os.path.splitext(os.path.basename(self.input_path))[0] if self.input_path else "IDPhoto"

        saved_files = []
        try:
            if self.current_sheet is not None:
                mode_idx = self.mode_combo.currentIndex()
                if mode_idx == 2:
                    tag = "混排冲印"
                elif mode_idx == 3:
                    tag = "网格排版"
                else:
                    tag = self.opt_paper.currentText().split(" ")[0]
                png_path = os.path.join(out_dir, f"{base}_{tag}_{id_name}.png")
                jpg_path = os.path.join(out_dir, f"{base}_{tag}_{id_name}.jpg")
                self.current_sheet.save(png_path, "PNG")
                self.current_sheet.save(jpg_path, "JPEG", quality=95)
                saved_files.append(png_path)

            if self.current_single is not None:
                single_png = os.path.join(out_dir, f"{base}_{id_name}_单张.png")
                single_jpg = os.path.join(out_dir, f"{base}_{id_name}_单张.jpg")
                self.current_single.save(single_png, "PNG")
                self.current_single.save(single_jpg, "JPEG", quality=95)
                saved_files.append(single_png)

            msg = "成功导出以下文件（同时生成 PNG + JPG 300DPI）：\n\n" + "\n".join(f"• {os.path.basename(f)}" for f in saved_files)
            QMessageBox.information(self, "导出成功", msg)
            self.status_label.setText(f"已导出到: {out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def open_preset_dialog(self):
        d = PresetDialog(self)
        d.exec()
        self.refresh_sizes()
        self.refresh_papers()
        self.trigger_render_debounce()

    def open_batch_dialog(self):
        d = BatchDialog(self)
        d.exec()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update_canvas_display()

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


# ============================================================ 预设管理
class PresetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义预设管理")
        self.resize(540, 440)
        self.pm = core.PresetManager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        self.size_list = QListWidget()
        size_tab = QWidget()
        sl = QVBoxLayout(size_tab); sl.addWidget(self.size_list)
        sf = QFormLayout()
        self.s_name = QLineEdit(); self.s_cat = QLineEdit("我的预设")
        self.s_w = QDoubleSpinBox(); self.s_w.setRange(1, 300); self.s_w.setValue(25)
        self.s_h = QDoubleSpinBox(); self.s_h.setRange(1, 300); self.s_h.setValue(35)
        sf.addRow("名称", self.s_name); sf.addRow("分类", self.s_cat)
        sf.addRow("宽 (mm)", self.s_w); sf.addRow("高 (mm)", self.s_h)
        sl.addLayout(sf)
        sb = QHBoxLayout()
        b_add_s = QPushButton("添加尺寸"); b_del_s = QPushButton("删除选中")
        b_add_s.clicked.connect(self.add_size); b_del_s.clicked.connect(self.del_size)
        sb.addWidget(b_add_s); sb.addWidget(b_del_s); sl.addLayout(sb)
        tabs.addTab(size_tab, "证件规格")

        self.paper_list = QListWidget()
        paper_tab = QWidget()
        pl = QVBoxLayout(paper_tab); pl.addWidget(self.paper_list)
        pf = QFormLayout()
        self.p_name = QLineEdit()
        self.p_w = QDoubleSpinBox(); self.p_w.setRange(10, 1000); self.p_w.setValue(102)
        self.p_h = QDoubleSpinBox(); self.p_h.setRange(10, 1000); self.p_h.setValue(152)
        pf.addRow("相纸名", self.p_name); pf.addRow("宽 (mm)", self.p_w); pf.addRow("高 (mm)", self.p_h)
        pl.addLayout(pf)
        pb = QHBoxLayout()
        b_add_p = QPushButton("添加相纸"); b_del_p = QPushButton("删除选中")
        b_add_p.clicked.connect(self.add_paper); b_del_p.clicked.connect(self.del_paper)
        pb.addWidget(b_add_p); pb.addWidget(b_del_p); pl.addLayout(pb)
        tabs.addTab(paper_tab, "相纸规格")

        self.refresh()
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept)
        layout.addWidget(bb)

    def refresh(self):
        self.size_list.clear()
        for s in self.pm.sizes():
            self.size_list.addItem(f"{s['name']} [{s['category']}] {s['w_mm']}×{s['h_mm']} mm")
        self.paper_list.clear()
        for p in self.pm.papers():
            self.paper_list.addItem(f"{p['name']} {p['w_mm']}×{p['h_mm']} mm")

    def add_size(self):
        if self.s_name.text().strip():
            self.pm.add_size(self.s_name.text().strip(), self.s_w.value(), self.s_h.value(), self.s_cat.text().strip() or "我的预设")
            self.refresh()

    def del_size(self):
        it = self.size_list.currentItem()
        if it:
            self.pm.remove_size(it.text().split(" [")[0]); self.refresh()

    def add_paper(self):
        if self.p_name.text().strip():
            self.pm.add_paper(self.p_name.text().strip(), self.p_w.value(), self.p_h.value()); self.refresh()

    def del_paper(self):
        it = self.paper_list.currentItem()
        if it:
            self.pm.remove_paper(it.text().split(" ")[0]); self.refresh()


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f8fafc"))
    pal.setColor(QPalette.WindowText, QColor("#0f172a"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    pal.setColor(QPalette.Text, QColor("#0f172a"))
    pal.setColor(QPalette.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ButtonText, QColor("#1e293b"))
    pal.setColor(QPalette.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    app.setStyleSheet(STUDIO_QSS)

    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.icns")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    w = MainWindow()
    if os.path.exists(icon_path):
        w.setWindowIcon(QIcon(icon_path))
    w.raise_()
    w.activateWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
