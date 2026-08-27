# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
- 智能抠图：SOTA 级 BRIA RMBG-1.4 高清发丝抠图模型（1024x1024 亚像素精度，发丝边缘极致纯净）
- 照相馆国标证件照构图 (Head-Centric Standard)：
  - 自动检测头部中轴线与头部几何比例（头高占相片 58%~62%，头顶留白 8%~10%）
  - 锁骨与上胸口自然饱满延伸，双肩完美对称，彻底根治右侧缺角与不对称
- 行业规范冲印排版：5寸/6寸置顶，舒适留白，带标准裁切虚线框与尺寸标线
- 照相馆经典混排冲印：
  - 5寸相纸 (上2张二寸 + 下4张一寸)：整齐对称满幅
  - 6寸相纸 (上4张二寸 + 下4张一寸)：经典多规格满幅
  - 6寸实用 (上2张二寸 + 下8张一寸)：多一寸高性价比版
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
    ("p5", "5寸 (89×127mm) - 照相馆常用相纸", 89, 127),
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


# ============================================================ 照相馆国标标准证件照构图 (Head-Centric Standard)
def create_standard_id_photo(rgba, target_w, target_h, bg_rgb):
    """
    照相馆国标证件照构图（Head-Centric Standard）：
    1. 自动定位头部头顶与耳朵两侧宽度
    2. 国标比例：头部在相片中饱满大方（头高占 58%~62%，头宽占 62%~68%）
    3. 裁切框下边缘刚好切至锁骨/胸口上方，双肩自然向两侧饱满延伸穿出画幅
    4. 彻底解决右侧缺角/衣服不对称与大片背景空白问题
    """
    alpha_arr = np.array(rgba.split()[-1])
    orig_w, orig_h = rgba.size

    rows = np.where(np.any(alpha_arr > 25, axis=1))[0]
    if len(rows) == 0:
        return _center_crop_fill(rgba.convert("RGB"), target_w, target_h)

    y_min = rows[0]

    # 扫描头部最大宽度点 (耳朵处)
    head_w_list = []
    for y in range(y_min, min(orig_h, y_min + 1200), 10):
        cols = np.where(alpha_arr[y, :] > 40)[0]
        if len(cols) > 0:
            head_w_list.append((y, cols[-1] - cols[0], (cols[0] + cols[-1]) / 2.0))

    if head_w_list:
        max_head_item = max(head_w_list, key=lambda x: x[1])
        ear_y, head_w, head_cx = max_head_item
    else:
        head_cx = orig_w / 2.0
        head_w = orig_w * 0.45

    # 照相馆国标构图法则：
    # 头部在画幅中的宽度占比约为 63% ~ 66% (两侧留白优雅舒适)
    # 头顶留白占相片高度的 8% ~ 10%
    aspect = target_w / target_h # 例如一寸 295/413 = 0.7143
    crop_h = int(round(head_w * 1.25 / 0.58))
    crop_w = int(round(crop_h * aspect))

    crop_x1 = int(round(head_cx - crop_w / 2.0))
    crop_x2 = crop_x1 + crop_w
    crop_y1 = int(round(y_min - crop_h * 0.08))
    crop_y2 = crop_y1 + crop_h

    # 截取原图
    crop_rgba = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))
    src_x1 = max(0, crop_x1); src_y1 = max(0, crop_y1)
    src_x2 = min(orig_w, crop_x2); src_y2 = min(orig_h, crop_y2)
    dst_x1 = src_x1 - crop_x1; dst_y1 = src_y1 - crop_y1
    dst_x2 = dst_x1 + (src_x2 - src_x1); dst_y2 = dst_y1 + (src_y2 - src_y1)

    if src_x2 > src_x1 and src_y2 > src_y1:
        part = rgba.crop((src_x1, src_y1, src_x2, src_y2))
        crop_rgba.paste(part, (dst_x1, dst_y1))

    scaled = crop_rgba.resize((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg_rgb if bg_rgb else (255, 255, 255))
    canvas.paste(scaled, (0, 0), scaled.split()[-1])

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


# ============================================================ 照相馆规范舒适冲印排版算法
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm):
    standards = {
        # 6寸相纸: 102 x 152 mm (横放 152 x 102)
        (102, 152, 25, 35): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.5, "margin": 4.0},
        (102, 152, 35, 49): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.0},
        (102, 152, 22, 32): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.5, "margin": 4.0},
        (102, 152, 33, 48): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.0},
        (102, 152, 35, 45): {"paper_w": 152, "paper_h": 102, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.0},

        # 5寸相纸: 89 x 127 mm (横放 127 x 89)
        (89, 127, 25, 35): {"paper_w": 127, "paper_h": 89, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.5},
        (89, 127, 35, 49): {"paper_w": 89, "paper_h": 127, "cols": 2, "rows": 2, "count": 4, "gap": 2.0, "margin": 5.0},
        (89, 127, 22, 32): {"paper_w": 127, "paper_h": 89, "cols": 4, "rows": 2, "count": 8, "gap": 1.2, "margin": 3.5},
        (89, 127, 33, 48): {"paper_w": 89, "paper_h": 127, "cols": 2, "rows": 2, "count": 4, "gap": 2.0, "margin": 5.0},
        (89, 127, 35, 45): {"paper_w": 89, "paper_h": 127, "cols": 2, "rows": 2, "count": 4, "gap": 2.0, "margin": 5.0},

        # 7寸相纸: 127 x 178 mm
        (127, 178, 25, 35): {"paper_w": 178, "paper_h": 127, "cols": 4, "rows": 3, "count": 12, "gap": 1.5, "margin": 4.0},
        (127, 178, 35, 49): {"paper_w": 178, "paper_h": 127, "cols": 4, "rows": 2, "count": 8, "gap": 2.0, "margin": 5.0},

        # A4相纸: 210 x 297 mm
        (210, 297, 25, 35): {"paper_w": 210, "paper_h": 297, "cols": 6, "rows": 6, "count": 36, "gap": 2.0, "margin": 8.0},
        (210, 297, 35, 49): {"paper_w": 210, "paper_h": 297, "cols": 4, "rows": 4, "count": 16, "gap": 3.0, "margin": 10.0},
    }

    match = standards.get((min(paper_w_mm, paper_h_mm), max(paper_w_mm, paper_h_mm), id_w_mm, id_h_mm))
    if match:
        pw, ph = match["paper_w"], match["paper_h"]
        cols, rows, count = match["cols"], match["rows"], match["count"]
        gap, margin = match["gap"], match["margin"]
    else:
        best = None
        for (w_p, h_p) in [(paper_w_mm, paper_h_mm), (paper_h_mm, paper_w_mm)]:
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
            pw, ph = paper_w_mm, paper_h_mm
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


def compute_layout_grid(id_w_mm, id_h_mm, rows, cols, paper_w_mm=102, paper_h_mm=152, gap_mm=1.0, margin_mm=3.0):
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


# ============================================================ 照相馆标准规整混排冲印 (上下分段·整齐对齐)
def compose_mixed_sheet(id_1in, id_2in, mix_type="5in_2_4", cut_lines=True, add_text=True):
    """
    照相馆标准规整混排：
    - 5寸竖版 (89x127mm): 上2张二寸 + 下4张一寸 (上下分段居中，满幅对齐)
    - 6寸竖版 (102x152mm): 上4张二寸 + 下4张一寸 (经典多规格)
    - 6寸多一寸 (102x152mm): 上2张二寸 + 下8张一寸 (2行4列)
    """
    w_2in, h_2in = mm_to_px(35), mm_to_px(49)
    w_1in, h_1in = mm_to_px(25), mm_to_px(35)
    border_color = (200, 200, 200)

    if mix_type == "5in_2_4":
        # 5寸竖版: 89 x 127 mm (1051 x 1500 px)
        pw, ph = mm_to_px(89), mm_to_px(127)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(4.0)

        # 上部: 2张二寸 (1行2列) -> 宽 71mm, 高 49mm
        top_w = w_2in * 2 + gap
        top_h = h_2in

        # 下部: 4张一寸 (2行2列) -> 宽 51mm, 高 71mm
        bot_w = w_1in * 2 + gap
        bot_h = h_1in * 2 + gap

        total_h = top_h + gap_sec + bot_h
        oy = (ph - total_h) // 2

        # 绘制上部 2张二寸
        ox_top = (pw - top_w) // 2
        for c in range(2):
            x = ox_top + c * (w_2in + gap)
            y = oy
            sheet.paste(id_2in, (x, y))
            draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 绘制下部 4张一寸
        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(2):
                x = ox_bot + c * (w_1in + gap)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"5寸标准混排 · 2张二寸 + 4张一寸 · {pw}×{ph} px"
        return sheet, info

    elif mix_type == "6in_4_4":
        # 6寸竖版: 102 x 152 mm (1205 x 1795 px)
        pw, ph = mm_to_px(102), mm_to_px(152)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(5.0)

        # 上部: 4张二寸 (2行2列) -> 宽 71mm, 高 99mm
        top_w = w_2in * 2 + gap
        top_h = h_2in * 2 + gap

        # 下部: 4张一寸 (1行4列) -> gap=0.5mm 宽 101.5mm <= 102mm
        gap_1in = mm_to_px(0.5)
        bot_w = w_1in * 4 + gap_1in * 3
        bot_h = h_1in

        total_h = top_h + gap_sec + bot_h
        oy = (ph - total_h) // 2

        ox_top = (pw - top_w) // 2
        for r in range(2):
            for c in range(2):
                x = ox_top + c * (w_2in + gap)
                y = oy + r * (h_2in + gap)
                sheet.paste(id_2in, (x, y))
                draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for c in range(4):
            x = ox_bot + c * (w_1in + gap_1in)
            y = oy_bot
            sheet.paste(id_1in, (x, y))
            draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"6寸标准混排 · 4张二寸 + 4张一寸 · {pw}×{ph} px"
        return sheet, info

    else: # 6in_2_8 多一寸版
        pw, ph = mm_to_px(102), mm_to_px(152)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        gap = mm_to_px(1.0)
        gap_sec = mm_to_px(5.0)

        # 上部: 2张二寸 (1行2列) -> 宽 71mm, 高 49mm
        top_w = w_2in * 2 + gap
        top_h = h_2in

        # 下部: 8张一寸 (2行4列) -> gap=0.5mm 宽 101.5mm, 高 71mm
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
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(4):
                x = ox_bot + c * (w_1in + gap_1in)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"6寸多一寸混排 · 2张二寸 + 8张一寸 · {pw}×{ph} px"
        return sheet, info


# ============================================================ 自由多尺寸自定义混排装箱引擎
def compose_custom_mixed_sheet(images_dict, counts_dict, paper_dict, cut_lines=True):
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

    best_sol = None

    for margin_m in [2.5, 2.0, 1.5, 1.0]:
        for gap_grp_m in [4.0, 3.0, 2.0, 1.0]:
            for gap_m in [0.8, 0.5]:
                # 尝试竖放与横放
                for pw_m, ph_m in [(min(pw_mm, ph_mm), max(pw_mm, ph_mm)), (max(pw_mm, ph_mm), min(pw_mm, ph_mm))]:
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
                        # 策略 A: 上下分段 (Vertical Partition) - 照相馆最规整推荐
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

                        # 策略 B: 左右分段 (Horizontal Partition)
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

                    if best_sol and best_sol.get("fits"):
                        break
                if best_sol and best_sol.get("fits"):
                    break
            if best_sol and best_sol.get("fits"):
                break

    # 兜底：2D 装箱
    if best_sol is None or not best_sol.get("fits"):
        pw_m, ph_m = min(pw_mm, ph_mm), max(pw_mm, ph_mm)
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
