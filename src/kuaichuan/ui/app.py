"""主窗口：左侧导航 + 页面区 + 底部传输进度；负责调度后台线程并处理其事件。"""

import os
import queue
import sys
import threading
from tkinter import messagebox

import customtkinter as ctk

from kuaichuan import __version__, config
from kuaichuan.transfer import Receiver, Sender, discover
from kuaichuan.ui import theme
from kuaichuan.ui.icons import icon, logo_image
from kuaichuan.ui.pages import HistoryPage, PhonePage, ReceivePage, SendPage
from kuaichuan.ui.widgets import ResultDialog, TransferPanel
from kuaichuan.utils import fmt_size, local_ips
from kuaichuan.web import WebServer

NAV = [("recv", "接收文件", "recv", "开启接收，局域网内的电脑即可把文件发给本机"),
       ("send", "发送文件", "send", "搜索同一网络中的设备，发送文件或整个文件夹"),
       ("phone", "手机互传", "phone", "手机扫码即可与电脑互传，无需安装 App"),
       ("history", "传输记录", "history", "查看最近的传输，一键打开文件所在位置")]


class App(ctk.CTk):
    def __init__(self):
        self.settings = config.load_settings()
        ctk.set_appearance_mode(self.settings.get("appearance", "light"))
        super().__init__(fg_color=theme.BG)
        self.title(f"{config.APP_NAME} · {config.APP_SLOGAN}")
        self.geometry("1000x700")
        self.minsize(900, 640)
        self._set_icon()

        self.events = queue.Queue()
        self.history = config.load_history()
        self.receiver = None
        self.sender = None
        self.web = None

        self.save_dir_var = ctk.StringVar(value=self.settings["save_dir"])
        self.auto_open_var = ctk.BooleanVar(value=self.settings["auto_open"])
        self.phone_up_var = ctk.StringVar(value=self.settings["phone_upload_dir"])
        self.phone_share_var = ctk.StringVar(value=self.settings["phone_share_dir"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self.show("recv")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._poll)

    # ================================================================ 布局
    def _set_icon(self):
        if os.name == "nt":
            try:   # 让任务栏使用本程序图标，而不是 python.exe 的图标
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{config.APP_ID}.App")
            except (OSError, AttributeError):
                pass
        ico = config.resource_path("assets", "icon.ico")
        if os.path.exists(ico):
            # customtkinter 启动后约 200ms 会设置自带图标，这里延后覆盖
            self.after(300, lambda: self.iconbitmap(ico))

    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=theme.SIDEBAR)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.pack_propagate(False)

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 30))
        logo = logo_image(128)
        ctk.CTkLabel(brand, text="", image=ctk.CTkImage(logo, logo, size=(40, 40))).pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=12)
        ctk.CTkLabel(names, text=config.APP_NAME, font=theme.font(20, "bold"), text_color="white",
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(names, text=config.APP_SLOGAN, font=theme.font(11), text_color=theme.SIDEBAR_TEXT,
                     anchor="w").pack(fill="x")

        self.nav_buttons = {}
        for key, text, ico, _ in NAV:
            btn = ctk.CTkButton(bar, text=f"  {text}", image=icon(ico, 20, light="#C7D2E5", dark="#AEB9CC"),
                                anchor="w", height=44, corner_radius=10, font=theme.font(14),
                                fg_color="transparent", hover_color=theme.SIDEBAR_HOVER,
                                text_color=theme.SIDEBAR_TEXT, command=lambda k=key: self.show(k))
            btn.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = btn

        bottom = ctk.CTkFrame(bar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=14, pady=18)
        device = ctk.CTkFrame(bottom, fg_color=theme.SIDEBAR_HOVER, corner_radius=12)
        device.pack(fill="x")
        ctk.CTkLabel(device, text="本机", font=theme.font(11), text_color=theme.SIDEBAR_TEXT, anchor="w").pack(
            fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(device, text=config.HOSTNAME, font=theme.font(13, "bold"), text_color="white",
                     anchor="w").pack(fill="x", padx=14)
        ctk.CTkLabel(device, text="\n".join(local_ips()[:2]) or "未连接网络", font=theme.font(11),
                     text_color=theme.SIDEBAR_TEXT, anchor="w", justify="left").pack(fill="x", padx=14,
                                                                                    pady=(0, 10))
        self.appearance = ctk.CTkSegmentedButton(bottom, values=["浅色", "深色"], height=30,
                                                 font=theme.font(12), command=self._switch_appearance,
                                                 selected_color=theme.BRAND, selected_hover_color=theme.BRAND_HOVER,
                                                 unselected_color=theme.SIDEBAR_HOVER,
                                                 unselected_hover_color=theme.SIDEBAR_HOVER, text_color="white")
        self.appearance.set("深色" if self.settings.get("appearance") == "dark" else "浅色")
        self.appearance.pack(fill="x", pady=(12, 6))
        ctk.CTkLabel(bottom, text=f"v{__version__}", font=theme.font(11), text_color=theme.SIDEBAR_TEXT).pack()

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=24, pady=(20, 20))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.page_title = ctk.CTkLabel(head, text="", font=theme.font(24, "bold"), text_color=theme.TEXT, anchor="w")
        self.page_title.pack(fill="x")
        self.page_sub = ctk.CTkLabel(head, text="", font=theme.font(13), text_color=theme.TEXT_MUTED, anchor="w")
        self.page_sub.pack(fill="x")

        holder = ctk.CTkFrame(main, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.pages = {"recv": ReceivePage(holder, self), "send": SendPage(holder, self),
                      "phone": PhonePage(holder, self), "history": HistoryPage(holder, self)}
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.panel = TransferPanel(main)
        self.panel.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def show(self, key):
        for k, btn in self.nav_buttons.items():
            active = k == key
            btn.configure(fg_color=theme.SIDEBAR_ACTIVE if active else "transparent",
                          text_color="white" if active else theme.SIDEBAR_TEXT,
                          image=icon(dict((n[0], n[2]) for n in NAV)[k], 20,
                                     light="white" if active else "#C7D2E5", dark="white" if active else "#AEB9CC"))
        _, text, _, sub = next(n for n in NAV if n[0] == key)
        self.page_title.configure(text=text)
        self.page_sub.configure(text=sub)
        self.pages[key].tkraise()

    def _switch_appearance(self, value):
        mode = "dark" if value == "深色" else "light"
        ctk.set_appearance_mode(mode)
        self.settings["appearance"] = mode
        self.persist_settings()

    # ================================================================ 设置与通用动作
    def persist_settings(self):
        self.settings.update(save_dir=os.path.abspath(self.save_dir_var.get()),
                             auto_open=bool(self.auto_open_var.get()),
                             phone_upload_dir=os.path.abspath(self.phone_up_var.get()),
                             phone_share_dir=os.path.abspath(self.phone_share_var.get()))
        config.save_settings(self.settings)

    def on_save_dir_changed(self):
        self.persist_settings()
        if self.receiver:
            self.toast("保存位置已修改，重新开启接收后生效")

    def on_phone_dir_changed(self):
        self.persist_settings()
        if self.web:
            self.toast("文件夹已修改，重新开启手机互传后生效")

    def open_path(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)  # noqa: S606  打开用户自己的文件夹
        except OSError as exc:
            messagebox.showerror(config.APP_NAME, f"无法打开：{path}\n{exc}")

    def toast(self, text, ok=True):
        if ok:
            self.panel.connecting(text)
        else:
            self.panel.failure(text)

    def record(self, kind, peer, count, size, path):
        config.append_history(self.history, kind, peer, count, size, path)
        self.pages["history"].refresh()

    def clear_history(self):
        if self.history and messagebox.askyesno(config.APP_NAME, "确定清空全部传输记录吗？（不会删除文件）"):
            config.clear_history(self.history)
            self.pages["history"].refresh()

    # ================================================================ 接收
    def toggle_receive(self):
        page = self.pages["recv"]
        if self.receiver:
            self.receiver.stop()
            self.receiver = None
            page.set_active(False)
            return
        save_dir = os.path.abspath(self.save_dir_var.get())
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(config.APP_NAME, f"无法使用保存位置：\n{save_dir}\n{exc}")
            return
        self.persist_settings()
        self.receiver = Receiver(save_dir, self.events)
        self.receiver.start()

    # ================================================================ 发送
    def search_peers(self):
        self.pages["send"].set_searching(True)
        threading.Thread(target=lambda: self.events.put({"type": "discovered", "peers": discover()}),
                         daemon=True).start()

    def start_send(self):
        page = self.pages["send"]
        ip = page.target_ip()
        if not ip:
            messagebox.showwarning(config.APP_NAME, "请先点击「搜索设备」，或输入对方 IP")
            return
        if ip in local_ips() or ip.startswith("127."):
            messagebox.showwarning(config.APP_NAME, "这是本机的地址，请选择另一台电脑")
            return
        if not page.paths:
            messagebox.showwarning(config.APP_NAME, "请先添加要发送的文件或文件夹")
            return
        self.sender = Sender(ip, page.paths, self.events)
        self.sender.start()
        page.set_sending(True)
        self.panel.connecting(f"正在连接 {ip} …")

    def cancel_send(self):
        if self.sender:
            self.sender.cancel()

    # ================================================================ 手机互传
    def toggle_phone(self):
        page = self.pages["phone"]
        if self.web:
            self.web.stop()
            self.web = None
            page.set_active(False)
            return
        upload_dir = os.path.abspath(self.phone_up_var.get())
        share_dir = os.path.abspath(self.phone_share_var.get())
        try:
            os.makedirs(upload_dir, exist_ok=True)
            os.makedirs(share_dir, exist_ok=True)
            self.web = WebServer(upload_dir, share_dir, self.events)
        except OSError as exc:
            self.web = None
            messagebox.showerror(config.APP_NAME, f"无法开启手机互传：{exc}\n"
                                                  f"可能本机已开着另一个快传在使用端口 {config.WEB_PORT}")
            return
        self.web.start()
        self.persist_settings()
        page.set_active(True)
        self.refresh_phone_qr()

    def refresh_phone_qr(self):
        if self.web:
            self.pages["phone"].show_qr(self.web.url(self.pages["phone"].ip_var.get()))

    # ================================================================ 事件
    def _poll(self):
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, ev):
        kind = ev["type"]
        if kind == "progress":
            self.panel.update(ev)
        elif kind == "log":
            if ev.get("level") == "error":
                self.panel.failure(ev["text"])
        elif kind == "recv_ready":
            self.pages["recv"].set_active(True)
        elif kind == "recv_failed":
            self.receiver = None
            self.pages["recv"].set_active(False, error=ev["text"])
        elif kind == "recv_done":
            speed = fmt_size(ev["total"] / ev["elapsed"])
            self.panel.success(f"接收完成：{ev['count']} 个文件，{fmt_size(ev['total'])}",
                               f"来自 {ev['peer']}，平均 {speed}/s，保存在 {ev['path']}")
            self.record("recv", ev["peer"], ev["count"], ev["total"], ev["path"])
            if self.auto_open_var.get():
                self.open_path(ev["path"])
            ResultDialog(self, "接收完成", [("来自", f"{ev['peer']}（{ev['ip']}）"),
                                            ("文件", f"{ev['count']} 个，{fmt_size(ev['total'])}"),
                                            ("平均速度", f"{speed}/s"), ("保存在", ev["path"])],
                         path=ev["path"], on_open=self.open_path)
        elif kind == "send_done":
            self.sender = None
            self.pages["send"].set_sending(False)
            speed = fmt_size(ev["total"] / ev["elapsed"])
            self.panel.success(f"发送完成：{ev['count']} 个文件，{fmt_size(ev['total'])}",
                               f"已发送到 {ev['peer']}，平均 {speed}/s")
            self.record("send", ev["peer"], ev["count"], ev["total"], ev["saved"])
            ResultDialog(self, "发送成功", [("接收设备", f"{ev['peer']}（{ev['ip']}）"),
                                            ("文件", f"{ev['count']} 个，{fmt_size(ev['total'])}"),
                                            ("平均速度", f"{speed}/s"), ("对方保存在", ev["saved"])])
        elif kind == "send_failed":
            self.sender = None
            self.pages["send"].set_sending(False)
            self.panel.failure(ev["text"])
            if not ev.get("cancelled"):
                ResultDialog(self, "发送未完成", [("原因", ev["text"])], ok=False)
        elif kind == "transfer_error":
            self.panel.failure(ev["text"])
        elif kind == "discovered":
            self.pages["send"].set_peers(ev["peers"])
        elif kind == "phone_opened":
            self.pages["phone"].pill.set(f"手机 {ev['ip']} 已连接", "active")
        elif kind == "phone_upload_done":
            self.panel.success(f"收到手机上传：{ev['name']}（{fmt_size(ev['size'])}）",
                               f"来自手机 {ev['ip']}，保存在 {ev['path']}")
            self.record("phone_up", f"手机 {ev['ip']}", 1, ev["size"], ev["path"])
        elif kind == "phone_download_done":
            self.panel.success(f"手机已下载：{ev['name']}（{fmt_size(ev['size'])}）", f"手机 {ev['ip']}")
            self.record("phone_down", f"手机 {ev['ip']}", 1, ev["size"], self.web.httpd.share_dir if self.web else "")

    # ================================================================ 退出
    def on_close(self):
        if self.sender and not messagebox.askyesno(config.APP_NAME, "正在发送文件，确定退出吗？"):
            return
        self.persist_settings()
        if self.receiver:
            self.receiver.stop()
        if self.web:
            self.web.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()
    sys.exit(0)
