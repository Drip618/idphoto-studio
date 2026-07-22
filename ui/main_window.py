# -*- coding: utf-8 -*-
"""
ui/main_window.py — PySide6 原生桌面界面
- 拖拽/选择照片
- 尺寸搜索 + 类别筛选（全量国际尺寸）
- 底色选择（含自定义）
- 排版格式：按打印纸自动排 / 自定义行列 / 指定张数
- 序列排序：行优先 / 列优先
- 自定义预设编辑器（尺寸/打印纸/底色，自助增删，持久化）
- 后台线程处理（抠图不卡界面），实时预览，导出 PNG/JPG@300dpi
"""

import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QFileDialog,
    QMessageBox, QGroupBox, QDialog, QDialogButtonBox, QTabWidget, QListWidget,
    QProgressBar, QRadioButton, QButtonGroup, QDoubleSpinBox)
from PySide6.QtCore import Qt, QThread, Signal, QMimeData
from PySide6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import idphoto_core as core


def pil_to_pixmap(img):
    from PIL import Image
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


class Worker(QThread):
    progress = Signal(str)
    # done 参数：(排版纸 or 单张图, 信息文本, 是否单张模式, 原始单张图)
    done = Signal(object, str, bool, object)
    error = Signal(str)

    def __init__(self, image_path, size, color, layout_mode, layout_params, order):
        super().__init__()
        self.image_path = image_path
        self.size = size
        self.color = color
        self.layout_mode = layout_mode
        self.layout_params = layout_params
        self.order = order

    def run(self):
        try:
            from PIL import Image
            self.progress.emit("读取照片…")
            img = Image.open(self.image_path)
            bg = self.color["rgb"]
            matting = None
            if bg is not None:
                self.progress.emit("加载抠图模型（首次较慢）…")
                matting = core.Matting()
                if not matting.available():
                    self.progress.emit("未找到模型，改用「不换背景」排版…")
                    bg = None
                    matting = None
                else:
                    self.progress.emit("抠图中…")
            self.progress.emit("裁切到证件照尺寸…")
            id_photo = core.prepare_id_photo(img, self.size["w_px"], self.size["h_px"], bg, matting)

            if self.layout_mode == "single":
                info = "已生成单张 %s · %d×%d px" % (
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
            else:  # count -> 近似方形网格塞进选定纸张
                paper = self.layout_params["paper"]
                lay = core.compute_layout(paper["w_mm"], paper["h_mm"],
                                          self.size["w_mm"], self.size["h_mm"],
                                          order=self.order)

            size_dims = "%d×%dmm" % (self.size["w_mm"], self.size["h_mm"])
            sheet = core.compose_sheet(id_photo, lay,
                                       size_name=self.size["name"],
                                       size_dims=size_dims)
            info = "已生成 %d 张（%d×%d）· 纸张 %d×%d px" % (
                lay["count"], lay["cols"], lay["rows"], lay["paper"][0], lay["paper"][1])
            self.done.emit(sheet, info, False, id_photo)
        except Exception as e:
            import traceback
            self.error.emit(str(e) + "\n" + traceback.format_exc())


class PresetEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义预设管理")
        self.resize(520, 460)
        self.pm = core.PresetManager()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ---- 尺寸 ----
        self.size_list = QListWidget()
        size_tab = QWidget()
        sl = QVBoxLayout(size_tab)
        sl.addWidget(self.size_list)
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

        # ---- 打印纸 ----
        self.paper_list = QListWidget()
        paper_tab = QWidget()
        pl = QVBoxLayout(paper_tab)
        pl.addWidget(self.paper_list)
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

        # ---- 底色 ----
        self.color_list = QListWidget()
        color_tab = QWidget()
        cl = QVBoxLayout(color_tab)
        cl.addWidget(self.color_list)
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
        layout.addWidget(QLabel("修改即时保存到 ~/.idphoto_studio/user_presets.json，重启生效于所有下拉框。"))
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
        if not self.s_name.text().strip():
            return
        self.pm.add_size(self.s_name.text().strip(), self.s_w.value(), self.s_h.value(), self.s_cat.text().strip() or "我的预设")
        self.refresh()

    def del_size(self):
        it = self.size_list.currentItem()
        if it:
            self.pm.remove_size(it.text().split(" [")[0])
            self.refresh()

    def add_paper(self):
        if not self.p_name.text().strip():
            return
        self.pm.add_paper(self.p_name.text().strip(), self.p_w.value(), self.p_h.value())
        self.refresh()

    def del_paper(self):
        it = self.paper_list.currentItem()
        if it:
            self.pm.remove_paper(it.text().split(" ")[0])
            self.refresh()

    def add_color(self):
        if not self.c_name.text().strip():
            return
        self.pm.add_color(self.c_name.text().strip(), self.c_hex.text().strip())
        self.refresh()

    def del_color(self):
        it = self.color_list.currentItem()
        if it:
            self.pm.remove_color(it.text().split(" ")[0])
            self.refresh()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照换底色 · 排版打印一体")
        self.resize(1080, 700)
        self.input_path = None
        self.current_sheet = None
        self.current_single = None
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # ---------- 左：控制 ----------
        left = QVBoxLayout()
        root.addLayout(left, 1)

        # 导入
        self.path_edit = QLineEdit(); self.path_edit.setReadOnly(True)
        b_import = QPushButton("选择照片")
        b_import.clicked.connect(self.choose_photo)
        hl = QHBoxLayout(); hl.addWidget(self.path_edit); hl.addWidget(b_import)
        left.addLayout(hl)

        # 尺寸
        left.addWidget(QLabel("证件照尺寸（可搜索）"))
        self.search = QLineEdit(); self.search.setPlaceholderText("输入关键字，如 一寸 / 美国 / 签证…")
        self.search.textChanged.connect(self.refresh_sizes)
        left.addWidget(self.search)
        self.size_combo = QComboBox(); self.size_combo.setEditable(False)
        left.addWidget(self.size_combo)

        # 底色
        left.addWidget(QLabel("底色"))
        self.color_combo = QComboBox()
        left.addWidget(self.color_combo)

        # 排版格式
        left.addWidget(QLabel("排版格式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["仅出单张证件照", "按打印纸自动排满", "自定义行列", "指定张数(塞入打印纸)"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        left.addWidget(self.mode_combo)

        self.opt_paper = QComboBox(); left.addWidget(QLabel("打印纸")); left.addWidget(self.opt_paper)
        self.opt_rows = QSpinBox(); self.opt_rows.setRange(1, 50); self.opt_rows.setValue(4)
        self.opt_cols = QSpinBox(); self.opt_cols.setRange(1, 50); self.opt_cols.setValue(3)
        self.opt_count = QSpinBox(); self.opt_count.setRange(1, 200); self.opt_count.setValue(8)
        grid = QFormLayout()
        grid.addRow("行数", self.opt_rows); grid.addRow("列数", self.opt_cols)
        grid.addRow("张数", self.opt_count)
        left.addLayout(grid)

        # 排序
        left.addWidget(QLabel("序列排序"))
        self.order_group = QButtonGroup(self)
        r1 = QRadioButton("行优先（1→右→换行）"); r2 = QRadioButton("列优先（1→下→换列）")
        r1.setChecked(True); self.order_group.addButton(r1, 0); self.order_group.addButton(r2, 1)
        left.addWidget(r1); left.addWidget(r2)

        # 操作
        b_gen = QPushButton("生成预览")
        b_gen.clicked.connect(self.generate)
        b_save = QPushButton("保存 PNG+JPG")
        b_save.clicked.connect(self.save)
        b_preset = QPushButton("自定义预设…")
        b_preset.clicked.connect(self.open_preset)
        bl2 = QHBoxLayout(); bl2.addWidget(b_gen); bl2.addWidget(b_save)
        left.addLayout(bl2)
        left.addWidget(b_preset)

        self.progress = QProgressBar(); self.progress.setTextVisible(False)
        left.addWidget(self.progress)
        self.status = QLabel("选择照片 → 设置 → 生成预览")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)

        # ---------- 右：预览 ----------
        right = QVBoxLayout()
        root.addLayout(right, 2)
        self.preview = QLabel("把照片拖到这里，或点「选择照片」")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border: 2px dashed #bbb; background:#fafafa;")
        self.preview.setMinimumSize(420, 520)
        right.addWidget(self.preview, 1)

        self.refresh_sizes()
        self.refresh_colors()
        self.refresh_papers()
        self.on_mode_changed()

        # 拖拽
        self.setAcceptDrops(True)

    # ---------- 数据刷新 ----------
    def refresh_sizes(self):
        self.size_combo.clear()
        for s in core.search_sizes(self.search.text()):
            self.size_combo.addItem("%s (%dx%dmm)" % (s["name"], s["w_mm"], s["h_mm"]), s)

    def refresh_colors(self):
        self.color_combo.clear()
        for c in core.load_colors():
            self.color_combo.addItem(c["name"], c)

    def refresh_papers(self):
        self.opt_paper.clear()
        for p in core.load_papers():
            self.opt_paper.addItem(p["name"], p)

    def on_mode_changed(self):
        mode = self.mode_combo.currentIndex()
        self.opt_paper.setVisible(mode in (1, 3))
        self.opt_rows.setVisible(mode == 2)
        self.opt_cols.setVisible(mode == 2)
        self.opt_count.setVisible(mode == 3)

    # ---------- 交互 ----------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                self.set_photo(p)
                break

    def choose_photo(self):
        p = QFileDialog.getOpenFileName(self, "选择照片", "", "图片 (*.jpg *.jpeg *.png *.bmp)")[0]
        if p:
            self.set_photo(p)

    def set_photo(self, p):
        self.input_path = p
        self.path_edit.setText(p)
        self.status.setText("已选择照片，设置好后点「生成预览」")

    def open_preset(self):
        d = PresetEditorDialog(self)
        d.exec()
        self.refresh_sizes(); self.refresh_colors(); self.refresh_papers()

    def current_size(self):
        return self.size_combo.currentData()

    def current_color(self):
        return self.color_combo.currentData()

    def generate(self):
        if not self.input_path:
            QMessageBox.warning(self, "提示", "请先选择一张照片")
            return
        size = self.current_size()
        color = self.current_color()
        if size is None or color is None:
            return
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            layout_mode = "single"
            layout_params = {}
        elif mode == 1:
            layout_mode = "paper"
            layout_params = {"paper": self.opt_paper.currentData()}
        elif mode == 2:
            layout_mode = "grid"
            layout_params = {"rows": self.opt_rows.value(), "cols": self.opt_cols.value()}
        else:
            layout_mode = "count"
            layout_params = {"paper": self.opt_paper.currentData(), "count": self.opt_count.value()}
        order = "col" if self.order_group.checkedId() == 1 else "row"

        self.progress.setRange(0, 0)
        self.status.setText("处理中（抠图首次会下载模型）…")
        self.worker = Worker(self.input_path, size, color, layout_mode, layout_params, order)
        self.worker.progress.connect(self.status.setText)
        self.worker.done.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(lambda: self.progress.setRange(0, 1))
        self.worker.start()

    def on_done(self, image, info, is_single, single_photo):
        self.current_sheet = None if is_single else image
        self.current_single = single_photo
        self.preview.setPixmap(pil_to_pixmap(image).scaled(
            self.preview.width(), self.preview.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.status.setText(info + " — 点「保存 PNG+JPG」导出")

    def on_error(self, msg):
        QMessageBox.critical(self, "出错", msg)

    def save(self):
        if self.current_sheet is None and self.current_single is None:
            QMessageBox.warning(self, "提示", "请先生成预览")
            return
        out_dir = os.path.join(os.path.expanduser("~/.idphoto_studio"), "output")
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(self.input_path))[0]
        id_short = self.current_size()["name"]
        saved = []

        # 排版纸
        if self.current_sheet is not None:
            paper_short = (self.opt_paper.currentText().split(" ")[0]
                           if self.mode_combo.currentIndex() != 2 else "网格")
            png = os.path.join(out_dir, "%s_%s_%s.png" % (base, paper_short, id_short))
            self.current_sheet.save(png, "PNG")
            self.current_sheet.save(png[:-4] + ".jpg", "JPEG", quality=95)
            saved.append(png)

        # 单张证件照（排版模式也顺带导出单张，方便上传/冲洗）
        if self.current_single is not None:
            png = os.path.join(out_dir, "%s_单张_%s.png" % (base, id_short))
            self.current_single.save(png, "PNG")
            self.current_single.save(png[:-4] + ".jpg", "JPEG", quality=95)
            saved.append(png)

        QMessageBox.information(self, "已保存", "已导出：\n" + "\n".join(saved))
        self.status.setText("已保存到：" + out_dir)


def run():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
