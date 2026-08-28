# -*- coding: utf-8 -*-
"""
idphoto_core.py — 证件照换底色 + 排版打印 核心引擎（数据驱动，无 GUI 依赖）
=========================================================================
- 智能抠图：SOTA 级 BRIA RMBG-1.4 高清发丝抠图模型（1024x1024 亚像素精度，发丝边缘极致纯净）
- 照相馆自然标准半身证件照构图 (Studio Natural Framing)：
  - 完整呈现头顶、人脸、五官、下巴、脖子、衣领与双肩展开
  - 支持人像缩放 (zoom_ratio) 与 上下/左右 位置微调 (offset_y, offset_x)
- 照相馆规范相纸排版：
  - 6寸横版金牌满排 (152x102mm): 左4张二寸 (2x2) + 右8张横放一寸 (2x4) (共12张，左右齐平，照相馆最畅销冲印版)
  - 5寸竖版标准满排 (89x127mm): 上2张二寸 (1x2) + 下6张一寸 (3x2) (共8张满幅)
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


def load_presets():
    sizes = [_size_to_dict(t) for t in BUILTIN_SIZES]
    if os.path.exists(USER_CONFIG):
        try:
            with open(USER_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            custom_sizes = data.get("sizes", [])
            for c in custom_sizes:
                if "w_px" not in c:
                    c["w_px"] = mm_to_px(c["w_mm"])
                if "h_px" not in c:
                    c["h_px"] = mm_to_px(c["h_mm"])
                sizes.append(c)
        except Exception:
            pass
    return sizes


def load_papers():
    papers = [_paper_to_dict(t) for t in BUILTIN_PAPERS]
    if os.path.exists(USER_CONFIG):
        try:
            with open(USER_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            custom_papers = data.get("papers", [])
            for p in custom_papers:
                if "w_px" not in p:
                    p["w_px"] = mm_to_px(p["w_mm"])
                if "h_px" not in p:
                    p["h_px"] = mm_to_px(p["h_mm"])
                papers.append(p)
        except Exception:
            pass
    return papers


# ============================================================ 异常类定义
class MattingError(RuntimeError):
    pass


# ============================================================ 智能发丝抠图引擎
class Matting:
    def __init__(self, model_path=None):
        self.model_path = model_path or self._locate_model()
        self._session = None

    @staticmethod
    def _locate_model():
        for p in Matting.model_search_paths():
            if os.path.exists(p):
                return p
        return Matting.model_search_paths()[-1]

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
            raise MattingError(
                "未找到抠图模型。\n已搜索路径：\n%s\n请确认 weights/ 目录下存在模型文件。"
                % "\n".join(self.model_search_paths()[:4]))
        import onnxruntime as ort
        self._session = ort.InferenceSession(self.model_path,
                                             providers=["CPUExecutionProvider"])
        return self._session

    def remove(self, image):
        sess = self._ensure_session()
        inp = sess.get_inputs()[0]
        orig_w, orig_h = image.size
        is_rmbg = "rmbg" in os.path.basename(self.model_path).lower()

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

        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba

    # ---- 启动自检：模型是否真的可用（防止打包漏模型却静默出废片）----
    def self_check(self, test_size=64):
        """返回 (ok, message)。用合成图验证模型能产出非退化的 alpha。"""
        if not self.available():
            return False, "模型文件缺失，未打进包或未下载：\n%s" % self.model_path
        try:
            import onnxruntime as ort
        except Exception as e:
            return False, "onnxruntime 未安装/无法导入：%s" % e
        try:
            self._ensure_session()
        except Exception as e:
            return False, "模型加载失败（可能 ORT 版本不兼容量化算子）：%s" % e
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (test_size, test_size), (0, 0, 0))
            d = ImageDraw.Draw(img)
            r = test_size // 4
            d.ellipse([test_size // 2 - r, test_size // 2 - r,
                       test_size // 2 + r, test_size // 2 + r], fill=(255, 255, 255))
            rgba = self.remove(img)
            alpha = rgba.split()[-1]
            a = np.asarray(alpha, dtype=np.float32)
            fg = float((a > 128).mean())
            bg = float((a < 128).mean())
            mean_v = float(a.mean())
            if fg < 0.02 or bg < 0.02:
                return False, "模型输出退化（alpha 几乎全前景/全背景，抠图失效）：fg=%.3f bg=%.3f" % (fg, bg)
            if not (20 <= mean_v <= 240):
                return False, "模型输出异常（alpha 均值越界）：mean=%.1f" % mean_v
            return True, "OK (fg=%.3f bg=%.3f mean=%.1f)" % (fg, bg, mean_v)
        except Exception as e:
            return False, "自检推理异常：%s" % e

    @staticmethod
    def model_md5():
        try:
            import hashlib
            p = Matting._locate_model()
            if not os.path.exists(p):
                return "(缺失)"
            h = hashlib.md5()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            return "(读取失败: %s)" % e


def app_diagnostic_dir():
    """诊断日志目录：打包后放在 exe 同目录，开发态放项目根。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return PROJECT_ROOT


def write_diagnostic_report(extra_lines=None):
    """写一份启动诊断报告到日志文件，便于远端排错。返回日志路径或 None。"""
    try:
        import onnxruntime as ort
        ort_ver = ort.__version__
        ort_prov = ",".join(ort.get_available_providers())
    except Exception as e:
        ort_ver = "(未安装: %s)" % e
        ort_prov = "-"
    m = Matting()
    ok, msg = m.self_check()
    import datetime
    lines = [
        "===== 证件照工作室 启动诊断 =====",
        "时间: %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "系统: %s" % (sys.platform),
        "onnxruntime 版本: %s" % ort_ver,
        "onnxruntime 后端: %s" % ort_prov,
        "模型路径: %s" % m.model_path,
        "模型可用: %s" % m.available(),
        "模型 MD5: %s" % Matting.model_md5(),
        "自检结果: %s | %s" % ("通过" if ok else "失败", msg),
    ]
    if extra_lines:
        lines += extra_lines
    try:
        d = app_diagnostic_dir()
        os.makedirs(d, exist_ok=True)
        log_path = os.path.join(d, "idphoto_diagnose.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return log_path
    except Exception:
        return None


# ============================================================ 照相馆自然标准半身胸像裁剪算法
def create_standard_id_photo(rgba, target_w, target_h, bg_rgb, zoom_ratio=1.0, offset_y_ratio=0.0, offset_x_ratio=0.0):
    """
    照相馆自然标准半身证件照构图 (Studio Natural Framing)：
    - 完整呈现头顶、人脸、五官、下巴、脖子、衣领与双肩展开
    - 支持人像缩放 (zoom_ratio) 与 上下/左右 位置微调 (offset_y, offset_x)
    """
    alpha_arr = np.array(rgba.split()[-1])
    orig_w, orig_h = rgba.size

    rows = np.where(np.any(alpha_arr > 25, axis=1))[0]
    cols = np.where(np.any(alpha_arr > 25, axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return rgba.convert("RGB").resize((target_w, target_h), Image.LANCZOS)

    y_top = rows[0]
    y_bot = rows[-1]

    # 扫描头部中心线
    head_scan_h = min(800, y_bot - y_top)
    head_rows = alpha_arr[y_top : y_top + head_scan_h, :]
    head_cols = np.where(np.any(head_rows > 45, axis=0))[0]
    if len(head_cols) > 0:
        face_cx = (head_cols[0] + head_cols[-1]) / 2.0
    else:
        face_cx = (cols[0] + cols[-1]) / 2.0

    person_h = max(100, y_bot - y_top)
    base_scale = (target_h * 0.91) / person_h
    scale = base_scale * zoom_ratio

    scaled_w = max(1, int(round(orig_w * scale)))
    scaled_h = max(1, int(round(orig_h * scale)))
    scaled_rgba = rgba.resize((scaled_w, scaled_h), Image.LANCZOS)

    scaled_cx = int(round(face_cx * scale))
    paste_x = int(round((target_w / 2.0) - scaled_cx + target_w * offset_x_ratio))

    scaled_ytop = int(round(y_top * scale))
    paste_y = int(round(target_h * 0.08 - scaled_ytop + target_h * offset_y_ratio))

    canvas = Image.new("RGB", (target_w, target_h), bg_rgb if bg_rgb else (255, 255, 255))
    canvas.paste(scaled_rgba, (paste_x, paste_y), scaled_rgba.split()[-1])

    # 如果是白底，绘制极细的 1px 浅灰色外边框，防止与白相纸融为一体
    if bg_rgb == (255, 255, 255):
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, 0, target_w - 1, target_h - 1], outline=(220, 220, 220), width=1)

    return canvas


def prepare_id_photo(image, id_w_px, id_h_px, bg_rgb, matting=None, zoom_ratio=1.0, offset_y_ratio=0.0, offset_x_ratio=0.0):
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA") if image.mode != "RGBA" else image.copy()

    if bg_rgb is not None and matting is not None:
        try:
            rgba = matting.remove(image)
            return create_standard_id_photo(rgba, id_w_px, id_h_px, bg_rgb, zoom_ratio, offset_y_ratio, offset_x_ratio)
        except MattingError:
            raise
        except Exception as e:
            raise MattingError("抠图处理异常：%s" % str(e))

    # 原图不换背景，直接做自然半身居中裁剪
    alpha_img = Image.new("L", image.size, 255)
    rgba = image.copy()
    rgba.putalpha(alpha_img)
    return create_standard_id_photo(rgba, id_w_px, id_h_px, None, zoom_ratio, offset_y_ratio, offset_x_ratio)


# ============================================================ 极度精准的单规格相纸排版算法
def compute_layout(paper_w_mm, paper_h_mm, id_w_mm, id_h_mm, preferred_orientation="auto"):
    """
    智能选择横向/竖向相纸朝向以获取最大冲印张数。
    """
    if preferred_orientation == "landscape":
        candidate_orientations = [(max(paper_w_mm, paper_h_mm), min(paper_w_mm, paper_h_mm))]
    elif preferred_orientation == "portrait":
        candidate_orientations = [(min(paper_w_mm, paper_h_mm), max(paper_w_mm, paper_h_mm))]
    else:
        candidate_orientations = [
            (max(paper_w_mm, paper_h_mm), min(paper_w_mm, paper_h_mm)),
            (min(paper_w_mm, paper_h_mm), max(paper_w_mm, paper_h_mm))
        ]

    best = None
    for (w_p, h_p) in candidate_orientations:
        for g in [1.0, 0.8, 0.5]:
            for m in [4.0, 3.0, 2.0, 1.0]:
                cols_c = int((w_p - 2 * m + g) // (id_w_mm + g))
                rows_c = int((h_p - 2 * m + g) // (id_h_mm + g))
                if cols_c >= 1 and rows_c >= 1:
                    cnt = cols_c * rows_c
                    total_w = cols_c * id_w_mm + (cols_c - 1) * g
                    total_h = rows_c * id_h_mm + (rows_c - 1) * g
                    if total_w <= w_p and total_h <= h_p:
                        if best is None or cnt > best["count"] or (cnt == best["count"] and m > best["margin"]):
                            best = {
                                "paper_w": w_p, "paper_h": h_p,
                                "cols": cols_c, "rows": rows_c, "count": cnt,
                                "gap": g, "margin": m, "total_w": total_w, "total_h": total_h
                            }

    if not best:
        pw, ph = candidate_orientations[0]
        cols, rows, count = 1, 1
        gap, margin = 1.0, 2.0
    else:
        pw, ph = best["paper_w"], best["paper_h"]
        cols, rows, count = best["cols"], best["rows"], best["count"]
        gap, margin = best["gap"], best["margin"]

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
        "gap_mm": gap,
        "margin_mm": margin,
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

    border_color = (200, 200, 200)
    for r in range(rows):
        for c in range(cols):
            x = ox + c * (iw + gap)
            y = oy + r * (ih + gap)
            sheet.paste(id_photo, (x, y))

            draw.rectangle([x, y, x + iw - 1, y + ih - 1], outline=border_color, width=1)
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + iw - 1, y + ih - 1, color=(185, 185, 185))

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

    if size_name:
        txt = f"{size_name} · {size_dims} · 300DPI 标准冲印"
        try:
            draw.text((ox, max(4, oy - 20)), txt, fill=(150, 150, 150))
        except Exception:
            pass

    return sheet


# ============================================================ 照相馆标配权威混排冲印方案
def compose_mixed_sheet(id_1in, id_2in, mix_type="6in_landscape_4_8", cut_lines=True, add_text=True):
    """
    照相馆权威混排方案：
    - 6in_landscape_4_8: 6寸横版金牌满排 (152x102mm) -> 左4张二寸(竖 2x2) + 右8张一寸(横放 2x4) (共12张，左右完全等宽等高齐平，最畅销)
    - 5in_portrait_2_6: 5寸竖版标准满排 (89x127mm) -> 上2张二寸(1x2) + 下6张一寸(3x2) (共8张满幅)
    """
    w_2in, h_2in = mm_to_px(35), mm_to_px(49)
    w_1in, h_1in = mm_to_px(25), mm_to_px(35)
    border_color = (200, 200, 200)

    if mix_type in ("6in_landscape_4_8", "6in_landscape_4_6", "6in_4_8", "6in_4_6", "6in_portrait_4_6", "6in_4_4"):
        # 6寸横版金牌满排: 152 x 102 mm -> 左边 4张二寸 (竖放 2x2), 右边 8张一寸 (横放 2x4)
        pw, ph = mm_to_px(152), mm_to_px(102)
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        id_1in_rot = id_1in.rotate(-90, expand=True) # 35mm宽 x 25mm高 (413 x 295 px)

        gap = mm_to_px(0.8) # 9 px
        gap_sec = mm_to_px(3.5) # 41 px

        left_w = w_2in * 2 + gap # 71mm (835 px)
        left_h = h_2in * 2 + gap # 99mm (1167 px)

        w_1in_h, h_1in_h = mm_to_px(35), mm_to_px(25)
        gap_y_1in = mm_to_px(0.5) # 6 px
        right_w = w_1in_h * 2 + gap # 71mm (835 px)
        right_h = h_1in_h * 4 + gap_y_1in * 3 # 101.5mm (1198 px)

        total_w = left_w + gap_sec + right_w # 145.5mm <= 152mm
        ox = (pw - total_w) // 2

        # 绘制左侧 4张二寸 (垂直居中)
        oy_left = (ph - left_h) // 2
        for r in range(2):
            for c in range(2):
                x = ox + c * (w_2in + gap)
                y = oy_left + r * (h_2in + gap)
                sheet.paste(id_2in, (x, y))
                draw.rectangle([x, y, x + w_2in - 1, y + h_2in - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 绘制右侧 8张一寸 (横放，垂直居中)
        ox_right = ox + left_w + gap_sec
        oy_right = (ph - right_h) // 2
        for r in range(4):
            for c in range(2):
                x = ox_right + c * (w_1in_h + gap)
                y = oy_right + r * (h_1in_h + gap_y_1in)
                sheet.paste(id_1in_rot, (x, y))
                draw.rectangle([x, y, x + w_1in_h - 1, y + h_1in_h - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_1in_h - 1, y + h_1in_h - 1)

        info = f"6寸横版金牌满排 · 4张二寸(竖) + 8张一寸(横) · 共12张 · {pw}×{ph} px"
        return sheet, info

    else: # 5in_portrait_2_6 (5寸竖版标准满排)
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
            if cut_lines:
                _draw_dashed_rect(draw, x, y, x + w_2in - 1, y + h_2in - 1)

        # 下部 6张一寸
        ox_bot = (pw - bot_w) // 2
        oy_bot = oy + top_h + gap_sec
        for r in range(2):
            for c in range(3):
                x = ox_bot + c * (w_1in + gap)
                y = oy_bot + r * (h_1in + gap)
                sheet.paste(id_1in, (x, y))
                draw.rectangle([x, y, x + w_1in - 1, y + h_1in - 1], outline=border_color, width=1)
                if cut_lines:
                    _draw_dashed_rect(draw, x, y, x + w_1in - 1, y + h_1in - 1)

        info = f"5寸标准满排 · 2张二寸 + 6张一寸 (共8张满幅) · {pw}×{ph} px"
        return sheet, info


# ============================================================ 自由多尺寸自定义混排装箱引擎
def compose_custom_mixed_sheet(images_dict, counts_dict, paper_dict,
                               cut_lines=True, add_text=True, preferred_orientation="auto"):
    """
    智能多规格分栏装箱混排引擎：
    - 支持任意数量组合
    - 自动自适应边距与分组分栏
    """
    specs_map = {
        "1in": (25, 35, "一寸"),
        "2in": (35, 49, "二寸"),
        "s_1in": (22, 32, "小一寸"),
        "l_2in": (35, 53, "大二寸"),
    }

    groups = []
    for k, cnt in counts_dict.items():
        if cnt > 0 and k in specs_map and k in images_dict and images_dict[k] is not None:
            w_mm, h_mm, tag = specs_map[k]
            groups.append({
                "key": k,
                "w_mm": w_mm,
                "h_mm": h_mm,
                "count": cnt,
                "img": images_dict[k],
                "tag": tag
            })

    if not groups:
        pw = mm_to_px(paper_dict["w_mm"])
        ph = mm_to_px(paper_dict["h_mm"])
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        return sheet, "请至少设定一种尺寸数量 > 0", True

    paper_w = paper_dict["w_mm"]
    paper_h = paper_dict["h_mm"]

    best_solution = None

    for margin_mm in [3.0, 2.5, 2.0, 1.5, 1.0]:
        for gap_group_mm in [3.0, 2.5, 2.0, 1.5, 1.0]:
            for gap_mm in [1.0, 0.8, 0.5]:
                if preferred_orientation == "landscape":
                    candidate_orientations = [(max(paper_w, paper_h), min(paper_w, paper_h))]
                elif preferred_orientation == "portrait":
                    candidate_orientations = [(min(paper_w, paper_h), max(paper_w, paper_h))]
                else:
                    candidate_orientations = [
                        (max(paper_w, paper_h), min(paper_w, paper_h)),
                        (min(paper_w, paper_h), max(paper_w, paper_h))
                    ]

                for pw, ph in candidate_orientations:
                    avail_w = pw - 2 * margin_mm
                    avail_h = ph - 2 * margin_mm

                    if len(groups) == 1:
                        g = groups[0]
                        cnt = g["count"]
                        for cols in range(1, cnt + 1):
                            rows = (cnt + cols - 1) // cols
                            bw = cols * g["w_mm"] + (cols - 1) * gap_mm
                            bh = rows * g["h_mm"] + (rows - 1) * gap_mm
                            if bw <= avail_w and bh <= avail_h:
                                placed_items = []
                                ox_b = (pw - bw) / 2.0
                                oy_b = (ph - bh) / 2.0
                                idx = 0
                                for r in range(rows):
                                    for c in range(cols):
                                        if idx < cnt:
                                            x = ox_b + c * (g["w_mm"] + gap_mm)
                                            y = oy_b + r * (g["h_mm"] + gap_mm)
                                            placed_items.append((x, y, g["w_mm"], g["h_mm"], g["img"], g["tag"]))
                                            idx += 1
                                area_used = cnt * g["w_mm"] * g["h_mm"]
                                sol = {"pw": pw, "ph": ph, "fits": True, "items": placed_items, "util": area_used / (pw * ph), "count": cnt}
                                if best_solution is None or sol["util"] > best_solution["util"]:
                                    best_solution = sol

                    elif len(groups) == 2:
                        g1, g2 = groups[0], groups[1]
                        # 策略 A: 左右并列
                        for cols1 in range(1, g1["count"] + 1):
                            rows1 = (g1["count"] + cols1 - 1) // cols1
                            bw1 = cols1 * g1["w_mm"] + (cols1 - 1) * gap_mm
                            bh1 = rows1 * g1["h_mm"] + (rows1 - 1) * gap_mm
                            if bh1 > avail_h:
                                continue

                            for cols2 in range(1, g2["count"] + 1):
                                rows2 = (g2["count"] + cols2 - 1) // cols2
                                bw2 = cols2 * g2["w_mm"] + (cols2 - 1) * gap_mm
                                bh2 = rows2 * g2["h_mm"] + (rows2 - 1) * gap_mm
                                if bh2 > avail_h:
                                    continue

                                total_w = bw1 + gap_group_mm + bw2
                                total_h = max(bh1, bh2)
                                if total_w <= avail_w and total_h <= avail_h:
                                    ox = (pw - total_w) / 2.0
                                    oy1 = (ph - bh1) / 2.0
                                    oy2 = (ph - bh2) / 2.0

                                    items = []
                                    idx = 0
                                    for r in range(rows1):
                                        for c in range(cols1):
                                            if idx < g1["count"]:
                                                x = ox + c * (g1["w_mm"] + gap_mm)
                                                y = oy1 + r * (g1["h_mm"] + gap_mm)
                                                items.append((x, y, g1["w_mm"], g1["h_mm"], g1["img"], g1["tag"]))
                                                idx += 1
                                    idx = 0
                                    ox2 = ox + bw1 + gap_group_mm
                                    for r in range(rows2):
                                        for c in range(cols2):
                                            if idx < g2["count"]:
                                                x = ox2 + c * (g2["w_mm"] + gap_mm)
                                                y = oy2 + r * (g2["h_mm"] + gap_mm)
                                                items.append((x, y, g2["w_mm"], g2["h_mm"], g2["img"], g2["tag"]))
                                                idx += 1

                                    area_used = g1["count"] * g1["w_mm"] * g1["h_mm"] + g2["count"] * g2["w_mm"] * g2["h_mm"]
                                    sol = {"pw": pw, "ph": ph, "fits": True, "items": items, "util": area_used / (pw * ph), "count": len(items)}
                                    if best_solution is None or sol["util"] > best_solution["util"]:
                                        best_solution = sol

                        # 策略 B: 上下并列
                        for cols1 in range(1, g1["count"] + 1):
                            rows1 = (g1["count"] + cols1 - 1) // cols1
                            bw1 = cols1 * g1["w_mm"] + (cols1 - 1) * gap_mm
                            bh1 = rows1 * g1["h_mm"] + (rows1 - 1) * gap_mm
                            if bw1 > avail_w:
                                continue

                            for cols2 in range(1, g2["count"] + 1):
                                rows2 = (g2["count"] + cols2 - 1) // cols2
                                bw2 = cols2 * g2["w_mm"] + (cols2 - 1) * gap_mm
                                bh2 = rows2 * g2["h_mm"] + (rows2 - 1) * gap_mm
                                if bw2 > avail_w:
                                    continue

                                total_h = bh1 + gap_group_mm + bh2
                                total_w = max(bw1, bw2)
                                if total_w <= avail_w and total_h <= avail_h:
                                    oy = (ph - total_h) / 2.0
                                    ox1 = (pw - bw1) / 2.0
                                    ox2 = (pw - bw2) / 2.0

                                    items = []
                                    idx = 0
                                    for r in range(rows1):
                                        for c in range(cols1):
                                            if idx < g1["count"]:
                                                x = ox1 + c * (g1["w_mm"] + gap_mm)
                                                y = oy + r * (g1["h_mm"] + gap_mm)
                                                items.append((x, y, g1["w_mm"], g1["h_mm"], g1["img"], g1["tag"]))
                                                idx += 1
                                    idx = 0
                                    oy2 = oy + bh1 + gap_group_mm
                                    for r in range(rows2):
                                        for c in range(cols2):
                                            if idx < g2["count"]:
                                                x = ox2 + c * (g2["w_mm"] + gap_mm)
                                                y = oy2 + r * (g2["h_mm"] + gap_mm)
                                                items.append((x, y, g2["w_mm"], g2["h_mm"], g2["img"], g2["tag"]))
                                                idx += 1

                                    area_used = g1["count"] * g1["w_mm"] * g1["h_mm"] + g2["count"] * g2["w_mm"] * g2["h_mm"]
                                    sol = {"pw": pw, "ph": ph, "fits": True, "items": items, "util": area_used / (pw * ph), "count": len(items)}
                                    if best_solution is None or sol["util"] > best_solution["util"]:
                                        best_solution = sol

                    else:
                        # 3 组或 4 组 (复杂混排): 2D Shelf 装箱
                        flat_items = []
                        for g in sorted(groups, key=lambda x: (x["h_mm"], x["w_mm"]), reverse=True):
                            for _ in range(g["count"]):
                                flat_items.append((g["w_mm"], g["h_mm"], g["img"], g["tag"]))

                        placed = []
                        cur_x = margin_mm
                        cur_y = margin_mm
                        row_h = 0
                        fits = True
                        for w_m, h_m, im, tg in flat_items:
                            if cur_x + w_m > pw - margin_mm:
                                cur_x = margin_mm
                                cur_y += row_h + gap_mm
                                row_h = 0
                            if cur_y + h_m > ph - margin_mm:
                                fits = False
                                break
                            placed.append((cur_x, cur_y, w_m, h_m, im, tg))
                            cur_x += w_m + gap_mm
                            if h_m > row_h:
                                row_h = h_m

                        area_used = sum(it[2] * it[3] for it in placed)
                        sol = {"pw": pw, "ph": ph, "fits": fits, "items": placed, "util": area_used / (pw * ph), "count": len(placed)}
                        if best_solution is None or (fits and not best_solution["fits"]) or (fits == best_solution["fits"] and sol["util"] > best_solution["util"]):
                            best_solution = sol

                if best_solution and best_solution["fits"]:
                    break
            if best_solution and best_solution["fits"]:
                break
        if best_solution and best_solution["fits"]:
            break

    if not best_solution:
        pw = mm_to_px(paper_dict["w_mm"])
        ph = mm_to_px(paper_dict["h_mm"])
        sheet = Image.new("RGB", (pw, ph), (255, 255, 255))
        return sheet, "相纸容量不足以容纳所有设定张数", False

    pw_px = mm_to_px(best_solution["pw"])
    ph_px = mm_to_px(best_solution["ph"])
    sheet = Image.new("RGB", (pw_px, ph_px), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    border_color = (200, 200, 200)

    total_req_count = sum(counts_dict.values())
    for x_mm, y_mm, w_mm, h_mm, img, tag in best_solution["items"]:
        x_px = mm_to_px(x_mm)
        y_px = mm_to_px(y_mm)
        w_px = mm_to_px(w_mm)
        h_px = mm_to_px(h_mm)
        scaled_img = img.resize((w_px, h_px), Image.LANCZOS)
        sheet.paste(scaled_img, (x_px, y_px))
        draw.rectangle([x_px, y_px, x_px + w_px - 1, y_px + h_px - 1], outline=border_color, width=1)
        if cut_lines:
            _draw_dashed_rect(draw, x_px, y_px, x_px + w_px - 1, y_px + h_px - 1)

    fits = best_solution["fits"]
    placed_count = best_solution["count"]
    if fits:
        info = f"{paper_dict['name']} 自定义混排 · 成功排入 {placed_count} 张 (利用率 {best_solution['util']*100:.1f}%) · {pw_px}×{ph_px} px"
    else:
        info = f"⚠️ 超出相纸容量！已排入 {placed_count}/{total_req_count} 张，请减少张数或更换相纸"

    return sheet, info, fits
