"""电脑互传端到端测试：在本机起接收服务，模拟「另一台电脑」完成收发。"""

import hashlib
import os
import time

import pytest

from conftest import drain
from kuaichuan import transfer, utils


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "src"
    (src / "资料" / "子目录").mkdir(parents=True)
    (src / "大文件.bin").write_bytes(os.urandom(12 * 1024 * 1024))
    (src / "资料" / "子目录" / "说明.txt").write_text("中文内容", encoding="utf-8")
    (src / "资料" / "空文件.txt").write_bytes(b"")
    return src


@pytest.fixture
def receiver(tmp_path, events, free_port):
    r = transfer.Receiver(tmp_path / "out", events, port=free_port)
    r.name = "另一台电脑"             # 模拟另一台电脑，避开「发给自己」校验
    r.start()
    deadline = time.time() + 3
    while time.time() < deadline and not any(e["type"] == "recv_ready" for e in list(events.queue)):
        time.sleep(0.05)
    yield r
    r.stop()


def _send(host, paths, port, cancel=False):
    from queue import Queue

    q = Queue()
    s = transfer.Sender(host, paths, q, port=port)
    if cancel:
        # 启动前就置位取消：发送方握手、发出首个文件头后，在发送第一块内容前中止。
        # 不依赖计时，避免在快机器上文件已传完才取消导致结果不稳定
        s.cancel()
    s.start()
    s.join(timeout=30)
    return [e for e in drain(q) if e["type"] in ("send_done", "send_failed")][-1]


def _md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def test_send_files_and_folder(receiver, source, lan_ip, monkeypatch):
    monkeypatch.setattr(utils, "local_ips", lambda: ["10.255.255.1"])   # 让发送方不把目标认作本机
    result = _send(lan_ip, [source / "大文件.bin", source / "资料"], receiver.port)
    assert result["type"] == "send_done"
    assert result["peer"] == "另一台电脑"
    assert result["count"] == 3
    out = receiver.save_dir
    assert _md5(source / "大文件.bin") == _md5(os.path.join(out, "大文件.bin"))
    assert open(os.path.join(out, "资料", "子目录", "说明.txt"), encoding="utf-8").read() == "中文内容"
    assert os.path.exists(os.path.join(out, "资料", "空文件.txt"))
    time.sleep(0.3)
    done = [e for e in drain(receiver.events) if e["type"] == "recv_done"]
    assert done and done[-1]["count"] == 3


def test_refuse_sending_to_self(tmp_path, events, free_port, source):
    r = transfer.Receiver(tmp_path / "out", events, port=free_port)   # 电脑名即本机名
    r.start()
    time.sleep(0.5)
    try:
        result = _send("127.0.0.1", [source / "大文件.bin"], free_port)
        assert result["type"] == "send_failed"
        assert "本机" in result["text"]
    finally:
        r.stop()


def test_cancel_removes_partial_file(receiver, source, lan_ip, monkeypatch):
    monkeypatch.setattr(utils, "local_ips", lambda: ["10.255.255.1"])
    result = _send(lan_ip, [source / "大文件.bin"], receiver.port, cancel=True)
    assert result["type"] == "send_failed" and result["cancelled"]
    deadline = time.time() + 5
    while time.time() < deadline and not any(e["type"] == "transfer_error" for e in list(receiver.events.queue)):
        time.sleep(0.05)
    assert any(e["type"] == "transfer_error" for e in drain(receiver.events))
    assert not os.path.exists(os.path.join(receiver.save_dir, "大文件.bin"))


def test_connection_refused(source, free_port):
    result = _send("127.0.0.1", [source / "大文件.bin"], free_port)    # 该端口没有接收服务
    assert result["type"] == "send_failed"
    assert "拒绝连接" in result["text"]
