"""生成应用图标 assets/icon.ico 与 assets/icon.png（品牌渐变 + 双向箭头）。

用法：python scripts/make_icon.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from kuaichuan.ui.icons import logo_image  # noqa: E402

ASSETS = os.path.join(ROOT, "src", "kuaichuan", "assets")


def main():
    img = logo_image(256)
    img.save(os.path.join(ASSETS, "icon.png"))
    img.save(os.path.join(ASSETS, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                                      (128, 128), (256, 256)])
    print("已生成", os.path.join(ASSETS, "icon.ico"))


if __name__ == "__main__":
    main()
