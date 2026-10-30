"""用演示数据渲染各页面并截图到 docs/images，用于 README 配图与界面回归检查。

用法：python scripts/screenshots.py [--dark]
设置与记录写到临时目录，不影响本机真实配置。仅支持 Windows（依赖屏幕截图）。
"""

import os
import sys
import tempfile
import time

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="kuaichuan_shot_")   # 必须在导入 kuaichuan 前设置

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import ImageGrab  # noqa: E402

from kuaichuan import config  # noqa: E402
from kuaichuan.ui.app import App  # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")
DEMO = os.path.join(os.environ["APPDATA"], "demo")


def grab(app, name):
    for _ in range(30):
        app.update()
        time.sleep(0.03)
    # customtkinter 开启了高 DPI 感知，窗口坐标即物理像素，无需再按缩放比例换算
    x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, name))
    print("已保存", name)


def main():
    dark = "--dark" in sys.argv
    suffix = "_dark" if dark else ""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(DEMO, "项目资料"), exist_ok=True)
    for name, size in (("方案评审.pdf", 3_400_000), ("现场照片.zip", 52_000_000)):
        with open(os.path.join(DEMO, name), "wb") as f:
            f.truncate(size)
    for i in range(6):
        with open(os.path.join(DEMO, "项目资料", f"附件{i + 1}.docx"), "wb") as f:
            f.truncate(800_000)

    app = App()
    app.settings["appearance"] = "dark" if dark else "light"
    app.appearance.set("深色" if dark else "浅色")
    app._switch_appearance("深色" if dark else "浅色")
    app.geometry("+10+10")
    app.attributes("-topmost", True)
    for kind, peer, count, size in (("recv", "LAPTOP-WANG", 12, 1_932_735_283), ("send", "DESKTOP-ZHANG", 3, 56_000_000),
                                    ("phone_up", "手机 192.168.0.120", 1, 3_600_000),
                                    ("phone_down", "手机 192.168.0.120", 1, 52_000_000)):
        config.append_history(app.history, kind, peer, count, size, r"C:\Users\demo\Desktop\快传接收")
    app.pages["history"].refresh()

    app.pages["recv"].set_active(True)
    app.panel.update({"direction": "recv", "index": 5, "count": 12, "name": "项目资料/方案评审.pdf",
                      "file_done": 31_000_000, "file_size": 48_000_000, "done": 860_000_000,
                      "total": 1_932_735_283, "elapsed": 9.6})
    app.show("recv")
    grab(app, f"receive{suffix}.png")

    send = app.pages["send"]
    send.paths = [os.path.join(DEMO, "方案评审.pdf"), os.path.join(DEMO, "现场照片.zip"), os.path.join(DEMO, "项目资料")]
    send.refresh()
    send.set_peers([("192.168.0.115", "LAPTOP-WANG"), ("192.168.0.130", "DESKTOP-ZHANG")])
    app.panel.success("发送完成：8 个文件，60.2 MB", "已发送到 LAPTOP-WANG，平均 86.3 MB/s")
    app.show("send")
    grab(app, f"send{suffix}.png")

    app.phone_up_var.set(os.path.join(DEMO, "up"))
    app.phone_share_var.set(os.path.join(DEMO, "share"))
    app.toggle_phone()
    app.panel.update({"direction": "phone_up", "index": 1, "count": 1, "name": "IMG_20261031_1024.jpg",
                      "file_done": 2_100_000, "file_size": 3_600_000, "done": 2_100_000, "total": 3_600_000,
                      "elapsed": 0.3})
    app.show("phone")
    grab(app, f"phone{suffix}.png")

    app.panel.idle()
    app.show("history")
    grab(app, f"history{suffix}.png")

    if app.web:
        app.web.stop()
    app.destroy()


if __name__ == "__main__":
    main()
