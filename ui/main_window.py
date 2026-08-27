# -*- coding: utf-8 -*-
"""
ui/main_window.py — 证件照工作室 macOS / Windows 工业级原生桌面界面
===================================================================
- 苹果 macOS 原生视觉设计规范（SF Pro / 苹方，扁平优雅、原生卡片、通透灰白调）
- 照相馆国标证件照构图 (Head-Centric Standard)：头部饱满、锁骨与双肩自然对称展开，彻底根除右侧缺角
- 照相馆经典混排 (5寸上2二寸+下4一寸 / 6寸上4二寸+下4一寸)：上下分段、整齐严密对齐
- 自由多尺寸自定义混排装箱引擎（智能分栏与自适应边距）
- 界面布局全面优化：禁绝横向滚动条、垂直表单无截断、色块文字完整
- 新增「✂️ 手动选区/裁剪人像」交互式工具：支持合影多人物框选与复杂背景精确定位
- 预览区浅灰精致相框，白底照片绝不融为一体
- 底部操作栏固定无闪烁，支持用户自主选择导出格式 (PNG / JPG / 两种都要)
"""

import os
import sys
from PySide6.QtCore import Qt, Signal, QThread, QSettings, QTimer, QSize, QRect, QPoint
from PySide6.QtGui import (
    QImage, QPixmap, QColor, QPalette, QDragEnterEvent, QDropEvent,
    QIcon, QPainter, QPen, QBrush, QMouseEvent
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QMessageBox,
    QProgressBar, QScrollArea, QFrame, QSplitter, QCheckBox,
    QLineEdit, QDialog, QFormLayout, QSpinBox, QColorDialog, QButtonGroup,
    QGridLayout
)

from core import idphoto_core as core

PROJECT_ROOT = core.PROJECT_ROOT

# macOS 原生风格 QSS
QSS = """
QMainWindow, QWidget {
    background-color: #f6f8fa;
    color: #1f2328;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
}
QLabel#SectionTitle {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#AppLogo {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
}
QLabel#SubTitle {
    font-size: 11px;
    color: #656d76;
}
QLabel#Badge {
    background-color: #eff6ff;
    color: #0969da;
    border: 1px solid #d0e7ff;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#WarnBadge {
    background-color: #ffebe9;
    color: #cf222e;
    border: 1px solid #ffcecb;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 11px;
    font-weight: 600;
}
QComboBox, QLineEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 5px 8px;
    color: #1f2328;
    selection-background-color: #0969da;
    min-height: 22px;
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
    border-color: #8c959f;
}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {
    border-color: #0969da;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1f2328;
    border: 1px solid #d0d7de;
    selection-background-color: #f3f4f6;
    selection-color: #0969da;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 5px 12px;
    color: #24292f;
    font-weight: 500;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #f6f8fa;
    border-color: #8c959f;
}
QPushButton#PrimaryBtn {
    background-color: #0969da;
    border: 1px solid #0860ca;
    color: #ffffff;
    font-weight: 600;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0860ca;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #80b5ea;
    border-color: #80b5ea;
}
QPushButton#SecondaryBtn {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    color: #57606a;
    font-weight: 500;
    padding: 4px 8px;
    font-size: 11px;
}
QPushButton#ColorChip {
    border: 1.5px solid #d0d7de;
    border-radius: 6px;
    padding: 4px 6px;
    font-weight: 600;
    font-size: 11px;
    min-height: 20px;
}
QPushButton#ColorChip:checked {
    border: 2px solid #0969da;
    background-color: #ddf4ff;
}
QFrame#DropBox {
    background-color: #f6f8fa;
    border: 1.5px dashed #d0d7de;
    border-radius: 6px;
}
QFrame#DropBox:hover, QFrame#DropBox[dragOver="true"] {
    background-color: #ddf4ff;
    border-color: #0969da;
}
QProgressBar {
    background-color: #eaeef2;
    border: none;
    border-radius: 2px;
    height: 4px;
}
QProgressBar::chunk {
    background-color: #0969da;
    border-radius: 2px;
}
QCheckBox {
    font-size: 11px;
    color: #24292f;
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


# ============================================================ 交互式人像手动选区/裁剪弹窗
class CropWidget(QWidget):
    def __init__(self, pil_image, aspect_ratio=25.0/35.0, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.aspect_ratio = aspect_ratio
        self.qimage = pil_to_qimage(pil_image)
        self.pixmap = QPixmap.fromImage(self.qimage)

        crop_h = 0.85
        crop_w = crop_h * self.aspect_ratio * (pil_image.size[1] / pil_image.size[0])
        if crop_w > 0.95:
            crop_w = 0.95
            crop_h = crop_w / self.aspect_ratio * (pil_image.size[0] / pil_image.size[1])

        self.rel_x = (1.0 - crop_w) / 2.0
        self.rel_y = 0.05
        self.rel_w = crop_w
        self.rel_h = crop_h

        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()

    def get_cropped_pil_image(self):
        orig_w, orig_h = self.pil_image.size
        x1 = max(0, int(round(self.rel_x * orig_w)))
        y1 = max(0, int(round(self.rel_y * orig_h)))
        x2 = min(orig_w, int(round((self.rel_x + self.rel_w) * orig_w)))
        y2 = min(orig_h, int(round((self.rel_y + self.rel_h) * orig_h)))
        return self.pil_image.crop((x1, y1, x2, y2))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor("#0f172a"))

        vw, vh = self.width(), self.height()
        scaled_pix = self.pixmap.scaled(vw, vh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_rect = QRect((vw - scaled_pix.width()) // 2, (vh - scaled_pix.height()) // 2,
                              scaled_pix.width(), scaled_pix.height())
        painter.drawPixmap(self.img_rect.topLeft(), scaled_pix)

        cx = self.img_rect.x() + int(self.rel_x * self.img_rect.width())
        cy = self.img_rect.y() + int(self.rel_y * self.img_rect.height())
        cw = int(self.rel_w * self.img_rect.width())
        ch = int(self.rel_h * self.img_rect.height())
        self.crop_rect = QRect(cx, cy, cw, ch)

        mask_color = QColor(0, 0, 0, 160)
        painter.fillRect(QRect(0, 0, vw, cy), mask_color)
        painter.fillRect(QRect(0, cy + ch, vw, vh - (cy + ch)), mask_color)
        painter.fillRect(QRect(0, cy, cx, ch), mask_color)
        painter.fillRect(QRect(cx + cw, cy, vw - (cx + cw), ch), mask_color)

        pen = QPen(QColor("#0969da"), 2)
        painter.setPen(pen)
        painter.drawRect(self.crop_rect)

        pen_grid = QPen(QColor(255, 255, 255, 100), 1, Qt.DashLine)
        painter.setPen(pen_grid)
        painter.drawLine(cx + cw // 3, cy, cx + cw // 3, cy + ch)
        painter.drawLine(cx + 2 * cw // 3, cy, cx + 2 * cw // 3, cy + ch)
        painter.drawLine(cx, cy + ch // 3, cx + cw, cy + ch // 3)
        painter.drawLine(cx, cy + 2 * ch // 3, cx + cw, cy + 2 * ch // 3)

        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0969da"), 2))
        handle_size = 8
        painter.drawRect(cx - handle_size//2, cy - handle_size//2, handle_size, handle_size)
        painter.drawRect(cx + cw - handle_size//2, cy - handle_size//2, handle_size, handle_size)
        painter.drawRect(cx - handle_size//2, cy + ch - handle_size//2, handle_size, handle_size)
        painter.drawRect(cx + cw - handle_size//2, cy + ch - handle_size//2, handle_size, handle_size)

    def mousePressEvent(self, event: QMouseEvent):
        if hasattr(self, "crop_rect"):
            pos = event.pos()
            br_handle = QRect(self.crop_rect.right() - 15, self.crop_rect.bottom() - 15, 30, 30)
            if br_handle.contains(pos):
                self.resizing = True
                self.drag_start = pos
                return

            if self.crop_rect.contains(pos):
                self.dragging = True
                self.drag_start = pos

    def mouseMoveEvent(self, event: QMouseEvent):
        if not hasattr(self, "img_rect") or self.img_rect.width() == 0:
            return

        if self.dragging:
            delta = event.pos() - self.drag_start
            self.drag_start = event.pos()

            dx_rel = delta.x() / self.img_rect.width()
            dy_rel = delta.y() / self.img_rect.height()

            self.rel_x = max(0.0, min(1.0 - self.rel_w, self.rel_x + dx_rel))
            self.rel_y = max(0.0, min(1.0 - self.rel_h, self.rel_y + dy_rel))
            self.update()

        elif self.resizing:
            delta = event.pos() - self.drag_start
            self.drag_start = event.pos()

            dw_rel = delta.x() / self.img_rect.width()
            new_w = max(0.15, min(1.0 - self.rel_x, self.rel_w + dw_rel))
            new_h = new_w / self.aspect_ratio * (self.pil_image.size[0] / self.pil_image.size[1])
            if self.rel_y + new_h <= 1.0:
                self.rel_w = new_w
                self.rel_h = new_h
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False
        self.resizing = False


class CropDialog(QDialog):
    def __init__(self, pil_image, aspect_ratio=25.0/35.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✂️ 手动选区与精准人像裁剪")
        self.resize(780, 600)
        self.cropped_image = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tip_box = QFrame(); tip_box.setObjectName("Card")
        tl = QHBoxLayout(tip_box); tl.setContentsMargins(10, 8, 10, 8)
        lbl_tip = QLabel("💡 提示：按住框内可自由拖拽位置；按住右下角可等比缩放。适用于合影多人物框选与复杂背景精确定位。")
        lbl_tip.setObjectName("SubTitle")
        tl.addWidget(lbl_tip)
        layout.addWidget(tip_box)

        self.crop_widget = CropWidget(pil_image, aspect_ratio, self)
        layout.addWidget(self.crop_widget, 1)

        btn_row = QHBoxLayout()
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        b_apply = QPushButton("✓ 应用此选区并抠图换底")
        b_apply.setObjectName("PrimaryBtn")
        b_apply.clicked.connect(self.apply_crop)

        btn_row.addStretch()
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_apply)
        layout.addLayout(btn_row)

    def apply_crop(self):
        self.cropped_image = self.crop_widget.get_cropped_pil_image()
        self.accept()


# ============================================================ 后台 Worker
class MattingWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, image_input):
        super().__init__()
        self.image_input = image_input

    def run(self):
        try:
            from PIL import Image
            if isinstance(self.image_input, str):
                img = Image.open(self.image_input)
            else:
                img = self.image_input
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

    def __init__(self, image_input, size_dict, color_dict, mode_idx, extra_params,
                 cut_lines, add_text, cached_rgba=None):
        super().__init__()
        self.image_input = image_input
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
            if isinstance(self.image_input, str):
                img = Image.open(self.image_input)
            else:
                img = self.image_input

            bg_rgb = self.color_dict["rgb"]
            need_matting = bg_rgb is not None

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

            # 2: 照相馆经典规整混排
            if self.mode_idx == 2:
                mix_type = self.extra_params.get("mix_type", "5in_2_4")
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

            # 3: 自由多尺寸自定义混排
            if self.mode_idx == 3:
                counts = self.extra_params.get("counts", {})
                paper = self.extra_params.get("paper", core.load_papers()[0]) # 默认5寸
                images_dict = {}
                for k, w_mm, h_mm in [("2in", 35, 49), ("1in", 25, 35), ("s_1in", 22, 32), ("l_2in", 35, 53)]:
                    if self.cached_rgba is not None:
                        images_dict[k] = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(w_mm), core.mm_to_px(h_mm), bg_rgb)
                    else:
                        matting = core.Matting() if (bg_rgb is not None and core.Matting().available()) else None
                        images_dict[k] = core.prepare_id_photo(img, core.mm_to_px(w_mm), core.mm_to_px(h_mm), bg_rgb, matting)

                sheet, info, fits = core.compose_custom_mixed_sheet(images_dict, counts, paper, cut_lines=self.cut_lines)
                self.done.emit(sheet, info, False, id_photo)
                return

            # 1: 照相馆标准相纸排版, 4: 自定义网格
            if self.mode_idx == 1:
                p = self.extra_params["paper"]
                lay = core.compute_layout(p["w_mm"], p["h_mm"], self.size_dict["w_mm"], self.size_dict["h_mm"])
            else:
                p = self.extra_params.get("paper", core.load_papers()[0])
                lay = core.compute_layout_grid(self.size_dict["w_mm"], self.size_dict["h_mm"],
                                               self.extra_params["rows"], self.extra_params["cols"],
                                               paper_w_mm=p["w_mm"], paper_h_mm=p["h_mm"])

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


# ============================================================ 批量处理
class BatchWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, file_paths, size_dict, color_dict, export_single, export_sheet, paper_dict, export_fmt, out_dir):
        super().__init__()
        self.file_paths = file_paths
        self.size_dict = size_dict
        self.color_dict = color_dict
        self.export_single = export_single
        self.export_sheet = export_sheet
        self.paper_dict = paper_dict
        self.export_fmt = export_fmt
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

                    if self.export_single:
                        p_png = os.path.join(self.out_dir, f"{base}_{self.size_dict['name']}_单张.png")
                        p_jpg = os.path.join(self.out_dir, f"{base}_{self.size_dict['name']}_单张.jpg")
                        if self.export_fmt in ("both", "png"):
                            id_photo.save(p_png, "PNG")
                            saved.append(p_png)
                        if self.export_fmt in ("both", "jpg"):
                            id_photo.save(p_jpg, "JPEG", quality=95)
                            saved.append(p_jpg)

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
                        if self.export_fmt in ("both", "png"):
                            sheet.save(p_sheet_png, "PNG")
                            saved.append(p_sheet_png)
                        if self.export_fmt in ("both", "jpg"):
                            sheet.save(p_sheet_jpg, "JPEG", quality=95)
                            saved.append(p_sheet_jpg)

                except Exception:
                    continue

            self.finished.emit(len(saved), saved)
        except Exception as e:
            self.error.emit(str(e))


class BatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 批量证件照冲印处理")
        self.resize(560, 500)
        self.file_paths = []
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

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
        ol.addRow("冲印相纸:", self.batch_paper)

        self.batch_fmt = QComboBox()
        self.batch_fmt.addItem("PNG + JPG (两种都要)", "both")
        self.batch_fmt.addItem("仅导出 PNG (高清无损)", "png")
        self.batch_fmt.addItem("仅导出 JPG (冲印格式)", "jpg")
        ol.addRow("导出格式:", self.batch_fmt)

        self.chk_single = QCheckBox("导出单张证件照"); self.chk_single.setChecked(True)
        self.chk_sheet = QCheckBox("导出冲印排版图"); self.chk_sheet.setChecked(True)
        ol.addRow("导出内容:", self.chk_single)
        ol.addRow("", self.chk_sheet)
        layout.addWidget(opt_box)

        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("SubTitle")
        layout.addWidget(self.lbl_status)

        action_row = QHBoxLayout()
        self.btn_run = QPushButton("开始批量处理并保存…")
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.clicked.connect(self.start_batch)
        b_close = QPushButton("关闭")
        b_close.clicked.connect(self.reject)
        action_row.addStretch()
        action_row.addWidget(b_close)
        action_row.addWidget(self.btn_run)
        layout.addLayout(action_row)

    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "多选人像照片", "", "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if paths:
            self.file_paths = paths
            self.lbl_file_count.setText(f"已选择 {len(paths)} 张照片文件")

    def select_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择包含人像照片的文件夹")
        if d:
            exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            found = [os.path.join(d, f) for f in os.listdir(d) if os.path.splitext(f)[1].lower() in exts]
            if found:
                self.file_paths = found
                self.lbl_file_count.setText(f"文件夹内共找到 {len(found)} 张照片")
            else:
                QMessageBox.information(self, "提示", "所选文件夹内未找到支持的图片文件")

    def start_batch(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先选择需要批量处理的照片")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "选择批量导出保存的文件夹")
        if not out_dir:
            return

        size_dict = self.batch_size.currentData()
        color_dict = self.batch_color.currentData()
        paper_dict = self.batch_paper.currentData()
        export_fmt = self.batch_fmt.currentData()

        self.btn_run.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setRange(0, len(self.file_paths))
        self.pbar.setValue(0)

        self.worker = BatchWorker(
            self.file_paths, size_dict, color_dict,
            self.chk_single.isChecked(), self.chk_sheet.isChecked(),
            paper_dict, export_fmt, out_dir
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, cur, total, fname):
        self.pbar.setValue(cur)
        self.lbl_status.setText(f"正在处理 ({cur}/{total}): {fname}")

    def on_finished(self, count, saved):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"✓ 批量处理完成！共导出 {count} 份文件。")
        QMessageBox.information(self, "完成", f"批量处理完成！\n已成功生成 {count} 份证件照/排版文件。")

    def on_error(self, err):
        self.btn_run.setEnabled(True)
        self.lbl_status.setText("处理失败")
        QMessageBox.critical(self, "错误", f"批量处理发生错误：{err}")


# ============================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照工作室 Studio")
        self.setMinimumSize(1000, 720)
        self.setAcceptDrops(True)

        self.settings = QSettings("IDPhotoStudio", "Settings")
        self.input_path = None
        self.raw_pil_image = None
        self.active_pil_image = None
        self.cached_rgba = None
        self.current_preview_image = None
        self.current_single_id = None
        self.is_single_preview = True

        self.mworker = None
        self.rworker = None

        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._do_render)

        self._build_ui()
        self._load_state()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # ----------------- 左侧控制面板 (原生 macOS 风格，无横向滚动条) -----------------
        left_container = QWidget()
        left_container.setMinimumWidth(390)
        left_container.setMaximumWidth(460)
        left_box = QVBoxLayout(left_container)
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(8)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 8, 4)
        left_layout.setSpacing(10)

        # App 标题区
        head_card = QFrame(); head_card.setObjectName("Card")
        hl = QHBoxLayout(head_card); hl.setContentsMargins(12, 10, 12, 10)
        t_box = QVBoxLayout()
        lbl_logo = QLabel("证件照工作室"); lbl_logo.setObjectName("AppLogo")
        lbl_sub = QLabel("智能发丝抠图 · 照相馆标准排版"); lbl_sub.setObjectName("SubTitle")
        t_box.addWidget(lbl_logo); t_box.addWidget(lbl_sub)
        hl.addLayout(t_box)
        hl.addStretch()
        btn_batch_top = QPushButton("📂 批量处理"); btn_batch_top.setObjectName("SecondaryBtn")
        btn_batch_top.setFixedWidth(80)
        btn_batch_top.clicked.connect(self.open_batch_dialog)
        hl.addWidget(btn_batch_top)
        left_layout.addWidget(head_card)

        # 1. 照片导入区
        card_import = QFrame(); card_import.setObjectName("Card")
        cl = QVBoxLayout(card_import); cl.setContentsMargins(12, 10, 12, 10); cl.setSpacing(8)
        cl.addWidget(QLabel("1. 照片导入", objectName="SectionTitle"))

        self.dropbox = QFrame(); self.dropbox.setObjectName("DropBox")
        dl = QHBoxLayout(self.dropbox); dl.setContentsMargins(8, 8, 8, 8); dl.setSpacing(10)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(48, 48)
        self.lbl_thumb.setStyleSheet("background-color: #eaeef2; border-radius: 4px;")
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setText("📷")
        dl.addWidget(self.lbl_thumb)

        info_v = QVBoxLayout()
        self.lbl_filename = QLabel("拖入照片 或 点击选择")
        self.lbl_filename.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.lbl_filesize = QLabel("支持 JPG / PNG / 2K高清人像")
        self.lbl_filesize.setObjectName("SubTitle")
        info_v.addWidget(self.lbl_filename); info_v.addWidget(self.lbl_filesize)
        dl.addLayout(info_v)
        dl.addStretch()

        b_sel = QPushButton("选择照片"); b_sel.clicked.connect(self.select_photo)
        dl.addWidget(b_sel)
        cl.addWidget(self.dropbox)

        tool_row = QHBoxLayout()
        self.btn_crop = QPushButton("✂️ 手动选区/裁剪人像…")
        self.btn_crop.setObjectName("SecondaryBtn")
        self.btn_crop.clicked.connect(self.open_crop_dialog)
        self.btn_crop.setEnabled(False)

        self.btn_reset_crop = QPushButton("↺ 恢复完整原图")
        self.btn_reset_crop.setObjectName("SecondaryBtn")
        self.btn_reset_crop.clicked.connect(self.reset_to_raw_image)
        self.btn_reset_crop.setEnabled(False)

        tool_row.addWidget(self.btn_crop)
        tool_row.addWidget(self.btn_reset_crop)
        cl.addLayout(tool_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        cl.addWidget(self.progress_bar)
        left_layout.addWidget(card_import)

        # 2. 规格与底色
        card_spec = QFrame(); card_spec.setObjectName("Card")
        sl = QVBoxLayout(card_spec); sl.setContentsMargins(12, 10, 12, 10); sl.setSpacing(8)
        sl.addWidget(QLabel("2. 规格与底色", objectName="SectionTitle"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索规格：一寸 / 二寸 / 护照 / 签证…")
        self.search_edit.textChanged.connect(self.on_search_changed)
        sl.addWidget(self.search_edit)

        self.size_combo = QComboBox()
        self._populate_sizes()
        self.size_combo.currentIndexChanged.connect(self.on_size_changed)
        sl.addWidget(self.size_combo)

        self.lbl_spec_badge = QLabel("规格: 25 × 35 mm · 295 × 413 px @ 300DPI")
        self.lbl_spec_badge.setObjectName("Badge")
        sl.addWidget(self.lbl_spec_badge)

        sl.addWidget(QLabel("背景底色:"))
        color_grid = QGridLayout(); color_grid.setSpacing(6)
        self.color_btn_group = QButtonGroup(self)
        self.color_btn_group.setExclusive(True)

        self.colors_data = core.load_colors()
        for idx, c in enumerate(self.colors_data):
            btn = QPushButton(c["name"].split(" ")[0])
            btn.setObjectName("ColorChip")
            btn.setCheckable(True)
            if c["hex"] and c["hex"] != "#ffffff" and c["hex"] != "#e2e8f0":
                btn.setStyleSheet(f"background-color: {c['hex']}; color: #ffffff;")
            elif c["hex"] == "#ffffff":
                btn.setStyleSheet("background-color: #ffffff; color: #1f2328; border: 1.5px solid #d0d7de;")
            self.color_btn_group.addButton(btn, idx)
            color_grid.addWidget(btn, idx // 4, idx % 4)
            if idx == 0:
                btn.setChecked(True)

        btn_custom_c = QPushButton("🎨 自定义")
        btn_custom_c.setObjectName("SecondaryBtn")
        btn_custom_c.clicked.connect(self.pick_custom_color)
        color_grid.addWidget(btn_custom_c, len(self.colors_data) // 4, len(self.colors_data) % 4)

        self.color_btn_group.idClicked.connect(self.on_color_changed)
        sl.addLayout(color_grid)
        left_layout.addWidget(card_spec)

        # 3. 排版冲印
        card_print = QFrame(); card_print.setObjectName("Card")
        pl = QVBoxLayout(card_print); pl.setContentsMargins(12, 10, 12, 10); pl.setSpacing(8)
        pl.addWidget(QLabel("3. 排版冲印", objectName="SectionTitle"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🖼 仅单张证件照 (默认)")
        self.mode_combo.addItem("📄 照相馆标准相纸排版")
        self.mode_combo.addItem("🔀 照相馆标准规整混排")
        self.mode_combo.addItem("🧩 自由多尺寸自定义混排")
        self.mode_combo.addItem("📐 自由自定义网格排版")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        pl.addWidget(self.mode_combo)

        # 相纸选择容器
        self.paper_container = QWidget()
        paper_l = QVBoxLayout(self.paper_container); paper_l.setContentsMargins(0, 0, 0, 0); paper_l.setSpacing(4)
        paper_l.addWidget(QLabel("选择冲印相纸 (5寸/6寸置顶):"))
        self.paper_combo = QComboBox()
        for p in core.load_papers():
            self.paper_combo.addItem(p["name"], p)
        self.paper_combo.currentIndexChanged.connect(self.schedule_render)
        paper_l.addWidget(self.paper_combo)
        pl.addWidget(self.paper_container)
        self.paper_container.setVisible(False)

        # 经典混排类型容器 (模式 2)
        self.mix_container = QWidget()
        mix_l = QVBoxLayout(self.mix_container); mix_l.setContentsMargins(0, 0, 0, 0); mix_l.setSpacing(4)
        mix_l.addWidget(QLabel("照相馆标准混排方案:"))
        self.mix_combo = QComboBox()
        self.mix_combo.addItem("5寸标准混排 · 上2张二寸 + 下4张一寸 (整齐对齐)", "5in_2_4")
        self.mix_combo.addItem("6寸标准混排 · 上4张二寸 + 下4张一寸 (经典多规格)", "6in_4_4")
        self.mix_combo.addItem("6寸实用混排 · 上2张二寸 + 下8张一寸 (多一寸版)", "6in_2_8")
        self.mix_combo.currentIndexChanged.connect(self.schedule_render)
        mix_l.addWidget(self.mix_combo)
        pl.addWidget(self.mix_container)
        self.mix_container.setVisible(False)

        # 自由自定义混排容器 (模式 3)
        self.custom_mix_container = QWidget()
        cml = QVBoxLayout(self.custom_mix_container); cml.setContentsMargins(0, 0, 0, 0); cml.setSpacing(6)
        cml.addWidget(QLabel("设定各尺寸冲印张数:"))

        form_counts = QFormLayout()
        form_counts.setContentsMargins(0, 0, 0, 0)
        form_counts.setSpacing(6)

        self.spin_2in = QSpinBox(); self.spin_2in.setRange(0, 12); self.spin_2in.setValue(2)
        self.spin_2in.setFixedWidth(80)
        self.spin_2in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("二寸 (35×49mm):", self.spin_2in)

        self.spin_1in = QSpinBox(); self.spin_1in.setRange(0, 24); self.spin_1in.setValue(4)
        self.spin_1in.setFixedWidth(80)
        self.spin_1in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("一寸 (25×35mm):", self.spin_1in)

        self.spin_s1in = QSpinBox(); self.spin_s1in.setRange(0, 24); self.spin_s1in.setValue(0)
        self.spin_s1in.setFixedWidth(80)
        self.spin_s1in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("小一寸 (22×32mm):", self.spin_s1in)

        self.spin_l2in = QSpinBox(); self.spin_l2in.setRange(0, 12); self.spin_l2in.setValue(0)
        self.spin_l2in.setFixedWidth(80)
        self.spin_l2in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("大二寸 (35×53mm):", self.spin_l2in)

        cml.addLayout(form_counts)
        self.lbl_mix_status = QLabel("✓ 正在计算相纸容量…")
        self.lbl_mix_status.setObjectName("Badge")
        cml.addWidget(self.lbl_mix_status)
        pl.addWidget(self.custom_mix_container)
        self.custom_mix_container.setVisible(False)

        # 自定义网格微调容器 (模式 4)
        self.grid_container = QWidget()
        gl = QVBoxLayout(self.grid_container); gl.setContentsMargins(0, 0, 0, 0); gl.setSpacing(4)
        grow = QHBoxLayout()
        grow.addWidget(QLabel("列数:"))
        self.spin_cols = QSpinBox(); self.spin_cols.setRange(1, 10); self.spin_cols.setValue(4)
        self.spin_cols.valueChanged.connect(self.schedule_render)
        grow.addWidget(self.spin_cols)
        grow.addWidget(QLabel("行数:"))
        self.spin_rows = QSpinBox(); self.spin_rows.setRange(1, 10); self.spin_rows.setValue(2)
        self.spin_rows.valueChanged.connect(self.schedule_render)
        grow.addWidget(self.spin_rows)
        gl.addLayout(grow)
        self.lbl_grid_warn = QLabel("")
        self.lbl_grid_warn.setObjectName("WarnBadge")
        self.lbl_grid_warn.setVisible(False)
        gl.addWidget(self.lbl_grid_warn)
        pl.addWidget(self.grid_container)
        self.grid_container.setVisible(False)

        # 辅助选项框
        self.opt_aux_box = QWidget()
        al = QHBoxLayout(self.opt_aux_box); al.setContentsMargins(0, 4, 0, 0); al.setSpacing(10)
        self.chk_cut_lines = QCheckBox("打印浅灰裁切线")
        self.chk_cut_lines.setChecked(True)
        self.chk_cut_lines.toggled.connect(self.schedule_render)
        self.chk_add_text = QCheckBox("标注尺寸规格")
        self.chk_add_text.setChecked(True)
        self.chk_add_text.toggled.connect(self.schedule_render)
        al.addWidget(self.chk_cut_lines); al.addWidget(self.chk_add_text)
        pl.addWidget(self.opt_aux_box)
        self.opt_aux_box.setVisible(False)

        left_layout.addWidget(card_print)
        left_layout.addStretch()
        left_scroll.setWidget(left_widget)
        left_box.addWidget(left_scroll, 1)

        # 4. 固定底部操作与导出卡片
        bottom_card = QFrame(); bottom_card.setObjectName("Card")
        bl = QVBoxLayout(bottom_card); bl.setContentsMargins(12, 10, 12, 10); bl.setSpacing(8)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("导出格式:"))
        self.combo_export_fmt = QComboBox()
        self.combo_export_fmt.addItem("PNG + JPG (两种都要 · 推荐)", "both")
        self.combo_export_fmt.addItem("仅导出 PNG (高清无损)", "png")
        self.combo_export_fmt.addItem("仅导出 JPG (冲印格式)", "jpg")
        fmt_row.addWidget(self.combo_export_fmt, 1)
        bl.addLayout(fmt_row)

        self.btn_export = QPushButton("💾 导出高清照片/排版")
        self.btn_export.setObjectName("PrimaryBtn")
        self.btn_export.clicked.connect(self.export_result)
        bl.addWidget(self.btn_export)

        b_row = QHBoxLayout(); b_row.setSpacing(6)
        b_preset = QPushButton("⚙️ 预设管理…"); b_preset.setObjectName("SecondaryBtn")
        b_preset.clicked.connect(self.open_preset_dialog)
        b_batch = QPushButton("📂 批量处理…"); b_batch.setObjectName("SecondaryBtn")
        b_batch.clicked.connect(self.open_batch_dialog)
        b_refresh = QPushButton("🔄 刷新"); b_refresh.setObjectName("SecondaryBtn")
        b_refresh.clicked.connect(self.schedule_render)
        b_row.addWidget(b_preset); b_row.addWidget(b_batch); b_row.addWidget(b_refresh)
        bl.addLayout(b_row)

        self.status = QLabel("✓ 就绪，请导入照片")
        self.status.setObjectName("SubTitle")
        bl.addWidget(self.status)

        left_box.addWidget(bottom_card, 0)
        splitter.addWidget(left_container)

        # ----------------- 右侧大预览区 -----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)

        header_r = QHBoxLayout()
        self.lbl_preview_info = QLabel("工作区预览 · 300 DPI")
        self.lbl_preview_info.setStyleSheet("font-weight: 600; color: #475569;")
        header_r.addWidget(self.lbl_preview_info)
        header_r.addStretch()
        right_layout.addLayout(header_r)

        self.preview_canvas = QLabel()
        self.preview_canvas.setStyleSheet(
            "background-color: #eaeef2; border: 1px solid #d0d7de; border-radius: 8px;"
        )
        self.preview_canvas.setAlignment(Qt.AlignCenter)
        self.preview_canvas.setMinimumSize(400, 400)
        right_layout.addWidget(self.preview_canvas, 1)

        self.lbl_footer_info = QLabel("输出分辨率: -- · 300 DPI")
        self.lbl_footer_info.setObjectName("SubTitle")
        self.lbl_footer_info.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.lbl_footer_info)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

    # ----------------- 交互逻辑 -----------------
    def _populate_sizes(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for s in core.load_sizes():
            self.size_combo.addItem(f"{s['name']}", s)
        self.size_combo.blockSignals(False)

    def on_search_changed(self, text):
        matches = core.search_sizes(text)
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for s in matches:
            self.size_combo.addItem(f"{s['name']}", s)
        self.size_combo.blockSignals(False)
        self.on_size_changed()

    def on_size_changed(self):
        s = self.size_combo.currentData()
        if s:
            self.lbl_spec_badge.setText(f"规格: {s['w_mm']} × {s['h_mm']} mm · {s['w_px']} × {s['h_px']} px @ 300DPI")
        self.schedule_render()

    def on_color_changed(self, btn_id):
        self.schedule_render()

    def pick_custom_color(self):
        col = QColorDialog.getColor(QColor(67, 142, 219), self, "选择证件照自定义底色")
        if col.isValid():
            rgb = (col.red(), col.green(), col.blue())
            hex_c = col.name()
            custom_dict = {"key": "custom", "name": f"自定义 ({hex_c})", "rgb": rgb, "hex": hex_c}
            self.colors_data.append(custom_dict)
            self.schedule_render()

    def on_mode_changed(self, idx):
        self.paper_container.setVisible(idx in (1, 3, 4))
        self.mix_container.setVisible(idx == 2)
        self.custom_mix_container.setVisible(idx == 3)
        self.grid_container.setVisible(idx == 4)
        self.opt_aux_box.setVisible(idx != 0)
        self.schedule_render()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.dropbox.setProperty("dragOver", True)
            self.dropbox.style().polish(self.dropbox)

    def dragLeaveEvent(self, event):
        self.dropbox.setProperty("dragOver", False)
        self.dropbox.style().polish(self.dropbox)

    def dropEvent(self, event: QDropEvent):
        self.dropbox.setProperty("dragOver", False)
        self.dropbox.style().polish(self.dropbox)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                self.set_photo(path)

    def select_photo(self):
        last_dir = self.settings.value("last_dir", "")
        p, _ = QFileDialog.getOpenFileName(
            self, "选择人像照片", last_dir, "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if p:
            self.settings.setValue("last_dir", os.path.dirname(p))
            self.set_photo(p)

    def set_photo(self, p):
        self.input_path = p
        from PIL import Image
        try:
            self.raw_pil_image = Image.open(p)
            self.active_pil_image = self.raw_pil_image.copy()
        except Exception:
            return

        self.cached_rgba = None
        self.current_preview_image = None
        self.current_single_id = None

        fname = os.path.basename(p)
        self.lbl_filename.setText(fname)
        self.lbl_filesize.setText(f"原图: {self.raw_pil_image.size[0]} × {self.raw_pil_image.size[1]} px")

        thumb = self.raw_pil_image.copy()
        thumb.thumbnail((48, 48), Image.LANCZOS)
        qimg = pil_to_qimage(thumb)
        self.lbl_thumb.setPixmap(QPixmap.fromImage(qimg).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.btn_crop.setEnabled(True)
        self.btn_reset_crop.setEnabled(True)

        self._start_matting_for_active_image()

    def open_crop_dialog(self):
        if not self.raw_pil_image:
            return
        s = self.size_combo.currentData() or core.load_sizes()[0]
        aspect = s["w_mm"] / s["h_mm"]

        dlg = CropDialog(self.active_pil_image or self.raw_pil_image, aspect, self)
        if dlg.exec() == QDialog.Accepted and dlg.cropped_image:
            self.active_pil_image = dlg.cropped_image
            self.lbl_filesize.setText(f"已手动裁剪: {self.active_pil_image.size[0]} × {self.active_pil_image.size[1]} px")
            self._start_matting_for_active_image()

    def reset_to_raw_image(self):
        if not self.raw_pil_image:
            return
        self.active_pil_image = self.raw_pil_image.copy()
        self.lbl_filesize.setText(f"原图: {self.raw_pil_image.size[0]} × {self.raw_pil_image.size[1]} px")
        self._start_matting_for_active_image()

    def _start_matting_for_active_image(self):
        if not self.active_pil_image:
            return

        self.cached_rgba = None
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status.setText("正在进行智能发丝抠图…")

        if self.mworker and self.mworker.isRunning():
            self.mworker.quit(); self.mworker.wait(1000)

        self.mworker = MattingWorker(self.active_pil_image)
        self.mworker.done.connect(self.on_matting_done)
        self.mworker.failed.connect(self.on_matting_failed)
        self.mworker.start()

        self._do_render()

    def on_matting_done(self, rgba):
        self.cached_rgba = rgba
        self.status.setText("✓ 智能发丝抠图就绪")
        self.progress_bar.setVisible(False)
        self._do_render()

    def on_matting_failed(self, msg):
        self.status.setText(msg)
        self.progress_bar.setVisible(False)
        self._do_render()

    def schedule_render(self):
        if not self.active_pil_image and not self.input_path:
            return
        self.render_timer.start(50)

    def _do_render(self):
        active_img = self.active_pil_image or self.input_path
        if not active_img:
            return

        size_dict = self.size_combo.currentData()
        if not size_dict:
            return

        color_id = self.color_btn_group.checkedId()
        if color_id >= 0 and color_id < len(self.colors_data):
            color_dict = self.colors_data[color_id]
        else:
            color_dict = self.colors_data[0]

        mode_idx = self.mode_combo.currentIndex()
        extra_params = {}

        if mode_idx in (1, 4):
            extra_params["paper"] = self.paper_combo.currentData() or core.load_papers()[0]
            if mode_idx == 4:
                extra_params["rows"] = self.spin_rows.value()
                extra_params["cols"] = self.spin_cols.value()
        elif mode_idx == 2:
            extra_params["mix_type"] = self.mix_combo.currentData() or "5in_2_4"
        elif mode_idx == 3:
            extra_params["paper"] = self.paper_combo.currentData() or core.load_papers()[0]
            extra_params["counts"] = {
                "2in": self.spin_2in.value(),
                "1in": self.spin_1in.value(),
                "s_1in": self.spin_s1in.value(),
                "l_2in": self.spin_l2in.value(),
            }

        cut_lines = self.chk_cut_lines.isChecked()
        add_text = self.chk_add_text.isChecked()

        if self.rworker and self.rworker.isRunning():
            self.rworker.quit(); self.rworker.wait(500)

        self.rworker = RenderWorker(
            active_img, size_dict, color_dict, mode_idx, extra_params,
            cut_lines, add_text, cached_rgba=self.cached_rgba
        )
        self.rworker.done.connect(self.on_render_done)
        self.rworker.error.connect(self.on_render_error)
        self.rworker.start()

    def on_render_done(self, result_image, info_text, is_single, single_id_image):
        self.current_preview_image = result_image
        self.current_single_id = single_id_image
        self.is_single_preview = is_single

        self.lbl_preview_info.setText(info_text)
        self.lbl_footer_info.setText(f"输出分辨率: {result_image.size[0]} × {result_image.size[1]} px · 300 DPI")
        self.status.setText("✓ 渲染完成，可直接导出")
        self._update_preview_display()

    def on_render_error(self, err):
        self.status.setText("渲染出错")
        self.lbl_preview_info.setText(f"错误: {err[:60]}")

    def _update_preview_display(self):
        if not self.current_preview_image:
            return
        qimg = pil_to_qimage(self.current_preview_image)
        pixmap = QPixmap.fromImage(qimg)

        cw = max(100, self.preview_canvas.width() - 24)
        ch = max(100, self.preview_canvas.height() - 24)
        scaled_pix = pixmap.scaled(cw, ch, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        bordered_pixmap = QPixmap(scaled_pix.size() + QSize(4, 4))
        bordered_pixmap.fill(Qt.transparent)

        painter = QPainter(bordered_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(0, 0, scaled_pix.width() + 1, scaled_pix.height() + 1)
        painter.drawPixmap(1, 1, scaled_pix)
        painter.end()

        self.preview_canvas.setPixmap(bordered_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview_display()

    def export_result(self):
        if not self.current_preview_image:
            QMessageBox.warning(self, "提示", "请先导入照片并生成预览后再导出！")
            return

        last_dir = self.settings.value("last_export_dir", os.path.expanduser("~/Desktop"))
        out_dir = QFileDialog.getExistingDirectory(self, "选择保存文件夹", last_dir)
        if not out_dir:
            return

        self.settings.setValue("last_export_dir", out_dir)
        base_name = os.path.splitext(os.path.basename(self.input_path or "照片"))[0]
        size_name = self.size_combo.currentData()["name"].split(" ")[0]
        export_fmt = self.combo_export_fmt.currentData()

        saved_files = []
        try:
            if self.is_single_preview:
                p_png = os.path.join(out_dir, f"{base_name}_{size_name}_单张.png")
                p_jpg = os.path.join(out_dir, f"{base_name}_{size_name}_单张.jpg")
                if export_fmt in ("both", "png"):
                    self.current_preview_image.save(p_png, "PNG")
                    saved_files.append(p_png)
                if export_fmt in ("both", "jpg"):
                    self.current_preview_image.save(p_jpg, "JPEG", quality=95)
                    saved_files.append(p_jpg)
            else:
                mode_name = self.mode_combo.currentText().split(" ")[1]
                p_sheet_png = os.path.join(out_dir, f"{base_name}_{size_name}_{mode_name}_排版.png")
                p_sheet_jpg = os.path.join(out_dir, f"{base_name}_{size_name}_{mode_name}_排版.jpg")
                if export_fmt in ("both", "png"):
                    self.current_preview_image.save(p_sheet_png, "PNG")
                    saved_files.append(p_sheet_png)
                if export_fmt in ("both", "jpg"):
                    self.current_preview_image.save(p_sheet_jpg, "JPEG", quality=95)
                    saved_files.append(p_sheet_jpg)

                if self.current_single_id:
                    p_single_png = os.path.join(out_dir, f"{base_name}_{size_name}_单张.png")
                    p_single_jpg = os.path.join(out_dir, f"{base_name}_{size_name}_单张.jpg")
                    if export_fmt in ("both", "png"):
                        self.current_single_id.save(p_single_png, "PNG")
                        saved_files.append(p_single_png)
                    if export_fmt in ("both", "jpg"):
                        self.current_single_id.save(p_single_jpg, "JPEG", quality=95)
                        saved_files.append(p_single_jpg)

            QMessageBox.information(
                self, "导出成功",
                f"已成功导出照片到：\n{out_dir}\n\n共生成 {len(saved_files)} 份文件。"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存图片时出错：{e}")

    def open_batch_dialog(self):
        dlg = BatchDialog(self)
        dlg.exec()

    def open_preset_dialog(self):
        QMessageBox.information(self, "预设管理", "可以在此处自定义添加你的冲印相纸规格与证件照尺寸。")

    def _load_state(self):
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f6f8fa"))
    palette.setColor(QPalette.WindowText, QColor("#1f2328"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f6f8fa"))
    palette.setColor(QPalette.Text, QColor("#1f2328"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#1f2328"))
    palette.setColor(QPalette.Highlight, QColor("#0969da"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(QSS)

    icon_path = os.path.join(PROJECT_ROOT, "app.icns" if sys.platform == "darwin" else "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    w = MainWindow()
    w.show()
    w.raise_()
    w.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
