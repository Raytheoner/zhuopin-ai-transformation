"""工具-仓库外载体扫描.py 单测（队列 #227②；队列 #398⑵ 补反例）。

覆盖点：
- 四类载体各自命中/未命中关键词
- 目录不存在时降级跳过（不抛异常）
- 二进制/无法解码文件跳过，不中断整体扫描
- .51 服务扫描：真实本地 HTTP 桩命中 + 网络不可达降级为"不可达清单"
- --skip-http 不发起任何网络请求
- CLI 端到端：多类载体命中同时出现在输出里

🔴 队列 #398⑵ 新增的**反例**（每条都对应 2026-08-24 环境体检实测到的一种
结构性假零；这些用例的作用是"零命中必须说不出口"，而不是"零命中要正确"）：
- ② 口令门：HTTP 200 + 正文是登录页 ⇒ 不得报「命中 0 处」，须报「无法核验」
- ①④ 目录还在但 0 个可扫文件 ⇒ 同上
- --skip-http 时 ② 类不得被算作"已核验"
- --strict 下有类无法核验即退出码 2

🔧 队列 #585 ⑶ ③ 类拆分（2026-09-16，CC 侧库内正本免扫／Cowork 侧账号级
安装本机结构性不可达）三态覆盖：
- 仅 CC 侧有 skill、Cowork 侧为空 ⇒ 整体已核验（CC 免扫 ＋ Cowork 侧「无」）
- 仅 Cowork 侧有 skill、CC 侧为空 ⇒ Cowork 侧无法核验，总表落"有类无法核验"
- 两侧都有（混合）⇒ CC 半已核验免扫、Cowork 半无法核验，两条状态并存
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


def _make_full_layout(
    base: Path, cc_names=("zhuopin-followup-letter",), cowork_names=("zhuopin-queue-audit",),
) -> dict:
    """搭一套四类载体齐全的临时目录；③ 类按 CC／Cowork 两侧分别落子目录。"""
    artifacts = base / "artifacts"
    scheduled = base / "scheduled" / "some-task"
    cc_skills = base / ".claude" / "skills"
    source = base / "skills源码"
    for d in (artifacts, scheduled, cc_skills, source):
        d.mkdir(parents=True, exist_ok=True)
    (artifacts / "index.html").write_text("周期 PT1H\n", encoding="utf-8")
    (scheduled / "run.ps1").write_text("周期 PT1H\n", encoding="utf-8")
    for name in cc_names:
        (cc_skills / name).mkdir(exist_ok=True)
        (cc_skills / name / "SKILL.md").write_text("周期 PT1H\n", encoding="utf-8")
    for name in cowork_names:
        (source / name).mkdir(exist_ok=True)
        (source / name / "SKILL.md").write_text("周期 PT1H\n", encoding="utf-8")
    return {
        "artifacts": artifacts,
        "scheduled": scheduled.parent,
        "cc_skills": cc_skills,
        "source": source,
    }


def _cli_args(layout: dict) -> list[str]:
    return [
        "--artifacts-dir", str(layout["artifacts"]),
        "--scheduled-dir", str(layout["scheduled"]),
        "--cc-skills-dir", str(layout["cc_skills"]),
        "--skill-source-dir", str(layout["source"]),
    ]


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

class CountScannableFilesTests(unittest.TestCase):
    """①④ 类阳性对照的判据本身。"""

    def test_counts_only_text_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a.md").write_text("x", encoding="utf-8")
            (base / "b.png").write_bytes(b"\x89PNG")
            self.assertEqual(scan_tool.count_scannable_files(base), 1)

    def test_missing_dir_counts_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(scan_tool.count_scannable_files(Path(tmp) / "无"), 0)


class AuthGateDetectionTests(unittest.TestCase):
    """② 类阳性对照的判据本身（2026-08-24 体检 §4.2 实测形态）。"""

    def test_password_form_is_gate(self):
        self.assertTrue(scan_tool.looks_like_auth_gate(
            '<html><body><input type="password" name="pw"></body></html>'
        ))

    def test_chinese_prompt_is_gate(self):
        self.assertTrue(scan_tool.looks_like_auth_gate("<div>请输入口令</div>"))

    def test_board_content_is_not_gate(self):
        self.assertFalse(scan_tool.looks_like_auth_gate(
            "<html><body>保供看板：落库 sweep 每 4h 运行一次</body></html>"
        ))


class SkillOwnershipSplitTests(unittest.TestCase):
    """③ 类拆分后的判据本身（队列 #585 ⑶，2026-09-16）——CC 侧库内枚举
    ＋ Cowork 侧库内枚举，两者互不依赖对方是否存在。"""

    def test_cc_skill_names_reads_repo_local_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            cc_dir = Path(tmp) / ".claude" / "skills"
            (cc_dir / "zhuopin-followup-letter").mkdir(parents=True)
            self.assertEqual(scan_tool.cc_skill_names(cc_dir), {"zhuopin-followup-letter"})

    def test_cc_skill_names_missing_dir_is_empty_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(scan_tool.cc_skill_names(Path(tmp) / "无此目录"), set())

    def test_cowork_skill_names_reads_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "源码"
            (source / "zhuopin-queue-audit").mkdir(parents=True)
            self.assertEqual(scan_tool.cowork_skill_names(source), {"zhuopin-queue-audit"})

    def test_cowork_skill_names_missing_dir_is_empty_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(scan_tool.cowork_skill_names(Path(tmp) / "无此目录"), set())


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


class _AuthGateHandler(BaseHTTPRequestHandler):
    """反例桩：**HTTP 200**，但正文是访问口令登录页（体检 §4.2 实测形态）。"""

    def do_GET(self):  # noqa: N802
        body = (
            "<html><body><h3>访问口令</h3>"
            '<form><input type="password" name="pw"></form></body></html>'
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _ServerFixture:
    def start(self, handler):
        self._server = HTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_port}/"

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


class Scan51ServicesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _ServerFixture()
        self.url = self.fixture.start(_StubServiceHandler)

    def tearDown(self):
        self.fixture.stop()

    def test_reachable_service_keyword_hit(self):
        hits, unreachable, gated = scan_tool.scan_51_services("每 4h", (self.url,), timeout=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(unreachable, [])
        self.assertEqual(gated, [])

    def test_unreachable_service_is_reported_not_raised(self):
        # 127.0.0.1 上一个大概率无人监听的端口，制造连接失败。
        dead_url = "http://127.0.0.1:1/"
        hits, unreachable, gated = scan_tool.scan_51_services("任意关键词", (dead_url,), timeout=1)
        self.assertEqual(hits, [])
        self.assertEqual(gated, [])
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(unreachable[0]["url"], dead_url)


class Scan51AuthGateTests(unittest.TestCase):
    """🔴 反例：200 + 登录页，绝不能落进"扫过了、零命中"。"""

    def setUp(self):
        self.fixture = _ServerFixture()
        self.url = self.fixture.start(_AuthGateHandler)

    def tearDown(self):
        self.fixture.stop()

    def test_gate_is_not_counted_as_scanned(self):
        hits, unreachable, gated = scan_tool.scan_51_services("每 4h", (self.url,), timeout=3)
        self.assertEqual(hits, [])
        self.assertEqual(unreachable, [], "口令门是内容层问题，不得混进网络不可达")
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0]["url"], self.url)

    def test_cli_reports_unverifiable_not_zero_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=())
            result = _run_cli(
                "每 4h", *_cli_args(layout), "--service-urls", self.url,
            )
            self.assertIn("② .51 四服务页面】🔴 本类无法核验", result.stdout)
            self.assertIn("访问口令登录页", result.stdout)
            self.assertNotIn("【② .51 四服务页面】命中 0 处", result.stdout)
            self.assertIn("🔴 本次 1/5 类无法核验", result.stdout)

    def test_strict_exits_2_when_a_class_is_unverifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=())
            result = _run_cli(
                "每 4h", *_cli_args(layout), "--service-urls", self.url, "--strict",
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_without_strict_exit_code_stays_0(self):
        """不传 --strict 时退出码语义不变，避免打断既有调用方。"""
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp))
            result = _run_cli("每 4h", *_cli_args(layout), "--service-urls", self.url)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CliEndToEndTests(unittest.TestCase):
    def test_multiple_carriers_hit_reported_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp))
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cowork artifacts", result.stdout)
            self.assertIn("命中 1 处", result.stdout)
            self.assertIn("已按 --skip-http 跳过联网检查", result.stdout)

    def test_all_classes_verified_when_only_cc_side_skill_exists(self):
        """三态之一：仅 CC 侧有 skill、Cowork 侧为空 ⇒ 总表全绿。"""
        fixture = _ServerFixture()
        url = fixture.start(_StubServiceHandler)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                layout = _make_full_layout(
                    Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=(),
                )
                result = _run_cli(
                    "PT1H", *_cli_args(layout), "--service-urls", url, "--strict",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("✅ 全部", result.stdout)
                self.assertIn("已核验", result.stdout)
                self.assertIn("CC 侧 skill", result.stdout)
                self.assertIn("免扫", result.stdout)
        finally:
            fixture.stop()

    def test_skip_http_marks_51_class_unverifiable(self):
        """--skip-http 是"没扫"，不是"扫过没有"——总表里必须是无法核验。"""
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=())
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertIn("② .51 四服务页面】🔴 本类无法核验", result.stdout)
            self.assertNotIn("✅ 全部", result.stdout)

    def test_cowork_side_skill_present_reports_unverifiable(self):
        """三态之二：仅 Cowork 侧有 skill、CC 侧为空 ⇒ Cowork 半无法核验。"""
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp), cc_names=(), cowork_names=("zhuopin-queue-audit",))
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertIn("Cowork 侧 skill（账号级安装）】🔴 本类无法核验", result.stdout)
            self.assertIn("不在本机文件系统", result.stdout)
            self.assertIn("zhuopin-queue-audit", result.stdout)
            self.assertNotIn("✅ 全部", result.stdout)

    def test_mixed_cc_and_cowork_skills_reports_split_status(self):
        """三态之三：两侧都有 ⇒ CC 半免扫已核验、Cowork 半无法核验，两条并存。"""
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(
                Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=("zhuopin-queue-audit",),
            )
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertIn("CC 侧 skill（库内 .claude/skills/）】1 个", result.stdout)
            self.assertIn("免扫", result.stdout)
            self.assertIn("Cowork 侧 skill（账号级安装）】🔴 本类无法核验", result.stdout)

    def test_dir_present_but_no_scannable_file_is_unverifiable(self):
        """🔴 反例：①④ 目录还在、但一个可扫文件都没有。"""
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp))
            (layout["artifacts"] / "index.html").unlink()
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertIn("① Cowork artifacts】🔴 本类无法核验", result.stdout)
            self.assertIn("0 个可扫文本文件", result.stdout)

    def test_missing_carrier_directories_do_not_fail_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "不存在"
            result = _run_cli(
                "任意关键词", "--skip-http",
                "--artifacts-dir", str(missing),
                "--scheduled-dir", str(missing),
                "--cc-skills-dir", str(missing),
                "--skill-source-dir", str(missing),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("扫描根目录不存在", result.stdout)


class OutputThrottleTests(unittest.TestCase):
    """队列 #597 ⑵：成功路径摘要 + `reports/output-throttle/` 落盘 + `--verbose` 全量、
    失败路径（--strict 触发非零退出码）不受影响。"""

    REPORT_DIR = SCRIPT.parent.parent / "reports" / "output-throttle" / "工具-仓库外载体扫描"

    def test_success_path_summarized_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp))
            before = set(self.REPORT_DIR.glob("*.log")) if self.REPORT_DIR.is_dir() else set()
            result = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            lines = result.stdout.splitlines()
            self.assertLessEqual(len(lines), 20, result.stdout)
            self.assertTrue(
                any(("全文见" in ln) or ("全文已存" in ln) for ln in lines), result.stdout)
            after = set(self.REPORT_DIR.glob("*.log")) if self.REPORT_DIR.is_dir() else set()
            new_files = after - before
            self.assertTrue(new_files, "应至少新增一个 .log 报告文件")
            content = "".join(p.read_text(encoding="utf-8") for p in new_files)
            self.assertIn("Cowork artifacts", content)   # 全文落盘须含被摘要裁掉前的完整命中行

    def test_verbose_keeps_full_output_uncut(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = _make_full_layout(Path(tmp))
            terse = _run_cli("PT1H", "--skip-http", *_cli_args(layout))
            full = _run_cli("PT1H", "--skip-http", "--verbose", *_cli_args(layout))
            self.assertEqual(full.returncode, 0, full.stdout + full.stderr)
            self.assertGreater(len(full.stdout.splitlines()), len(terse.stdout.splitlines()))
            self.assertIn("🔴 本次 2/5 类无法核验", full.stdout)   # 摘要版会把总表尾行裁掉
            self.assertNotIn("已省略", full.stdout)
            self.assertNotIn("全文已存", full.stdout)

    def test_failure_path_full_output_without_verbose(self):
        """借用既有失败夹具（口令门 + --strict ⇒ 退出码 2）：不加 --verbose 也必须
        整段完整打印，退出码不变，且不落盘摘要报告。"""
        fixture = _ServerFixture()
        url = fixture.start(_AuthGateHandler)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                layout = _make_full_layout(
                    Path(tmp), cc_names=("zhuopin-followup-letter",), cowork_names=())
                before = set(self.REPORT_DIR.glob("*.log")) if self.REPORT_DIR.is_dir() else set()
                result = _run_cli(
                    "每 4h", *_cli_args(layout), "--service-urls", url, "--strict",
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("访问口令登录页", result.stdout)
                self.assertIn("核验状态总表", result.stdout)
                self.assertNotIn("已省略", result.stdout)
                self.assertNotIn("全文已存", result.stdout)
                after = set(self.REPORT_DIR.glob("*.log")) if self.REPORT_DIR.is_dir() else set()
                self.assertEqual(after - before, set(), "失败路径不应触发摘要落盘")
        finally:
            fixture.stop()


if __name__ == "__main__":
    unittest.main()
