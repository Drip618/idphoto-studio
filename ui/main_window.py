# -*- coding: utf-8 -*-
"""
ui/main_window.py — 证件照工作室 专业工作室版 UI
=========================================================================
- 现代化苹果 Studio 风格界面，支持自由拉伸窗口并自动记忆窗口尺寸
- 记忆上次打开和导出的文件夹目录
- 全窗口支持拖拽图片导入（带高亮交互）
- 视觉化底色色块选择器 + 证件照规格实时计算
- 左右分栏支持自由拖拽调节（QSplitter）
- 无残留孤立文本标签，所有排版模式控件整齐切换
- 异步后台智能抠图（Hivision MODNet / RMBG 模型），毫秒级换底色
"""
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox, QTabWidget, QListWidget,
    QProgressBar, QRadioButton, QButtonGroup, QDoubleSpinBox, QFrame,
    QSplitter, QCheckBox, QColorDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings, QSize
from PySide6.QtGui import (
    QPixmap, QImage, QDragEnterEvent, QDragMoveEvent, QDropEvent,
    QPainter, QColor, QIcon, QFont, QPalette, QBrush
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import idphoto_core as core

# ============================================================ 现代化 Studio 主题 QSS
STUDIO_QSS = """
* {
    font-family: -apple-system, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif;
}
QMainWindow {
    background-color: #f8fafc;
}
QWidget#LeftPanel {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-bottom: 2px;
}
QFrame#Card:hover {
    border-color: #cbd5e1;
}
QLabel#CardTitle {
    font-size: 12px;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.5px;
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
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 13px;
    color: #1e293b;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    selection-background-color: #eff6ff;
    selection-color: #2563eb;
    padding: 4px;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 14px;
    color: #334155;
    font-size: 13px;
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
    font-size: 14px;
    padding: 10px 18px;
    border-radius: 8px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #1e40af;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #93c5fd;
    border-color: #bfdbfe;
}
QPushButton#SecondaryBtn {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    color: #475569;
    font-weight: 600;
    padding: 8px 14px;
}
QPushButton#SecondaryBtn:hover {
    background-color: #f1f5f9;
    color: #1e293b;
}
QPushButton#ColorChip {
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    min-height: 24px;
}
QPushButton#ColorChip:checked {
    border: 2.5px solid #2563eb;
    background-color: #eff6ff;
}
QFrame#DropBox {
    background-color: #f8fafc;
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
}
QFrame#DropBox:hover, QFrame#DropBox[dragOver="true"] {
    background-color: #eff6ff;
    border-color: #3b82f6;
}
QProgressBar {
    background-color: #e2e8f0;
    border: none;
    border-radius: 4px;
    height: 6px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}
QRadioButton {
    font-size: 12px;
    color: #334155;
    spacing: 6px;
}
QCheckBox {
    font-size: 12px;
    color: #475569;
    spacing: 6px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def pil_to_pixmap(img, max_w=1200, max_h=900):
    if img is None:
        return QPixmap()
    from PIL import Image
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    scale = min(max_w / max(1, w), max_h / max(1, h))
    if scale < 1.0:
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = new_w, new_h
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ============================================================ 异步抠图 Worker
class MattingWorker(QThread):
    done = Signal(object)      # RGBA PIL.Image
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
                self.failed.emit("未找到抠图模型，已转为原图裁切排版")
                return
            rgba = m.remove(img)
            self.done.emit(rgba)
        except Exception as e:
            self.failed.emit("智能抠图失败：%s" % str(e)[:80])


# ============================================================ 异步渲染 Worker
class RenderWorker(QThread):
    done = Signal(object, str, bool, object)  # (sheet/single, info, is_single, single_photo)
    error = Signal(str)

    def __init__(self, image_path, size_dict, color_dict, layout_mode, layout_params,
                 order, cut_lines, add_text, cached_rgba=None):
        super().__init__()
        self.image_path = image_path
        self.size_dict = size_dict
        self.color_dict = color_dict
        self.layout_mode = layout_mode
        self.layout_params = layout_params
        self.order = order
        self.cut_lines = cut_lines
        self.add_text = add_text
        self.cached_rgba = cached_rgba

    def run(self):
        try:
            from PIL import Image
            img = Image.open(self.image_path)
            bg_rgb = self.color_dict["rgb"]
            need_matting = bg_rgb is not None

            # 优先使用缓存的抠图 RGBA
            if need_matting and self.cached_rgba is not None:
                id_photo = core._center_crop_by_subject(
                    self.cached_rgba, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb
                )
            else:
                matting = core.Matting() if (need_matting and core.Matting().available()) else None
                try:
                    id_photo = core.prepare_id_photo(
                        img, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb, matting
                    )
                except Exception as e:
                    # 抠图异常时，降级原图裁切（不换底）
                    id_photo = core.prepare_id_photo(
                        img, self.size_dict["w_px"], self.size_dict["h_px"], None, None
                    )

            if self.layout_mode == "single":
                info = "单张 %s · %d×%d px (300 DPI)" % (
                    self.size_dict["name"], self.size_dict["w_px"], self.size_dict["h_px"]
                )
                self.done.emit(id_photo, info, True, id_photo)
                return

            if self.layout_mode == "paper":
                lay = core.compute_layout(
                    self.layout_params["paper"]["w_mm"],
                    self.layout_params["paper"]["h_mm"],
                    self.size_dict["w_mm"],
                    self.size_dict["h_mm"],
                    order=self.order
                )
            elif self.layout_mode == "grid":
                lay = core.compute_layout_grid(
                    self.size_dict["w_mm"],
                    self.size_dict["h_mm"],
                    self.layout_params["rows"],
                    self.layout_params["cols"],
                    order=self.order
                )
            else:  # count
                paper = self.layout_params["paper"]
                lay = core.compute_layout(
                    paper["w_mm"], paper["h_mm"],
                    self.size_dict["w_mm"], self.size_dict["h_mm"],
                    order=self.order
                )

            size_name = self.size_dict["name"] if self.add_text else ""
            size_dims = "%d×%dmm" % (self.size_dict["w_mm"], self.size_dict["h_mm"]) if self.add_text else ""

            sheet = core.compose_sheet(
                id_photo, lay,
                sheet_color=(255, 255, 255),
                size_name=size_name,
                size_dims=size_dims,
                cut_lines=self.cut_lines
            )

            info = "排版完成 · %d 张 (%d列 × %d行) · 纸张 %d×%d px" % (
                lay["count"], lay["cols"], lay["rows"], lay["paper"][0], lay["paper"][1]
            )
            self.done.emit(sheet, info, False, id_photo)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()[-300:]}")


# ============================================================ 预设管理弹窗
class PresetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义预设管理")
        self.resize(560, 480)
        self.pm = core.PresetManager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 尺寸 Tab
        self.size_list = QListWidget()
        size_tab = QWidget()
        sl = QVBoxLayout(size_tab)
        sl.addWidget(self.size_list)
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
        sb.addWidget(b_add_s); sb.addWidget(b_del_s)
        sl.addLayout(sb)
        tabs.addTab(size_tab, "证件规格")

        # 相纸 Tab
        self.paper_list = QListWidget()
        paper_tab = QWidget()
        pl = QVBoxLayout(paper_tab)
        pl.addWidget(self.paper_list)
        pf = QFormLayout()
        self.p_name = QLineEdit()
        self.p_w = QDoubleSpinBox(); self.p_w.setRange(10, 1000); self.p_w.setValue(102)
        self.p_h = QDoubleSpinBox(); self.p_h.setRange(10, 1000); self.p_h.setValue(152)
        pf.addRow("相纸名", self.p_name); pf.addRow("宽 (mm)", self.p_w); pf.addRow("高 (mm)", self.p_h)
        pl.addLayout(pf)
        pb = QHBoxLayout()
        b_add_p = QPushButton("添加相纸"); b_del_p = QPushButton("删除选中")
        b_add_p.clicked.connect(self.add_paper); b_del_p.clicked.connect(self.del_paper)
        pb.addWidget(b_add_p); pb.addWidget(b_del_p)
        pl.addLayout(pb)
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
            self.pm.remove_size(it.text().split(" [")[0])
            self.refresh()

    def add_paper(self):
        if self.p_name.text().strip():
            self.pm.add_paper(self.p_name.text().strip(), self.p_w.value(), self.p_h.value())
            self.refresh()

    def del_paper(self):
        it = self.paper_list.currentItem()
        if it:
            self.pm.remove_paper(it.text().split(" ")[0])
            self.refresh()


# ============================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照工作室 Studio")
        self.setMinimumSize(1020, 680)

        self.settings = QSettings("IDPhotoStudio", "App")
        self.input_path = None
        self.cached_rgba = None
        self.current_sheet = None
        self.current_single = None
        self.current_color_data = {"name": "白底", "rgb": (255, 255, 255), "hex": "#FFFFFF"}
        self._busy = False
        self.worker = None
        self.mworker = None

        # 恢复上次窗口几何位置
        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1260, 840)

        # 根布局：主分栏（QSplitter 支持拖拽调整左右宽度）
        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # ---------- 左侧控制面板 (可滚动) ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setObjectName("LeftPanel")
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(14)

        # 1. 顶部 Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("证件照工作室")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f172a;")
        subtitle = QLabel("智能抠图换底 · 多规格冲印排版")
        subtitle.setObjectName("SubTitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        left_layout.addLayout(header)

        # 2. 照片导入卡片
        card_img = QFrame(); card_img.setObjectName("Card")
        cl_img = QVBoxLayout(card_img); cl_img.setContentsMargins(14, 12, 14, 14); cl_img.setSpacing(8)
        t_img = QLabel("1. 照片导入"); t_img.setObjectName("CardTitle")
        cl_img.addWidget(t_img)

        self.dropbox = QFrame(); self.dropbox.setObjectName("DropBox")
        self.dropbox.setCursor(Qt.PointingHandCursor)
        self.dropbox.mousePressEvent = lambda e: self.choose_photo()
        db_layout = QHBoxLayout(self.dropbox); db_layout.setContentsMargins(12, 12, 12, 12)
        
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(48, 48)
        self.thumb_label.setStyleSheet("background-color: #e2e8f0; border-radius: 6px;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setText("📸")
        db_layout.addWidget(self.thumb_label)

        db_text_box = QVBoxLayout()
        self.filename_label = QLabel("点击选择 或 拖入照片")
        self.filename_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #1e293b;")
        self.fileinfo_label = QLabel("支持 JPG / PNG / WEBP / BMP")
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
        cl_spec = QVBoxLayout(card_spec); cl_spec.setContentsMargins(14, 12, 14, 14); cl_spec.setSpacing(10)
        t_spec = QLabel("2. 规格与底色"); t_spec.setObjectName("CardTitle")
        cl_spec.addWidget(t_spec)

        # 搜索 + 尺寸下拉
        size_head = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 快速搜索：一寸 / 二寸 / 护照 / 签证…")
        self.search_input.textChanged.connect(self.on_search_changed)
        size_head.addWidget(self.search_input)
        cl_spec.addLayout(size_head)

        self.size_combo = QComboBox()
        self.size_combo.currentIndexChanged.connect(self.on_spec_changed)
        cl_spec.addWidget(self.size_combo)

        self.badge_dim = QLabel("尺寸: 25 × 35 mm · 295 × 413 px @ 300DPI")
        self.badge_dim.setObjectName("DimensionBadge")
        cl_spec.addWidget(self.badge_dim)

        # 视觉化底色选择器
        cl_spec.addWidget(QLabel("背景底色选择:"))
        color_grid = QHBoxLayout(); color_grid.setSpacing(6)
        self.color_btn_group = QButtonGroup(self)
        self.color_btn_group.setExclusive(True)

        colors_def = [
            ("白底", "#FFFFFF", "#1e293b", (255, 255, 255)),
            ("红底", "#FF0000", "#ffffff", (255, 0, 0)),
            ("蓝底", "#438EDB", "#ffffff", (67, 142, 219)),
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
            if idx == 0:
                btn.setChecked(True)

        b_custom_c = QPushButton("🎨 自定义…")
        b_custom_c.setObjectName("SecondaryBtn")
        b_custom_c.clicked.connect(self.pick_custom_color)
        color_grid.addWidget(b_custom_c)

        cl_spec.addLayout(color_grid)
        left_layout.addWidget(card_spec)

        # 4. 排版冲印卡片
        card_layout = QFrame(); card_layout.setObjectName("Card")
        cl_lay = QVBoxLayout(card_layout); cl_lay.setContentsMargins(14, 12, 14, 14); cl_lay.setSpacing(10)
        t_lay = QLabel("3. 排版冲印"); t_lay.setObjectName("CardTitle")
        cl_lay.addWidget(t_lay)

        # 排版模式选择
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "📄 打印相纸自动排满",
            "🖼 仅单张证件照",
            "📐 自定义网格 (指定行/列)",
            "🔢 指定张数 (塞入打印纸)"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        cl_lay.addWidget(self.mode_combo)

        # 动态相纸选择容器
        self.paper_container = QWidget()
        pc_layout = QVBoxLayout(self.paper_container); pc_layout.setContentsMargins(0, 0, 0, 0); pc_layout.setSpacing(4)
        self.opt_paper = QComboBox()
        self.opt_paper.currentIndexChanged.connect(self.trigger_render_debounce)
        pc_layout.addWidget(self.opt_paper)
        self.paper_info_badge = QLabel("排版结果计算中…")
        self.paper_info_badge.setObjectName("SubTitle")
        pc_layout.addWidget(self.paper_info_badge)
        cl_lay.addWidget(self.paper_container)

        # 自定义网格容器 (完全隔离，无悬空标签)
        self.grid_container = QWidget()
        gc_layout = QHBoxLayout(self.grid_container); gc_layout.setContentsMargins(0, 0, 0, 0); gc_layout.setSpacing(8)
        gc_layout.addWidget(QLabel("行数:"))
        self.opt_rows = QSpinBox(); self.opt_rows.setRange(1, 50); self.opt_rows.setValue(4)
        self.opt_rows.valueChanged.connect(self.trigger_render_debounce)
        gc_layout.addWidget(self.opt_rows)
        gc_layout.addWidget(QLabel("列数:"))
        self.opt_cols = QSpinBox(); self.opt_cols.setRange(1, 50); self.opt_cols.setValue(3)
        self.opt_cols.valueChanged.connect(self.trigger_render_debounce)
        gc_layout.addWidget(self.opt_cols)
        cl_lay.addWidget(self.grid_container)

        # 指定张数容器
        self.count_container = QWidget()
        cnt_layout = QHBoxLayout(self.count_container); cnt_layout.setContentsMargins(0, 0, 0, 0); cnt_layout.setSpacing(8)
        cnt_layout.addWidget(QLabel("目标张数:"))
        self.opt_count = QSpinBox(); self.opt_count.setRange(1, 200); self.opt_count.setValue(8)
        self.opt_count.valueChanged.connect(self.trigger_render_debounce)
        cnt_layout.addWidget(self.opt_count)
        cl_lay.addWidget(self.count_container)

        # 排版辅助选项
        opt_line = QHBoxLayout()
        self.cb_cutlines = QCheckBox("打印裁切虚线")
        self.cb_cutlines.setChecked(True)
        self.cb_cutlines.toggled.connect(self.trigger_render_debounce)
        opt_line.addWidget(self.cb_cutlines)

        self.cb_sizetext = QCheckBox("标注尺寸规格")
        self.cb_sizetext.setChecked(True)
        self.cb_sizetext.toggled.connect(self.trigger_render_debounce)
        opt_line.addWidget(self.cb_sizetext)
        cl_lay.addLayout(opt_line)

        # 序列顺序
        order_line = QHBoxLayout()
        order_line.addWidget(QLabel("序列方向:"))
        self.order_group = QButtonGroup(self)
        r_row = QRadioButton("行优先 (→)")
        r_col = QRadioButton("列优先 (↓)")
        r_row.setChecked(True)
        self.order_group.addButton(r_row, 0)
        self.order_group.addButton(r_col, 1)
        r_row.toggled.connect(self.trigger_render_debounce)
        order_line.addWidget(r_row)
        order_line.addWidget(r_col)
        order_line.addStretch()
        cl_lay.addLayout(order_line)

        left_layout.addWidget(card_layout)

        # 5. 底部操作栏
        act_box = QVBoxLayout(); act_box.setSpacing(8)
        self.btn_export = QPushButton("💾 导出照片与排版 (PNG + JPG)")
        self.btn_export.setObjectName("PrimaryBtn")
        self.btn_export.clicked.connect(self.export_images)
        act_box.addWidget(self.btn_export)

        bottom_tools = QHBoxLayout()
        b_preset = QPushButton("⚙️ 自定义预设管理…")
        b_preset.setObjectName("SecondaryBtn")
        b_preset.clicked.connect(self.open_preset_dialog)
        bottom_tools.addWidget(b_preset)

        b_refresh = QPushButton("🔄 重新生成预览")
        b_refresh.setObjectName("SecondaryBtn")
        b_refresh.clicked.connect(self.render_now)
        bottom_tools.addWidget(b_refresh)
        act_box.addLayout(bottom_tools)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        act_box.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪 · 请导入照片")
        self.status_label.setObjectName("SubTitle")
        self.status_label.setWordWrap(True)
        act_box.addWidget(self.status_label)

        left_layout.addLayout(act_box)
        left_layout.addStretch()

        left_scroll.setWidget(left_container)
        left_scroll.setMinimumWidth(360)
        splitter.addWidget(left_scroll)

        # ---------- 右侧工作区 (大预览画布) ----------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(10)

        # 顶部提示条
        top_bar = QHBoxLayout()
        self.view_status = QLabel("工作区：拖入图片即可开始")
        self.view_status.setStyleSheet("font-weight: 600; font-size: 13px; color: #475569;")
        top_bar.addWidget(self.view_status)
        top_bar.addStretch()
        right_layout.addLayout(top_bar)

        # 预览画布 (QLabel 支持缩放)
        self.preview_canvas = QLabel()
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_canvas.setStyleSheet(
            "background-color: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 12px;"
        )
        self.preview_canvas.setText("把照片拖入此处\n或点击左侧「选择照片」")
        right_layout.addWidget(self.preview_canvas, 1)

        # 底部规格信息条
        self.footer_info = QLabel("尚未载入图像")
        self.footer_info.setObjectName("SubTitle")
        self.footer_info.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.footer_info)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 880])

        # 初始化数据与模式
        self.refresh_sizes()
        self.refresh_papers()
        self.on_mode_changed()

        # 全局支持拖拽
        self.setAcceptDrops(True)

        # 防抖渲染定时器
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

        fname = os.path.basename(p)
        self.filename_label.setText(fname)
        self.settings.setValue("last_dir", os.path.dirname(p))

        try:
            from PIL import Image
            orig_img = Image.open(p)
            w, h = orig_img.size
            self.fileinfo_label.setText(f"分辨率: {w} × {h} px")

            # 缩略图
            thumb = pil_to_pixmap(orig_img, 48, 48)
            self.thumb_label.setPixmap(thumb)

            # 首先在画布呈现原图真实比例
            pm = pil_to_pixmap(orig_img, self.preview_canvas.width() - 40, self.preview_canvas.height() - 40)
            self.preview_canvas.setPixmap(pm)
            self.view_status.setText(f"已载入原图: {fname} · 后台智能抠图中…")
            self.footer_info.setText(f"原图分辨率: {w} × {h} px")
        except Exception as e:
            self.fileinfo_label.setText(str(e))

        # 异步启动智能抠图
        self.status_label.setText("正在执行 AI 智能发丝级抠图…")
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
        self.status_label.setText("✓ 智能抠图就绪！换底色与排版实时极速刷新")
        self.trigger_render_debounce()

    def on_matting_failed(self, msg):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"{msg}")
        self.trigger_render_debounce()

    # ---------- 参数与底色交互 ----------
    def set_background_color(self, name, rgb, hex_c):
        self.current_color_data = {"name": name, "rgb": rgb, "hex": hex_c}
        self.trigger_render_debounce()

    def pick_custom_color(self):
        col = QColorDialog.getColor(QColor("#438EDB"), self, "选择自定义背景底色")
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
        # 0: 相纸排版, 1: 仅单张, 2: 自定义网格, 3: 指定张数
        self.paper_container.setVisible(mode in (0, 3))
        self.grid_container.setVisible(mode == 2)
        self.count_container.setVisible(mode == 3)
        self.update_paper_calc_badge()
        self.trigger_render_debounce()

    def update_paper_calc_badge(self):
        s = self.size_combo.currentData()
        p = self.opt_paper.currentData()
        if s and p and self.mode_combo.currentIndex() == 0:
            lay = core.compute_layout(p["w_mm"], p["h_mm"], s["w_mm"], s["h_mm"])
            self.paper_info_badge.setText(f"💡 自动排满: {lay['count']} 张 ({lay['cols']}列 × {lay['rows']}行)")
        elif self.mode_combo.currentIndex() == 1:
            self.paper_info_badge.setText("💡 输出单张证件照")
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
            self.opt_paper.addItem(f"{p['name']} ({p['w_mm']}×{p['h_mm']}mm)", p)
        self.opt_paper.blockSignals(False)

    # ---------- 渲染管理 ----------
    def trigger_render_debounce(self):
        if self.input_path:
            self.debounce_timer.start(250)

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
        if mode_idx == 0:
            layout_mode = "paper"
            layout_params = {"paper": self.opt_paper.currentData()}
        elif mode_idx == 1:
            layout_mode = "single"
            layout_params = {}
        elif mode_idx == 2:
            layout_mode = "grid"
            layout_params = {"rows": self.opt_rows.value(), "cols": self.opt_cols.value()}
        else:
            layout_mode = "count"
            layout_params = {"paper": self.opt_paper.currentData(), "count": self.opt_count.value()}

        order = "col" if self.order_group.checkedId() == 1 else "row"
        cut_lines = self.cb_cutlines.isChecked()
        add_text = self.cb_sizetext.isChecked()

        self._busy = True
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.btn_export.setEnabled(False)

        if self.worker and self.worker.isRunning():
            self.worker.quit(); self.worker.wait(500)

        self.worker = RenderWorker(
            self.input_path, s, self.current_color_data, layout_mode, layout_params,
            order, cut_lines, add_text, cached_rgba=self.cached_rgba
        )
        self.worker.done.connect(self.on_render_done)
        self.worker.error.connect(self.on_render_error)
        self.worker.finished.connect(self.on_render_finished)
        self.worker.start()

    def on_render_done(self, img, info, is_single, single_photo):
        self.current_sheet = None if is_single else img
        self.current_single = single_photo

        if img is not None:
            pm = pil_to_pixmap(img, self.preview_canvas.width() - 30, self.preview_canvas.height() - 30)
            self.preview_canvas.setPixmap(pm)
            self.view_status.setText(info)
            self.footer_info.setText(f"输出分辨率: {img.size[0]} × {img.size[1]} px · 300 DPI")
            self.status_label.setText("✓ 预览渲染完成，可直接导出")

    def on_render_error(self, err):
        self.status_label.setText(f"渲染出错: {err}")

    def on_render_finished(self):
        self._busy = False
        self.progress_bar.setVisible(False)
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
            # 导出排版
            if self.current_sheet is not None:
                p_name = self.opt_paper.currentText().split(" ")[0] if self.mode_combo.currentIndex() != 2 else "网格"
                png_path = os.path.join(out_dir, f"{base}_{p_name}_{id_name}_排版.png")
                jpg_path = os.path.join(out_dir, f"{base}_{p_name}_{id_name}_排版.jpg")
                self.current_sheet.save(png_path, "PNG")
                self.current_sheet.save(jpg_path, "JPEG", quality=95)
                saved_files.append(png_path)

            # 导出单张
            if self.current_single is not None:
                single_png = os.path.join(out_dir, f"{base}_{id_name}_单张.png")
                single_jpg = os.path.join(out_dir, f"{base}_{id_name}_单张.jpg")
                self.current_single.save(single_png, "PNG")
                self.current_single.save(single_jpg, "JPEG", quality=95)
                saved_files.append(single_png)

            msg = "成功导出以下文件（同时生成 PNG + JPG 300DPI）：\n\n" + "\n".join(f"• {os.path.basename(f)}" for f in saved_files)
            QMessageBox.information(self, "导出成功", msg)
            self.status_label.setText(f"已成功导出到: {out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def open_preset_dialog(self):
        d = PresetDialog(self)
        d.exec()
        self.refresh_sizes()
        self.refresh_papers()
        self.trigger_render_debounce()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.current_sheet is not None:
            self.preview_canvas.setPixmap(pil_to_pixmap(self.current_sheet, self.preview_canvas.width() - 30, self.preview_canvas.height() - 30))
        elif self.current_single is not None:
            self.preview_canvas.setPixmap(pil_to_pixmap(self.current_single, self.preview_canvas.width() - 30, self.preview_canvas.height() - 30))

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


# ============================================================ 启动入口
def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 亮色强制 Palette (彻底告别深色模式看不见字)
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

    # 设置 macOS Dock 图标与 App 图标
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
