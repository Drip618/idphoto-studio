# -*- coding: utf-8 -*-
"""
idphoto_studio.py — 程序入口
双击启动图形界面；无 PySide6 时给出安装提示。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        from ui.main_window import run
    except ImportError as e:
        sys.stderr.write(
            "未安装 PySide6，无法启动图形界面。\n"
            "请先执行：pip install -r requirements.txt\n"
            "错误详情：%s\n" % e)
        sys.exit(1)
    run()


if __name__ == "__main__":
    main()
