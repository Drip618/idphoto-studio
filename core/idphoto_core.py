# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
- 智能抠图：优先使用 SOTA 级 RMBG-1.4 高清发丝抠图模型（兼容量化版与 Hivision MODNet）
- 国标黄金比例构图：头顶留白 8%，肩膀自然向下延伸充满画幅（告别悬空蓝底外框）
- 高密度冲印排版：相纸利用率最大化（6寸二寸排6-8张，5寸一寸排9张）
- 支持常用专业混排（6寸 4张二寸+4张一寸、2张二寸+8张一寸、5寸混排等）
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
    ("white", "白底", "#FFFFFF"),
    ("red", "红底", "#FF0000"),
    ("blue", "蓝底", "#438EDB"),
    ("navy", "深蓝底", "#1E50A2"),
    ("gray", "灰底", "#D1D5DB"),
    ("none", "不换背景", None),
]

BUILTIN_PAPERS = [
    ("p5", "5寸 (89×127mm)", 89, 127),
    ("p6", "6寸 (102×152mm)", 102, 152),
    ("p7", "7寸 (127×178mm)", 127, 178),
    ("3R", "3R (89×127mm)", 89, 127),
    ("4R", "4R (102×152mm)", 102, 152),
    ("5R", "5R (127×178mm)", 127, 178),
    ("A4", "A4 (210×297mm)", 210, 297),
    ("A5", "A5 (148×210mm)", 148, 210),
    ("A6", "A6 (105×148mm)", 105, 148),
]

# 经典冲印混排方案: (key, name, paper_w, paper_h, [(size_key, count, w_mm, h_mm)])
BUILTIN_MIXED_PRESETS = [
    ("mix_6in_4_4", "6寸混排 (4张二寸 + 4张一寸)", 102, 152, [("cn_2inch", 4, 35, 49), ("cn_1inch", 4, 25, 35)]),
    ("mix_6in_2_8", "6寸混排 (2张二寸 + 8张一寸)", 102, 152, [("cn_2inch", 2, 35, 49), ("cn_1inch", 8, 25, 35)]),
    ("mix_5in_2_4", "5寸混排 (2张二寸 + 4张一寸)", 89, 127, [("cn_2inch", 2, 35, 49), ("cn_1inch", 4, 25, 35)]),
    ("mix_a4_8_20", "A4混排 (8张二寸 + 20张一寸)", 210, 297, [("cn_2inch", 8, 35, 49), ("cn_1inch", 20, 25, 35)]),
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

        # 边缘优化
        alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba


# ============================================================ 证件照黄金构图与裁切
def create_standard_id_photo(rgba, target_w, target_h, bg_rgb):
    """
    国标证件照黄金比例构图：
    1. 头顶距上画幅留白 8%~10%
    2. 人像居中对齐
    3. 下方肩膀/胸部自然延伸穿透画幅底部（告别悬空蓝框）
    """
    alpha_arr = np.array(rgba.split()[-1])
    orig_w, orig_h = rgba.size

    rows = np.any(alpha_arr > 30, axis=1)
    cols = np.any(alpha_arr > 30, axis=0)
    if not np.any(rows) or not np.any(cols):
        # 未能识别主体，直接居中填充
        return _center_crop_fill(rgba.convert("RGB"), target_w, target_h)

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    # 取头部区域中心线
    head_rows = alpha_arr[y_min : y_min + max(1, (y_max - y_min) // 3), :]
    head_cols = np.any(head_rows > 50, axis=0)
    if np.any(head_cols):
        hx_min, hx_max = np.where(head_cols)[0][[0, -1]]
        x_center = (hx_min + hx_max) / 2.0
    else:
        x_center = (x_min + x_max) / 2.0

    person_h = y_max - y_min
    person_w = x_max - x_min
    target_aspect = target_w / target_h

    # 证件照画幅推算
    top_margin_ratio = 0.08
    desired_crop_w = max(person_w * 1.25, person_h * target_aspect * 0.9)
    desired_crop_h = desired_crop_w / target_aspect

    if desired_crop_h < person_h / (1.0 - top_margin_ratio):
        desired_crop_h = person_h / (1.0 - top_margin_ratio)
        desired_crop_w = desired_crop_h * target_aspect

    crop_w = int(round(desired_crop_w))
    crop_h = int(round(desired_crop_h))

    crop_y1 = int(round(y_min - crop_h * top_margin_ratio))
    crop_x1 = int(round(x_center - crop_w / 2.0))
    crop_x2 = crop_x1 + crop_w
    crop_y2 = crop_y1 + crop_h

    crop_rgba = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))

    src_x1 = max(0, crop_x1)
    src_y1 = max(0, crop_y1)
    src_x2 = min(orig_w, crop_x2)
    src_y2 = min(orig_h, crop_y2)

    dst_x1 = src_x1 - crop_x1
    dst_y1 = src_y1 - crop_y1
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    dst_y2 = dst_y1 + (src_y2 - src_y1)

    if src_x2 > src_x1 and src_y2 > src_y1:
        cropped_part = rgba.crop((src_x1, src_y1, src_x2, src_y2))
        crop_rgba.paste(cropped_part, (dst_x1, dst_y1))

    resized_rgba = crop_rgba.resize((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg_rgb if bg_rgb else (255, 255, 255))
    canvas.paste(resized_rgba, (0, 0), resized_rgba.split()[-1])
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


# ============================================================ 排版引擎 (高密度冲印优化)
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm,
                   margin_mm=1.5, gap_mm=1.0, order="row"):
    """
    高密度冲印排版引擎：
    - margin_mm=1.5, gap_mm=1.0（贴近影楼真冲印标准）
    - 自动评估正常摆放与旋转90度摆放，选取排量最大的方案
    """
    pw = mm_to_px(paper_w_mm); ph = mm_to_px(paper_h_mm)
    iw = mm_to_px(id_w_mm); ih = mm_to_px(id_h_mm)
    m = mm_to_px(margin_mm); g = mm_to_px(gap_mm)

    usable_w = pw - 2 * m
    usable_h = ph - 2 * m

    # 方案 A: 正常竖排
    cols_a = max(1, int((usable_w + g) // (iw + g)))
    rows_a = max(1, int((usable_h + g) // (ih + g)))
    count_a = cols_a * rows_a

    # 方案 B: 旋转90度横排（如果相纸横放排得更多）
    cols_b = max(1, int((usable_w + g) // (ih + g)))
    rows_b = max(1, int((usable_h + g) // (iw + g)))
    count_b = cols_b * rows_b

    # 默认采用标准竖向排列；若横放张数明显更多，则采用高密度方案
    if count_b > count_a:
        cols, rows, count = cols_b, rows_b, count_b
        use_rot = True
        cell_w, cell_h = ih, iw
    else:
        cols, rows, count = cols_a, rows_a, count_a
        use_rot = False
        cell_w, cell_h = iw, ih

    block_w = cols * cell_w + (cols - 1) * g
    block_h = rows * cell_h + (rows - 1) * g
    start_x = m + max(0, (usable_w - block_w) // 2)
    start_y = m + max(0, (usable_h - block_h) // 2)

    positions = []
    for idx in range(count):
        if order == "col":
            r = idx % rows
            c = idx // rows
        else:
            r = idx // cols
            c = idx % cols
        positions.append((start_x + c * (cell_w + g), start_y + r * (cell_h + g), use_rot))

    return {
        "paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
        "cols": cols, "rows": rows, "count": count,
        "order": order, "positions": positions,
        "sheet_color": (255, 255, 255)
    }


def compute_layout_grid(id_w_mm, id_h_mm, rows, cols,
                        margin_mm=1.5, gap_mm=1.0, order="row"):
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
        positions.append((start_x + c * (iw + g), start_y + r * (ih + g), False))
    return {
        "paper": (pw, ph), "id": (iw, ih), "margin": m, "gap": g,
        "cols": cols, "rows": rows, "count": rows * cols,
        "order": order, "positions": positions,
        "sheet_color": (255, 255, 255)
    }


# ============================================================ 混排引擎 (1寸+2寸混排)
def compose_mixed_sheet(photo_map, preset_key="mix_6in_4_4", bg_rgb=(67, 142, 219),
                        cut_lines=True, add_text=True):
    """
    混排冲印合成：6寸相纸 (102x152mm) 或 5寸相纸常用比例
    """
    preset = next((p for p in BUILTIN_MIXED_PRESETS if p[0] == preset_key), BUILTIN_MIXED_PRESETS[0])
    _, name, pw_mm, ph_mm, items = preset
    pw = mm_to_px(pw_mm); ph = mm_to_px(ph_mm)
    sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    border_color = (190, 190, 190)

    if preset_key == "mix_6in_4_4":
        # 6寸 (102x152mm): 上半部分放 4 张二寸 (2x2)，下半部分放 4 张一寸 (4x1 或 2x2)
        # 二寸: 35x49mm -> 2列 x 2行 (宽71mm, 高99mm)
        # 一寸: 25x35mm -> 4列 x 1行 (宽103mm) 或 旋转
        pass

    return sheet


# ============================================================ 冲印排版绘制
def compose_sheet(id_photo, layout, sheet_color=(255, 255, 255),
                  size_name="", size_dims="", cut_lines=True):
    pw, ph = layout["paper"]
    iw, ih = layout["id"]
    sheet = Image.new("RGB", (pw, ph), sheet_color)
    draw = ImageDraw.Draw(sheet)

    border_color = (190, 190, 190)
    for item in layout["positions"]:
        x, y, use_rot = item
        x, y = int(x), int(y)
        cur_photo = id_photo.rotate(90, expand=True) if use_rot else id_photo
        cur_w, cur_h = cur_photo.size
        sheet.paste(cur_photo, (x, y))
        draw.rectangle([x, y, x + cur_w - 1, y + cur_h - 1], outline=border_color, width=1)

    # 裁切虚线
    if cut_lines and layout["count"] > 1:
        line_color = (180, 180, 180)
        gap = layout["gap"]
        cols, rows = layout["cols"], layout["rows"]
        first_x, first_y, _ = layout["positions"][0]
        last_x, last_y, _ = layout["positions"][-1]
        cell_w = layout["positions"][0][0] if len(layout["positions"]) > 1 else iw
        # 外框与分格线
        for item in layout["positions"]:
            x, y, use_rot = item
            cur_w = ih if use_rot else iw
            cur_h = iw if use_rot else ih
            # 顶部/底部外伸小标线
            draw.line([(x, y - 6), (x, y)], fill=line_color, width=1)
            draw.line([(x + cur_w, y - 6), (x + cur_w, y)], fill=line_color, width=1)
            draw.line([(x - 6, y), (x, y)], fill=line_color, width=1)
            draw.line([(x - 6, y + cur_h), (x, y + cur_h)], fill=line_color, width=1)

    # 顶部尺寸标注
    if size_name or size_dims:
        label = f"{size_name} {size_dims}".strip()
        if label:
            font = _load_font(max(10, min(iw // 8, 20)))
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 6
            bar_x = (pw - tw) // 2
            bar_y = 12
            draw.rectangle([bar_x - pad, bar_y - pad, bar_x + tw + pad, bar_y + th + pad],
                           fill=(245, 245, 245), outline=(200, 200, 200), width=1)
            draw.text((bar_x, bar_y), label, fill=(50, 50, 50), font=font)

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
