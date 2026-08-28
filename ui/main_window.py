# -*- coding: utf-8 -*-
"""
ui/main_window.py — 证件照工作室 macOS / Windows 工业级原生桌面界面
===================================================================
- 苹果 macOS 原生视觉设计规范（SF Pro / 苹方，扁平优雅、原生卡片、通透灰白调）
- 照相馆自然标准证件照构图 (Studio Natural Framing)：
  - 完整呈现头脸、五官、下巴、脖子、衣领与双肩展开，彻底根除大头贴放大截断
  - 支持「人像缩放」与「上下/左右位置微调」，带防截断数值显示
- 交互与布局优化：
  - 左右面板支持 QSplitter 自由拖拽调整宽度，并自动记忆分割位置
  - 彻底禁用控件滚轮事件 (NoWheelComboBox / NoWheelSpinBox / NoWheelSlider)，杜绝滚轮误改配置
  - 一屏式紧凑卡片排版，无需向下滚动即可掌控全局
  - 全局配置持久化记忆 (QSettings)，下次打开自动恢复所有参数、相纸、底色、微调值
- 照相馆规范相纸排版：
  - 6寸横版金牌满排 (152x102mm): 左4张二寸(竖 2x2) + 右8张一寸(横放 2x4) (共12张，左右齐平满排，最畅销)
  - 5寸竖版标准满排 (89x127mm): 上2张二寸(1x2) + 下6张一寸(3x2) (共8张满幅)
- 自由多尺寸自定义混排装箱引擎与手动裁剪工具
"""

import os
import sys
from PySide6.QtCore import Qt, Signal, QThread, QSettings, QTimer, QSize, QRect, QPoint
from PySide6.QtGui import (
    QImage, QPixmap, QColor, QPalette, QDragEnterEvent, QDropEvent,
    QIcon, QPainter, QPen, QBrush, QMouseEvent, QWheelEvent
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QMessageBox,
    QProgressBar, QScrollArea, QFrame, QSplitter, QCheckBox,
    QLineEdit, QDialog, QFormLayout, QSpinBox, QColorDialog, QButtonGroup,
    QGridLayout, QSlider
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
    font-size: 15px;
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
    padding: 2px 6px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#WarnBadge {
    background-color: #ffebe9;
    color: #cf222e;
    border: 1px solid #ffcecb;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: 600;
}
QComboBox, QLineEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 4px 8px;
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
    selection-background-color: #0969da;
    selection-color: #ffffff;
    padding: 4px;
}
QPushButton {
    background-color: #ffffff;
    color: #1f2328;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: 500;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #f3f4f6;
    border-color: #8c959f;
}
QPushButton:pressed {
    background-color: #e5e7eb;
}
QPushButton#PrimaryBtn {
    background-color: #0969da;
    color: #ffffff;
    border: 1px solid #0969da;
    font-weight: 600;
    font-size: 13px;
    border-radius: 6px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0856b8;
    border-color: #0856b8;
}
QPushButton#SecondaryBtn {
    background-color: #f6f8fa;
    color: #1f2328;
    border: 1px solid #d0d7de;
}
QPushButton#SecondaryBtn:hover {
    background-color: #eaeef2;
}
QCheckBox {
    spacing: 6px;
    color: #1f2328;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid #d0d7de;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #0969da;
    border-color: #0969da;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #e2e8f0;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0969da;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #0969da;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QFrame#DropBox {
    background-color: #ffffff;
    border: 1px dashed #0969da;
    border-radius: 8px;
}
QFrame#DropBox:hover {
    background-color: #f0f7ff;
}
QSplitter::handle {
    background-color: #e1e4e8;
}
QSplitter::handle:hover {
    background-color: #0969da;
}
"""


# ============================================================ 防误触滚轮自定义控件
class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoWheelSlider(QSlider):
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


def pil_to_pixmap(pil_img):
    if pil_img.mode == "RGBA":
        fmt = QImage.Format_RGBA8888
    else:
        pil_img = pil_img.convert("RGB")
        fmt = QImage.Format_RGB888
    data = pil_img.tobytes()
    qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * (4 if pil_img.mode == "RGBA" else 3), fmt)
    return QPixmap.fromImage(qimg)


# ============================================================ 交互式裁剪组件与对话框
class CropWidget(QWidget):
    def __init__(self, pil_image, aspect_ratio=25.0/35.0, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image.convert("RGB")
        self.aspect_ratio = aspect_ratio
        self.setMouseTracking(True)

        self.rel_x = 0.15
        self.rel_y = 0.08
        self.rel_w = 0.70
        self.rel_h = self.rel_w / self.aspect_ratio * (self.pil_image.size[0] / self.pil_image.size[1])
        if self.rel_h > 0.85:
            self.rel_h = 0.85
            self.rel_w = self.rel_h * self.aspect_ratio * (self.pil_image.size[1] / self.pil_image.size[0])

        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        vw, vh = self.width(), self.height()
        iw, ih = self.pil_image.size

        scale = min(vw / iw, vh / ih) * 0.95
        nw, nh = int(iw * scale), int(ih * scale)
        ox, oy = (vw - nw) // 2, (vh - nh) // 2
        self.img_rect = QRect(ox, oy, nw, nh)

        pix = pil_to_pixmap(self.pil_image).scaled(nw, nh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(ox, oy, pix)

        cx = ox + int(self.rel_x * nw)
        cy = oy + int(self.rel_y * nh)
        cw = int(self.rel_w * nw)
        ch = int(self.rel_h * nh)
        self.crop_rect = QRect(cx, cy, cw, ch)

        mask_color = QColor(0, 0, 0, 140)
        painter.fillRect(QRect(ox, oy, nw, cy - oy), mask_color)
        painter.fillRect(QRect(ox, cy + ch, nw, oy + nh - (cy + ch)), mask_color)
        painter.fillRect(QRect(ox, cy, cx - ox, ch), mask_color)
        painter.fillRect(QRect(cx + cw, cy, ox + nw - (cx + cw), ch), mask_color)

        pen = QPen(QColor("#0969da"), 2)
        painter.setPen(pen)
        painter.drawRect(self.crop_rect)

        pen_grid = QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine)
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
        cw = self.crop_widget
        iw, ih = cw.pil_image.size
        x1 = int(round(cw.rel_x * iw))
        y1 = int(round(cw.rel_y * ih))
        x2 = int(round((cw.rel_x + cw.rel_w) * iw))
        y2 = int(round((cw.rel_y + cw.rel_h) * ih))

        x1 = max(0, min(iw - 10, x1))
        y1 = max(0, min(ih - 10, y1))
        x2 = max(x1 + 10, min(iw, x2))
        y2 = max(y1 + 10, min(ih, y2))

        self.cropped_image = cw.pil_image.crop((x1, y1, x2, y2))
        self.accept()


# ============================================================ 异步发丝抠图线程
class MattingWorker(QThread):
    done = Signal(object, int)
    failed = Signal(str, int)

    def __init__(self, image_input, req_id):
        super().__init__()
        self.image_input = image_input
        self.req_id = req_id

    def run(self):
        try:
            from PIL import Image
            if isinstance(self.image_input, str):
                img = Image.open(self.image_input)
            else:
                img = self.image_input
            m = core.Matting()
            rgba = m.remove(img)
            self.done.emit(rgba, self.req_id)
        except Exception as e:
            self.failed.emit(str(e), self.req_id)


# ============================================================ 异步冲印排版渲染线程
class RenderWorker(QThread):
    done = Signal(object, str, bool, object, int)
    error = Signal(str, int)

    def __init__(self, image_input, size_dict, color_dict, mode_idx, extra_params,
                 cut_lines, add_text, cached_rgba, req_id, zoom_ratio=1.0, offset_y_ratio=0.0, offset_x_ratio=0.0):
        super().__init__()
        self.image_input = image_input
        self.size_dict = size_dict
        self.color_dict = color_dict
        self.mode_idx = mode_idx
        self.extra_params = extra_params
        self.cut_lines = cut_lines
        self.add_text = add_text
        self.cached_rgba = cached_rgba
        self.req_id = req_id
        self.zoom_ratio = zoom_ratio
        self.offset_y_ratio = offset_y_ratio
        self.offset_x_ratio = offset_x_ratio

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
                    self.cached_rgba, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb,
                    zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio
                )
            else:
                matting = core.Matting() if (need_matting and core.Matting().available()) else None
                id_photo = core.prepare_id_photo(
                    img, self.size_dict["w_px"], self.size_dict["h_px"], bg_rgb, matting,
                    zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio
                )

            # 0: 仅单张证件照 (默认)
            if self.mode_idx == 0:
                info = f"单张 {self.size_dict['name']} · {self.size_dict['w_px']}×{self.size_dict['h_px']} px (300 DPI)"
                self.done.emit(id_photo, info, True, id_photo, self.req_id)
                return

            # 2: 照相馆标准规整混排
            if self.mode_idx == 2:
                mix_type = self.extra_params.get("mix_type", "6in_landscape_4_8")
                if self.cached_rgba is not None:
                    id_1in = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(25), core.mm_to_px(35), bg_rgb,
                                                           zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)
                    id_2in = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(35), core.mm_to_px(49), bg_rgb,
                                                           zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)
                else:
                    matting = core.Matting() if (bg_rgb is not None and core.Matting().available()) else None
                    id_1in = core.prepare_id_photo(img, core.mm_to_px(25), core.mm_to_px(35), bg_rgb, matting,
                                                   zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)
                    id_2in = core.prepare_id_photo(img, core.mm_to_px(35), core.mm_to_px(49), bg_rgb, matting,
                                                   zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)

                sheet, info = core.compose_mixed_sheet(id_1in, id_2in, mix_type=mix_type, cut_lines=self.cut_lines, add_text=self.add_text)
                self.done.emit(sheet, info, False, id_photo, self.req_id)
                return

            # 3: 自由多尺寸自定义混排
            if self.mode_idx == 3:
                counts = self.extra_params.get("counts", {})
                paper = self.extra_params.get("paper", core.load_papers()[1])
                ori = self.extra_params.get("orientation", "auto")
                images_dict = {}
                for k, w_mm, h_mm in [("2in", 35, 49), ("1in", 25, 35), ("s_1in", 22, 32), ("l_2in", 35, 53)]:
                    if self.cached_rgba is not None:
                        images_dict[k] = core.create_standard_id_photo(self.cached_rgba, core.mm_to_px(w_mm), core.mm_to_px(h_mm), bg_rgb,
                                                                       zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)
                    else:
                        matting = core.Matting() if (bg_rgb is not None and core.Matting().available()) else None
                        images_dict[k] = core.prepare_id_photo(img, core.mm_to_px(w_mm), core.mm_to_px(h_mm), bg_rgb, matting,
                                                               zoom_ratio=self.zoom_ratio, offset_y_ratio=self.offset_y_ratio, offset_x_ratio=self.offset_x_ratio)

                sheet, info, fits = core.compose_custom_mixed_sheet(images_dict, counts, paper, cut_lines=self.cut_lines, preferred_orientation=ori)
                self.done.emit(sheet, info, False, id_photo, self.req_id)
                return

            # 1: 照相馆标准相纸排版, 4: 自定义网格
            ori = self.extra_params.get("orientation", "auto")
            if self.mode_idx == 1:
                p = self.extra_params["paper"]
                lay = core.compute_layout(p["w_mm"], p["h_mm"], self.size_dict["w_mm"], self.size_dict["h_mm"], preferred_orientation=ori)
            else:
                p = self.extra_params.get("paper", core.load_papers()[1])
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
            self.done.emit(sheet, info, False, id_photo, self.req_id)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()[-300:]}", self.req_id)


# ============================================================ 批量处理对话框
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

        p_box = QFrame(); p_box.setObjectName("Card")
        pl = QVBoxLayout(p_box); pl.setContentsMargins(12, 10, 12, 10); pl.setSpacing(8)
        pl.addWidget(QLabel("2. 统一输出规格与底色:"))

        form = QFormLayout()
        form.setSpacing(8)
        self.b_size_combo = NoWheelComboBox()
        for s in core.load_presets():
            self.b_size_combo.addItem(s["name"], s)
        form.addRow("目标证件照规格:", self.b_size_combo)

        self.b_color_combo = NoWheelComboBox()
        for c in core.BUILTIN_COLORS:
            self.b_color_combo.addItem(c[1], {"key": c[0], "name": c[1], "rgb": c[2]})
        form.addRow("替换背景底色:", self.b_color_combo)

        self.b_paper_combo = NoWheelComboBox()
        for p in core.load_papers():
            self.b_paper_combo.addItem(p["name"], p)
        form.addRow("排版冲印相纸:", self.b_paper_combo)

        self.b_export_fmt = NoWheelComboBox()
        self.b_export_fmt.addItem("PNG + JPG (两种格式都导出)", "both")
        self.b_export_fmt.addItem("仅导出 PNG", "png")
        self.b_export_fmt.addItem("仅导出 JPG", "jpg")
        form.addRow("导出格式:", self.b_export_fmt)

        pl.addLayout(form)

        chk_row = QHBoxLayout()
        self.chk_exp_single = QCheckBox("同时导出单张证件照")
        self.chk_exp_single.setChecked(True)
        self.chk_exp_sheet = QCheckBox("同时导出相纸冲印排版")
        self.chk_exp_sheet.setChecked(True)
        chk_row.addWidget(self.chk_exp_single)
        chk_row.addWidget(self.chk_exp_sheet)
        pl.addLayout(chk_row)
        layout.addWidget(p_box)

        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("SubTitle")
        layout.addWidget(self.lbl_status)

        b_row = QHBoxLayout()
        b_close = QPushButton("关闭")
        b_close.clicked.connect(self.reject)
        self.btn_start = QPushButton("🚀 开始批量处理并导出")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.clicked.connect(self.start_batch)
        b_row.addStretch()
        b_row.addWidget(b_close)
        b_row.addWidget(self.btn_start)
        layout.addLayout(b_row)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "多选照片", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp)")
        if files:
            self.file_paths = files
            self.lbl_file_count.setText(f"已选 {len(files)} 张照片")

    def select_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择包含照片的文件夹")
        if d:
            valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            found = [os.path.join(d, f) for f in os.listdir(d) if os.path.splitext(f)[1].lower() in valid_exts]
            if found:
                self.file_paths = sorted(found)
                self.lbl_file_count.setText(f"从文件夹载入 {len(found)} 张照片")
            else:
                QMessageBox.warning(self, "提示", "所选文件夹内未找到图片文件")

    def start_batch(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先选择要处理的照片文件")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "选择批量结果保存目录")
        if not out_dir:
            return

        self.btn_start.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setRange(0, len(self.file_paths))
        self.pbar.setValue(0)

        s_dict = self.b_size_combo.currentData()
        c_dict = self.b_color_combo.currentData()
        p_dict = self.b_paper_combo.currentData()
        fmt = self.b_export_fmt.currentData()

        self.worker = BatchWorker(
            self.file_paths, s_dict, c_dict,
            self.chk_exp_single.isChecked(),
            self.chk_exp_sheet.isChecked(),
            p_dict, fmt, out_dir
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, cur, total, fname):
        self.pbar.setValue(cur)
        self.lbl_status.setText(f"正在处理 ({cur}/{total}): {fname}")

    def on_finished(self, count, saved):
        self.btn_start.setEnabled(True)
        self.pbar.setVisible(False)
        self.lbl_status.setText(f"✓ 批量处理完成！共生成 {count} 份文件")
        QMessageBox.information(self, "完成", f"批量处理完成！\n已生成 {count} 份证件照与排版文件。")

    def on_error(self, err):
        self.btn_start.setEnabled(True)
        self.pbar.setVisible(False)
        QMessageBox.critical(self, "错误", f"批量处理出错：{err}")


# ============================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("证件照工作室 Studio · 专业版")
        self.setMinimumSize(980, 680)

        self.settings = QSettings("IDPhotoStudio", "DesktopApp")
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1140, 750)

        self.setAcceptDrops(True)

        self.raw_pil_image = None
        self.active_pil_image = None
        self.input_path = ""
        self.cached_rgba = None
        self.current_preview_image = None
        self.current_single_id = None
        self.is_single_view = True

        self._render_req_id = 0
        self._matting_req_id = 0
        self._running_threads = []

        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._do_render)

        self.init_ui()
        self.load_user_settings()

        # 启动自检：模型漏打/量化不兼容会在这里明确报错，而不是静默出废片
        QTimer.singleShot(400, self._run_startup_diagnostic)

    def _run_startup_diagnostic(self):
        try:
            log_path = core.write_diagnostic_report()
            ok, msg = core.Matting().self_check()
            if not ok:
                detail = ("抠图模型自检未通过，换背景功能将无法正常工作。\n\n"
                          "原因：%s\n\n诊断日志：%s") % (msg, log_path or "(无法写入)")
                QMessageBox.critical(self, "模型异常 · 无法换背景", detail)
        except Exception:
            pass

    def init_ui(self):
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)

        # ------------------------------------------------ 左侧控制面板 (支持拖拽调整，最小320，最大560)
        left_box = QWidget()
        left_box.setMinimumWidth(330)
        left_box.setMaximumWidth(560)
        left_v = QVBoxLayout(left_box)
        left_v.setContentsMargins(6, 6, 6, 6)
        left_v.setSpacing(6)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(2, 2, 4, 2)
        left_layout.setSpacing(8)

        # App 标题区
        head_card = QFrame(); head_card.setObjectName("Card")
        hl = QHBoxLayout(head_card); hl.setContentsMargins(10, 8, 10, 8)
        t_box = QVBoxLayout()
        lbl_logo = QLabel("证件照工作室"); lbl_logo.setObjectName("AppLogo")
        lbl_sub = QLabel("智能发丝抠图 · 照相馆标准排版"); lbl_sub.setObjectName("SubTitle")
        t_box.addWidget(lbl_logo); t_box.addWidget(lbl_sub)
        hl.addLayout(t_box)
        hl.addStretch()
        btn_batch_top = QPushButton("📂 批量处理"); btn_batch_top.setObjectName("SecondaryBtn")
        btn_batch_top.setMinimumWidth(86)
        btn_batch_top.clicked.connect(self.open_batch_dialog)
        hl.addWidget(btn_batch_top)
        left_layout.addWidget(head_card)

        # 1. 照片导入区
        card_import = QFrame(); card_import.setObjectName("Card")
        cl = QVBoxLayout(card_import); cl.setContentsMargins(10, 8, 10, 8); cl.setSpacing(6)
        cl.addWidget(QLabel("1. 照片导入", objectName="SectionTitle"))

        self.dropbox = QFrame(); self.dropbox.setObjectName("DropBox")
        dl = QHBoxLayout(self.dropbox); dl.setContentsMargins(6, 6, 6, 6); dl.setSpacing(8)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(44, 44)
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

        # 人像构图微调控制器
        framing_box = QFrame()
        framing_l = QVBoxLayout(framing_box); framing_l.setContentsMargins(0, 2, 0, 0); framing_l.setSpacing(4)

        row_zoom = QHBoxLayout()
        row_zoom.addWidget(QLabel("人像大小:"))
        self.slider_zoom = NoWheelSlider(Qt.Horizontal)
        self.slider_zoom.setRange(70, 140)
        self.slider_zoom.setValue(100)
        self.slider_zoom.valueChanged.connect(self.schedule_render)
        row_zoom.addWidget(self.slider_zoom)
        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setFixedWidth(46)
        self.lbl_zoom_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_zoom.valueChanged.connect(lambda v: self.lbl_zoom_val.setText(f"{v}%"))
        row_zoom.addWidget(self.lbl_zoom_val)
        framing_l.addLayout(row_zoom)

        row_pos = QHBoxLayout()
        row_pos.addWidget(QLabel("上下位置:"))
        self.slider_pos_y = NoWheelSlider(Qt.Horizontal)
        self.slider_pos_y.setRange(-20, 20)
        self.slider_pos_y.setValue(0)
        self.slider_pos_y.valueChanged.connect(self.schedule_render)
        row_pos.addWidget(self.slider_pos_y)
        self.lbl_pos_y_val = QLabel("0%")
        self.lbl_pos_y_val.setFixedWidth(46)
        self.lbl_pos_y_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_pos_y.valueChanged.connect(lambda v: self.lbl_pos_y_val.setText(f"{v}%"))
        row_pos.addWidget(self.lbl_pos_y_val)
        framing_l.addLayout(row_pos)

        row_pos_x = QHBoxLayout()
        row_pos_x.addWidget(QLabel("左右位置:"))
        self.slider_pos_x = NoWheelSlider(Qt.Horizontal)
        self.slider_pos_x.setRange(-20, 20)
        self.slider_pos_x.setValue(0)
        self.slider_pos_x.valueChanged.connect(self.schedule_render)
        row_pos_x.addWidget(self.slider_pos_x)
        self.lbl_pos_x_val = QLabel("0%")
        self.lbl_pos_x_val.setFixedWidth(46)
        self.lbl_pos_x_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider_pos_x.valueChanged.connect(lambda v: self.lbl_pos_x_val.setText(f"{v}%"))
        row_pos_x.addWidget(self.lbl_pos_x_val)
        framing_l.addLayout(row_pos_x)

        row_reset = QHBoxLayout()
        row_reset.addStretch()
        btn_reset_frame = QPushButton("↺ 重置微调参数")
        btn_reset_frame.setObjectName("SecondaryBtn")
        btn_reset_frame.clicked.connect(self.reset_framing)
        row_reset.addWidget(btn_reset_frame)
        framing_l.addLayout(row_reset)

        cl.addWidget(framing_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        cl.addWidget(self.progress_bar)
        left_layout.addWidget(card_import)

        # 2. 证件规格与背景底色
        card_spec = QFrame(); card_spec.setObjectName("Card")
        sl = QVBoxLayout(card_spec); sl.setContentsMargins(10, 8, 10, 8); sl.setSpacing(6)
        sl.addWidget(QLabel("2. 证件规格与背景底色", objectName="SectionTitle"))

        self.size_combo = NoWheelComboBox()
        for s in core.load_presets():
            self.size_combo.addItem(s["name"], s)
        self.size_combo.currentIndexChanged.connect(self.schedule_render)
        sl.addWidget(self.size_combo)

        sl.addWidget(QLabel("选择替换底色:"))
        color_grid = QGridLayout()
        color_grid.setSpacing(5)
        color_grid.setContentsMargins(0, 0, 0, 0)
        self.color_btn_group = QButtonGroup(self)
        self.color_btn_group.setExclusive(True)

        self.colors_data = []
        for idx, (ckey, cname, crgb, chex) in enumerate(core.BUILTIN_COLORS):
            self.colors_data.append({"key": ckey, "name": cname, "rgb": crgb, "hex": chex})
            btn = QPushButton(cname.split(" ")[0])
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            border_css = "border: 1px solid #d0d7de;"
            if crgb == (255, 255, 255):
                btn_css = f"background-color: #ffffff; color: #1f2937; {border_css}"
            elif crgb is None:
                btn_css = "background-color: #f1f5f9; color: #475569; border: 1px dashed #94a3b8;"
            else:
                text_c = "#ffffff" if (ckey in ("blue", "red", "dark_blue")) else "#1f2937"
                btn_css = f"background-color: {chex}; color: {text_c}; border: none;"

            btn.setStyleSheet(f"""
                QPushButton {{ {btn_css} border-radius: 4px; font-weight: 500; font-size: 12px; }}
                QPushButton:checked {{ border: 2px solid #0969da; font-weight: 700; }}
            """)
            if idx == 0:
                btn.setChecked(True)
            self.color_btn_group.addButton(btn, idx)
            color_grid.addWidget(btn, idx // 4, idx % 4)

        btn_custom_c = QPushButton("🎨 自定义")
        btn_custom_c.setFixedHeight(26)
        btn_custom_c.setObjectName("SecondaryBtn")
        btn_custom_c.clicked.connect(self.pick_custom_color)
        color_grid.addWidget(btn_custom_c, len(self.colors_data) // 4, len(self.colors_data) % 4)

        self.color_btn_group.idClicked.connect(self.on_color_changed)
        sl.addLayout(color_grid)
        left_layout.addWidget(card_spec)

        # 3. 排版冲印
        card_print = QFrame(); card_print.setObjectName("Card")
        pl = QVBoxLayout(card_print); pl.setContentsMargins(10, 8, 10, 8); pl.setSpacing(6)
        pl.addWidget(QLabel("3. 排版冲印", objectName="SectionTitle"))

        self.mode_combo = NoWheelComboBox()
        self.mode_combo.addItem("🖼 仅单张证件照 (默认)")
        self.mode_combo.addItem("📄 照相馆标准相纸排版")
        self.mode_combo.addItem("🔀 照相馆标准规整混排")
        self.mode_combo.addItem("🧩 自由多尺寸自定义混排")
        self.mode_combo.addItem("📐 自由自定义网格排版")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        pl.addWidget(self.mode_combo)

        # 相纸朝向选择器 (模式 1、3、4 使用)
        self.ori_container = QWidget()
        ori_l = QHBoxLayout(self.ori_container); ori_l.setContentsMargins(0, 0, 0, 0); ori_l.setSpacing(6)
        ori_l.addWidget(QLabel("相纸朝向:"))
        self.ori_combo = NoWheelComboBox()
        self.ori_combo.addItem("🔄 自动最优朝向", "auto")
        self.ori_combo.addItem("↔️ 强制横版 (Landscape)", "landscape")
        self.ori_combo.addItem("↕️ 强制竖版 (Portrait)", "portrait")
        self.ori_combo.currentIndexChanged.connect(self.schedule_render)
        ori_l.addWidget(self.ori_combo, 1)
        pl.addWidget(self.ori_container)
        self.ori_container.setVisible(False)

        # 相纸选择容器
        self.paper_container = QWidget()
        paper_l = QVBoxLayout(self.paper_container); paper_l.setContentsMargins(0, 0, 0, 0); paper_l.setSpacing(4)
        paper_l.addWidget(QLabel("选择冲印相纸 (5寸/6寸置顶):"))
        self.paper_combo = NoWheelComboBox()
        for p in core.load_papers():
            self.paper_combo.addItem(p["name"], p)
        self.paper_combo.currentIndexChanged.connect(self.schedule_render)
        paper_l.addWidget(self.paper_combo)
        pl.addWidget(self.paper_container)
        self.paper_container.setVisible(False)

        # 经典混排类型容器 (模式 2 · 精简权威两款)
        self.mix_container = QWidget()
        mix_l = QVBoxLayout(self.mix_container); mix_l.setContentsMargins(0, 0, 0, 0); mix_l.setSpacing(4)
        mix_l.addWidget(QLabel("照相馆标准混排方案:"))
        self.mix_combo = NoWheelComboBox()
        self.mix_combo.addItem("6寸横版金牌满排 · 4张二寸(竖) + 8张一寸(横) (共12张 · 最畅销)", "6in_landscape_4_8")
        self.mix_combo.addItem("5寸标准满排 · 2张二寸 + 6张一寸 (共8张满幅)", "5in_portrait_2_6")
        self.mix_combo.currentIndexChanged.connect(self.schedule_render)
        mix_l.addWidget(self.mix_combo)
        pl.addWidget(self.mix_container)
        self.mix_container.setVisible(False)

        # 自由自定义混排容器 (模式 3)
        self.custom_mix_container = QWidget()
        cml = QVBoxLayout(self.custom_mix_container); cml.setContentsMargins(0, 0, 0, 0); cml.setSpacing(4)
        cml.addWidget(QLabel("设定各尺寸冲印张数:"))

        form_counts = QFormLayout()
        form_counts.setContentsMargins(0, 0, 0, 0)
        form_counts.setSpacing(5)

        self.spin_2in = NoWheelSpinBox(); self.spin_2in.setRange(0, 12); self.spin_2in.setValue(4)
        self.spin_2in.setFixedWidth(76)
        self.spin_2in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("二寸 (35×49mm):", self.spin_2in)

        self.spin_1in = NoWheelSpinBox(); self.spin_1in.setRange(0, 24); self.spin_1in.setValue(6)
        self.spin_1in.setFixedWidth(76)
        self.spin_1in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("一寸 (25×35mm):", self.spin_1in)

        self.spin_s1in = NoWheelSpinBox(); self.spin_s1in.setRange(0, 24); self.spin_s1in.setValue(0)
        self.spin_s1in.setFixedWidth(76)
        self.spin_s1in.valueChanged.connect(self.schedule_render)
        form_counts.addRow("小一寸 (22×32mm):", self.spin_s1in)

        self.spin_l2in = NoWheelSpinBox(); self.spin_l2in.setRange(0, 12); self.spin_l2in.setValue(0)
        self.spin_l2in.setFixedWidth(76)
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
        self.spin_cols = NoWheelSpinBox(); self.spin_cols.setRange(1, 10); self.spin_cols.setValue(4)
        self.spin_cols.valueChanged.connect(self.schedule_render)
        grow.addWidget(self.spin_cols)
        grow.addWidget(QLabel("行数:"))
        self.spin_rows = NoWheelSpinBox(); self.spin_rows.setRange(1, 10); self.spin_rows.setValue(2)
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
        al = QHBoxLayout(self.opt_aux_box); al.setContentsMargins(0, 2, 0, 0); al.setSpacing(10)
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
        left_v.addWidget(left_scroll, 1)

        # 4. 固定底部操作与导出卡片 (紧凑精致，无需滚动)
        bottom_card = QFrame(); bottom_card.setObjectName("Card")
        bl = QVBoxLayout(bottom_card); bl.setContentsMargins(10, 8, 10, 8); bl.setSpacing(6)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("导出格式:"))
        self.combo_export_fmt = NoWheelComboBox()
        self.combo_export_fmt.addItem("PNG + JPG (两种都要 · 推荐)", "both")
        self.combo_export_fmt.addItem("仅导出 PNG (高清无损)", "png")
        self.combo_export_fmt.addItem("仅导出 JPG (高品质冲印格式)", "jpg")
        fmt_row.addWidget(self.combo_export_fmt, 1)
        bl.addLayout(fmt_row)

        btn_row_exp = QHBoxLayout()
        self.btn_export = QPushButton("💾 导出当前冲印图")
        self.btn_export.setObjectName("PrimaryBtn")
        self.btn_export.setFixedHeight(34)
        self.btn_export.clicked.connect(self.export_image)
        btn_row_exp.addWidget(self.btn_export)
        bl.addLayout(btn_row_exp)

        self.status = QLabel("就绪 · 请导入人像照片")
        self.status.setObjectName("SubTitle")
        bl.addWidget(self.status)

        left_v.addWidget(bottom_card)
        self.splitter.addWidget(left_box)

        # ------------------------------------------------ 右侧大预览区
        right_panel = QWidget()
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(6)

        preview_card = QFrame(); preview_card.setObjectName("Card")
        pcl = QVBoxLayout(preview_card); pcl.setContentsMargins(10, 10, 10, 10); pcl.setSpacing(6)

        self.preview_info = QLabel("等待导入照片…")
        self.preview_info.setStyleSheet("font-weight: 600; color: #1f2937;")
        pcl.addWidget(self.preview_info)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background-color: #f1f5f9; border-radius: 6px; border: 1px solid #e2e8f0;")
        pcl.addWidget(self.preview, 1)

        self.lbl_dims = QLabel("输出分辨率: -- · 300 DPI")
        self.lbl_dims.setObjectName("SubTitle")
        self.lbl_dims.setAlignment(Qt.AlignCenter)
        pcl.addWidget(self.lbl_dims)

        rl.addWidget(preview_card)
        self.splitter.addWidget(right_panel)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        sp_state = self.settings.value("splitter_state")
        if sp_state:
            self.splitter.restoreState(sp_state)
        else:
            self.splitter.setSizes([360, 780])

        self.setCentralWidget(self.splitter)

    # ------------------------------------------------ 用户配置记忆持久化
    def save_user_settings(self):
        try:
            s = self.size_combo.currentData()
            if s:
                self.settings.setValue("selected_size_key", s.get("key"))
            self.settings.setValue("selected_color_id", self.color_btn_group.checkedId())
            self.settings.setValue("selected_mode_idx", self.mode_combo.currentIndex())
            p = self.paper_combo.currentData()
            if p:
                self.settings.setValue("selected_paper_key", p.get("key"))
            self.settings.setValue("selected_ori", self.ori_combo.currentData())
            self.settings.setValue("selected_mix_type", self.mix_combo.currentData())
            self.settings.setValue("export_fmt", self.combo_export_fmt.currentData())
            self.settings.setValue("zoom_val", self.slider_zoom.value())
            self.settings.setValue("pos_y_val", self.slider_pos_y.value())
            self.settings.setValue("pos_x_val", self.slider_pos_x.value())
            self.settings.setValue("cut_lines", self.chk_cut_lines.isChecked())
            self.settings.setValue("add_text", self.chk_add_text.isChecked())
            self.settings.setValue("spin_2in", self.spin_2in.value())
            self.settings.setValue("spin_1in", self.spin_1in.value())
            self.settings.setValue("spin_s1in", self.spin_s1in.value())
            self.settings.setValue("spin_l2in", self.spin_l2in.value())
            self.settings.setValue("spin_cols", self.spin_cols.value())
            self.settings.setValue("spin_rows", self.spin_rows.value())
            self.settings.setValue("splitter_state", self.splitter.saveState())
        except Exception:
            pass

    def load_user_settings(self):
        try:
            # 恢复规格
            saved_size_key = self.settings.value("selected_size_key")
            if saved_size_key:
                for i in range(self.size_combo.count()):
                    d = self.size_combo.itemData(i)
                    if d and d.get("key") == saved_size_key:
                        self.size_combo.setCurrentIndex(i)
                        break

            # 恢复底色
            saved_color_id = self.settings.value("selected_color_id")
            if saved_color_id is not None:
                cid = int(saved_color_id)
                btn = self.color_btn_group.button(cid)
                if btn:
                    btn.setChecked(True)

            # 恢复相纸
            saved_paper_key = self.settings.value("selected_paper_key")
            if saved_paper_key:
                for i in range(self.paper_combo.count()):
                    d = self.paper_combo.itemData(i)
                    if d and d.get("key") == saved_paper_key:
                        self.paper_combo.setCurrentIndex(i)
                        break

            # 恢复排版模式
            saved_mode = self.settings.value("selected_mode_idx")
            if saved_mode is not None:
                self.mode_combo.setCurrentIndex(int(saved_mode))

            # 恢复相纸朝向
            saved_ori = self.settings.value("selected_ori")
            if saved_ori:
                for i in range(self.ori_combo.count()):
                    if self.ori_combo.itemData(i) == saved_ori:
                        self.ori_combo.setCurrentIndex(i)
                        break

            # 恢复导出格式
            saved_fmt = self.settings.value("export_fmt")
            if saved_fmt:
                for i in range(self.combo_export_fmt.count()):
                    if self.combo_export_fmt.itemData(i) == saved_fmt:
                        self.combo_export_fmt.setCurrentIndex(i)
                        break

            # 恢复微调滑块
            if self.settings.value("zoom_val") is not None:
                self.slider_zoom.setValue(int(self.settings.value("zoom_val")))
            if self.settings.value("pos_y_val") is not None:
                self.slider_pos_y.setValue(int(self.settings.value("pos_y_val")))
            if self.settings.value("pos_x_val") is not None:
                self.slider_pos_x.setValue(int(self.settings.value("pos_x_val")))

            # 恢复复选框
            if self.settings.value("cut_lines") is not None:
                self.chk_cut_lines.setChecked(str(self.settings.value("cut_lines")).lower() in ("true", "1"))
            if self.settings.value("add_text") is not None:
                self.chk_add_text.setChecked(str(self.settings.value("add_text")).lower() in ("true", "1"))

            # 恢复自定义数量
            if self.settings.value("spin_2in") is not None:
                self.spin_2in.setValue(int(self.settings.value("spin_2in")))
            if self.settings.value("spin_1in") is not None:
                self.spin_1in.setValue(int(self.settings.value("spin_1in")))
            if self.settings.value("spin_s1in") is not None:
                self.spin_s1in.setValue(int(self.settings.value("spin_s1in")))
            if self.settings.value("spin_l2in") is not None:
                self.spin_l2in.setValue(int(self.settings.value("spin_l2in")))
        except Exception:
            pass

    # ------------------------------------------------ 事件与交互
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.dropbox.setStyleSheet("background-color: #e0f2fe; border: 1px solid #0969da;")

    def dragLeaveEvent(self, event):
        self.dropbox.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.dropbox.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            p = urls[0].toLocalFile()
            if p and os.path.exists(p):
                self.set_photo(p)

    def select_photo(self):
        last_dir = self.settings.value("last_dir", os.path.expanduser("~/Pictures"))
        p, _ = QFileDialog.getOpenFileName(self, "选择人像照片", last_dir, "图片 (*.jpg *.jpeg *.png *.webp *.bmp)")
        if p:
            self.settings.setValue("last_dir", os.path.dirname(p))
            self.set_photo(p)

    def set_photo(self, p):
        from PIL import Image
        try:
            img = Image.open(p)
            self.input_path = p
            self.raw_pil_image = img.copy()
            self.active_pil_image = img.copy()
            self.lbl_filename.setText(os.path.basename(p))
            self.lbl_filesize.setText(f"{img.size[0]} × {img.size[1]} px · 原始照片")
            self.lbl_thumb.setPixmap(pil_to_pixmap(img).scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.btn_crop.setEnabled(True)
            self.btn_reset_crop.setEnabled(True)
            self._start_matting_for_active_image()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法载入照片：{e}")

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

        self._matting_req_id += 1
        worker = MattingWorker(self.active_pil_image, self._matting_req_id)
        self._running_threads.append(worker)

        worker.done.connect(self.on_matting_done)
        worker.failed.connect(self.on_matting_failed)
        worker.finished.connect(lambda w=worker: self._cleanup_thread(w))
        worker.start()

        self._do_render()

    def on_matting_done(self, rgba, req_id):
        if req_id != self._matting_req_id:
            return
        self.cached_rgba = rgba
        self.status.setText("✓ 智能发丝抠图就绪")
        self.progress_bar.setVisible(False)
        self._do_render()

    def on_matting_failed(self, msg, req_id):
        if req_id != self._matting_req_id:
            return
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

        ori = self.ori_combo.currentData() or "auto"
        extra_params["orientation"] = ori

        if mode_idx in (1, 4):
            extra_params["paper"] = self.paper_combo.currentData() or core.load_papers()[1]
            if mode_idx == 4:
                extra_params["rows"] = self.spin_rows.value()
                extra_params["cols"] = self.spin_cols.value()
        elif mode_idx == 2:
            extra_params["mix_type"] = self.mix_combo.currentData() or "6in_landscape_4_8"
        elif mode_idx == 3:
            extra_params["paper"] = self.paper_combo.currentData() or core.load_papers()[1]
            extra_params["counts"] = {
                "2in": self.spin_2in.value(),
                "1in": self.spin_1in.value(),
                "s_1in": self.spin_s1in.value(),
                "l_2in": self.spin_l2in.value(),
            }

        zoom_val = self.slider_zoom.value() / 100.0
        pos_y_val = self.slider_pos_y.value() / 100.0
        pos_x_val = self.slider_pos_x.value() / 100.0

        self._render_req_id += 1
        worker = RenderWorker(
            active_img, size_dict, color_dict, mode_idx, extra_params,
            self.chk_cut_lines.isChecked(), self.chk_add_text.isChecked(),
            self.cached_rgba, self._render_req_id,
            zoom_ratio=zoom_val, offset_y_ratio=pos_y_val, offset_x_ratio=pos_x_val
        )
        self._running_threads.append(worker)
        worker.done.connect(self.on_render_done)
        worker.error.connect(self.on_render_error)
        worker.finished.connect(lambda w=worker: self._cleanup_thread(w))
        worker.start()

    def _cleanup_thread(self, thread):
        if thread in self._running_threads:
            self._running_threads.remove(thread)

    def on_render_done(self, img, info, is_single, single_id_img, req_id):
        if req_id != self._render_req_id:
            return
        self.current_preview_image = img
        self.current_single_id = single_id_img
        self.is_single_view = is_single

        self.preview_info.setText(info)
        self.lbl_dims.setText(f"输出分辨率: {img.size[0]} × {img.size[1]} px · 300 DPI")

        vw = max(100, self.preview.width() - 20)
        vh = max(100, self.preview.height() - 20)

        pix = pil_to_pixmap(img)
        scaled_pix = pix.scaled(vw, vh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled_pix)

    def on_render_error(self, err_msg, req_id):
        if req_id != self._render_req_id:
            return
        self.status.setText("渲染异常")
        self.preview_info.setText(f"❌ 错误：{err_msg}")

    def on_color_changed(self, btn_id):
        self.schedule_render()

    def pick_custom_color(self):
        c = QColorDialog.getColor(QColor("#ffffff"), self, "选取自定义证件照底色")
        if c.isValid():
            rgb = (c.red(), c.green(), c.blue())
            hex_c = c.name()
            custom_data = {"key": "custom", "name": f"自定义 ({hex_c})", "rgb": rgb, "hex": hex_c}
            if len(self.colors_data) > 6:
                self.colors_data[6] = custom_data
            else:
                self.colors_data.append(custom_data)
            btn = self.color_btn_group.button(self.color_btn_group.buttons()[-1].id() if hasattr(self.color_btn_group.buttons()[-1], 'id') else 0)
            self.color_btn_group.buttons()[-1].setChecked(True)
            self.schedule_render()

    def on_mode_changed(self, idx):
        self.paper_container.setVisible(idx in (1, 3, 4))
        self.ori_container.setVisible(idx in (1, 3, 4))
        self.mix_container.setVisible(idx == 2)
        self.custom_mix_container.setVisible(idx == 3)
        self.grid_container.setVisible(idx == 4)
        self.opt_aux_box.setVisible(idx != 0)
        self.schedule_render()

    def reset_framing(self):
        self.slider_zoom.setValue(100)
        self.slider_pos_y.setValue(0)
        self.slider_pos_x.setValue(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_preview_image:
            vw = max(100, self.preview.width() - 20)
            vh = max(100, self.preview.height() - 20)
            pix = pil_to_pixmap(self.current_preview_image)
            scaled_pix = pix.scaled(vw, vh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(scaled_pix)

    def export_image(self):
        if not self.current_preview_image:
            QMessageBox.warning(self, "提示", "请先导入照片并生成预览")
            return

        last_dir = self.settings.value("last_dir", os.path.expanduser("~/Pictures"))
        d = QFileDialog.getExistingDirectory(self, "选择保存文件夹", last_dir)
        if not d:
            return
        self.settings.setValue("last_dir", d)

        base_name = "证件照"
        if self.input_path:
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]

        s_dict = self.size_combo.currentData() or core.load_sizes()[0]
        s_name = s_dict["name"]
        color_id = self.color_btn_group.checkedId()
        c_dict = self.colors_data[color_id] if (0 <= color_id < len(self.colors_data)) else self.colors_data[0]
        c_name = c_dict["name"].split(" ")[0]

        exp_fmt = self.combo_export_fmt.currentData()

        saved_files = []
        try:
            if self.is_single_view:
                p_png = os.path.join(d, f"{base_name}_{s_name}_{c_name}_单张.png")
                p_jpg = os.path.join(d, f"{base_name}_{s_name}_{c_name}_单张.jpg")
                if exp_fmt in ("both", "png"):
                    self.current_preview_image.save(p_png, "PNG")
                    saved_files.append(p_png)
                if exp_fmt in ("both", "jpg"):
                    self.current_preview_image.save(p_jpg, "JPEG", quality=95)
                    saved_files.append(p_jpg)
            else:
                p_sheet_png = os.path.join(d, f"{base_name}_{s_name}_{c_name}_相纸冲印排版.png")
                p_sheet_jpg = os.path.join(d, f"{base_name}_{s_name}_{c_name}_相纸冲印排版.jpg")
                if exp_fmt in ("both", "png"):
                    self.current_preview_image.save(p_sheet_png, "PNG")
                    saved_files.append(p_sheet_png)
                if exp_fmt in ("both", "jpg"):
                    self.current_preview_image.save(p_sheet_jpg, "JPEG", quality=95)
                    saved_files.append(p_sheet_jpg)

            QMessageBox.information(
                self, "导出成功",
                f"已成功保存 {len(saved_files)} 份高清文件至：\n{d}\n\n文件列表：\n" + "\n".join([os.path.basename(f) for f in saved_files])
            )
            self.status.setText(f"✓ 已导出至: {os.path.basename(saved_files[0])}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存出错：{e}")

    def open_batch_dialog(self):
        dlg = BatchDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.save_user_settings()
        for th in list(self._running_threads):
            if th.isRunning():
                th.quit()
                th.wait(300)
        super().closeEvent(event)


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f6f8fa"))
    palette.setColor(QPalette.WindowText, QColor("#1f2328"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f6f8fa"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#1f2328"))
    palette.setColor(QPalette.Text, QColor("#1f2328"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#1f2328"))
    palette.setColor(QPalette.Highlight, QColor("#0969da"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    icon_path = os.path.join(PROJECT_ROOT, "app.icns") if sys.platform == "darwin" else os.path.join(PROJECT_ROOT, "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    w = MainWindow()
    w.show()
    w.raise_()
    w.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
