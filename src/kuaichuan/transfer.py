"""电脑互传：接收服务、发送任务与局域网设备搜索。

后台线程不直接操作界面，只向 ``events``（queue.Queue）推送事件字典，由界面线程统一刷新：

=================  ==========================================================
type               字段
=================  ==========================================================
progress           direction, index, count, name, file_done, file_size,
                   done, total, elapsed
log                text, level（info / success / error）
recv_ready         ——
recv_failed        text
recv_done          peer, ip, count, total, elapsed, path, files
send_done          peer, ip, count, total, elapsed, saved
send_failed        text, cancelled
transfer_error     text
discovered         peers：[(ip, 电脑名)]
=================  ==========================================================
"""

import json
import os
import socket
import threading
import time

from kuaichuan import config, utils
from kuaichuan.protocol import ACK, recv_exact, recv_msg, send_msg


class Progress:
    """按时间节流地推送进度事件。"""

    def __init__(self, events, direction, count, total):
        self.events, self.direction, self.count, self.total = events, direction, count, total
        self.start = time.time()
        self.done = 0
        self._last = 0.0

    def update(self, index, name, file_done, file_size, added, force=False):
        self.done += added
        now = time.time()
        if force or now - self._last >= config.PROGRESS_INTERVAL:
            self._last = now
            self.events.put({"type": "progress", "direction": self.direction, "index": index,
                             "count": self.count, "name": name, "file_done": file_done,
                             "file_size": file_size, "done": self.done, "total": self.total,
                             "elapsed": now - self.start})

    @property
    def elapsed(self):
        return max(time.time() - self.start, 1e-6)


class Receiver(threading.Thread):
    """监听 TCP 端口接收文件，并在 UDP 端口响应设备搜索。"""

    def __init__(self, save_dir, events, port=None):
        super().__init__(daemon=True)
        self.save_dir = os.path.abspath(save_dir)
        self.events = events
        self.port = port or config.PORT
        self.name = config.HOSTNAME          # 报给对方的电脑名（测试中可替换以模拟另一台电脑）
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    # ------------------------------------------------------------ 设备搜索应答
    def _discover_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", config.DISCOVER_PORT))
        except OSError:
            self.events.put({"type": "log", "level": "error",
                             "text": "搜索端口被占用，对方需要手动输入本机 IP"})
            return
        sock.settimeout(1)
        while not self.stop_event.is_set():
            try:
                data, addr = sock.recvfrom(1024)
            except OSError:
                continue
            if data == config.DISCOVER_MAGIC:
                reply = json.dumps({"name": self.name, "port": self.port}, ensure_ascii=False)
                sock.sendto(reply.encode("utf-8"), addr)
        sock.close()

    # ------------------------------------------------------------ 接收服务
    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(("0.0.0.0", self.port))
        except OSError:
            self.events.put({"type": "recv_failed",
                             "text": f"端口 {self.port} 已被占用，可能本机已经开着一个快传在接收"})
            return
        threading.Thread(target=self._discover_loop, daemon=True).start()
        server.listen(1)
        server.settimeout(1)
        self.events.put({"type": "recv_ready"})
        while not self.stop_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            self._handle(conn, addr[0])
        server.close()

    def _handle(self, conn, ip):
        partial = None
        with conn:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, config.CHUNK_SIZE)
            try:
                send_msg(conn, {"name": self.name, "dir": self.save_dir})
                hello = recv_msg(conn)
                peer = hello.get("from") or ip
                count, total = hello.get("count", 0), hello.get("total", 0)
                self.events.put({"type": "log", "level": "info",
                                 "text": f"开始接收：来自 {peer}（{ip}），{count} 个文件，{utils.fmt_size(total)}"})
                progress = Progress(self.events, "recv", count, total)
                received = []
                while True:
                    head = recv_msg(conn)
                    if not head["name"]:
                        break
                    index = len(received) + 1
                    target = utils.safe_join(self.save_dir, head["name"])
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    size, done = head["size"], 0
                    partial = target
                    with open(target, "wb") as fh:
                        while done < size:
                            block = conn.recv(min(config.CHUNK_SIZE, size - done))
                            if not block:
                                raise ConnectionError("对方已取消或连接中断")
                            fh.write(block)
                            done += len(block)
                            progress.update(index, head["name"], done, size, len(block))
                    partial = None
                    progress.update(index, head["name"], size, size, 0, force=True)
                    conn.sendall(ACK)
                    received.append(head["name"])
                send_msg(conn, {"saved": self.save_dir, "count": len(received), "total": total})
                self.events.put({"type": "recv_done", "peer": peer, "ip": ip, "count": len(received),
                                 "total": total, "elapsed": progress.elapsed, "path": self.save_dir,
                                 "files": received})
            except (ConnectionError, ValueError, OSError) as exc:
                if partial and os.path.exists(partial):
                    try:
                        os.remove(partial)      # 半截文件没有意义，删除以免误用
                    except OSError:
                        pass
                self.events.put({"type": "transfer_error", "text": f"接收中断：{exc}"})


class Sender(threading.Thread):
    """连接接收方并依次发送文件；可通过 cancel() 中途取消。"""

    def __init__(self, host, paths, events, port=None):
        super().__init__(daemon=True)
        self.host, self.paths, self.events = host, list(paths), events
        self.port = port or config.PORT
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def _fail(self, text, cancelled=False):
        self.events.put({"type": "send_failed", "text": text, "cancelled": cancelled})

    def run(self):
        files = list(utils.iter_files(self.paths))
        if not files:
            self._fail("没有可发送的文件")
            return
        total = sum(os.path.getsize(f) for f, _ in files)
        try:
            with socket.create_connection((self.host, self.port), timeout=config.CONNECT_TIMEOUT) as conn:
                conn.settimeout(config.IO_TIMEOUT)
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, config.CHUNK_SIZE)
                peer = recv_msg(conn)
                # 连上后再校验一次：电脑名相同或 IP 属于本机，说明选中了自己
                if peer.get("name") == config.HOSTNAME or self.host in utils.local_ips() or self.host.startswith("127."):
                    self._fail(f"目标「{peer.get('name')}」就是本机，请选择另一台电脑")
                    return
                self.events.put({"type": "log", "level": "info",
                                 "text": f"已连接 {peer['name']}（{self.host}），对方保存到：{peer['dir']}"})
                send_msg(conn, {"from": config.HOSTNAME, "count": len(files), "total": total})
                progress = Progress(self.events, "send", len(files), total)
                for index, (full, rel) in enumerate(files, 1):
                    size = os.path.getsize(full)
                    send_msg(conn, {"name": rel.replace("\\", "/"), "size": size})
                    done = 0
                    with open(full, "rb") as fh:
                        while True:
                            if self.cancel_event.is_set():
                                raise InterruptedError
                            block = fh.read(config.CHUNK_SIZE)
                            if not block:
                                break
                            conn.sendall(block)
                            done += len(block)
                            progress.update(index, rel, done, size, len(block))
                    if recv_exact(conn, 1) != ACK:
                        raise ConnectionError(f"对方未确认 {rel}")
                    progress.update(index, rel, size, size, 0, force=True)
                send_msg(conn, {"name": ""})
                receipt = recv_msg(conn)
                self.events.put({"type": "send_done", "peer": peer["name"], "ip": self.host,
                                 "count": receipt["count"], "total": total, "elapsed": progress.elapsed,
                                 "saved": receipt["saved"]})
        except InterruptedError:
            self._fail("已取消发送", cancelled=True)
        except socket.timeout:
            self._fail("连接超时：请确认对方已开启接收，且两台电脑在同一网络")
        except ConnectionRefusedError:
            self._fail("对方拒绝连接：请确认对方已开启接收")
        except (OSError, ValueError, KeyError) as exc:
            self._fail(f"发送失败：{exc}")


def discover(timeout=1.5):
    """广播搜索正在接收的设备，按电脑名与 IP 双重排除本机，返回 [(ip, 电脑名)]。"""
    mine = set(utils.local_ips())
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.3)
    # 全局广播之外再按各网卡 /24 子网广播一次，部分路由器不转发 255.255.255.255
    targets = {"255.255.255.255"} | {".".join(ip.split(".")[:3]) + ".255" for ip in mine}
    for target in targets:
        try:
            sock.sendto(config.DISCOVER_MAGIC, (target, config.DISCOVER_PORT))
        except OSError:
            pass
    found = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            name = json.loads(data.decode("utf-8")).get("name", "")
        except (OSError, ValueError):
            continue
        if addr[0] in mine or name == config.HOSTNAME:
            continue
        found[addr[0]] = name
    sock.close()
    return sorted(found.items(), key=lambda item: item[1])
