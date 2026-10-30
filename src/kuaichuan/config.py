"""全局常量、资源路径、用户设置与传输记录的读写。

设置与记录保存在 ``%APPDATA%\\KuaiChuan``，读取失败时回退默认值，不影响启动。
"""

import json
import os
import socket
import sys
import time

APP_NAME = "快传"
APP_ID = "KuaiChuan"
APP_SLOGAN = "局域网极速互传"

PORT = 9000                 # 电脑互传：TCP
DISCOVER_PORT = 9001        # 设备搜索：UDP 广播
WEB_PORT = 9002             # 手机互传：HTTP
DISCOVER_MAGIC = b"KUAICHUAN2?"

CHUNK_SIZE = 4 * 1024 * 1024    # 读写块大小：局域网吞吐与内存占用的折中
PROGRESS_INTERVAL = 0.1         # 进度事件最小间隔（秒），避免大量小文件刷屏
CONNECT_TIMEOUT = 8
IO_TIMEOUT = 30

HOSTNAME = socket.gethostname()
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_ID)
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
HISTORY_LIMIT = 200


def resource_path(*parts):
    """返回包内资源路径；兼容 PyInstaller 单文件模式解压目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.join(sys._MEIPASS, "kuaichuan")  # noqa: SLF001  PyInstaller 约定属性
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def desktop_dir():
    """取 Windows 实际桌面路径（开启 OneDrive 桌面同步时不是 ~/Desktop）。"""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD),
                            ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

            folder_id = GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                             (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
            path = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(path)) == 0:
                result = path.value
                ctypes.windll.ole32.CoTaskMemFree(path)
                return result
        except (OSError, AttributeError):
            pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def default_settings():
    desk = desktop_dir()
    return {
        "save_dir": os.path.join(desk, "快传接收"),
        "auto_open": True,
        "phone_upload_dir": os.path.join(desk, "快传接收"),
        "phone_share_dir": os.path.join(desk, "快传共享"),
        "appearance": "light",
    }


def _read_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def _write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)   # 先写临时文件再替换，避免写一半时崩溃把设置清空
    except OSError:
        pass


def load_settings():
    settings = default_settings()
    stored = _read_json(SETTINGS_FILE, {})
    if isinstance(stored, dict):
        settings.update({k: v for k, v in stored.items() if k in settings})
    return settings


def save_settings(settings):
    _write_json(SETTINGS_FILE, settings)


def load_history():
    data = _read_json(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def append_history(history, kind, peer, count, size, path):
    """新增一条传输记录（最新在前）并落盘。kind：recv / send / phone_up / phone_down。"""
    history.insert(0, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "peer": peer,
                       "count": count, "size": size, "path": path})
    del history[HISTORY_LIMIT:]
    _write_json(HISTORY_FILE, history)
    return history


def clear_history(history):
    history.clear()
    _write_json(HISTORY_FILE, history)
