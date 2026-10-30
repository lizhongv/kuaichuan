"""手机互传网页服务测试：用 HTTP 请求模拟手机浏览器。"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from conftest import drain
from kuaichuan import config
from kuaichuan.web import WebServer

# 绕过系统代理：部分办公电脑设置了 HTTP 代理，会把本机请求转走
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture
def server(tmp_path, events, free_port):
    (tmp_path / "share" / "子目录").mkdir(parents=True)
    (tmp_path / "share" / "电脑文件.bin").write_bytes(os.urandom(2 * 1024 * 1024))
    (tmp_path / "share" / "子目录" / "说明 文档.txt").write_text("中文", encoding="utf-8")
    s = WebServer(tmp_path / "up", tmp_path / "share", events, port=free_port)
    s.start()
    time.sleep(0.2)
    yield s
    s.stop()


def _call(server, path, data=None):
    url = f"http://127.0.0.1:{server.port}{path}"
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    try:
        with _OPENER.open(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def test_page_requires_token(server):
    assert _call(server, "/")[0] == 403
    assert _call(server, "/list?k=wrong")[0] == 403
    status, body = _call(server, f"/?k={server.token}")
    assert status == 200 and config.HOSTNAME in body.decode("utf-8")


def test_upload_does_not_overwrite(server):
    name = urllib.parse.quote("IMG_手机照片.jpg")
    photo = os.urandom(300 * 1024)
    for expected in ("IMG_手机照片.jpg", "IMG_手机照片 (1).jpg"):
        status, body = _call(server, f"/upload?k={server.token}&name={name}", photo)
        assert status == 200 and json.loads(body)["saved"] == expected
    with open(os.path.join(server.httpd.upload_dir, "IMG_手机照片.jpg"), "rb") as f:
        assert f.read() == photo


def test_upload_name_cannot_escape(server):
    name = urllib.parse.quote("../../evil.txt")
    status, body = _call(server, f"/upload?k={server.token}&name={name}", b"x")
    assert status == 200 and json.loads(body)["saved"] == "evil.txt"
    assert os.path.exists(os.path.join(server.httpd.upload_dir, "evil.txt"))


def test_list_and_download(server, events):
    status, body = _call(server, f"/list?k={server.token}")
    files = {f["p"]: f["s"] for f in json.loads(body)["files"]}
    assert files == {"子目录/说明 文档.txt": 6, "电脑文件.bin": 2 * 1024 * 1024}
    status, body = _call(server, f"/dl?k={server.token}&p=" + urllib.parse.quote("子目录/说明 文档.txt"))
    assert status == 200 and body.decode("utf-8") == "中文"
    time.sleep(0.2)
    assert any(e["type"] == "phone_download_done" for e in drain(events))


def test_download_cannot_escape(server):
    assert _call(server, f"/dl?k={server.token}&p=" + urllib.parse.quote("../up/x"))[0] == 403
