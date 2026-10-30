"""电脑互传的线路协议：每条控制消息为 8 字节大端长度 + UTF-8 JSON。

一次会话（详见 docs/protocol.md）::

    接收方 → {name, dir}                 握手：报电脑名与保存路径
    发送方 → {from, count, total}        本次文件数与总大小
    循环：发送方 → {name, size} + 文件内容；接收方 → 1 字节确认 0x01
    发送方 → {name: ""}                  结束标记
    接收方 → {saved, count, total}       回执
"""

import json
import struct

from kuaichuan.config import CHUNK_SIZE

ACK = b"\x01"
_HEADER = struct.Struct(">Q")


def send_msg(conn, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    conn.sendall(_HEADER.pack(len(data)) + data)


def recv_exact(conn, n):
    buf = bytearray()
    while len(buf) < n:
        part = conn.recv(min(CHUNK_SIZE, n - len(buf)))
        if not part:
            raise ConnectionError("连接已断开")
        buf += part
    return bytes(buf)


def recv_msg(conn):
    (length,) = _HEADER.unpack(recv_exact(conn, _HEADER.size))
    return json.loads(recv_exact(conn, length).decode("utf-8"))
