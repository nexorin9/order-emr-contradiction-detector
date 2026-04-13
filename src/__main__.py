"""
门诊医嘱-病程矛盾实时检测系统 CLI 入口

支持通过 python -m order_emr_detect 调用
"""

from src.py.cli import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)
