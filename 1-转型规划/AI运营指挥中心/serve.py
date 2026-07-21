"""AI 运营指挥中心 · 静态托管服务（Python 标准库，零三方依赖，便于 .51 常驻）。

托管当前目录：
  · index.html            —— 命令中心页面（部署时由 AI运营指挥中心-框架原型-*.html 改名而来）
  · data/                 —— 同源数据目录（销售域实时 JSON dashboard_data.json 等，见队列 #53）
端口默认 8092（区别于保供看板 8091 / 企微服务）；绑 0.0.0.0 供 LAN 访问。
所有响应 Cache-Control: no-store —— 保证销售域 fetch 每次拿到最新 dashboard_data.json。

用法：python serve.py [端口]    （不传端口则用环境变量 CC_PORT 或默认 8092）
"""
from __future__ import annotations

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("CC_PORT", "8092"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("AI 运营指挥中心 serving %s on 0.0.0.0:%d" % (ROOT, PORT), flush=True)
    httpd.serve_forever()
