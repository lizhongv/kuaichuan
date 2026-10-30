"""通用组件：卡片、状态标签、路径行、文件行、传输进度面板、结果弹窗。"""

import os
import time
from tkinter import filedialog

import customtkinter as ctk

from kuaichuan.ui import theme
from kuaichuan.ui.icons import icon
from kuaichuan.utils import fmt_duration, fmt_size


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=theme.CARD, corner_radius=theme.RADIUS, border_width=1,
                         border_color=theme.CARD_BORDER, **kw)


def title_label(master, text, size=15):
    return ctk.CTkLabel(master, text=text, font=theme.font(size, "bold"), text_color=theme.TEXT, anchor="w")


def hint_label(master, text, wrap=0):
    return ctk.CTkLabel(master, text=text, font=theme.font(12), text_color=theme.TEXT_MUTED, anchor="w",
                        justify="left", wraplength=wrap)


def primary_button(master, text, command, image=None, height=44):
    return ctk.CTkButton(master, text=text, command=command, image=image, height=height, corner_radius=10,
                         fg_color=theme.BRAND, hover_color=theme.BRAND_HOVER, font=theme.font(15, "bold"))


def secondary_button(master, text, command, image=None, width=100, height=34):
    return ctk.CTkButton(master, text=text, command=command, image=image, width=width, height=height,
                         corner_radius=8, fg_color=theme.SECONDARY_BTN, hover_color=theme.SECONDARY_BTN_HOVER,
                         text_color=theme.TEXT, font=theme.font(13))


class StatusPill(ctk.CTkFrame):
    """带圆点的状态标签：idle / active / error。"""

    _STYLE = {"idle": (theme.NEUTRAL_SOFT, theme.TEXT_MUTED),
              "active": (theme.SUCCESS_SOFT, theme.SUCCESS),
              "error": (theme.DANGER_SOFT, theme.DANGER)}

    def __init__(self, master, text="", state="idle"):
        super().__init__(master, corner_radius=14, height=28)
        self.label = ctk.CTkLabel(self, text="", font=theme.font(12, "bold"))
        self.label.pack(padx=12, pady=3)
        self.set(text, state)

    def set(self, text, state="idle"):
        bg, fg = self._STYLE[state]
        self.configure(fg_color=bg)
        self.label.configure(text=f"●  {text}", text_color=fg)


class PathRow(ctk.CTkFrame):
    """「标题 + 路径输入 + 更改 + 打开」一行。"""

    def __init__(self, master, title, variable, on_open, on_change=None):
        super().__init__(master, fg_color="transparent")
        self.variable, self.on_change = variable, on_change
        ctk.CTkLabel(self, text=title, width=92, anchor="w", font=theme.font(13, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        ctk.CTkEntry(self, textvariable=variable, height=34, corner_radius=8, fg_color=theme.INPUT_BG,
                     border_color=theme.CARD_BORDER, font=theme.font(12)).pack(side="left", fill="x", expand=True)
        secondary_button(self, "更改", self._pick, width=60).pack(side="left", padx=(8, 0))
        secondary_button(self, "打开", lambda: on_open(variable.get()), image=icon("folder", 16), width=84).pack(
            side="left", padx=(8, 0))

    def _pick(self):
        path = filedialog.askdirectory(initialdir=self.variable.get())
        if path:
            self.variable.set(os.path.normpath(path))
            if self.on_change:
                self.on_change()


class FileRow(ctk.CTkFrame):
    """待发送列表中的一行。"""

    def __init__(self, master, path, meta, on_remove):
        super().__init__(master, fg_color=theme.INPUT_BG, corner_radius=10)
        kind = "folder" if os.path.isdir(path) else "file"
        ctk.CTkLabel(self, text="", image=icon(kind, 20, light="#2563EB", dark="#60A5FA")).pack(side="left",
                                                                                            padx=(12, 8), pady=8)
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(side="left", fill="x", expand=True, pady=6)
        ctk.CTkLabel(box, text=os.path.basename(path) or path, font=theme.font(13, "bold"), anchor="w",
                     text_color=theme.TEXT).pack(fill="x")
        ctk.CTkLabel(box, text=f"{meta}    {os.path.dirname(path)}", font=theme.font(11), anchor="w",
                     text_color=theme.TEXT_MUTED).pack(fill="x")
        ctk.CTkButton(self, text="", image=icon("close", 14), width=30, height=30, corner_radius=8,
                      fg_color="transparent", hover_color=theme.SECONDARY_BTN_HOVER,
                      command=lambda: on_remove(path)).pack(side="right", padx=8)


class TransferPanel(Card):
    """底部传输进度：标题、总进度、统计信息、当前文件进度。"""

    _DIRECTION = {"send": "正在发送", "recv": "正在接收", "phone_up": "手机正在上传", "phone_down": "手机正在下载"}

    def __init__(self, master):
        super().__init__(master)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=theme.PAD, pady=(14, 0))
        self.title = ctk.CTkLabel(top, text="", font=theme.font(14, "bold"), anchor="w")
        self.title.pack(side="left")
        self.percent = ctk.CTkLabel(top, text="", font=theme.font(14, "bold"), text_color=theme.BRAND)
        self.percent.pack(side="right")
        self.bar = ctk.CTkProgressBar(self, height=10, corner_radius=5, progress_color=theme.BRAND,
                                      fg_color=theme.NEUTRAL_SOFT)
        self.bar.pack(fill="x", padx=theme.PAD, pady=(8, 4))
        self.stat = hint_label(self, "")
        self.stat.pack(fill="x", padx=theme.PAD)
        file_row = ctk.CTkFrame(self, fg_color="transparent")
        file_row.pack(fill="x", padx=theme.PAD, pady=(2, 14))
        self.file_label = hint_label(file_row, "")
        self.file_label.pack(side="left", fill="x", expand=True)
        self.file_bar = ctk.CTkProgressBar(file_row, width=180, height=6, corner_radius=3,
                                           progress_color=theme.BRAND, fg_color=theme.NEUTRAL_SOFT)
        self.file_bar.pack(side="right")
        self.idle()

    def idle(self):
        self.title.configure(text="暂无传输任务", text_color=theme.TEXT_MUTED)
        self.percent.configure(text="")
        self.bar.configure(progress_color=theme.BRAND)
        self.bar.set(0)
        self.file_bar.set(0)
        self.stat.configure(text="开启接收、选择文件发送或开启手机互传后，这里显示实时进度")
        self.file_label.configure(text="")

    def connecting(self, text):
        self.idle()
        self.title.configure(text=text, text_color=theme.TEXT)
        self.stat.configure(text="")

    def update(self, ev):
        pct = ev["done"] / ev["total"] if ev["total"] else 1.0
        speed = ev["done"] / max(ev["elapsed"], 1e-6)
        left = (ev["total"] - ev["done"]) / speed if speed > 0 else 0
        count = f"   第 {ev['index']} / {ev['count']} 个" if ev["count"] > 1 else ""
        self.title.configure(text=self._DIRECTION.get(ev["direction"], "正在传输") + count, text_color=theme.TEXT)
        self.percent.configure(text=f"{pct * 100:.1f}%", text_color=theme.BRAND)
        self.bar.configure(progress_color=theme.BRAND)
        self.bar.set(pct)
        self.stat.configure(text=f"{fmt_size(ev['done'])} / {fmt_size(ev['total'])}      {fmt_size(speed)}/s"
                                 f"      剩余约 {fmt_duration(left)}")
        self.file_label.configure(text=f"当前文件：{ev['name']}")
        self.file_bar.set(ev["file_done"] / ev["file_size"] if ev["file_size"] else 1.0)

    def success(self, text, detail=""):
        self.title.configure(text=f"✔  {text}", text_color=theme.SUCCESS)
        self.percent.configure(text="100%", text_color=theme.SUCCESS)
        self.bar.configure(progress_color=theme.SUCCESS)
        self.bar.set(1)
        self.file_bar.set(1)
        self.stat.configure(text=detail)
        self.file_label.configure(text=f"完成时间 {time.strftime('%H:%M:%S')}")

    def failure(self, text):
        self.title.configure(text=f"✖  {text}", text_color=theme.DANGER)
        self.percent.configure(text="")
        self.stat.configure(text="")
        self.file_label.configure(text="")


class ResultDialog(ctk.CTkToplevel):
    """传输结果弹窗：图标、标题、明细，以及「打开文件夹」按钮。"""

    def __init__(self, master, title, rows, ok=True, path=None, on_open=None):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=theme.CARD)
        self.transient(master)
        color = theme.SUCCESS if ok else theme.DANGER
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(26, 10))
        ctk.CTkLabel(head, text="", image=icon("check" if ok else "close", 34, light=color, dark=color)).pack(
            side="left")
        ctk.CTkLabel(head, text=title, font=theme.font(18, "bold"), text_color=theme.TEXT).pack(side="left",
                                                                                              padx=12)
        body = ctk.CTkFrame(self, fg_color=theme.INPUT_BG, corner_radius=10)
        body.pack(fill="x", padx=28)
        for key, value in rows:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=key, width=84, anchor="w", font=theme.font(12), text_color=theme.TEXT_MUTED).pack(
                side="left", anchor="n")
            ctk.CTkLabel(row, text=value, anchor="w", justify="left", wraplength=360, font=theme.font(13),
                         text_color=theme.TEXT).pack(side="left", fill="x", expand=True)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=28, pady=(18, 24))
        secondary_button(btns, "关闭", self.destroy, width=96, height=38).pack(side="right")
        if path and on_open:
            primary_button(btns, "打开文件夹", lambda: (on_open(path), self.destroy()),
                           image=icon("folder", 16, light="white", dark="white"), height=38).pack(
                side="right", padx=(0, 10))
        self.after(50, self._center)

    def _center(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_width()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.lift()
        self.focus_force()
