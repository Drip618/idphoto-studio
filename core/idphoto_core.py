# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
- 智能抠图：SOTA 级 BRIA RMBG-1.4 高清发丝抠图模型（1024x1024 亚像素精度，发丝边缘极致纯净）
- 照相馆自然标准证件照构图 (Studio Natural Framing)：
  - 完整呈现头顶、人脸、五官、下巴、脖子、衣领与双肩展开
  - 支持人像缩放 (zoom_ratio) 与 上下/左右 位置微调 (offset_y, offset_x)
- 照相馆规范相纸排版：
  - 5寸相纸 (89x127mm 竖版): 上2张二寸 + 下6张一寸 (3列x2行，共8张满幅)
  - 6寸横版 (152x102mm): 左4张二寸 (2x2) + 右6张一寸 (3x2) (共10张，照相馆最畅销冲印版)
  - 6寸竖版 (102x152mm): 上4张二寸 (2x2) + 下6张一寸 (3x2) (共10张)
  - 6寸多一寸 (102x152mm): 上2张二寸 (1x2) + 下8张一寸 (4x2) (共10张)
  - 支持强制横版 / 强制竖版 / 自动最优朝向
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
    "modnet_photographic_portrait_matting.onnx",
]


def mm_to_px(mm):
    return int(round(mm * PX_PER_MM))


def px_to_mm(px):
    return round(px / PX_PER_MM, 1)


# ============================================================ 内置常用证件照规格
BUILTIN_SIZES = [
    # 常用中国标准
    ("cn_1inch", "一寸 (25×35mm) - 中国标准", "常用", 25, 35),
    ("cn_2inch", "二寸 (35×49mm) - 中国标准", "常用", 35, 49),
    ("cn_1inch_s", "小一寸 (22×32mm) - 驾驶证/表格", "常用", 22, 32),
    ("cn_1inch_l", "大一寸 (33×48mm) - 中国护照/签证", "常用", 33, 48),
    ("cn_2inch_s", "小二寸 (35×45mm) - 护照通用", "常用", 35, 45),
    ("cn_2inch_l", "大二寸 (35×53mm) - 部分专业证书", "常用", 35, 53),
    ("cn_3inch", "三寸 (55×84mm)", "常用", 55, 84),
    ("cn_5inch", "五寸 (89×127mm) - 证件档案", "常用", 89, 127),

    # 国际护照与签证
    ("visa_us", "美国签证 (51×51mm / 2×2英寸)", "国际签证", 51, 51),
    ("visa_schengen", "申根/欧洲签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_jp", "日本签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_kr", "韩国签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_uk", "英国签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_ca", "加拿大签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_au", "澳大利亚签证 (35×45mm)", "国际签证", 35, 45),
    ("visa_sg", "新加坡签证 (35×45mm)", "国际签证", 35, 45),

    # 考试与职业资格
    ("exam_teacher", "教师资格证 (25×35mm)", "考试考证", 25, 35),
    ("exam_cet", "英语四六级 CET (240×320px)", "考试考证", 20, 27),
    ("exam_ncre", "计算机二级 NCRE (33×48mm)", "考试考证", 33, 48),
    ("exam_civil", "国考/省考公务员 (35×45mm)", "考试考证", 35, 45),
    ("exam_postgrad", "全国考研网报 (35×45mm)", "考试考证", 35, 45),
    ("exam_driver", "机动车驾驶证 (22×32mm)", "考试考证", 22, 32),
    ("exam_social_sec", "社保卡/医保卡 (26×32mm)", "考试考证", 26, 32),
    ("exam_law", "法律职业资格 (35×45mm)", "考试考证", 35, 45),
    ("exam_account", "初级/中级会计 (25×35mm)", "考试考证", 25, 35),
]

# ============================================================ 内置常用冲印相纸 (5寸置顶，从小到大规范排列)
BUILTIN_PAPERS = [
    ("p5", "5寸 (89×127mm) - 照相馆常用相纸 (3R)", 89, 127),
    ("p6", "6寸 (102×152mm) - 最主流冲印相纸 (4R)", 102, 152),
    ("p7", "7寸 (127×178mm) - 常用大相纸 (5R)", 127, 178),
    ("p8", "8寸 (152×203mm) - 8R", 152, 203),
    ("p10", "10寸 (203×254mm) - 10R", 203, 254),
    ("A4", "A4 (210×297mm) - 普通办公打印纸", 210, 297),
    ("A5", "A5 (148×210mm) - A4半张", 148, 210),
    ("A6", "A6 (105×148mm) - A4四分之一", 105, 148),
    ("3R", "3R相纸 (89×127mm)", 89, 127),
    ("4R", "4R相纸 (102×152mm)", 102, 152),
    ("5R", "5R相纸 (127×178mm)", 127, 178),
]

# ============================================================ 内置证件照标准底色
BUILTIN_COLORS = [
    ("blue", "蓝色 (标准冲印蓝)", (67, 142, 219), "#438edb"),
    ("red", "红色 (标准证件红)", (255, 0, 0), "#ff0000"),
    ("white", "白色 (标准白底)", (255, 255, 255), "#ffffff"),
    ("dark_blue", "深蓝 (港澳通行证)", (18, 59, 145), "#123b91"),
    ("gray", "灰色 (高端证件灰)", (219, 222, 227), "#dbdee3"),
    ("orig", "原图 (不换背景)", None, "#e2e8f0"),
]


def _size_to_dict(t):
    key, name, cat, w_mm, h_mm = t
    return {
        "key": key,
        "name": name,
        "category": cat,
        "w_mm": w_mm,
        "h_mm": h_mm,
        "w_px": mm_to_px(w_mm),
        "h_px": mm_to_px(h_mm),
    }


def _paper_to_dict(t):
    key, name, w_mm, h_mm = t
    return {
        "key": key,
        "name": name,
        "w_mm": w_mm,
        "h_mm": h_mm,
        "w_px": mm_to_px(w_mm),
        "h_px": mm_to_px(h_mm),
    }


def _color_to_dict(t):
    key, name, rgb, hex_c = t
    return {
        "key": key,
        "name": name,
        "rgb": rgb,
        "hex": hex_c,
    }


def load_sizes():
    return [_size_to_dict(t) for t in BUILTIN_SIZES] + PresetManager().sizes()


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

    def colors(self):
        out = []
        for c in self.data["colors"]:
            out.append({"key": "u_" + c["name"], "name": c["name"],
                        "rgb": tuple(c["rgb"]), "hex": c["hex"]})
        return out

    def add_color(self, name, rgb, hex_c):
        self.data["colors"].append({"name": name, "rgb": list(rgb), "hex": hex_c})
        self._save()

    def remove_color(self, name):
        self.data["colors"] = [c for c in self.data["colors"] if c["name"] != name]
        self._save()


# ============================================================ 智能抠图管线 (纯正 SOTA RMBG-1.4 高清模型)
class Matting:
    def __init__(self):
        self._session = None
        self._model_path = self.locate_model_path()

    @staticmethod
    def locate_model_path():
        for name in MODEL_NAMES:
            cands = []
            if getattr(sys, "frozen", False):
                base = getattr(sys, "_MEIPASS", None)
                if base:
                    cands.append(os.path.join(base, "weights", name))
            cands.append(os.path.join(PROJECT_ROOT, "weights", name))
            cands.append(os.path.join(USER_WEIGHTS_DIR, name))
            for p in cands:
                if os.path.exists(p):
                    return p
        return None

    def available(self):
        return self._model_path is not None and os.path.exists(self._model_path)

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        if not self.available():
            raise RuntimeError("未找到抠图模型，请选择「原图」仅排版。")
        import onnxruntime as ort
        self._session = ort.InferenceSession(self._model_path, providers=["CPUExecutionProvider"])
        return self._session

    def remove(self, image):
        sess = self._ensure_session()
        inp = sess.get_inputs()[0]
        orig_w, orig_h = image.size

        is_rmbg = "rmbg" in os.path.basename(self._model_path).lower()

        if is_rmbg:
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

        alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba


# ============================================================ 照相馆自然标准证件照构图 (Studio Natural Framing)
def create_standard_id_photo(rgba, target_w, target_h, bg_rgb, zoom_ratio=1.0, offset_y_ratio=0.0, offset_x_ratio=0.0):
    """
    照相馆自然半身胸像标准证件照构图：
    1. 保持原图半身人像的完整优雅形态：头顶留白约 8%~10%，下巴、脖子、领口、双肩自然展开
    2. 支持 zoom_ratio 人像缩放调节 (默认 1.0)
    3. 支持 offset_y_ratio / offset_x_ratio 上下左右位置微调
    4. 白底照片自带 1px 细微浅灰外边框，防止与白纸融为一体
    """
    alpha_arr = np.array(rgba.split()[-1])
    orig_w, orig_h = rgba.size

    rows = np.where(np.any(alpha_arr > 25, axis=1))[0]
    if len(rows) == 0:
        return _center_crop_fill(rgba.convert("RGB"), target_w, target_h)

    y_top = rows[0]
    y_bot = rows[-1]
    person_h = max(100, y_bot - y_top)

    # 扫描头部中心线
    head_scan_h = min(800, max(100, int(person_h * 0.4)))
    head_slice = alpha_arr[y_top : y_top + head_scan_h, :]
    head_cols = np.where(np.any(head_slice > 45, axis=0))[0]
    if len(head_cols) > 0:
        face_cx = (head_cols[0] + head_cols[-1]) / 2.0
    else:
        face_cx = orig_w / 2.0

    # 照相馆自然胸像基准比例：半身像高度在相片中占约 91%
    base_scale = (target_h * 0.91) / person_h
    scale = base_scale * zoom_ratio

    scaled_w = max(1, int(round(orig_w * scale)))
    scaled_h = max(1, int(round(orig_h * scale)))
    scaled_rgba = rgba.resize((scaled_w, scaled_h), Image.LANCZOS)

    # 水平居中 + 微调
    scaled_cx = int(round(face_cx * scale))
    paste_x = int(round((target_w / 2.0) - scaled_cx + target_w * offset_x_ratio))

    # 垂直位置：头顶位于相片 8% 处 + 微调
    scaled_ytop = int(round(y_top * scale))
    paste_y = int(round(target_h * 0.08 - scaled_ytop + target_h * offset_y_ratio))

    canvas = Image.new("RGB", (target_w, target_h), bg_rgb if bg_rgb else (255, 255, 255))
    canvas.paste(scaled_rgba, (paste_x, paste_y), scaled_rgba.split()[-1])

    # 如果是白底，绘制极细的 1px 浅灰色外边框 (防止白纸打印时融为一体)
    if bg_rgb == (255, 255, 255):
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, 0, target_w - 1, target_h - 1], outline=(220, 220, 220), width=1)

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


def prepare_id_photo(image, id_w_px, id_h_px, bg_rgb, matting=None, zoom_ratio=1.0, offset_y_ratio=0.0, offset_x_ratio=0.0):
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA") if image.mode != "RGBA" else image.copy()

    if bg_rgb is not None and matting is not None:
        try:
            rgba = matting.remove(image)
            return create_standard_id_photo(rgba, id_w_px, id_h_px, bg_rgb, zoom_ratio, offset_y_ratio, offset_x_ratio)
        except Exception:
            pass

    return _center_crop_fill(image.convert("RGB"), id_w_px, id_h_px)


# ============================================================ 照相馆规范舒适冲印排版算法 (单规格)
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm, orientation="auto"):
    """
    orientation: "auto" / "landscape" / "portrait"
    """
    p_min = min(paper_w_mm, paper_h_mm)
    p_max = max(paper_w_mm, paper_h_mm)

    if orientation == "landscape":
        candidate_orientations = [(p_max, p_min)]
    elif orientation == "portrait":
        candidate_orientations = [(p_min, p_max)]
    else:
        candidate_orientations = [(p_max, p_min), (p_min, p_max)]

    standards = {
        # 5寸竖版: 89 x 127 mm -> 一寸 9 张 (3x3), 二寸 4 张 (2x2)
        (89, 127, 25, 35): {"paper_w": 89, "paper_h": 127, "cols": 3, "rows": 3, "count": 9, "gap": 1.5, "margin": 5.0},
        (89, 127, 35, 49): {"paper_w": 89, "paper_h": 127, "cols": 2, "rows": 2, "count": 4, "gap": 2.0, "margin": 6.0},
        # 5寸横版: 127 x 89 mm -> 一寸 8 张 (4x2), 二寸 2 张
        (127, 89, 25, 35): {"paper_w": 127, "paper_h": 89, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.5},
        (127, 89, 35, 49): {"paper_w": 127, "paper_h": 89, "cols": 3, "rows": 1, "count": 3, "gap": 2.0, "margin": 5.0},

        # 6寸横版: 152 x 102 mm -> 一寸 16 张 (4x4) 或 8 张舒适版, 二寸 8 张 (4x2)
        (152, 102, 25, 35): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.5, "margin": 4.0},
        (152, 102, 35, 49): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.0},
        # 6寸竖版: 102 x 152 mm -> 一寸 12 张 (3x4), 二寸 4 张 (2x2)
        (102, 152, 25, 35): {"paper_w": 102, "paper_h": 152, "cols": 3, "rows": 4, "count": 12, "gap": 1.5, "margin": 4.0},
        (102, 152, 35, 49): {"paper_w": 102, "paper_h": 152, "cols": 2, "rows": 2, "count": 4, "gap": 2.0, "margin": 6.0},

        # 7寸: 178 x 127 mm
        (178, 127, 25, 35): {"paper_w": 178, "paper_h": 127, "cols": 4, "rows": 3, "count": 12, "gap": 1.5, "margin": 4.0},
        (178, 127, 35, 49): {"paper_w": 178, "paper_h": 127, "cols": 4, "rows": 2, "count": 8, "gap": 2.0, "margin": 5.0},

        # A4: 210 x 297 mm
        (210, 297, 25, 35): {"paper_w": 210, "paper_h": 297, "cols": 6, "rows": 6, "count": 36, "gap": 2.0, "margin": 8.0},
        (210, 297, 35, 49): {"paper_w": 210, "paper_h": 297, "cols": 4, "rows": 4, "count": 16, "gap": 3.0, "margin": 10.0},
    }

    best = None
    for (w_p, h_p) in candidate_orientations:
        match = standards.get((w_p, h_p, id_w_mm, id_h_mm))
        if match:
            if best is None or match["count"] > best["count"]:
                best = match
        else:
            for g in [1.5, 1.0, 0.8]:
                for m in [5.0, 4.0, 3.0, 2.0]:
                    cols_c = int((w_p - 2 * m + g) // (id_w_mm + g))
                    rows_c = int((h_p - 2 * m + g) // (id_h_mm + g))
                    if cols_c >= 1 and rows_c >= 1:
                        cnt = cols_c * rows_c
                        if best is None or cnt > best["count"]:
                            best = {"paper_w": w_p, "paper_h": h_p, "cols": cols_c, "rows": rows_c,
                                    "count": cnt, "gap": g, "margin": m}

    if best:
        pw, ph = best["paper_w"], best["paper_h"]
        cols, rows, count = best["cols"], best["rows"], best["count"]
        gap, margin = best["gap"], best["margin"]
    else:
        pw, ph = candidate_orientations[0]
        cols, rows, count = 1, 1
        gap, margin = 1.0, 2.0

    return {
        "paper": (mm_to_px(pw), mm_to_px(ph)),
        "paper_w_mm": pw,
        "paper_h_mm": ph,
        "id_w_mm": id_w_mm,
        "id_h_mm": id_h_mm,
        "id_w_px": mm_to_px(id_w_mm),
        "id_h_px": mm_to_px(id_h_mm),
        "cols": cols,
        "rows": rows,
        "count": count,
        "gap_px": mm_to_px(gap),
        "margin_px": mm_to_px(margin),
    }


def compute_layout_grid(id_w_mm, id_h_mm, rows, cols, paper_w_mm=89, paper_h_mm=127, gap_mm=1.0, margin_mm=3.0):
    req_w_mm = cols * id_w_mm + (cols - 1) * gap_mm + 2 * margin_mm
    req_h_mm = rows * id_h_mm + (rows - 1) * gap_mm + 2 * margin_mm

    fits = False
    best_pw, best_ph = paper_w_mm, paper_h_mm
    for pw, ph in [(paper_w_mm, paper_h_mm), (paper_h_mm, paper_w_mm)]:
        if req_w_mm <= pw and req_h_mm <= ph:
            fits = True
            best_pw, best_ph = pw, ph
            break

    if not fits:
        best_pw, best_ph = (max(paper_w_mm, paper_h_mm), min(paper_w_mm, paper_h_mm)) if req_w_mm > req_h_mm else (min(paper_w_mm, paper_h_mm), max(paper_w_mm, paper_h_mm))

    return {
        "paper": (mm_to_px(best_pw), mm_to_px(best_ph)),
        "paper_w_mm": best_pw,
        "paper_h_mm": best_ph,
        "id_w_mm": id_w_mm,
        "id_h_mm": id_h_mm,
        "id_w_px": mm_to_px(id_w_mm),
        "id_h_px": mm_to_px(id_h_mm),
        "cols": cols,
        "rows": rows,
        "count": rows * cols,
        "gap_px": mm_to_px(gap_mm),
        "margin_px": mm_to_px(margin_mm),
        "fits": fits,
        "req_w_mm": round(req_w_mm, 1),
        "req_h_mm": round(req_h_mm, 1),
    }


def _draw_dashed_rect(draw, x1, y1, x2, y2, color=(190, 190, 190), dash=8, space=5):
    for x in range(x1, x2, dash + space):
        draw.line([(x, y1), (min(x + dash, x2), y1)], fill=color, width=1)
        draw.line([(x, y2), (min(x + dash, x2), y2)], fill=color, width=1)
    for y in range(y1, y2, dash + space):
        draw.line([(x1, y), (x1, min(y + dash, y2))], fill=color, width=1)
        draw.line([(x2, y), (x2, min(y + dash, y2))], fill=color, width=1)


def compose_sheet(id_photo, layout, sheet_color=(255, 255, 255),
                  size_name="", size_dims="", cut_lines=True):
    pw, ph = layout["paper"]
    iw, ih = layout["id_w_px"], layout["id_h_px"]
    cols, rows = layout["cols"], layout["rows"]
    gap = layout["gap_px"]

    sheet = Image.new("RGB", (pw, ph), sheet_color)
    draw = ImageDraw.Draw(sheet)

    grid_w = cols * iw + (cols - 1) * gap
    grid_h = rows * ih + (rows - 1) * gap
    ox = (pw - grid_w) // 2
    oy = (ph - grid_h) // 2

    # 1. 贴照片 + 外框
    border_color = (200, 200, 200)
    for r in range(rows):
        for c in range(cols):
            x = ox + c * (iw + gap)
            y = oy + r * (ih + gap)
            sheet.paste(id_photo, (x, y))

            draw.rectangle([x, y, x + iw - 1, y + ih - 1], outline=border_color, width=1)
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + iw - 1, y + ih - 1, color=(185, 185, 185))

    # 2. 十字裁切延伸线
    if cut_lines:
        mark_color = (160, 160, 160)
        mark_len = 16
        for c in range(cols + 1):
            x = ox + c * (iw + gap) - (gap // 2 if c > 0 and c < cols else 0)
            draw.line([(x, oy - mark_len), (x, oy - 2)], fill=mark_color, width=1)
            draw.line([(x, oy + grid_h + 2), (x, oy + grid_h + mark_len)], fill=mark_color, width=1)
        for r in range(rows + 1):
            y = oy + r * (ih + gap) - (gap // 2 if r > 0 and r < rows else 0)
            draw.line([(ox - mark_len, y), (ox - 2, y)], fill=mark_color, width=1)
            draw.line([(ox + grid_w + 2, y), (ox + grid_w + mark_len, y)], fill=mark_color, width=1)

    # 3. 顶部相纸与尺寸规范水印
    if size_name:
        txt = f"{size_name} · {size_dims} · 300DPI 标准冲印"
        try:
            draw.text((ox, max(4, oy - 20)), txt, fill=(150, 150, 150))
        except Exception:
            pass

    return sheet


# ============================================================ 照相馆标准规整混排冲印
def compose_mixed_sheet(id_1in, id_2in, mix_type="6in_landscape_4_6", cut_lines=True, add_text=True):
    """
    照相馆标准规整混排：
    - 6in_landscape_4_6: 6寸横版金牌满幅 (152x102mm) -> 左4张二寸(2x2) + 右6张一寸(3x2) (共10张，最畅销)
    - 6in_portrait_4_6: 6寸竖版满幅 (102x152mm) -> 上4张二寸(2x2) + 下6张一寸(3x2) (共10张)
    - 5in_portrait_2_6: 5寸竖版满幅 (89x127mm) -> 上2张二寸(1x2) + 下6张一寸(3x2) (共8张)
    - 6in_portrait_2_8: 6寸多一寸混排 (102x152mm) -> 上2张二寸(1x2) + 下8张一寸(4x2) (共10张)
    """
    w_2in, h_2in = mm_to_px(35), mm_to_px(49)
    w_1in, h_1in = mm_to_px(25), mm_to_px(35)
    border_color = (200, 200, 200)

    if mix_type == "6in_landscape_4_6" or mix_type == "6in_4_6":
        # 6寸横版: 152 x 102 mm -> 左边 4张二寸 (2x2), 右边 6张一寸 (3x2)
        pw, ph = mm_to_px(152), mm_to_px(102)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(0.8)
        gap_sec = mm_to_px(3.5)

        left_w = w_2in * 2 + gap
        left_h = h_2in * 2 + gap
        right_w = w_1in * 3 + gap * 2
        right_h = h_1in * 2 + gap

        total_w = left_w + gap_sec + right_w
        ox = (pw - total_w) // 2

        # 左边 4张二寸
        oy_left = (ph - left_h) // 2
        for r in range(2):
            for c in range(2):
                x = ox + c * (w_2in + gap)
                y = oy_left + r * (h_2in + gap)
                sheet.paste(id_2in, (x, y))
                draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 右边 6张一寸
        ox_right = ox + left_w + gap_sec
        oy_right = (ph - right_h) // 2
        for r in range(2):
            for c in range(3):
                x = ox_right + c * (w_1in + gap)
                y = oy_right + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"6寸横版金牌混排 · 4张二寸 + 6张一寸 (共10张) · {pw}×{ph} px"
        return sheet, info

    elif mix_type == "6in_portrait_4_6" or mix_type == "6in_4_4":
        # 6寸竖版: 102 x 152 mm -> 上边 4张二寸 (2x2), 下边 6张一寸 (3x2)
        pw, ph = mm_to_px(102), mm_to_px(152)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(4.0)

        top_w = w_2in * 2 + gap
        top_h = h_2in * 2 + gap
        bot_w = w_1in * 3 + gap * 2
        bot_h = h_1in * 2 + gap

        total_h = top_h + gap_sec + bot_h
        oy = (ph - total_h) // 2

        # 上部 4张二寸
        ox_top = (pw - top_w) // 2
        for r in range(2):
            for c in range(2):
                x = ox_top + c * (w_2in + gap)
                y = oy + r * (h_2in + gap)
                sheet.paste(id_2in, (x, y))
                draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 下部 6张一寸
        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(3):
                x = ox_bot + c * (w_1in + gap)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"6寸竖版混排 · 4张二寸 + 6张一寸 (共10张) · {pw}×{ph} px"
        return sheet, info

    elif mix_type == "5in_portrait_2_6" or mix_type == "5in_2_6" or mix_type == "5in_2_4":
        # 5寸竖版: 89 x 127 mm -> 上2张二寸 (1x2) + 下6张一寸 (3x2)
        pw, ph = mm_to_px(89), mm_to_px(127)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(4.0)

        top_w = w_2in * 2 + gap
        top_h = h_2in
        bot_w = w_1in * 3 + gap * 2
        bot_h = h_1in * 2 + gap

        total_h = top_h + gap_sec + bot_h
        oy = (ph - total_h) // 2

        # 上部 2张二寸
        ox_top = (pw - top_w) // 2
        for c in range(2):
            x = ox_top + c * (w_2in + gap)
            y = oy
            sheet.paste(id_2in, (x, y))
            draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
            if cut_lines: _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 下部 6张一寸
        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(3):
                x = ox_bot + c * (w_1in + gap)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"5寸标准混排 · 2张二寸 + 6张一寸 (共8张) · {pw}×{ph} px"
        return sheet, info

    else: # 6in_portrait_2_8 多一寸版
        pw, ph = mm_to_px(102), mm_to_px(152)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(5.0)

        top_w = w_2in * 2 + gap
        top_h = h_2in
        gap_1in = mm_to_px(0.5)
        bot_w = w_1in * 4 + gap_1in * 3
        bot_h = h_1in * 2 + gap

        total_h = top_h + gap_sec + bot_h
        oy = (ph - total_h) // 2

        ox_top = (pw - top_w) // 2
        for c in range(2):
            x = ox_top + c * (w_2in + gap)
            y = oy
            sheet.paste(id_2in, (x, y))
            draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
            if cut_lines: _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(4):
                x = ox_bot + c * (w_1in + gap_1in)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines: _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"6寸多一寸混排 · 2张二寸 + 8张一寸 (共10张) · {pw}×{ph} px"
        return sheet, info


# ============================================================ 自由多尺寸自定义混排装箱引擎
def compose_custom_mixed_sheet(images_dict, counts_dict, paper_dict, cut_lines=True, orientation="auto"):
    pw_mm, ph_mm = paper_dict["w_mm"], paper_dict["h_mm"]
    dims_map = {
        "2in": (35, 49, "二寸"),
        "1in": (25, 35, "一寸"),
        "s_1in": (22, 32, "小一寸"),
        "l_2in": (35, 53, "大二寸"),
    }

    active_groups = []
    total_req_count = 0
    for k in ["2in", "1in", "s_1in", "l_2in"]:
        cnt = counts_dict.get(k, 0)
        if cnt > 0 and k in images_dict and k in dims_map:
            w_mm, h_mm, tag = dims_map[k]
            active_groups.append({
                "key": k, "w_mm": w_mm, "h_mm": h_mm,
                "count": cnt, "img": images_dict[k], "tag": tag
            })
            total_req_count += cnt

    if not active_groups:
        pw_px, ph_px = mm_to_px(pw_mm), mm_to_px(ph_mm)
        sheet = Image.new("RGB", (pw_px, ph_px), (255, 255, 255))
        return sheet, "请在左侧设定各尺寸冲印数量", True

    p_min = min(pw_mm, ph_mm)
    p_max = max(pw_mm, ph_mm)

    if orientation == "landscape":
        candidate_orientations = [(p_max, p_min)]
    elif orientation == "portrait":
        candidate_orientations = [(p_min, p_max)]
    else:
        candidate_orientations = [(p_max, p_min), (p_min, p_max)]

    best_sol = None

    for margin_m in [2.5, 2.0, 1.5, 1.0]:
        for gap_grp_m in [4.0, 3.0, 2.0, 1.0]:
            for gap_m in [0.8, 0.5]:
                for pw_m, ph_m in candidate_orientations:
                    avail_w = pw_m - 2 * margin_m
                    avail_h = ph_m - 2 * margin_m

                    if len(active_groups) == 1:
                        g = active_groups[0]
                        for cols in range(1, g["count"] + 1):
                            rows = (g["count"] + cols - 1) // cols
                            bw = cols * g["w_mm"] + (cols - 1) * gap_m
                            bh = rows * g["h_mm"] + (rows - 1) * gap_m
                            if bw <= avail_w and bh <= avail_h:
                                placed = []
                                ox_b = (pw_m - bw) / 2.0
                                oy_b = (ph_m - bh) / 2.0
                                idx = 0
                                for r in range(rows):
                                    for c in range(cols):
                                        if idx < g["count"]:
                                            x = ox_b + c * (g["w_mm"] + gap_m)
                                            y = oy_b + r * (g["h_mm"] + gap_m)
                                            placed.append((x, y, g["w_mm"], g["h_mm"], g["img"], g["tag"]))
                                            idx += 1
                                area_used = g["count"] * g["w_mm"] * g["h_mm"]
                                sol = {"pw": pw_m, "ph": ph_m, "fits": True, "items": placed,
                                       "util": area_used / (pw_m * ph_m), "count": g["count"]}
                                if best_sol is None or sol["util"] > best_sol["util"]:
                                    best_sol = sol

                    elif len(active_groups) == 2:
                        g1, g2 = active_groups[0], active_groups[1]
                        # 策略 A: 上下分段
                        for cols1 in range(1, g1["count"] + 1):
                            rows1 = (g1["count"] + cols1 - 1) // cols1
                            bw1 = cols1 * g1["w_mm"] + (cols1 - 1) * gap_m
                            bh1 = rows1 * g1["h_mm"] + (rows1 - 1) * gap_m
                            if bw1 > avail_w: continue

                            for cols2 in range(1, g2["count"] + 1):
                                rows2 = (g2["count"] + cols2 - 1) // cols2
                                bw2 = cols2 * g2["w_mm"] + (cols2 - 1) * gap_m
                                bh2 = rows2 * g2["h_mm"] + (rows2 - 1) * gap_m
                                if bw2 > avail_w: continue

                                total_h = bh1 + gap_grp_m + bh2
                                total_w = max(bw1, bw2)
                                if total_w <= avail_w and total_h <= avail_h:
                                    oy = (ph_m - total_h) / 2.0
                                    ox1 = (pw_m - bw1) / 2.0
                                    ox2 = (pw_m - bw2) / 2.0

                                    placed = []
                                    idx = 0
                                    for r in range(rows1):
                                        for c in range(cols1):
                                            if idx < g1["count"]:
                                                x = ox1 + c * (g1["w_mm"] + gap_m)
                                                y = oy + r * (g1["h_mm"] + gap_m)
                                                placed.append((x, y, g1["w_mm"], g1["h_mm"], g1["img"], g1["tag"]))
                                                idx += 1
                                    idx = 0
                                    oy2 = oy + bh1 + gap_grp_m
                                    for r in range(rows2):
                                        for c in range(cols2):
                                            if idx < g2["count"]:
                                                x = ox2 + c * (g2["w_mm"] + gap_m)
                                                y = oy2 + r * (g2["h_mm"] + gap_m)
                                                placed.append((x, y, g2["w_mm"], g2["h_mm"], g2["img"], g2["tag"]))
                                                idx += 1

                                    area_used = g1["count"] * g1["w_mm"] * g1["h_mm"] + g2["count"] * g2["w_mm"] * g2["h_mm"]
                                    sol = {"pw": pw_m, "ph": ph_m, "fits": True, "items": placed,
                                           "util": area_used / (pw_m * ph_m), "count": len(placed)}
                                    if best_sol is None or sol["util"] > best_sol["util"]:
                                        best_sol = sol

                        # 策略 B: 左右分段
                        for cols1 in range(1, g1["count"] + 1):
                            rows1 = (g1["count"] + cols1 - 1) // cols1
                            bw1 = cols1 * g1["w_mm"] + (cols1 - 1) * gap_m
                            bh1 = rows1 * g1["h_mm"] + (rows1 - 1) * gap_m
                            if bh1 > avail_h: continue

                            for cols2 in range(1, g2["count"] + 1):
                                rows2 = (g2["count"] + cols2 - 1) // cols2
                                bw2 = cols2 * g2["w_mm"] + (cols2 - 1) * gap_m
                                bh2 = rows2 * g2["h_mm"] + (rows2 - 1) * gap_m
                                if bh2 > avail_h: continue

                                total_w = bw1 + gap_grp_m + bw2
                                total_h = max(bh1, bh2)
                                if total_w <= avail_w and total_h <= avail_h:
                                    ox = (pw_m - total_w) / 2.0
                                    oy1 = (ph_m - bh1) / 2.0
                                    oy2 = (ph_m - bh2) / 2.0

                                    placed = []
                                    idx = 0
                                    for r in range(rows1):
                                        for c in range(cols1):
                                            if idx < g1["count"]:
                                                x = ox + c * (g1["w_mm"] + gap_m)
                                                y = oy1 + r * (g1["h_mm"] + gap_m)
                                                placed.append((x, y, g1["w_mm"], g1["h_mm"], g1["img"], g1["tag"]))
                                                idx += 1
                                    idx = 0
                                    ox2 = ox + bw1 + gap_grp_m
                                    for r in range(rows2):
                                        for c in range(cols2):
                                            if idx < g2["count"]:
                                                x = ox2 + c * (g2["w_mm"] + gap_m)
                                                y = oy2 + r * (g2["h_mm"] + gap_m)
                                                placed.append((x, y, g2["w_mm"], g2["h_mm"], g2["img"], g2["tag"]))
                                                idx += 1

                                    area_used = g1["count"] * g1["w_mm"] * g1["h_mm"] + g2["count"] * g2["w_mm"] * g2["h_mm"]
                                    sol = {"pw": pw_m, "ph": ph_m, "fits": True, "items": placed,
                                           "util": area_used / (pw_m * ph_m), "count": len(placed)}
                                    if best_sol is None or sol["util"] > best_sol["util"]:
                                        best_sol = sol

                    if best_sol and best_sol.get("fits"): break
                if best_sol and best_sol.get("fits"): break
            if best_sol and best_sol.get("fits"): break

    if best_sol is None or not best_sol.get("fits"):
        pw_m, ph_m = candidate_orientations[0]
        margin_m = 2.0
        gap_m = 0.8

        flat_items = []
        for g in sorted(active_groups, key=lambda x: (x["h_mm"], x["w_mm"]), reverse=True):
            for _ in range(g["count"]):
                flat_items.append((g["w_mm"], g["h_mm"], g["img"], g["tag"]))

        placed = []
        cur_x = margin_m
        cur_y = margin_m
        row_h = 0
        fits = True
        for w_m, h_m, im, tg in flat_items:
            if cur_x + w_m > pw_m - margin_m:
                cur_x = margin_m
                cur_y += row_h + gap_m
                row_h = 0
            if cur_y + h_m > ph_m - margin_m:
                fits = False
                break
            placed.append((cur_x, cur_y, w_m, h_m, im, tg))
            cur_x += w_m + gap_m
            if h_m > row_h:
                row_h = h_m

        area_used = sum(it[2] * it[3] for it in placed)
        best_sol = {"pw": pw_m, "ph": ph_m, "fits": fits, "items": placed,
                    "util": area_used / (pw_m * ph_m), "count": len(placed)}

    pw_px = mm_to_px(best_sol["pw"])
    ph_px = mm_to_px(best_sol["ph"])
    sheet = Image.new("RGB", (pw_px, ph_px), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    border_color = (200, 200, 200)

    for x_m, y_m, w_m, h_m, img, tag in best_sol["items"]:
        x = mm_to_px(x_m)
        y = mm_to_px(y_m)
        iw = mm_to_px(w_m)
        ih = mm_to_px(h_m)
        if img:
            sheet.paste(img, (x, y))
        draw.rectangle([x, y, x + iw - 1, y + ih - 1], outline=border_color, width=1)
        if cut_lines:
            _draw_dashed_rect(draw, x, y, x + iw - 1, y + ih - 1)

    if best_sol["fits"]:
        info = f"自定义混排成功 · 共 {best_sol['count']} 张 · {best_sol['pw']}×{best_sol['ph']}mm (利用率 {best_sol['util']*100:.1f}%)"
    else:
        info = f"⚠️ 超出相纸容量！已排 {best_sol['count']}/{total_req_count} 张，请减少数量或更换大相纸"

    return sheet, info, best_sol["fits"]
