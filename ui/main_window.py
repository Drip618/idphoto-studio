# -*- coding: utf-8 -*-
"""
ui/main_window.py — 证件照工作室 现代化界面（重写版）
- 导入照片即自动抠图 + 显示预览（不用手动点排版）
- 换底色/尺寸实时刷新（抠图结果缓存，只算一次）
- 导出可选路径（QFileDialog）
- 卡片式 QSS 浅色主题
"""
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QFileDialog,
    QMessageBox, QGroupBox, QDialog, QDialogButtonBox, QTabWidget, QListWidget,
    QProgressBar, QRadioButton, QButtonGroup, QDoubleSpinBox, QFrame, QScrollArea,
    QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMimeData
from PySide6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import idphoto_core as core


# ============================================================ QSS 现代化主题
QSS = """
* { font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial; }
QMainWindow, QScrollArea { background: #f4f5f7; }
QFrame#Card {
    background: #ffffff; border-radius: 14px;
    border: 1px solid #eceef1;
}
QLabel { color: #1f2937; }
QLabel#SectionTitle {
    font-size: 13px; font-weight: 600; color: #6b7280;
    padding-top: 2px;
}
QLabel#Hint { color: #9ca3af; font-size: 12px; }
QLabel#BigHint { color: #9ca3af; font-size: 15px; }
QPushButton {
    background: #ffffff; border: 1px solid #d1d5db; border-radius: 9px;
    padding: 8px 16px; color: #374151; font-size: 13px;
}
QPushButton:hover { background: #f9fafb; border-color: #9ca3af; }
QPushButton:pressed { background: #f3f4f6; }
QPushButton#Primary {
    background: #2563eb; border: none; color: #ffffff; font-weight: 600;
}
QPushButton#Primary:hover { background: #1d4ed8; }
QPushButton#Primary:pressed { background: #1e40af; }
QPushButton#Primary:disabled { background: #93c5fd; }
QPushButton#Accent {
    background: #ffffff; border: 1px solid #2563eb; color: #2563eb; font-weight: 600;
}
QPushButton#Accent:hover { background: #eff6ff; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
    padding: 7px 10px; color: #1f2937; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #2563eb; background: #ffffff;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;
    selection-background-color: #eff6ff; selection-color: #2563eb;
}
QRadioButton { color: #374151; font-size: 13px; spacing: 6px; }
QRadioButton::indicator { width: 16px; height: 16px; }
QRadioButton::indicator:unchecked {
    border: 2px solid #d1d5db; border-radius: 9px; background: #fff;
}
QRadioButton::indicator:checked {
    border: 2px solid #2563eb; border-radius: 9px; background: #fff;
}
QRadioButton::indicator:checked::after {
    /* Qt 不支持伪元素圆点，用 border 模拟已足够 */
}
QProgressBar {
    background: #e5e7eb; border: none; border-radius: 6px; height: 8px;
}
QProgressBar::chunk { background: #2563eb; border-radius: 6px; }
QLabel#PreviewArea {
    background: #ffffff; border: 2px dashed #d1d5db; border-radius: 14px;
}
QTabWidget::pane { border: 1px solid #e5e7eb; border-radius: 8px; }
QTabBar::tab {
    background: #f3f4f6; padding: 7px 14px; border-radius: 7px; margin-right: 4px;
    color: #6b7280;
}
QTabBar::tab:selected { background: #2563eb; color: #fff; }
"""


def pil_to_pixmap(img, max_w=900, max_h=700):
    from PIL import Image
    if img is None:
        return QPixmap()
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    w, h = img.size
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ============================================================ 后台 Worker
class Worker(QThread):
    progress = Signal(str)
    done = Signal(object, str, bool, object)  # (image, info, is_single, single_photo)

    def __init__(self, image_path, size, color, layout_mode, layout_params, order,
                 cached_rgba=None):
        super().__init__()
        self.image_path = image_path
        self.size = size
        self.color = color
        self.layout_mode = layout_mode
        self.layout_params = layout_params
        self.order = order
        self.cached_rgba = cached_rgba  # 已抠图的 RGBA，避免重复抠

    def run(self):
        try:
            from PIL import Image
            self.progress.emit("读取照片…")
            img = Image.open(self.image_path)
            bg = self.color["rgb"]
            matting = None
            need_matting = bg is not None

            # 有缓存且要换底：直接用缓存 rgba
            if need_matting and self.cached_rgba is not None:
                self.progress.emit("合成中…")
                id_photo = core._center_crop_by_subject(
                    self.cached_rgba, self.size["w_px"], self.size["h_px"], bg)
            else:
                if need_matting:
                    self.progress.emit("抠图中（首次约 2-5 秒）…")
                    matting = core.Matting()
                    if not matting.available():
                        self.progress.emit("未找到模型，改用原图裁切…")
                        bg = None
                try:
                    id_photo = core.prepare_id_photo(
                        img, self.size["w_px"], self.size["h_px"], bg, matting)
                except core.MattingError as e:
                    # 抠图失败：降级为原图裁切，提示用户
                    self.progress.emit("抠图失败，已用原图裁切：%s" % str(e)[:60])
                    id_photo = core.prepare_id_photo(
                        img, self.size["w_px"], self.size["h_px"], None, None)

            if self.layout_mode == "single":
                info = "单张 %s · %d×%d px" % (
                    self.size["name"], self.size["w_px"], self.size["h_px"])
                self.done.emit(id_photo, info, True, id_photo)
                return

            self.progress.emit("排版中…")
            if self.layout_mode == "paper":
                lay = core.compute_layout(self.layout_params["paper"]["w_mm"],
                                          self.layout_params["paper"]["h_mm"],
                                          self.size["w_mm"], self.size["h_mm"],
                                          order=self.order)
            elif self.layout_mode == "grid":
                lay = core.compute_layout_grid(self.size["w_mm"], self.size["h_mm"],
                                               self.layout_params["rows"],
                                               self.layout_params["cols"],
                                               order=self.order)
            else:
                paper = self.layout_params["paper"]
                lay = core.compute_layout(paper["w_mm"], paper["h_mm"],
                                          self.size["w_mm"], self.size["h_mm"],
                                          order=self.order)
            size_dims = "%d×%dmm" % (self.size["w_mm"], self.size["h_mm"])
            sheet = core.compose_sheet(id_photo, lay,
                                       size_name=self.size["name"],
                                       size_dims=size_dims)
            info = "排版 %d 张（%d×%d）· 纸张 %d×%d px" % (
                lay["count"], lay["cols"], lay["rows"], lay["paper"][0], lay["paper"][1])
            self.done.emit(sheet, info, False, id_photo)
        except Exception as e:
            import traceback
            self.done.emit(None, "出错：%s\n%s" % (e, traceback.format_exc()[-400:]),
                           False, None)


# 抠图专用 Worker（导入照片时自动跑一次，缓存结果）
class MattingWorker(QThread):
    done = Signal(object)  # rgba PIL.Image or None
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
                self.failed.emit("未找到抠图模型，换底功能不可用（可仅排版）")
                return
            rgba = m.remove(img)
            self.done.emit(rgba)
        except Exception as e:
            self.failed.emit("抠图失败：%s" % str(e)[:120])


# ============================================================ 预设编辑器
class PresetEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义预设管理")
        self.resize(520, 460)
        self.pm = core.PresetManager()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        self.size_list = QListWidget()
        size_tab = QWidget()
        sl = QVBoxLayout(size_tab); sl.addWidget(self.size_list)
        sf = QFormLayout()
        self.s_name = QLineEdit(); self.s_cat = QLineEdit("我的预设")
        self.s_w = QDoubleSpinBox(); self.s_w.setRange(1, 200); self.s_w.setValue(25)
        self.s_h = QDoubleSpinBox(); self.s_h.setRange(1, 200); self.s_h.setValue(35)
        sf.addRow("名称", self.s_name); sf.addRow("类别", self.s_cat)
        sf.addRow("宽(mm)", self.s_w); sf.addRow("高(mm)", self.s_h)
        sl.addLayout(sf)
        sbtn = QHBoxLayout()
        b1 = QPushButton("添加尺寸"); b2 = QPushButton("删除选中")
        b1.clicked.connect(self.add_size); b2.clicked.connect(self.del_size)
        sbtn.addWidget(b1); sbtn.addWidget(b2); sl.addLayout(sbtn)
        tabs.addTab(size_tab, "证件照尺寸")

        self.paper_list = QListWidget()
        paper_tab = QWidget()
        pl = QVBoxLayout(paper_tab); pl.addWidget(self.paper_list)
        pf = QFormLayout()
        self.p_name = QLineEdit(); self.p_w = QDoubleSpinBox(); self.p_w.setRange(1, 1000); self.p_w.setValue(152)
        self.p_h = QDoubleSpinBox(); self.p_h.setRange(1, 1000); self.p_h.setValue(102)
        pf.addRow("名称", self.p_name); pf.addRow("宽(mm)", self.p_w); pf.addRow("高(mm)", self.p_h)
        pl.addLayout(pf)
        pbtn = QHBoxLayout()
        b3 = QPushButton("添加打印纸"); b4 = QPushButton("删除选中")
        b3.clicked.connect(self.add_paper); b4.clicked.connect(self.del_paper)
        pbtn.addWidget(b3); pbtn.addWidget(b4); pl.addLayout(pbtn)
        tabs.addTab(paper_tab, "打印纸")

        self.color_list = QListWidget()
        color_tab = QWidget()
        cl = QVBoxLayout(color_tab); cl.addWidget(self.color_list)
        cf = QFormLayout()
        self.c_name = QLineEdit(); self.c_hex = QLineEdit("#438EDB")
        cf.addRow("名称", self.c_name); cf.addRow("Hex", self.c_hex)
        cl.addLayout(cf)
        cbtn = QHBoxLayout()
        b5 = QPushButton("添加底色"); b6 = QPushButton("删除选中")
        b5.clicked.connect(self.add_color); b6.clicked.connect(self.del_color)
        cbtn.addWidget(b5); cbtn.addWidget(b6); cl.addLayout(cbtn)
        tabs.addTab(color_tab, "底色")

        self.refresh()
        layout.addWidget(QLabel("修改即时保存到 ~/.idphoto_studio/user_presets.json，重启生效。"))
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept)
        layout.addWidget(bb)

    def refresh(self):
        self.size_list.clear()
        for s in self.pm.sizes():
            self.size_list.addItem("%s [%s] %dx%dmm" % (s["name"], s["category"], s["w_mm"], s["h_mm"]))
        self.paper_list.clear()
        for p in self.pm.papers():
            self.paper_list.addItem("%s %dx%dmm" % (p["name"], p["w_mm"], p["h_mm"]))
        self.color_list.clear()
        for c in self.pm.colors():
            self.color_list.addItem("%s %s" % (c["name"], c["hex"] or "原图"))

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

    def add_color(self):
        if self.c_name.text().strip():
            self.pm.add_color(self.c_name.text().strip(), self.c_hex.text().strip()); self.refresh()

    def del_color(self):
        it = self.color_list.currentItem()
        if it:
            self.pm.remove_color(it.text().split(" ")[0]); self.refresh()


# ============================================================ 卡片辅助
def make_card(title, parent_layout):
    card = QFrame(); card.setObjectName("Card")
    v = QVBoxLayout(card); v.setContentsMargins(16, 14, 16, 16); v.setSpacing(8)
    if title:
        t = QLabel(title); t.setObjectName("SectionTitle")
        v.addWidget(t)
    parent_layout.addWidget(card)
    return v


# ============================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照工作室")
        self.resize(1180, 760)
        self.input_path = None
        self.cached_rgba = None      # 抠图缓存
        self.current_sheet = None
        self.current_single = None
        self.worker = None
        self.mworker = None
        self._busy = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        # ---------- 左：控制面板 ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(360)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setSpacing(12)
        left.setContentsMargins(0, 0, 8, 0)

        # 导入卡片
        c_import = make_card("", left)
        hl = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("拖入照片 或 点此选择")
        b_import = QPushButton("选择照片"); b_import.setObjectName("Accent")
        b_import.clicked.connect(self.choose_photo)
        hl.addWidget(self.path_edit); hl.addWidget(b_import)
        c_import.addLayout(hl)

        # 尺寸卡片
        c_size = make_card("证件照尺寸", left)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索：一寸 / 美国 / 签证…")
        self.search.textChanged.connect(self._on_param_changed)
        c_size.addWidget(self.search)
        self.size_combo = QComboBox()
        self.size_combo.currentIndexChanged.connect(self._on_param_changed)
        c_size.addWidget(self.size_combo)

        # 底色卡片
        c_color = make_card("底色", left)
        self.color_combo = QComboBox()
        self.color_combo.currentIndexChanged.connect(self._on_param_changed)
        c_color.addWidget(self.color_combo)

        # 排版卡片
        c_layout = make_card("排版格式", left)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["按打印纸自动排满", "仅出单张证件照", "自定义行列", "指定张数(塞入打印纸)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_or_param)
        c_layout.addWidget(self.mode_combo)
        self.opt_paper = QComboBox()
        self.opt_paper.currentIndexChanged.connect(self._on_param_changed)
        c_layout.addRow = None
        c_layout.addWidget(self.opt_paper)
        g2 = QFormLayout(); g2.setSpacing(6)
        self.opt_rows = QSpinBox(); self.opt_rows.setRange(1, 50); self.opt_rows.setValue(4)
        self.opt_cols = QSpinBox(); self.opt_cols.setRange(1, 50); self.opt_cols.setValue(3)
        self.opt_count = QSpinBox(); self.opt_count.setRange(1, 200); self.opt_count.setValue(8)
        g2.addRow("行数", self.opt_rows); g2.addRow("列数", self.opt_cols); g2.addRow("张数", self.opt_count)
        c_layout.addLayout(g2)
        for w in (self.opt_rows, self.opt_cols, self.opt_count):
            w.valueChanged.connect(self._on_param_changed)

        # 排序卡片
        c_order = make_card("序列排序", left)
        self.order_group = QButtonGroup(self)
        r1 = QRadioButton("行优先（→ 换行）"); r2 = QRadioButton("列优先（↓ 换列）")
        r1.setChecked(True)
        self.order_group.addButton(r1, 0); self.order_group.addButton(r2, 1)
        r1.toggled.connect(self._on_param_changed)
        oh = QHBoxLayout(); oh.addWidget(r1); oh.addWidget(r2); oh.addStretch()
        c_order.addLayout(oh)

        # 操作卡片
        c_action = make_card("操作", left)
        bl = QHBoxLayout()
        self.b_gen = QPushButton("生成预览"); self.b_gen.setObjectName("Primary")
        self.b_gen.clicked.connect(self.generate_now)
        self.b_save = QPushButton("导出图片…"); self.b_save.setObjectName("Accent")
        self.b_save.clicked.connect(self.save)
        bl.addWidget(self.b_gen); bl.addWidget(self.b_save)
        c_action.addLayout(bl)
        b_preset = QPushButton("自定义预设…")
        b_preset.clicked.connect(self.open_preset)
        c_action.addWidget(b_preset)

        # 进度+状态
        self.progress = QProgressBar(); self.progress.setTextVisible(False); self.progress.setVisible(False)
        left.addWidget(self.progress)
        self.status = QLabel("拖入或选择一张照片开始"); self.status.setObjectName("Hint")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)

        left_scroll.setWidget(left_host)
        root.addWidget(left_scroll)

        # ---------- 右：预览 ----------
        right = QVBoxLayout(); right.setSpacing(10)
        self.preview = QLabel("把照片拖到这里\n或点左侧「选择照片」")
        self.preview.setObjectName("PreviewArea")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(620, 660)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right.addWidget(self.preview, 1)
        self.preview_info = QLabel(""); self.preview_info.setObjectName("Hint")
        self.preview_info.setAlignment(Qt.AlignCenter)
        right.addWidget(self.preview_info)

        root.addLayout(right, 1)

        self.refresh_sizes(); self.refresh_colors(); self.refresh_papers(); self.on_mode_changed()
        self.setAcceptDrops(True)

        # 防抖定时器
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_preview)

    # ---------- 数据刷新 ----------
    def refresh_sizes(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for s in core.search_sizes(self.search.text()):
            self.size_combo.addItem("%s (%dx%dmm)" % (s["name"], s["w_mm"], s["h_mm"]), s)
        self.size_combo.blockSignals(False)

    def refresh_colors(self):
        self.color_combo.blockSignals(True)
        self.color_combo.clear()
        for c in core.load_colors():
            self.color_combo.addItem(c["name"], c)
        self.color_combo.blockSignals(False)

    def refresh_papers(self):
        self.opt_paper.blockSignals(True)
        self.opt_paper.clear()
        for p in core.load_papers():
            self.opt_paper.addItem(p["name"], p)
        self.opt_paper.blockSignals(False)

    def on_mode_changed(self):
        mode = self.mode_combo.currentIndex()
        self.opt_paper.setVisible(mode in (0, 3))
        self.opt_rows.setVisible(mode == 2)
        self.opt_cols.setVisible(mode == 2)
        self.opt_count.setVisible(mode == 3)

    # ---------- 防抖 ----------
    def _on_param_changed(self, *a):
        self.refresh_sizes() if self.sender() is self.search else None
        self._debounce.start(350)

    def _on_mode_or_param(self, *a):
        self.on_mode_changed()
        self._debounce.start(350)

    def generate_now(self):
        self._debounce.stop()
        self._do_preview()

    # ---------- 交互 ----------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                self.set_photo(p); break

    def choose_photo(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择照片", "", "图片 (*.jpg *.jpeg *.png *.bmp *.webp)")
        if p:
            self.set_photo(p)

    def set_photo(self, p):
        self.input_path = p
        self.path_edit.setText(os.path.basename(p))
        self.cached_rgba = None  # 换图清缓存
        self.current_sheet = None
        self.current_single = None
        # 立即显示原图缩略图
        try:
            from PIL import Image
            img = Image.open(p)
            self.preview.setPixmap(pil_to_pixmap(img, self.preview.width() - 40, self.preview.height() - 40))
            self.preview_info.setText("原图已载入，正在后台抠图…")
        except Exception:
            pass
        self.status.setText("已选照片，自动抠图中…")
        # 后台抠图（缓存）
        if self.mworker and self.mworker.isRunning():
            self.mworker.quit(); self.mworker.wait(2000)
        self.mworker = MattingWorker(p)
        self.mworker.done.connect(self.on_matting_done)
        self.mworker.failed.connect(self.on_matting_failed)
        self.mworker.start()
        # 抠图同时先出一张原图裁切预览（不等抠图）
        self._do_preview()

    def on_matting_done(self, rgba):
        self.cached_rgba = rgba
        self.status.setText("抠图完成，已缓存。换底色/尺寸将实时刷新。")
        self._do_preview()

    def on_matting_failed(self, msg):
        self.status.setText(msg)
        self._do_preview()

    # ---------- 生成预览 ----------
    def _layout_args(self):
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            return "paper", {"paper": self.opt_paper.currentData()}, "row" if self.order_group.checkedId() == 0 else "col"
        elif mode == 1:
            return "single", {}, "row"
        elif mode == 2:
            return "grid", {"rows": self.opt_rows.value(), "cols": self.opt_cols.value()}, "row" if self.order_group.checkedId() == 0 else "col"
        else:
            return "count", {"paper": self.opt_paper.currentData(), "count": self.opt_count.value()}, "row" if self.order_group.checkedId() == 0 else "col"

    def _do_preview(self):
        if not self.input_path or self._busy:
            return
        size = self.size_combo.currentData()
        color = self.color_combo.currentData()
        if size is None or color is None:
            return
        layout_mode, layout_params, order = self._layout_args()
        self._busy = True
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.b_gen.setEnabled(False)
        if self.worker and self.worker.isRunning():
            self.worker.quit(); self.worker.wait(1000)
        self.worker = Worker(self.input_path, size, color, layout_mode, layout_params, order,
                             cached_rgba=self.cached_rgba)
        self.worker.progress.connect(self.status.setText)
        self.worker.done.connect(self.on_done)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def on_done(self, image, info, is_single, single_photo):
        if image is None:
            self.preview_info.setText(info)  # 出错信息
            return
        self.current_sheet = None if is_single else image
        self.current_single = single_photo
        pm = pil_to_pixmap(image, self.preview.width() - 30, self.preview.height() - 30)
        self.preview.setPixmap(pm)
        self.preview_info.setText(info)
        self.status.setText(info + " — 点「导出图片…」保存")

    def _on_worker_finished(self):
        self._busy = False
        self.progress.setVisible(False)
        self.b_gen.setEnabled(True)

    def open_preset(self):
        PresetEditorDialog(self).exec()
        self.refresh_sizes(); self.refresh_colors(); self.refresh_papers()

    # ---------- 导出 ----------
    def save(self):
        if self.current_sheet is None and self.current_single is None:
            QMessageBox.warning(self, "提示", "请先生成预览")
            return
        size = self.size_combo.currentData()
        id_short = size["name"] if size else "证件照"
        base = os.path.splitext(os.path.basename(self.input_path))[0] if self.input_path else "证件照"
        default_name = "%s_%s.png" % (base, id_short)
        default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        out_dir = QFileDialog.getExistingDirectory(self, "选择导出文件夹", default_dir)
        if not out_dir:
            return
        saved = []
        try:
            if self.current_sheet is not None:
                png = os.path.join(out_dir, "%s_排版_%s.png" % (base, id_short))
                self.current_sheet.save(png, "PNG")
                self.current_sheet.save(png[:-4] + ".jpg", "JPEG", quality=95)
                saved.append(png)
            if self.current_single is not None:
                png = os.path.join(out_dir, "%s_单张_%s.png" % (base, id_short))
                self.current_single.save(png, "PNG")
                self.current_single.save(png[:-4] + ".jpg", "JPEG", quality=95)
                saved.append(png)
            QMessageBox.information(self, "已导出", "已保存到：\n" + out_dir + "\n\n" + "\n".join(os.path.basename(f) for f in saved))
            self.status.setText("已导出到：" + out_dir)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))


def run():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
