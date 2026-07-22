# -*- coding: utf-8 -*-
"""生成应用图标：app.icns (Mac) + app.ico (Win)。纯 PIL 绘制证件照风格图标。"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角底板（蓝底证件照风格）
def rounded_rect(draw, box, r, fill):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill)

rounded_rect(d, [64, 64, S - 64, S - 64], 180, (45, 110, 200, 255))
rounded_rect(d, [88, 88, S - 88, S - 88], 160, (232, 240, 252, 255))

# 人像剪影（头 + 肩）
head_cx, head_cy, head_r = S // 2, 430, 165
d.ellipse([head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r],
          fill=(120, 100, 95, 255))
# 肩部
d.rounded_rectangle([S // 2 - 240, 600, S // 2 + 240, S - 64],
                    radius=120, fill=(120, 100, 95, 255))

# 高光描边
rounded_rect(d, [64, 64, S - 64, S - 64], 180, None)
d.line([(64, 64), (S - 64, S - 64)], fill=(255, 255, 255, 60), width=4)

img.convert("RGBA").save(os.path.join(HERE, "app_icon.png"))

# ---- 生成 Mac .icns ----
iconset = os.path.join(HERE, "app.iconset")
os.makedirs(iconset, exist_ok=True)
sizes = [16, 32, 64, 128, 256, 512, 1024]
for sz in sizes:
    im = img.resize((sz, sz), Image.LANCZOS)
    im.save(os.path.join(iconset, "icon_%dx%d.png" % (sz, sz)))
    if sz <= 512:
        im2 = img.resize((sz * 2, sz * 2), Image.LANCZOS)
        im2.save(os.path.join(iconset, "icon_%dx%d@2x.png" % (sz, sz)))
os.system("iconutil --convert icns '%s' -o '%s'" % (iconset, os.path.join(HERE, "app.icns")))
print("✓ 生成 app.icns")

# ---- 生成 Win .ico (多分辨率) ----
ico_path = os.path.join(HERE, "app.ico")
img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("✓ 生成 app.ico")
