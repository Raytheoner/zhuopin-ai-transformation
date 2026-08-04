"""工具-仓库外载体扫描.py 单测（队列 #227②）。

覆盖点：
- 四类载体各自命中/未命中关键词
- 目录不存在时降级跳过（不抛异常）
- 二进制/无法解码文件跳过，不中断整体扫描
- .51 服务扫描：真实本地 HTTP 桩命中 + 网络不可达降级为"不可达清单"
- --skip-http 不发起任何网络请求
- CLI 端到端：多类载体命中同时出现在输出里
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-仓库外载体扫描.py")

_spec = importlib.util.spec_from_file_location("external_carrier_scan", SCRIPT)
scan_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan_tool)


def _run_cli(*extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra],
        capture_output=True, text=True, encoding="utf-8",
    )


class ScanDirectoryUnitTests(unittest.TestCase):
    def test_missing_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "不存在的目录"
            self.assertEqual(scan_tool.scan_cowork_artifacts("关键词", missing), [])

    def test_keyword_found_with_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "index.html").write_text(
                "第一行\n落库 sweep 每 4h 运行一次\n第三行\n", encoding="utf-8",
            )
            hits = scan_tool.scan_cowork_artifacts("每 4h", base)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["line_no"], 2)
            self.assertIn("每 4h", hits[0]["line"])

    def test_binary_file_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "图片.html").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
            (base / "正常.md").write_text("含有关键词PT1H的一行\n", encoding="utf-8")
            hits = scan_tool.scan_cowork_artifacts("PT1H", base)
            self.assertEqual(len(hits), 1)
            self.assertIn("正常.md", hits[0]["path"])

    def test_non_text_suffix_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "图标.png").write_bytes(b"\x89PNG\r\n")
            hits = scan_tool.scan_cowork_artifacts("PNG", base)
            self.assertEqual(hits, [])

    def test_scheduled_tasks_scan_finds_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "some-task"
            base.mkdir()
            (base / "run.ps1").write_text("# 每小时触发一次 PT1H\n", encoding="utf-8")
            hits = scan_tool.scan_scheduled_tasks("PT1H", base.parent)
            self.assertEqual(len(hits), 1)

    def test_installed_skills_scan_finds_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "some-skill"
            base.mkdir()
            (base / "SKILL.md").write_text("周期：PT1H\n", encoding="utf-8")
            hits = scan_tool.scan_installed_skills("PT1H", base.parent)
            self.assertEqual(len(hits), 1)


class _StubServiceHandler(BaseHTTPRequestHandler):
    """极简本地桩：GET 请求恒回一段含"每 4h"字样的 HTML。"""

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler 既定命名
        body = "<html><body>落库 sweep 每 4h 运行一次</body></html>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默——不打印到测试输出
        pass


class Scan51ServicesTests(unittest.TestCase):
    def setUp(self):
        self._server = HTTPServer(("127.0.0.1", 0), _StubServiceHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.url = f"http://127.0.0.1:{self._server.server_port}/"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()

    def test_reachable_service_keyword_hit(self):
        hits, unreachable = scan_tool.scan_51_services("每 4h", (self.url,), timeout=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(unreachable, [])

    def test_unreachable_service_is_reported_not_raised(self):
        # 127.0.0.1 上一个大概率无人监听的端口，制造连接失败。
        dead_url = "http://127.0.0.1:1/"
        hits, unreachable = scan_tool.scan_51_services("任意关键词", (dead_url,), timeout=1)
        self.assertEqual(hits, [])
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(unreachable[0]["url"], dead_url)


class CliEndToEndTests(unittest.TestCase):
    def test_multiple_carriers_hit_reported_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            artifacts = base / "artifacts"
            scheduled = base / "scheduled" / "some-task"
            skills = base / "skills" / "some-skill"
            for d in (artifacts, scheduled, skills):
                d.mkdir(parents=True)
            (artifacts / "index.html").write_text("周期 PT1H\n", encoding="utf-8")
            (scheduled / "run.ps1").write_text("周期 PT1H\n", encoding="utf-8")
            (skills / "SKILL.md").write_text("周期 PT1H\n", encoding="utf-8")

            result = _run_cli(
                "PT1H", "--skip-http",
                "--artifacts-dir", str(artifacts),
                "--scheduled-dir", str(scheduled.parent),
                "--skills-dir", str(skills.parent),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cowork artifacts", result.stdout)
            self.assertIn("命中 1 处", result.stdout)
            self.assertIn("已按 --skip-http 跳过联网检查", result.stdout)

    def test_missing_carrier_directories_do_not_fail_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "不存在"
            result = _run_cli(
                "任意关键词", "--skip-http",
                "--artifacts-dir", str(missing),
                "--scheduled-dir", str(missing),
                "--skills-dir", str(missing),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("目录不存在，跳过", result.stdout)


if __name__ == "__main__":
    unittest.main()
