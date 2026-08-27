# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
- 智能抠图：SOTA 级 RMBG-1.4 高清发丝抠图模型（1024x1024 亚像素精度，彻底剔除暗斑）
- 照相馆标准证件照构图：头顶留白 8%，人像底部贴死画幅边缘（绝无悬空底边）
- 高密度冲印排版：智能相纸朝向自适应（6寸排8张二寸/16张一寸，5寸排10张一寸/4张二寸）
- 常用混排冲印：6寸相纸 (4张二寸 + 4张一寸，全正立直放，不旋转)
"""

import os
import sys
import json
import csv
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
USER_CONFIG_DIR = os.path.expanduser("~/.idphoto_studio")
USER_CONFIG = os.path.join(USER_CONFIG_DIR, "user_presets.json")
USER_WEIGHTS_DIR = os.path.join(USER_CONFIG_DIR, "weights")

DPI = 300
PX_PER_MM = DPI / 25.4

MODEL_NAMES = [
    "rmbg_quantized.onnx",
    "hivision_modnet.onnx",
    "modnet_photographic_portrait_matting.onnx"
]


def mm_to_px(mm):
    return int(round(mm * PX_PER_MM))


# ============================================================ 尺寸库
BUILTIN_SIZES = [
    ("cn_1inch", "一寸", "中国标准", 25, 35),
    ("cn_2inch", "二寸", "中国标准", 35, 49),
    ("cn_1inch_s", "小一寸", "中国标准", 22, 32),
    ("cn_2inch_s", "小二寸", "中国标准", 35, 45),
    ("cn_1inch_l", "大一寸", "中国标准", 33, 48),
    ("cn_2inch_l", "大二寸", "中国标准", 35, 53),
    ("cn_id", "身份证(冲洗)", "中国标准", 26, 32),
    ("cn_dl", "驾驶证", "中国标准", 22, 32),
    ("cn_passport", "中国护照", "中国标准", 33, 48),
    ("cn_hk_mo", "港澳通行证", "中国标准", 33, 48),
    ("cn_tw", "台湾通行证", "中国标准", 33, 48),
    ("cn_visa", "签证(通用)", "中国标准", 33, 48),
    ("cn_marry", "结婚证", "中国标准", 35, 49),
    ("cn_resume", "简历求职", "中国标准", 25, 35),
    ("us_passport", "美国护照/签证", "国际", 51, 51),
    ("us_green", "美国绿卡", "国际", 51, 51),
    ("eu_schengen", "申根签证", "国际", 35, 45),
    ("jp_visa", "日本签证/护照", "国际", 35, 45),
    ("kr_visa", "韩国签证/护照", "国际", 35, 45),
    ("uk_passport", "英国护照/签证", "国际", 35, 45),
    ("ca_passport", "加拿大护照", "国际", 50, 70),
    ("au_visa", "澳洲签证/护照", "国际", 35, 45),
    ("my_visa", "马来西亚签证", "国际", 35, 50),
    ("sg_visa", "新加坡签证", "国际", 35, 45),
    ("th_visa", "泰国签证", "国际", 35, 45),
]

BUILTIN_COLORS = [
    ("blue", "蓝底", "#438EDB"),
    ("red", "红底", "#FF0000"),
    ("white", "白底", "#FFFFFF"),
    ("navy", "深蓝底", "#1E50A2"),
    ("gray", "灰底", "#D1D5DB"),
    ("none", "不换背景", None),
]

BUILTIN_PAPERS = [
    ("p6", "6寸 (102×152mm)", 102, 152),
    ("p5", "5寸 (89×127mm)", 89, 127),
    ("p7", "7寸 (127×178mm)", 127, 178),
    ("3R", "3R (89×127mm)", 89, 127),
    ("4R", "4R (102×152mm)", 102, 152),
    ("5R", "5R (127×178mm)", 127, 178),
    ("A4", "A4 (210×297mm)", 210, 297),
    ("A5", "A5 (148×210mm)", 148, 210),
    ("A6", "A6 (105×148mm)", 105, 148),
]


def hex_to_rgb(h):
    if not h:
        return None
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


# ============================================================ 预设管理
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


# ============================================================ 智能抠图管线 (ONNX)
class Matting:
    def __init__(self, model_path=None):
        self.model_path = model_path or self._locate_model()
        self._session = None

    @staticmethod
    def _locate_model():
        cands = Matting.model_search_paths()
        for p in cands:
            if os.path.exists(p):
                return p
        return cands[-1] if cands else os.path.join(USER_WEIGHTS_DIR, MODEL_NAMES[0])

    @staticmethod
    def model_search_paths():
        paths = []
        for name in MODEL_NAMES:
            if getattr(sys, "frozen", False):
                base = getattr(sys, "_MEIPASS", None)
                if base:
                    paths.append(os.path.join(base, "weights", name))
            paths.append(os.path.join(PROJECT_ROOT, "weights", name))
            paths.append(os.path.join(USER_WEIGHTS_DIR, name))
        return paths

    def available(self):
        return os.path.exists(self.model_path)

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        if not self.available():
            raise RuntimeError("未找到抠图模型，请选择「不换背景」仅排版。")
        import onnxruntime as ort
        self._session = ort.InferenceSession(self.model_path, providers=["CPUExecutionProvider"])
        return self._session

    def remove(self, image):
        sess = self._ensure_session()
        inp = sess.get_inputs()[0]
        orig_w, orig_h = image.size

        is_rmbg = "rmbg" in os.path.basename(self.model_path).lower()

        if is_rmbg:
            # RMBG 1.4: 1024x1024 输入，亚像素发丝精细度
            target = 1024
            resized = image.resize((target, target), Image.BILINEAR).convert("RGB")
            arr = np.asarray(resized, dtype=np.float32) / 255.0
            arr = (arr - 0.5) / 1.0
            arr = arr.transpose(2, 0, 1)[None, ...]

            out = sess.run(None, {inp.name: arr})[0]
            alpha_raw = out[0, 0] if out.ndim == 4 else out[0]
            min_v, max_v = float(alpha_raw.min()), float(alpha_raw.max())
            if max_v > min_v:
                alpha_norm = (alpha_raw - min_v) / (max_v - min_v)
            else:
                alpha_norm = alpha_raw
            alpha = Image.fromarray((alpha_norm * 255).astype(np.uint8), mode="L").resize((orig_w, orig_h), Image.LANCZOS)
        else:
            # Hivision MODNet: 512x512 等比填充
            target = 512
            scale = target / max(orig_w, orig_h)
            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))
            resized = image.resize((new_w, new_h), Image.BILINEAR).convert("RGB")
            pad_left = (target - new_w) // 2
            pad_top = (target - new_h) // 2
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
            alpha_crop = alpha_full[pad_top:pad_top + new_h, pad_left:pad_left + new_w]
            alpha = Image.fromarray(alpha_crop, mode="L").resize((orig_w, orig_h), Image.LANCZOS)

        # 边缘平滑
        alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba


# ============================================================ 照相馆标准证件照黄金构图
def create_standard_id_photo(rgba, target_w, target_h, bg_rgb):
    """
    照相馆标准证件照构图规则：
    1. 人像底部（胸部/肩膀）绝对贴死目标相片底部边缘（y_bottom = target_h，绝不留悬空底边）
    2. 头顶距离相片顶部留白 8% (y_top = target_h * 0.08)
    3. 人像高度占整个相片高度的 92%
    4. 水平方向按头部与人像中心轴对称居中
    """
    alpha_arr = np.array(rgba.split()[-1])
    orig_w, orig_h = rgba.size

    rows = np.any(alpha_arr > 25, axis=1)
    cols = np.any(alpha_arr > 25, axis=0)
    if not np.any(rows) or not np.any(cols):
        return _center_crop_fill(rgba.convert("RGB"), target_w, target_h)

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    # 取头部区域 (顶部 1/3) 计算真实人脸中心线
    head_h = max(1, (y_max - y_min) // 3)
    head_rows = alpha_arr[y_min : y_min + head_h, :]
    head_cols = np.any(head_rows > 45, axis=0)
    if np.any(head_cols):
        hx_min, hx_max = np.where(head_cols)[0][[0, -1]]
        x_center = (hx_min + hx_max) / 2.0
    else:
        x_center = (x_min + x_max) / 2.0

    person_h = max(1, y_max - y_min)

    # 目标人像高度（占总画幅 92%）
    target_person_h = int(round(target_h * 0.92))
    scale = target_person_h / person_h

    # 等比缩放原图
    scaled_w = max(1, int(round(orig_w * scale)))
    scaled_h = max(1, int(round(orig_h * scale)))
    scaled_rgba = rgba.resize((scaled_w, scaled_h), Image.LANCZOS)

    scaled_x_center = int(round(x_center * scale))
    scaled_y_min = int(round(y_min * scale))

    # 创建底色画布
    canvas = Image.new("RGB", (target_w, target_h), bg_rgb if bg_rgb else (255, 255, 255))

    # 贴图位置：头顶在 8% 处，人像底部贴死画幅底边
    paste_y = int(round(target_h * 0.08)) - scaled_y_min
    paste_x = (target_w // 2) - scaled_x_center

    canvas.paste(scaled_rgba, (paste_x, paste_y), scaled_rgba.split()[-1])
    return canvas


def _center_crop_fill(img, target_w, target_h):
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def prepare_id_photo(image, id_w_px, id_h_px, bg_rgb, matting=None):
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA") if image.mode != "RGBA" else image.copy()

    if bg_rgb is not None and matting is not None:
        try:
            rgba = matting.remove(image)
            return create_standard_id_photo(rgba, id_w_px, id_h_px, bg_rgb)
        except Exception:
            pass

    return _center_crop_fill(image.convert("RGB"), id_w_px, id_h_px)


# ============================================================ 照相馆冲印实战高密度排版引擎
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm, order="row"):
    """
    自动评估竖放/横放相纸，以最大化冲印张数为目标计算最优排版（照相馆实战标准）。
    例如：
    - 6寸 (102x152mm) 排 二寸 (35x49mm) ➔ 8张 (4列x2行，横向满塞)
    - 6寸 (102x152mm) 排 一寸 (25x35mm) ➔ 16张 (4列x4行)
    - 5寸 (89x127mm)  排 一寸 (25x35mm) ➔ 10张 (5列x2行) 或 9张 (3列x3行)
    """
    best = None
    # 尝试两种相纸朝向 (竖版 / 横版)
    for (w_p, h_p) in [(paper_w_mm, paper_h_mm), (paper_h_mm, paper_w_mm)]:
        for g in [0.8, 0.5, 0.0]:
            for m in [1.5, 1.0, 0.5]:
                cols = int((w_p - 2 * m + g) // (id_w_mm + g))
                rows = int((h_p - 2 * m + g) // (id_h_mm + g))
                if cols >= 1 and rows >= 1:
                    cnt = cols * rows
                    if best is None or cnt > best["count"]:
                        best = {
                            "paper_w_mm": w_p, "paper_h_mm": h_p,
                            "cols": cols, "rows": rows, "count": cnt,
                            "margin_mm": m, "gap_mm": g
                        }

    pw = mm_to_px(best["paper_w_mm"])
    ph = mm_to_px(best["paper_h_mm"])
    iw = mm_to_px(id_w_mm)
    ih = mm_to_px(id_h_mm)
    m = mm_to_px(best["margin_mm"])
    g = mm_to_px(best["gap_mm"])
    cols = best["cols"]
    rows = best["rows"]
    count = best["count"]

    block_w = cols * iw + (cols - 1) * g
    block_h = rows * ih + (rows - 1) * g
    start_x = max(0, (pw - block_w) // 2)
    start_y = max(0, (ph - block_h) // 2)

    positions = []
    for idx in range(count):
        if order == "col":
            r = idx % rows
            c = idx // rows
        else:
            r = idx // cols
            c = idx % cols
        positions.append((start_x + c * (iw + g), start_y + r * (ih + g)))

    return {
        "paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
        "cols": cols, "rows": rows, "count": count,
        "order": order, "positions": positions,
        "sheet_color": (255, 255, 255),
        "paper_w_mm": best["paper_w_mm"], "paper_h_mm": best["paper_h_mm"]
    }


def compute_layout_grid(id_w_mm, id_h_mm, rows, cols, order="row"):
    iw = mm_to_px(id_w_mm); ih = mm_to_px(id_h_mm)
    m = mm_to_px(1.5); g = mm_to_px(1.0)
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
    return {
        "paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
        "cols": cols, "rows": rows, "count": rows * cols,
        "order": order, "positions": positions,
        "sheet_color": (255, 255, 255),
        "paper_w_mm": int(round(pw / PX_PER_MM)), "paper_h_mm": int(round(ph / PX_PER_MM))
    }


# ============================================================ 排版图生成绘制
def compose_sheet(id_photo, layout, sheet_color=(255, 255, 255),
                  size_name="", size_dims="", cut_lines=True):
    pw, ph = layout["paper"]
    iw, ih = layout["id"]
    sheet = Image.new("RGB", (pw, ph), sheet_color)
    draw = ImageDraw.Draw(sheet)

    border_color = (190, 190, 190)
    for (x, y) in layout["positions"]:
        x, y = int(x), int(y)
        sheet.paste(id_photo, (x, y))
        # 1px 细边框，防止白底照片融入白相纸
        draw.rectangle([x, y, x + iw - 1, y + ih - 1], outline=border_color, width=1)

    # 裁切参考十字线/标线
    if cut_lines and layout["count"] > 1:
        line_color = (180, 180, 180)
        gap = layout["gap"]
        cols, rows = layout["cols"], layout["rows"]
        # 外围角标线
        for (x, y) in layout["positions"]:
            draw.line([(x, y - 6), (x, y)], fill=line_color, width=1)
            draw.line([(x + iw, y - 6), (x + iw, y)], fill=line_color, width=1)
            draw.line([(x - 6, y), (x, y)], fill=line_color, width=1)
            draw.line([(x - 6, y + ih), (x, y + ih)], fill=line_color, width=1)

    # 顶部尺寸标注
    if size_name or size_dims:
        label = f"{size_name} {size_dims}".strip()
        if label:
            font = _load_font(16)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 5
            bar_x = (pw - tw) // 2
            bar_y = 10
            draw.rectangle([bar_x - pad, bar_y - pad, bar_x + tw + pad, bar_y + th + pad],
                           fill=(245, 245, 245), outline=(210, 210, 210), width=1)
            draw.text((bar_x, bar_y), label, fill=(50, 50, 50), font=font)

    return sheet


# ============================================================ 6寸常用混排 (4张2寸 + 4张1寸 全正立)
def compose_mixed_6in_sheet(id_1in, id_2in, cut_lines=True, add_text=True):
    """
    6寸相纸 (102x152mm) 冲印混排标准版：
    - 上方：4 张二寸 (2列 x 2行，全正立直放)
    - 下方：4 张一寸 (4列 x 1行，全正立直放)
    - 绝不旋转人像！整齐优雅充满相纸！
    """
    pw, ph = mm_to_px(102), mm_to_px(152) # 1205 x 1795 px
    sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    w_2in, h_2in = id_2in.size # 413 x 579
    w_1in, h_1in = id_1in.size # 295 x 413
    gap = int(round(1.0 * PX_PER_MM)) # 12px
    border_c = (190, 190, 190)

    # 1. 上半部 4 张二寸 (2列 x 2行)
    ox_2in = (pw - (w_2in * 2 + gap)) // 2
    oy_2in = 70
    for r in range(2):
        for c in range(2):
            x = ox_2in + c * (w_2in + gap)
            y = oy_2in + r * (h_2in + gap)
            sheet.paste(id_2in, (x, y))
            draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_c, width=1)

    # 2. 下半部 4 张一寸 (4列 x 1行，正立直放)
    ox_1in = (pw - (w_1in * 4)) // 2
    oy_1in = oy_2in + 2 * (h_2in + gap) + 24
    for c in range(4):
        x = ox_1in + c * w_1in
        y = oy_1in
        sheet.paste(id_1in, (x, y))
        draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_c, width=1)

    # 顶部标注
    if add_text:
        font = _load_font(16)
        label = "6寸冲印混排 · 4张二寸(35×49mm) + 4张一寸(25×35mm)"
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((pw - tw) // 2, 18), label, fill=(60, 60, 60), font=font)

    return sheet


def _load_font(size):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()
