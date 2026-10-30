"""测试公共夹具：把 src 加入导入路径，提供空闲端口与本机局域网 IP。"""

import os
import queue
import socket
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


@pytest.fixture
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def events():
    return queue.Queue()


@pytest.fixture
def lan_ip():
    """本机任一非回环 IP；没有网络（如部分 CI 环境）时跳过依赖它的测试。"""
    from kuaichuan.utils import local_ips

    ips = local_ips()
    if not ips:
        pytest.skip("本机没有可用的局域网 IP")
    return ips[0]


def drain(q):
    items = []
    while not q.empty():
        items.append(q.get())
    return items
