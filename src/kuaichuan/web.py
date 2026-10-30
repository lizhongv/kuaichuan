"""手机互传：内置 HTTP 服务，手机扫码用浏览器打开即可上传、下载，无需安装 App。

接口（均需携带口令 ``k``，口令每次开启随机生成）：

* ``GET  /``                     手机端网页
* ``GET  /list``                 列出共享文件夹 ``{"files": [{"p": 相对路径, "s": 大小}]}``
* ``GET  /dl?p=相对路径``        下载共享文件
* ``POST /upload?name=文件名``   请求体为文件原始内容，边收边写盘

推送给界面的事件：phone_opened(ip)、phone_upload_done(ip, name, size, path)、
phone_download_done(ip, name, size)、log、progress（direction 为 phone_up / phone_down）。
"""

import http.server
import json
import os
import secrets
import threading
import time
import urllib.parse

from kuaichuan import config, utils
from kuaichuan.transfer import Progress


def _load_page():
    with open(config.resource_path("assets", "mobile.html"), encoding="utf-8") as f:
        return f.read()


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = config.APP_ID

    def log_message(self, *args):     # 窗口版没有控制台，不输出访问日志
        pass

    # ------------------------------------------------------------ 工具
    def _parse(self):
        url = urllib.parse.urlparse(self.path)
        return url.path, {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}

    def _authorized(self, query):
        if not secrets.compare_digest(query.get("k", ""), self.server.token):
            self.send_error(403, "Forbidden")
            return False
        return True

    def _reply(self, code, body, content_type="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    @property
    def _ip(self):
        return self.client_address[0]

    # ------------------------------------------------------------ GET
    def do_GET(self):  # noqa: N802  BaseHTTPRequestHandler 约定方法名
        path, query = self._parse()
        if not self._authorized(query):
            return
        events, share = self.server.events, self.server.share_dir
        if path == "/":
            page = (self.server.page.replace("__HOST__", config.HOSTNAME)
                    .replace("__UPDIR__", os.path.basename(self.server.upload_dir)))
            self._reply(200, page, "text/html; charset=utf-8")
            events.put({"type": "phone_opened", "ip": self._ip})
        elif path == "/list":
            files = [{"p": os.path.relpath(full, share).replace("\\", "/"), "s": os.path.getsize(full)}
                     for full, _ in utils.iter_files([share])]
            self._reply(200, json.dumps({"files": sorted(files, key=lambda x: x["p"])}, ensure_ascii=False))
        elif path == "/dl":
            self._download(query.get("p", ""))
        else:
            self.send_error(404)

    def _download(self, rel):
        try:
            full = utils.safe_join(self.server.share_dir, rel)
        except ValueError:
            self.send_error(403)
            return
        if not os.path.isfile(full):
            self.send_error(404)
            return
        size = os.path.getsize(full)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition",
                         f"attachment; filename*=UTF-8''{urllib.parse.quote(os.path.basename(full))}")
        self.end_headers()
        progress = Progress(self.server.events, "phone_down", 1, size)
        done = 0
        try:
            with open(full, "rb") as fh:
                while True:
                    block = fh.read(config.CHUNK_SIZE)
                    if not block:
                        break
                    self.wfile.write(block)
                    done += len(block)
                    progress.update(1, rel, done, size, len(block))
            self.server.events.put({"type": "phone_download_done", "ip": self._ip, "name": rel, "size": size})
        except OSError:
            self.server.events.put({"type": "log", "level": "error", "text": f"手机下载中断：{rel}"})

    # ------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802
        path, query = self._parse()
        if not self._authorized(query):
            return
        if path != "/upload":
            self.send_error(404)
            return
        events, upload_dir = self.server.events, self.server.upload_dir
        # 只取文件名部分，丢弃手机端可能带来的目录，杜绝越界写入
        name = os.path.basename(query.get("name", "").replace("\\", "/")) or f"手机文件_{time.strftime('%H%M%S')}"
        size = int(self.headers.get("Content-Length", 0))
        os.makedirs(upload_dir, exist_ok=True)
        target = utils.unique_path(utils.safe_join(upload_dir, name))
        progress = Progress(events, "phone_up", 1, size)
        done = 0
        try:
            with open(target, "wb") as fh:
                while done < size:
                    block = self.rfile.read(min(config.CHUNK_SIZE, size - done))
                    if not block:
                        raise ConnectionError("手机端中断")
                    fh.write(block)
                    done += len(block)
                    progress.update(1, name, done, size, len(block))
        except (ConnectionError, OSError) as exc:
            try:
                os.remove(target)
            except OSError:
                pass
            events.put({"type": "log", "level": "error", "text": f"手机上传中断：{name}（{exc}）"})
            return
        saved = os.path.basename(target)
        self._reply(200, json.dumps({"ok": True, "saved": saved}, ensure_ascii=False))
        events.put({"type": "phone_upload_done", "ip": self._ip, "name": saved, "size": size, "path": upload_dir})


class WebServer(threading.Thread):
    """手机互传服务；构造时绑定端口，端口被占用会直接抛出 OSError。"""

    def __init__(self, upload_dir, share_dir, events, port=None):
        super().__init__(daemon=True)
        self.port = port or config.WEB_PORT
        self.httpd = http.server.ThreadingHTTPServer(("0.0.0.0", self.port), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.token = secrets.token_urlsafe(6)
        self.httpd.upload_dir = os.path.abspath(upload_dir)
        self.httpd.share_dir = os.path.abspath(share_dir)
        self.httpd.events = events
        self.httpd.page = _load_page()

    @property
    def token(self):
        return self.httpd.token

    def url(self, ip):
        return f"http://{ip}:{self.port}/?k={self.token}"

    def run(self):
        self.httpd.serve_forever(poll_interval=0.5)

    def stop(self):
        # shutdown 会阻塞到 serve_forever 退出，放到线程里避免卡住界面
        threading.Thread(target=lambda: (self.httpd.shutdown(), self.httpd.server_close()), daemon=True).start()
