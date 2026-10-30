"""通用工具：格式化、路径安全、文件展开、本机网络地址。"""

import os
import socket

from kuaichuan.config import HOSTNAME


def fmt_size(n):
    """字节数转可读大小，如 1.5 GB。"""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_duration(seconds):
    """秒数转 mm:ss 或 h:mm:ss。"""
    seconds = int(max(seconds, 0))
    if seconds >= 3600:
        return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def safe_join(base, rel):
    """拼接保存路径并拒绝 ``../`` 等越界路径，保证文件只写进 base 目录。"""
    base = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base, rel))
    if os.path.commonpath([target, base]) != base:
        raise ValueError(f"拒绝越界路径：{rel}")
    return target


def unique_path(path):
    """同名文件已存在时改名为「名称 (1).扩展名」，不覆盖已有文件。"""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{root} ({i}){ext}"):
        i += 1
    return f"{root} ({i}){ext}"


def iter_files(paths):
    """把文件与文件夹展开为（本地路径, 接收端相对路径）；文件夹保留目录结构。"""
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            yield p, os.path.basename(p)
        elif os.path.isdir(p):
            parent = os.path.dirname(p)
            for root, _, files in os.walk(p):
                for name in sorted(files):
                    full = os.path.join(root, name)
                    yield full, os.path.relpath(full, parent)


def summarize(paths):
    """统计待发送内容的文件数与总大小。"""
    count = total = 0
    for full, _ in iter_files(paths):
        count += 1
        total += os.path.getsize(full)
    return count, total


def local_ips():
    """本机全部 IPv4（含 VPN、虚拟网卡），默认出口网卡排第一。"""
    ips = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))     # UDP connect 不实际发包，只用来选出默认出口网卡
        ips.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(HOSTNAME, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except socket.gaierror:
        pass
    return ips
