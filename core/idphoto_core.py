# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
设计基线参考开源项目 HivisionIDPhotos（ONNX 抠图 + CSV 尺寸库 + PyInstaller 打包）。
本模块只做纯计算与数据处理，方便单测与复用：
  - 全量证件照尺寸库（中国 / 美国 / 欧盟 / 日韩 / 东南亚 / 考试 / 驾照 …）
  - 排版引擎：自动网格 / 自定义行列 / 按打印纸适配 / 序列排序（行优先·列优先）
  - 自定义预设管理：用户可自助增删尺寸与排版格式，持久化到用户配置
  - 换底管线：ONNX 抠图（懒加载 + 可替换为任意模型），无模型时纯排版兜底
"""

import os
import sys
import json
import csv

from PIL import ImageOps, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
USER_CONFIG_DIR = os.path.expanduser("~/.idphoto_studio")
USER_CONFIG = os.path.join(USER_CONFIG_DIR, "user_presets.json")
USER_WEIGHTS_DIR = os.path.join(USER_CONFIG_DIR, "weights")

DPI = 300
PX_PER_MM = DPI / 25.4


def mm_to_px(mm):
    return int(round(mm * PX_PER_MM))


# ============================================================ 尺寸库
# 每条: (key, 名称, 类别, 宽mm, 高mm)
BUILTIN_SIZES = [
    ("cn_1inch", "一寸", "中国标准", 25, 35),
    ("cn_2inch", "二寸", "中国标准", 35, 49),
    ("cn_1inch_s", "小一寸", "中国标准", 22, 32),
    ("cn_2inch_s", "小二寸", "中国标准", 35, 45),
    ("cn_1inch_l", "大一寸", "中国标准", 33, 48),
    ("cn_2inch_l", "大二寸", "中国标准", 35, 53),
    ("cn_id", "身份证(洗照)", "中国标准", 26, 32),
    ("cn_dl", "驾驶证", "中国标准", 22, 32),
    ("cn_passport", "中国护照", "中国标准", 33, 48),
    ("cn_hk_mo", "港澳通行证", "中国标准", 33, 48),
    ("cn_tw", "台湾通行证", "中国标准", 33, 48),
    ("cn_visa", "签证(通用)", "中国标准", 33, 48),
    ("cn_marry", "结婚证", "中国标准", 35, 49),
    ("cn_resume", "简历求职", "中国标准", 25, 35),
    ("us_passport", "美国护照/签证", "美国", 51, 51),
    ("us_green", "美国绿卡", "美国", 51, 51),
    ("us_dl", "美国驾照(通用)", "美国", 25, 30),
    ("eu_schengen", "申根签证", "欧盟/申根", 35, 45),
    ("eu_passport", "欧盟护照", "欧盟/申根", 35, 45),
    ("uk_passport", "英国护照/签证", "欧盟/申根", 35, 45),
    ("ru_visa", "俄罗斯签证", "欧盟/申根", 35, 45),
    ("jp_visa", "日本签证/护照", "日韩", 35, 45),
    ("kr_visa", "韩国签证/护照", "日韩", 35, 45),
    ("ca_visa", "加拿大签证", "加澳新", 35, 45),
    ("ca_passport", "加拿大护照", "加澳新", 50, 70),
    ("au_visa", "澳洲签证/护照", "加澳新", 35, 45),
    ("nz_visa", "新西兰签证", "加澳新", 35, 45),
    ("my_visa", "马来西亚", "东南亚", 35, 50),
    ("sg_visa", "新加坡", "东南亚", 35, 45),
    ("th_visa", "泰国", "东南亚", 35, 45),
    ("vn_visa", "越南", "东南亚", 35, 45),
    ("id_visa", "印尼", "东南亚", 35, 45),
    ("ph_visa", "菲律宾", "东南亚", 35, 45),
    ("in_passport", "印度护照", "东南亚", 35, 45),
    ("br_visa", "巴西", "其他", 35, 45),
    ("za_visa", "南非", "其他", 35, 45),
    ("tr_visa", "土耳其", "其他", 35, 45),
]

BUILTIN_COLORS = [
    ("white", "白底", "#FFFFFF"),
    ("red", "红底", "#FF0000"),
    ("blue", "蓝底", "#438EDB"),
    ("navy", "深蓝底", "#1E50A2"),
    ("gray", "灰底", "#C0C0C0"),
    ("none", "不换背景", None),
]

BUILTIN_PAPERS = [
    ("p5", "5寸 (127×89mm)", 127, 89),
    ("p6", "6寸 (152×102mm)", 152, 102),
    ("p7", "7寸 (178×127mm)", 178, 127),
    ("3R", "3R (89×127mm)", 89, 127),
    ("4R", "4R (102×152mm)", 102, 152),
    ("5R", "5R (127×178mm)", 127, 178),
    ("A4", "A4 (210×297mm)", 210, 297),
    ("A5", "A5 (148×210mm)", 148, 210),
    ("A6", "A6 (105×148mm)", 105, 148),
    ("L", "L (89×127mm)", 89, 127),
    ("2L", "2L (127×178mm)", 127, 178),
]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _size_to_dict(t):
    key, name, cat, w, h = t
    return {"key": key, "name": name, "category": cat,
            "w_mm": w, "h_mm": h, "w_px": mm_to_px(w), "h_px": mm_to_px(h)}


def _paper_to_dict(t):
    key, name, w, h = t
    return {"key": key, "name": name, "w_mm": w, "h_mm": h,
            "w_px": mm_to_px(w), "h_px": mm_to_px(h)}


def _color_to_dict(t):
    key, name, hexv = t
    return {"key": key, "name": name, "hex": hexv,
            "rgb": hex_to_rgb(hexv) if hexv else None}


def load_sizes(user_only=False):
    if user_only:
        return PresetManager().sizes()
    builtin = [_size_to_dict(t) for t in BUILTIN_SIZES]
    return builtin + PresetManager().sizes()


def load_papers():
    return [_paper_to_dict(t) for t in BUILTIN_PAPERS] + PresetManager().papers()


def load_colors():
    return [_color_to_dict(t) for t in BUILTIN_COLORS] + PresetManager().colors()


def search_sizes(keyword):
    kw = keyword.strip().lower()
    if not kw:
        return load_sizes()
    return [s for s in load_sizes()
            if kw in (s["name"] + s["category"] + s["key"]).lower()]


def size_by_name(name):
    for s in load_sizes():
        if s["name"] == name:
            return s
    return None


# ============================================================ 排版引擎
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm,
                   margin_mm=3.0, gap_mm=2.0, order="row"):
    """在给定打印纸上自动排满证件照。order: 'row' 行优先 / 'col' 列优先"""
    pw = mm_to_px(paper_w_mm); ph = mm_to_px(paper_h_mm)
    iw = mm_to_px(id_w_mm); ih = mm_to_px(id_h_mm)
    m = mm_to_px(margin_mm); g = mm_to_px(gap_mm)

    usable_w = pw - 2 * m
    usable_h = ph - 2 * m
    cols = max(1, int((usable_w + g) // (iw + g)))
    rows = max(1, int((usable_h + g) // (ih + g)))
    count = cols * rows

    block_w = cols * iw + (cols - 1) * g
    block_h = rows * ih + (rows - 1) * g
    start_x = m + (usable_w - block_w) // 2
    start_y = m + (usable_h - block_h) // 2

    positions = []
    for idx in range(count):
        if order == "col":
            r = idx % rows
            c = idx // rows
        else:
            r = idx // cols
            c = idx % cols
        positions.append((start_x + c * (iw + g), start_y + r * (ih + g)))

    return {"paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
            "cols": cols, "rows": rows, "count": count,
            "order": order, "positions": positions,
            "sheet_color": (255, 255, 255)}


def compute_layout_grid(id_w_mm, id_h_mm, rows, cols,
                        margin_mm=3.0, gap_mm=2.0, order="row"):
    """自定义行列排版：纸张按内容自动撑满。"""
    iw = mm_to_px(id_w_mm); ih = mm_to_px(id_h_mm)
    m = mm_to_px(margin_mm); g = mm_to_px(gap_mm)
    pw = cols * iw + (cols - 1) * g + 2 * m
    ph = rows * ih + (rows - 1) * g + 2 * m
    start_x = m; start_y = m
    positions = []
    for idx in range(rows * cols):
        if order == "col":
            r = idx % rows
            c = idx // rows
        else:
            r = idx // cols
            c = idx % cols
        positions.append((start_x + c * (iw + g), start_y + r * (ih + g)))
    return {"paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
            "cols": cols, "rows": rows, "count": rows * cols,
            "order": order, "positions": positions,
            "sheet_color": (255, 255, 255)}


# ============================================================ 自定义预设管理
class PresetManager:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if not os.path.exists(USER_CONFIG):
            return {"sizes": [], "papers": [], "colors": []}
        try:
            with open(USER_CONFIG, "r", encoding="utf-8") as f:
                d = json.load(f)
            d.setdefault("sizes", [])
            d.setdefault("papers", [])
            d.setdefault("colors", [])
            return d
        except Exception:
            return {"sizes": [], "papers": [], "colors": []}

    def _save(self):
        os.makedirs(USER_CONFIG_DIR, exist_ok=True)
        with open(USER_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def sizes(self):
        out = []
        for s in self.data["sizes"]:
            w, h = s["w_mm"], s["h_mm"]
            out.append({"key": s.get("key", s["name"]), "name": s["name"],
                        "category": s.get("category", "我的预设"),
                        "w_mm": w, "h_mm": h,
                        "w_px": mm_to_px(w), "h_px": mm_to_px(h)})
        return out

    def add_size(self, name, w_mm, h_mm, category="我的预设"):
        self.data["sizes"].append({"key": "u_" + name, "name": name,
                                   "category": category, "w_mm": w_mm, "h_mm": h_mm})
        self._save()

    def remove_size(self, name):
        self.data["sizes"] = [s for s in self.data["sizes"] if s["name"] != name]
        self._save()

    def papers(self):
        out = []
        for p in self.data["papers"]:
            w, h = p["w_mm"], p["h_mm"]
            out.append({"key": p.get("key", p["name"]), "name": p["name"],
                        "w_mm": w, "h_mm": h, "w_px": mm_to_px(w), "h_px": mm_to_px(h)})
        return out

    def add_paper(self, name, w_mm, h_mm):
        self.data["papers"].append({"key": "u_" + name, "name": name,
                                    "w_mm": w_mm, "h_mm": h_mm})
        self._save()

    def remove_paper(self, name):
        self.data["papers"] = [p for p in self.data["papers"] if p["name"] != name]
        self._save()

    def colors(self):
        out = []
        for c in self.data["colors"]:
            out.append({"key": c.get("key", c["name"]), "name": c["name"],
                        "hex": c["hex"], "rgb": hex_to_rgb(c["hex"]) if c["hex"] else None})
        return out

    def add_color(self, name, hexv):
        self.data["colors"].append({"key": "u_" + name, "name": name, "hex": hexv})
        self._save()

    def remove_color(self, name):
        self.data["colors"] = [c for c in self.data["colors"] if c["name"] != name]
        self._save()


# ============================================================ 换底管线（ONNX，懒加载）
class Matting:
    def __init__(self, model_path=None, model_type="modnet"):
        self.model_path = model_path or self._locate_model()
        self.model_type = model_type
        self._session = None

    @staticmethod
    def _locate_model():
        # 打包后优先用包内模型（开箱即用，无需用户自行下载）
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", None)
            if base:
                p = os.path.join(base, "weights",
                                 "modnet_photographic_portrait_matting.onnx")
                if os.path.exists(p):
                    return p
        # 开发态 / 用户目录兜底
        return os.path.join(USER_WEIGHTS_DIR, "modnet_photographic_portrait_matting.onnx")

    def available(self):
        return os.path.exists(self.model_path)

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        if not self.available():
            raise RuntimeError(
                "未找到抠图模型：%s\n请先运行 download_models.py 下载模型（约 25MB）。\n"
                "或选择「不换背景」仅做排版。" % self.model_path)
        import onnxruntime as ort
        self._session = ort.InferenceSession(self.model_path,
                                             providers=["CPUExecutionProvider"])
        return self._session

    def remove(self, image):
        from PIL import Image
        import numpy as np
        sess = self._ensure_session()
        inp = sess.get_inputs()[0]
        orig_w, orig_h = image.size

        # MODNet 固定输入 512x512。必须等比缩放 + pad，不能直接拉伸到 512x512，
        # 否则人脸会被压扁/拉长（这是之前输出变形的根本原因）。
        target = 512
        scale = target / max(orig_w, orig_h)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))

        resized = image.resize((new_w, new_h), Image.BILINEAR).convert("RGB")
        # pad 到 512x512，使用 ImageNet 均值灰（模型训练常见填充）
        pad_left = (target - new_w) // 2
        pad_top = (target - new_h) // 2
        pad_right = target - new_w - pad_left
        pad_bottom = target - new_h - pad_top
        padded = Image.new("RGB", (target, target), (128, 128, 128))
        padded.paste(resized, (pad_left, pad_top))

        arr = np.asarray(padded, dtype=np.float32)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr / 255.0 - mean) / std
        arr = arr.transpose(2, 0, 1)[None, ...]

        out = sess.run(None, {inp.name: arr})[0]
        alpha_full = out[0, 0] if out.ndim == 4 else out[0]
        alpha_full = (np.clip(alpha_full, 0, 1) * 255).astype(np.uint8)

        # 去掉 padding，还原到等比缩放后的尺寸
        alpha_crop = alpha_full[pad_top:pad_top + new_h, pad_left:pad_left + new_w]
        alpha = Image.fromarray(alpha_crop, mode="L").resize((orig_w, orig_h), Image.LANCZOS)

        # 轻微 morph 闭运算清理边缘噪点
        alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))

        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba


# ============================================================ 图像合成
def _center_crop_by_subject(rgba, target_w, target_h, bg_rgb):
    """以人像主体为中心，等比缩放后填充到目标证件照尺寸，不拉伸。
    按证件照惯例：主体高度约占照片高度 78%，头顶留约 7% 边距。"""
    from PIL import Image
    alpha = rgba.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        # 没抠出主体，直接居中裁切
        img = Image.new("RGB", rgba.size, bg_rgb)
        img.paste(rgba, (0, 0), alpha)
        return _center_crop(img, target_w, target_h)

    # 取主体 bbox 并加少量呼吸边距
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    pad = int(max(w, h) * 0.08)
    x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
    x2 = min(rgba.width, x2 + pad); y2 = min(rgba.height, y2 + pad)
    subj = rgba.crop((x1, y1, x2, y2))

    # 等比缩放：让人像高度占目标高度的 ~78%，留出头顶/下巴空白
    src_w, src_h = subj.size
    fill_ratio = 0.78
    scale = (target_h * fill_ratio) / src_h
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    # 若宽度超出，则按宽度限制
    if new_w > target_w:
        scale = target_w / src_w
        new_w = target_w
        new_h = max(1, round(src_h * scale))
    subj = subj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), bg_rgb)
    ox = (target_w - new_w) // 2
    # 头顶留白约 7%，证件照人头偏上
    oy = int(target_h * 0.07)
    # 保险：不能超出下边界
    if oy + new_h > target_h:
        oy = target_h - new_h
    canvas.paste(subj, (ox, oy), subj.split()[-1])
    return canvas


def _center_crop(img, target_w, target_h):
    from PIL import Image
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def prepare_id_photo(image, id_w_px, id_h_px, bg_rgb, matting=None):
    from PIL import Image
    # 自动校正手机/相机 EXIF 方向
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA") if image.mode != "RGBA" else image.copy()

    if bg_rgb is not None and matting is not None:
        try:
            rgba = matting.remove(image)
            return _center_crop_by_subject(rgba, id_w_px, id_h_px, bg_rgb)
        except Exception:
            # 抠图失败则退化为原图居中裁切
            pass

    img = image.convert("RGB")
    return _center_crop(img, id_w_px, id_h_px)


def _luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrasting_color(rgb):
    """返回与给定底色有足够对比度的文字/线条颜色。"""
    lum = _luminance(rgb)
    return (40, 40, 40) if lum > 128 else (220, 220, 220)


def compose_sheet(id_photo, layout, sheet_color=(255, 255, 255),
                  size_name="", size_dims="", cut_lines=True):
    from PIL import Image, ImageDraw, ImageFont
    pw, ph = layout["paper"]
    iw, ih = layout["id"]
    sheet = Image.new("RGB", (pw, ph), sheet_color)
    draw = ImageDraw.Draw(sheet)

    # 找一个能用的中文字体（Windows/macOS/Linux 常见路径）
    font = _load_font(max(10, min(iw // 8, 22)))
    small_font = _load_font(max(8, min(iw // 10, 16)))

    # 在每张照片位置贴图 + 细灰边框（防止白底融进白纸）
    border_color = (180, 180, 180)
    for (x, y) in layout["positions"]:
        x, y = int(x), int(y)
        sheet.paste(id_photo, (x, y))
        draw.rectangle([x, y, x + iw - 1, y + ih - 1], outline=border_color, width=1)

    # 裁切线：照片之间 + 整体外框
    if cut_lines and layout["count"] > 1:
        line_color = _contrasting_color(sheet_color)
        gap = layout["gap"]
        m = layout["margin"]
        cols, rows = layout["cols"], layout["rows"]
        start_x = layout["positions"][0][0]
        start_y = layout["positions"][0][1]
        end_x = start_x + cols * iw + (cols - 1) * gap
        end_y = start_y + rows * ih + (rows - 1) * gap

        # 水平裁切线（含外框）
        for r in range(rows + 1):
            y = start_y + r * (ih + gap)
            _draw_dashed_line(draw, start_x, y, end_x, y, line_color, dash=6, gap=4)
        # 垂直裁切线（含外框）
        for c in range(cols + 1):
            x = start_x + c * (iw + gap)
            _draw_dashed_line(draw, x, start_y, x, end_y, line_color, dash=6, gap=4)

    # 顶部尺寸标注
    if size_name or size_dims:
        label = " ".join(p for p in [size_name, ("%s" % size_dims) if size_dims else ""] if p)
        label = label.strip()
        if label:
            # 文字与背景条保持强对比
            if _luminance(sheet_color) < 200:
                text_color = (245, 245, 245)
                bar_color = (50, 50, 50)
            else:
                text_color = (40, 40, 40)
                bar_color = (230, 230, 230)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 8
            bar_x, bar_y = 14, 14
            draw.rectangle([bar_x - pad, bar_y - pad,
                            bar_x + tw + pad, bar_y + th + pad],
                           fill=bar_color, outline=text_color, width=1)
            draw.text((bar_x, bar_y), label, fill=text_color, font=font)

    return sheet


def _load_font(size):
    """尝试加载系统中文字体，失败则返回默认字体。"""
    from PIL import ImageFont
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",          # macOS
        "/System/Library/Fonts/STHeiti Light.ttc",      # macOS 备选
        "C:/Windows/Fonts/simhei.ttf",                  # Windows
        "C:/Windows/Fonts/msyh.ttc",                    # Windows 雅黑
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_dashed_line(draw, x1, y1, x2, y2, color, dash=6, gap=4):
    """用线段模拟虚线；PIL 没有原生虚线 API。"""
    if x1 == x2:
        # 垂直线
        y = min(y1, y2)
        end = max(y1, y2)
        while y < end:
            draw.line([(x1, y), (x1, min(y + dash, end))], fill=color, width=1)
            y += dash + gap
    else:
        # 水平线
        x = min(x1, x2)
        end = max(x1, x2)
        while x < end:
            draw.line([(x, y1), (min(x + dash, end), y1)], fill=color, width=1)
            x += dash + gap


def export_size_csv(path=None):
    path = path or os.path.join(USER_CONFIG_DIR, "size_list.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "name", "category", "w_mm", "h_mm", "w_px", "h_px"])
        for s in load_sizes():
            w.writerow([s["key"], s["name"], s["category"], s["w_mm"], s["h_mm"],
                        s["w_px"], s["h_px"]])
    return path


if __name__ == "__main__":
    print("内置尺寸数:", len(load_sizes()))
    print("内置打印纸:", [p["name"] for p in load_papers()])
    lay = compute_layout(152, 102, 25, 35)
    print("6寸排一寸:", lay["count"], "张", lay["cols"], "x", lay["rows"])
    lay2 = compute_layout_grid(25, 35, 3, 4)
    print("自定义3x4网格纸张(px):", lay2["paper"], "张数:", lay2["count"])
    pm = PresetManager()
    pm.add_size("测试尺寸", 30, 40)
    print("用户预设尺寸:", [s["name"] for s in pm.sizes()])
    pm.remove_size("测试尺寸")
    print("导出CSV:", export_size_csv())
