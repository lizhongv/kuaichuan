"""四个功能页：接收文件、发送文件、手机互传、传输记录。

页面只负责展示与收集输入，具体动作调用 App 上的控制方法（toggle_receive、start_send 等）。
"""

import io
import os
from tkinter import filedialog

import customtkinter as ctk
import segno
from PIL import Image, ImageDraw

from kuaichuan import config
from kuaichuan.ui import theme
from kuaichuan.ui.icons import icon
from kuaichuan.ui.widgets import (Card, FileRow, PathRow, StatusPill, hint_label, primary_button,
                                  secondary_button, title_label)
from kuaichuan.utils import fmt_size, iter_files, local_ips, summarize

WHITE_ICON = {"light": "white", "dark": "white"}


def _section(card, title, subtitle=None):
    title_label(card, title).pack(fill="x", padx=theme.PAD, pady=(18, 0))
    if subtitle:
        hint_label(card, subtitle).pack(fill="x", padx=theme.PAD, pady=(2, 0))


class ReceivePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        status = Card(self)
        status.pack(fill="x")
        row = ctk.CTkFrame(status, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=(20, 0))
        self.pill = StatusPill(row, "未开启", "idle")
        self.pill.pack(side="left")
        self.headline = ctk.CTkLabel(status, text="开启接收后，同一网络中的电脑即可把文件发给本机",
                                     font=theme.font(17, "bold"), text_color=theme.TEXT, anchor="w")
        self.headline.pack(fill="x", padx=theme.PAD, pady=(12, 2))
        hint_label(status, f"对方在「发送文件」中点击「搜索设备」，选择「{config.HOSTNAME}」即可。").pack(
            fill="x", padx=theme.PAD)
        self.button = primary_button(status, "开启接收", app.toggle_receive,
                                     image=icon("power", 18, **WHITE_ICON), height=48)
        self.button.pack(fill="x", padx=theme.PAD, pady=(16, 20))

        settings = Card(self)
        settings.pack(fill="x", pady=(14, 0))
        _section(settings, "保存设置")
        PathRow(settings, "保存位置", app.save_dir_var, app.open_path, on_change=app.on_save_dir_changed).pack(
            fill="x", padx=theme.PAD, pady=(12, 6))
        ctk.CTkCheckBox(settings, text="接收完成后自动打开保存位置", variable=app.auto_open_var,
                        font=theme.font(13), text_color=theme.TEXT, fg_color=theme.BRAND,
                        hover_color=theme.BRAND_HOVER, checkbox_width=20, checkbox_height=20,
                        corner_radius=5, command=app.persist_settings).pack(anchor="w", padx=theme.PAD,
                                                                             pady=(4, 18))

    def set_active(self, active, error=None):
        if error:
            self.pill.set("无法开启", "error")
            self.headline.configure(text=error)
        elif active:
            self.pill.set("接收中", "active")
            self.headline.configure(text="正在接收，等待对方发送…")
        else:
            self.pill.set("未开启", "idle")
            self.headline.configure(text="开启接收后，同一网络中的电脑即可把文件发给本机")
        self.button.configure(
            text="停止接收" if active else "开启接收",
            fg_color=theme.DANGER if active else theme.BRAND,
            hover_color="#B91C1C" if active else theme.BRAND_HOVER)


class SendPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.paths = []
        self.peers = []

        target = Card(self)
        target.pack(fill="x")
        _section(target, "发送给")
        row = ctk.CTkFrame(target, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=(10, 0))
        self.target_var = ctk.StringVar()
        self.combo = ctk.CTkComboBox(row, variable=self.target_var, values=[], height=38, corner_radius=8,
                                     font=theme.font(14), dropdown_font=theme.font(13),
                                     fg_color=theme.INPUT_BG, border_color=theme.CARD_BORDER,
                                     button_color=theme.BRAND, button_hover_color=theme.BRAND_HOVER)
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.set("")
        self.search_btn = primary_button(row, "搜索设备", app.search_peers,
                                         image=icon("search", 16, **WHITE_ICON), height=38)
        self.search_btn.configure(width=120, font=theme.font(13, "bold"))
        self.search_btn.pack(side="left", padx=(10, 0))
        self.target_hint = hint_label(target, "请让对方先开启接收，再点「搜索设备」；也可直接输入对方 IP")
        self.target_hint.pack(fill="x", padx=theme.PAD, pady=(6, 18))

        files = Card(self)
        files.pack(fill="both", expand=True, pady=(14, 0))
        head = ctk.CTkFrame(files, fg_color="transparent")
        head.pack(fill="x", padx=theme.PAD, pady=(16, 0))
        title_label(head, "待发送内容").pack(side="left")
        secondary_button(head, "清空", self.clear, width=64).pack(side="right")
        secondary_button(head, "添加文件夹", self.add_folder, image=icon("folder", 16), width=110).pack(
            side="right", padx=8)
        secondary_button(head, "添加文件", self.add_files, image=icon("plus", 16), width=100).pack(side="right")
        # 按钮与合计先固定在卡片底部，列表只占剩余空间，文件再多也不会把「发送」挤出页面
        actions = ctk.CTkFrame(files, fg_color="transparent")
        actions.pack(side="bottom", fill="x", padx=theme.PAD, pady=(10, 18))
        self.send_btn = primary_button(actions, "发送", app.start_send, image=icon("send", 18, **WHITE_ICON),
                                       height=46)
        self.send_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = secondary_button(actions, "取消", app.cancel_send, width=96, height=46)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn.configure(state="disabled")
        self.summary = hint_label(files, "")
        self.summary.pack(side="bottom", fill="x", padx=theme.PAD, pady=(6, 0))
        self.listbox = ctk.CTkScrollableFrame(files, fg_color="transparent", height=80)
        self.listbox.pack(fill="both", expand=True, padx=theme.PAD - 6, pady=(10, 0))
        self.empty = hint_label(self.listbox, "还没有添加内容。点击右上角「添加文件」或「添加文件夹」。")
        self.refresh()

    # ------------------------------------------------------------ 文件列表
    def add_files(self):
        for p in filedialog.askopenfilenames():
            self._add(p)
        self.refresh()

    def add_folder(self):
        p = filedialog.askdirectory()
        if p:
            self._add(p)
        self.refresh()

    def _add(self, path):
        path = os.path.normpath(path)
        if path not in self.paths:
            self.paths.append(path)

    def remove(self, path):
        self.paths.remove(path)
        self.refresh()

    def clear(self):
        self.paths = []
        self.refresh()

    def refresh(self):
        for child in self.listbox.winfo_children():
            if child is not self.empty:
                child.destroy()
        if not self.paths:
            self.empty.pack(fill="x", pady=20, padx=6)
            self.summary.configure(text="")
            return
        self.empty.pack_forget()
        for p in self.paths:
            if os.path.isdir(p):
                files = list(iter_files([p]))
                meta = f"文件夹 · {len(files)} 个文件 · {fmt_size(sum(os.path.getsize(f) for f, _ in files))}"
            else:
                meta = fmt_size(os.path.getsize(p))
            FileRow(self.listbox, p, meta, self.remove).pack(fill="x", pady=4, padx=6)
        count, total = summarize(self.paths)
        self.summary.configure(text=f"合计 {count} 个文件，{fmt_size(total)}")

    # ------------------------------------------------------------ 目标设备
    def set_searching(self, searching):
        self.search_btn.configure(state="disabled" if searching else "normal",
                                  text="搜索中…" if searching else "搜索设备")
        if searching:
            self.target_hint.configure(text="正在搜索局域网内已开启接收的设备…", text_color=theme.TEXT_MUTED)

    def set_peers(self, peers):
        self.peers = peers
        self.set_searching(False)
        if peers:
            values = [f"{name}  （{ip}）" for ip, name in peers]
            self.combo.configure(values=values)
            self.combo.set(values[0])
            self.target_hint.configure(text=f"找到 {len(peers)} 台设备，请核对电脑名后发送", text_color=theme.SUCCESS)
        else:
            self.target_hint.configure(
                text="没有找到设备：确认对方已开启接收；公司网络可能屏蔽搜索，可直接输入对方 IP",
                text_color=theme.DANGER)

    def target_ip(self):
        text = self.target_var.get().strip()
        for ip, name in self.peers:
            if text == f"{name}  （{ip}）":
                return ip
        return text.split()[0] if text else ""

    def set_sending(self, sending):
        self.send_btn.configure(state="disabled" if sending else "normal", text="发送中…" if sending else "发送")
        self.cancel_btn.configure(state="normal" if sending else "disabled")


class PhonePage(ctk.CTkFrame):
    QR_SIZE = 176

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = Card(self, width=300)
        left.grid(row=0, column=0, sticky="nsw")
        _section(left, "扫码连接", "手机连同一个 Wi-Fi，用相机或微信扫码")
        self.qr = ctk.CTkLabel(left, text="", image=self._placeholder())
        self.qr.pack(padx=theme.PAD, pady=(10, 6))
        self.url_var = ctk.StringVar(value="开启后显示访问地址")
        ctk.CTkEntry(left, textvariable=self.url_var, state="readonly", height=32, corner_radius=8, width=250,
                     fg_color=theme.INPUT_BG, border_color=theme.CARD_BORDER, font=theme.font(12, "bold"),
                     text_color=theme.BRAND, justify="center").pack(padx=theme.PAD)
        ip_row = ctk.CTkFrame(left, fg_color="transparent")
        ip_row.pack(fill="x", padx=theme.PAD, pady=(8, 0))
        ctk.CTkLabel(ip_row, text="网卡", font=theme.font(12), text_color=theme.TEXT_MUTED).pack(side="left")
        ips = local_ips() or ["127.0.0.1"]
        self.ip_var = ctk.StringVar(value=ips[0])
        ctk.CTkOptionMenu(ip_row, variable=self.ip_var, values=ips, height=30, corner_radius=8,
                          font=theme.font(12), fg_color=theme.SECONDARY_BTN, button_color=theme.SECONDARY_BTN_HOVER,
                          button_hover_color=theme.SECONDARY_BTN_HOVER, text_color=theme.TEXT,
                          command=lambda _: app.refresh_phone_qr()).pack(side="left", fill="x", expand=True,
                                                                         padx=(8, 0))
        self.button = primary_button(left, "开启手机互传", app.toggle_phone,
                                     image=icon("power", 18, **WHITE_ICON), height=44)
        self.button.pack(fill="x", padx=theme.PAD, pady=(12, 18))

        right = Card(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        row = ctk.CTkFrame(right, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=(20, 0))
        self.pill = StatusPill(row, "未开启", "idle")
        self.pill.pack(side="left")
        title_label(right, "无需安装 App，安卓与 iPhone 均可使用", 16).pack(fill="x", padx=theme.PAD, pady=(12, 4))
        steps = [("1", "点击「开启手机互传」，左侧出现二维码"),
                 ("2", "手机扫码，点「选择文件或照片」上传到电脑"),
                 ("3", "文件放进「共享给手机」，手机刷新后下载"),
                 ("4", "用完关闭，访问口令随即失效")]
        for num, text in steps:
            line = ctk.CTkFrame(right, fg_color="transparent")
            line.pack(fill="x", padx=theme.PAD, pady=3)
            ctk.CTkLabel(line, text=num, width=24, height=24, corner_radius=12, fg_color=theme.BRAND_SOFT,
                         text_color=theme.BRAND, font=theme.font(12, "bold")).pack(side="left")
            ctk.CTkLabel(line, text=text, font=theme.font(13), text_color=theme.TEXT, anchor="w", justify="left",
                         wraplength=380).pack(side="left", padx=10, fill="x", expand=True)
        _section(right, "文件夹设置")
        PathRow(right, "上传保存到", app.phone_up_var, app.open_path, on_change=app.on_phone_dir_changed).pack(
            fill="x", padx=theme.PAD, pady=(10, 6))
        PathRow(right, "共享给手机", app.phone_share_var, app.open_path, on_change=app.on_phone_dir_changed).pack(
            fill="x", padx=theme.PAD, pady=(0, 6))
        hint_label(right, "安全：地址带随机口令，每次开启都会变化；手机只能访问共享文件夹，读不到电脑上的其他文件。",
                   wrap=360).pack(fill="x", padx=theme.PAD, pady=(6, 18))

    def _placeholder(self):
        s = self.QR_SIZE * 2
        img = Image.new("RGB", (s, s), "#F1F5F9")
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([6, 6, s - 6, s - 6], radius=28, outline="#CBD5E1", width=4)
        return ctk.CTkImage(img, img, size=(self.QR_SIZE, self.QR_SIZE))

    def show_qr(self, url):
        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="png", scale=10, border=3)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        self.qr.configure(image=ctk.CTkImage(img, img, size=(self.QR_SIZE, self.QR_SIZE)), text="")
        self.url_var.set(url)

    def set_active(self, active):
        if active:
            self.pill.set("已开启，等待手机扫码", "active")
        else:
            self.pill.set("未开启", "idle")
            self.qr.configure(image=self._placeholder())
            self.url_var.set("开启后显示访问地址")
        self.button.configure(text="关闭手机互传" if active else "开启手机互传",
                              fg_color=theme.DANGER if active else theme.BRAND,
                              hover_color="#B91C1C" if active else theme.BRAND_HOVER)


class HistoryPage(ctk.CTkFrame):
    _KIND = {"recv": ("接收", theme.SUCCESS), "send": ("发送", theme.BRAND),
             "phone_up": ("手机上传", "#7C3AED"), "phone_down": ("手机下载", "#D97706")}

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        card = Card(self)
        card.pack(fill="both", expand=True)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=theme.PAD, pady=(18, 0))
        title_label(head, "传输记录").pack(side="left")
        secondary_button(head, "清空记录", app.clear_history, width=96).pack(side="right")
        self.body = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=theme.PAD - 6, pady=(10, 16))
        self.refresh()

    def refresh(self):
        for child in self.body.winfo_children():
            child.destroy()
        records = self.app.history
        if not records:
            hint_label(self.body, "暂无记录。完成的接收、发送和手机传输都会显示在这里，可一键打开所在位置。").pack(
                fill="x", pady=24, padx=6)
            return
        for rec in records:
            label, color = self._KIND.get(rec["kind"], ("传输", theme.BRAND))
            row = ctk.CTkFrame(self.body, fg_color=theme.INPUT_BG, corner_radius=10)
            row.pack(fill="x", pady=4, padx=6)
            ctk.CTkLabel(row, text=label, width=76, height=26, corner_radius=13, fg_color=color, text_color="white",
                         font=theme.font(12, "bold")).pack(side="left", padx=12, pady=12)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=f"{rec['peer']}    ·    {rec['count']} 个文件，{fmt_size(rec['size'])}",
                         font=theme.font(13, "bold"), text_color=theme.TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(info, text=f"{rec['time']}    {rec['path'] or ''}", font=theme.font(11),
                         text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x")
            if rec.get("path"):
                secondary_button(row, "打开位置", lambda p=rec["path"]: self.app.open_path(p),
                                 image=icon("folder", 16), width=104).pack(side="right", padx=12)
