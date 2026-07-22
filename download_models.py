# -*- coding: utf-8 -*-
"""
download_models.py — 一键下载抠图模型（约 25MB，CPU 毫秒级）
默认下载 modnet_photographic_portrait_matting.onnx 到 weights/ 目录。
换底色功能依赖此模型；不下载也能用「不换背景」纯排版。
"""
import os
import sys
import urllib.request

USER_CONFIG_DIR = os.path.expanduser("~/.idphoto_studio")
WEIGHTS = os.path.join(USER_CONFIG_DIR, "weights")
os.makedirs(WEIGHTS, exist_ok=True)

# HivisionIDPhotos 发布的 modnet 权重（依次尝试；pretrained-model 为官方发布 tag）
URLS = [
    "https://github.com/Zeyi-Lin/HivisionIDPhotos/releases/download/pretrained-model/modnet_photographic_portrait_matting.onnx",
    "https://github.com/Zeyi-Lin/HivisionIDPhotos/releases/download/pretrained-model/hivision_modnet.onnx",
]
OUT = os.path.join(WEIGHTS, "modnet_photographic_portrait_matting.onnx")


def download():
    for url in URLS:
        try:
            print("下载:", url)
            urllib.request.urlretrieve(url, OUT,
                                      lambda b, bs, sz: print("\r  进度 %.0f%%" %
                                                              (b * bs / sz * 100 if sz > 0 else 0), end=""))
            print("\n完成 ->", OUT)
            return True
        except Exception as e:
            print("失败:", e)
    return False


if __name__ == "__main__":
    if os.path.exists(OUT):
        print("模型已存在:", OUT)
    else:
        ok = download()
        if not ok:
            print("自动下载失败，请手动下载 modnet_photographic_portrait_matting.onnx 放到 weights/ 目录。")
            sys.exit(1)
