"""工具-使用度量采样.py 单测（队列 §一 `#436` ⑶③，`OP-0906-T`）。

mock 先行：本文件**不读 `.51` 任何真实日志**（本批硬边界），mock 日志由
`_write_audit()` / `_write_access()` / `_write_trace()` 按平台底座三个 dataclass
的**真实字段名**当场生成到 `tmp_path`——`AuditEvent`（scenario/action/evaluator/
automation_level）、`AccessLogEntry`（service/method/path/status/source_ip）、
`AccessTrace`（source/action/target）。🔴 mock 不能照抄「我以为的字段名」：字段
名一旦漂了，工具在真实日志上会静默把每一行都归到「格式不一」，而单测全绿。

两个场景各覆盖任务书要求的一正一反：
  · FI2（`8094` audit 形态）—— 一例正常在用、一例 14 天零使用。
  · SC8（`8091` 连接器审计形态）—— 一例正常在用、一例 14 天零使用。

🔴 本文件最要紧的三条，删掉任何一条工具都会退回它要治的那个病：
  · `test_三档边界_2_3_6_7_13_14` —— 锁死 3／7／14 三档的**边界日**。阈值是
    Shao Peishen 拍死的口径，不是实现细节。
  · `test_零触发全集无inventory时会漏掉从未触发的功能` —— 锁死「全集只取日志
    历史」的**已知盲区必须在报告里说出来**，不许沉默降级。
  · `test_访问日志无个人身份被单列为缺口且不猜人名` —— 锁死「不做 IP→人名的
    任何映射」。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().with_name("工具-使用度量采样.py")
_spec = importlib.util.spec_from_file_location("usage_sampler", SCRIPT)
usage_sampler = importlib.util.module_from_spec(_spec)
# 🔴 先进 sys.modules 再 exec —— 被测模块用了 @dataclass，而 dataclasses 在处理
# 注解时会回查 `sys.modules[cls.__module__]`；漏这一步会在 import 期直接
# AttributeError（Python 3.14 实测），且报错点在 dataclasses 内部、极难反推。
sys.modules["usage_sampler"] = usage_sampler
_spec.loader.exec_module(usage_sampler)

ASOF = date(2026, 9, 6)


def _utc_iso(d: date, hour: int = 3) -> str:
    """真实日志里的时间戳形态：`datetime.now(timezone.utc).isoformat()`。

    刻意取 03:00 UTC —— 落到东八区仍是同一天，避免本机时区把「日」推走
    导致断言随机漂移（判日基准问题在本工具里是一等公民，测试自己先别踩）。
    """
    return datetime.combine(d, time(hour), tzinfo=timezone.utc).isoformat()


def _jsonl(path: Path, records: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _audit_rec(scenario: str, action: str, evaluator: str, d: date) -> dict:
    """AuditEvent.to_dict() 的真实形态（见 zhuopin_platform/audit/events.py）。"""
    return {"scenario": scenario, "action": action, "evaluator": evaluator,
            "automation_level": "L3", "decision": {"ok": True},
            "data_sources": {"input": "mock"}, "content_hash": "",
            "oem_context": "", "override_reason": "", "report_path": "",
            "timestamp": _utc_iso(d)}


def _access_rec(service: str, path_: str, ip: str, d: date, method: str = "GET") -> dict:
    """AccessLogEntry.to_dict() 的真实形态（见 shared_tools/access_log.py）。"""
    return {"service": service, "method": method, "path": path_, "status": 200,
            "source_ip": ip, "timestamp": _utc_iso(d)}


def _trace_rec(source: str, action: str, d: date, target: str = "") -> dict:
    """AccessTrace.to_dict() 的真实形态（见 shared_tools/connector_audit.py）。"""
    return {"source": source, "action": action, "target": target, "timestamp": _utc_iso(d)}


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_tool(self, *argv: str) -> tuple[int, str]:
        out = self.tmp / "report.md"
        rc = usage_sampler.main([*argv, "--asof", ASOF.isoformat(),
                                 "--window", "30", "--no-diagnose",
                                 "--repo-root", str(self.tmp),
                                 "--out", str(out)])
        return rc, (out.read_text(encoding="utf-8") if out.exists() else "")


# ══════════════════════════════════════════════════════════════════════════
# FI2（8094 audit 形态）：一例正常 / 一例 14 天零使用
# ══════════════════════════════════════════════════════════════════════════

class TestFI2Audit(_Base):
    def _log(self) -> Path:
        recs = []
        # 正常在用：唐燕萍，最近三天都有决策
        for delta in (0, 1, 2, 5):
            recs.append(_audit_rec("FI2", "item_match", "唐燕萍", ASOF - timedelta(days=delta)))
        # 14 天零使用：李姣龙，最后一次活动在 asof-14
        recs.append(_audit_rec("FI2", "l3_override", "李姣龙", ASOF - timedelta(days=14)))
        recs.append(_audit_rec("FI2", "l3_override", "李姣龙", ASOF - timedelta(days=20)))
        return _jsonl(self.tmp / "fi2_audit.jsonl", recs)

    def test_正常在用者不进任何档(self):
        rc, rep = self.run_tool("--audit", str(self._log()))
        self.assertEqual(rc, 0)
        self.assertIn("| FI2 | `唐燕萍` |", rep)
        # 汇总行里唐燕萍这一格的「档」列为「—」
        line = next(l for l in rep.splitlines() if "`唐燕萍`" in l and l.startswith("| FI2"))
        self.assertTrue(line.rstrip().endswith("| — |"), line)

    def test_14天零使用进需你定夺档(self):
        rc, rep = self.run_tool("--audit", str(self._log()))
        self.assertEqual(rc, 0)
        head = rep.split("### ≥ 14 天零使用")[1].split("###")[0]
        self.assertIn("`李姣龙`", head)
        self.assertIn("闲置 14 天", head)
        # 🔴 需你定夺档只报候选，绝不自动起草
        self.assertIn("不自动起草", head)

    def test_报告不含任何写README或推企微的动作(self):
        _, rep = self.run_tool("--audit", str(self._log()))
        self.assertIn("只读", rep)
        for forbidden in ("已写入 README", "已推送企微", "已起草"):
            self.assertNotIn(forbidden, rep)

    def test_零触发动作按窗口判定(self):
        """`l3_override` 在窗口内（30 天）出现过 ⇒ 不算零触发；窗口收到 7 天就算。"""
        log = self._log()
        out = self.tmp / "narrow.md"
        rc = usage_sampler.main(["--audit", str(log), "--asof", ASOF.isoformat(),
                                 "--window", "7", "--no-diagnose",
                                 "--repo-root", str(self.tmp), "--out", str(out)])
        self.assertEqual(rc, 0)
        rep = out.read_text(encoding="utf-8")
        zero = rep.split("## 三 ·")[1].split("## 四 ·")[0]
        self.assertIn("`l3_override`", zero)
        self.assertNotIn("`item_match`", zero)


# ══════════════════════════════════════════════════════════════════════════
# SC8（8091 连接器审计形态）：一例正常 / 一例 14 天零使用
# ══════════════════════════════════════════════════════════════════════════

class TestSC8Connector(_Base):
    def _logs(self) -> tuple[Path, Path, Path]:
        audit = _jsonl(self.tmp / "baoguan_audit.jsonl", [
            *[_audit_rec("SC8", "promise_eval", "姚祖怡", ASOF - timedelta(days=d))
              for d in (0, 3)],
            # 14 天零使用的第二位使用者
            _audit_rec("SC8", "promise_eval", "孙涛", ASOF - timedelta(days=14)),
        ])
        access = _jsonl(self.tmp / "baoguan_http_requests.jsonl", [
            _access_rec("成品保供预警看板", "/baoguan", "192.168.100.77", ASOF),
            _access_rec("成品保供预警看板", "/cases/review", "192.168.100.77",
                        ASOF - timedelta(days=25)),
        ])
        trace = _jsonl(self.tmp / "baoguan_access_trace.jsonl", [
            _trace_rec("U9C", "get_purchase_orders", ASOF),
            _trace_rec("SRM", "get_delivery", ASOF - timedelta(days=2)),
        ])
        return audit, access, trace

    def test_连接器痕迹须显式给场景码_否则记未知场景缺口(self):
        _, _, trace = self._logs()
        rc, rep = self.run_tool("--trace", str(trace))
        self.assertEqual(rc, 0)
        self.assertIn("无法识别场景", rep)
        self.assertIn("（未知场景）", rep)

    def test_连接器痕迹带场景码时归到场景但仍无用户维度(self):
        _, _, trace = self._logs()
        rc, rep = self.run_tool("--trace", f"{trace}=SC8")
        self.assertEqual(rc, 0)
        self.assertIn("连接器痕迹无用户字段", rep.replace("连接器痕迹按设计无用户字段",
                                                        "连接器痕迹无用户字段"))
        self.assertIn("| SC8 |", rep)
        # 痕迹不带用户 ⇒ 不产生「场景 × 用户」汇总行
        self.assertNotIn("`（未署名）`", rep)

    def test_三源合流_14天零使用者被点名(self):
        audit, access, trace = self._logs()
        rc, rep = self.run_tool("--audit", str(audit), "--access", str(access),
                                "--trace", f"{trace}=SC8")
        self.assertEqual(rc, 0)
        decide = rep.split("### ≥ 14 天零使用")[1].split("###")[0]
        self.assertIn("`孙涛`", decide)
        self.assertNotIn("`姚祖怡`", decide)

    def test_访问日志无个人身份被单列为缺口且不猜人名(self):
        _, access, _ = self._logs()
        rc, rep = self.run_tool("--access", str(access))
        self.assertEqual(rc, 0)
        self.assertIn("不采集个人身份", rep)
        self.assertIn("`ip:192.168.100.77`", rep)     # 只到 IP 粒度
        self.assertIn("不做任何 IP→人名的猜测", rep)
        # 🔴 绝不能把 IP 说成任何一个人
        for name in ("姚祖怡", "唐燕萍", "李姣龙"):
            self.assertNotIn(f"ip:{name}", rep)


# ══════════════════════════════════════════════════════════════════════════
# 三档边界 · 零触发全集 · 日志缺口 · 流式
# ══════════════════════════════════════════════════════════════════════════

class TestBands(_Base):
    def test_三档边界_2_3_6_7_13_14(self):
        """🔴 阈值锁死：2→无档、3/6→记日志、7/13→只读诊断、14→需你定夺。"""
        cases = {2: "", 3: "记日志", 6: "记日志", 7: "只读诊断",
                 13: "只读诊断", 14: "需你定夺", 40: "需你定夺"}
        for idle, expected in cases.items():
            with self.subTest(idle=idle):
                self.assertEqual(usage_sampler.band_of(idle), expected)

    def test_档由报告如实呈现(self):
        recs = [_audit_rec("FI2", "a", f"u{d}", ASOF - timedelta(days=d))
                for d in (0, 3, 7, 14)]
        log = _jsonl(self.tmp / "bands.jsonl", recs)
        rc, rep = self.run_tool("--audit", str(log), "--window", "60")
        self.assertEqual(rc, 0)
        self.assertIn("| 0 |", rep)
        for user, band in (("u3", "记日志"), ("u7", "只读诊断"), ("u14", "需你定夺")):
            line = next(l for l in rep.splitlines()
                        if f"`{user}`" in l and l.startswith("| FI2"))
            self.assertIn(band, line)


class TestZeroTrigger(_Base):
    def test_零触发全集无inventory时会漏掉从未触发的功能_报告须明说(self):
        log = _jsonl(self.tmp / "a.jsonl", [_audit_rec("FI2", "item_match", "唐燕萍", ASOF)])
        rc, rep = self.run_tool("--audit", str(log))
        self.assertEqual(rc, 0)
        self.assertIn("从上线至今一次都没被触发过的功能，在本清单里看不见", rep)

    def test_inventory让从未触发的功能现形(self):
        log = _jsonl(self.tmp / "a.jsonl", [_audit_rec("FI2", "item_match", "唐燕萍", ASOF)])
        inv = self.tmp / "inv.json"
        inv.write_text(json.dumps({"FI2": {"actions": ["item_match", "tax_export", "l3_override"],
                                           "routes": ["GET /fi2", "GET /fi2/never"]}},
                                  ensure_ascii=False), encoding="utf-8")
        rc, rep = self.run_tool("--audit", str(log), "--inventory", str(inv))
        self.assertEqual(rc, 0)
        zero = rep.split("## 三 ·")[1].split("## 四 ·")[0]
        self.assertIn("`tax_export`", zero)
        self.assertIn("`GET /fi2/never`", zero)
        self.assertNotIn("`item_match`", zero)


class TestGaps(_Base):
    def test_四类缺口逐类计数并出样本(self):
        p = self.tmp / "dirty.jsonl"
        p.write_text("\n".join([
            "{ 这不是 JSON",                                          # bad_json
            json.dumps(["列表不是对象"], ensure_ascii=False),          # not_object
            json.dumps({"scenario": "FI2", "action": "a", "automation_level": "L3",
                        "evaluator": "唐燕萍"}, ensure_ascii=False),   # no_timestamp
            json.dumps({"scenario": "FI2", "action": "a", "automation_level": "L3",
                        "evaluator": "唐燕萍", "timestamp": "昨天下午"},
                       ensure_ascii=False),                            # bad_timestamp
            json.dumps({"scenario": "FI2", "action": "a", "automation_level": "L3",
                        "evaluator": "", "timestamp": _utc_iso(ASOF)},
                       ensure_ascii=False),                            # no_user
            json.dumps({"scenario": "FI2", "action": "a", "automation_level": "L3",
                        "evaluator": "唐燕萍",
                        "timestamp": f"{ASOF.isoformat()}T03:00:00"},
                       ensure_ascii=False),                            # naive_timestamp
        ]) + "\n", encoding="utf-8")
        rc, rep = self.run_tool("--audit", str(p))
        self.assertEqual(rc, 0)
        gaps = rep.split("## 五 ·")[1].split("## 六 ·")[0]
        for txt in ("非合法 JSON 行", "JSON 不是对象", "无时间戳", "时间戳无法解析",
                    "evaluator 为空", "无时区标记"):
            self.assertIn(txt, gaps)
        # 无署名的 audit 记录归到「（未署名）」而非丢弃
        self.assertIn("（未署名）", rep)

    def test_文件不存在时报缺口而非崩溃(self):
        rc = usage_sampler.main(["--audit", str(self.tmp / "nope.jsonl"),
                                 "--asof", ASOF.isoformat(), "--no-diagnose",
                                 "--repo-root", str(self.tmp),
                                 "--out", str(self.tmp / "r.md")])
        self.assertEqual(rc, 1)          # 全部输入不可读 ⇒ 非零退出，不产出报告

    def test_无输入即用法错误(self):
        self.assertEqual(usage_sampler.main(["--asof", ASOF.isoformat()]), 2)


class TestStreamingAndRotation(_Base):
    def test_逐行流式_不整读文件(self):
        """用一个 1 万行的日志验证聚合结果正确；实现若改成整读，真实 309 MB 会 OOM。"""
        recs = [_audit_rec("FI2", f"act{i % 4}", f"u{i % 3}", ASOF - timedelta(days=i % 10))
                for i in range(10_000)]
        log = _jsonl(self.tmp / "big.jsonl", recs)
        rc, rep = self.run_tool("--audit", str(log))
        self.assertEqual(rc, 0)
        self.assertIn("10,000", rep)     # 读入行数如实计
        # 只看代码，不看模块 docstring（那里正引用着这些禁用写法作反例）
        src = SCRIPT.read_text(encoding="utf-8").split('"""', 2)[-1]
        self.assertNotIn(".readlines()", src)
        self.assertNotIn(".read()", src.replace("read_text(", ""))
        self.assertNotIn("json.load(", src.replace("json.loads(", ""))

    def test_轮转建议只建议不实施(self):
        log = _jsonl(self.tmp / "a.jsonl", [_audit_rec("FI2", "a", "唐燕萍", ASOF)])
        rc, rep = self.run_tool("--audit", str(log))
        self.assertEqual(rc, 0)
        rot = rep.split("## 六 ·")[1].split("## 七 ·")[0]
        self.assertIn("只建议", rot)
        self.assertIn("#358", rot)
        self.assertIn("按大小截断", rot)      # 明确排除的错误修法
        self.assertIn("本工具不实施任何轮转", rot)


class TestInputSpec(unittest.TestCase):
    def test_windows盘符路径不被误拆(self):
        s = usage_sampler.parse_input_spec(r"C:\logs\a.jsonl", "audit")
        self.assertEqual(s.scenario_hint, "")
        self.assertEqual(str(s.path), r"C:\logs\a.jsonl")

    def test_场景码后缀被正确拆出(self):
        s = usage_sampler.parse_input_spec(r"C:\logs\a.jsonl=SC8", "trace")
        self.assertEqual(s.scenario_hint, "SC8")
        self.assertEqual(str(s.path), r"C:\logs\a.jsonl")

    def test_按字段判形态而非文件名(self):
        self.assertEqual(usage_sampler.classify(
            {"scenario": "FI2", "action": "a", "automation_level": "L3"}), "audit")
        self.assertEqual(usage_sampler.classify(
            {"service": "s", "method": "GET", "path": "/x"}), "access")
        self.assertEqual(usage_sampler.classify(
            {"source": "U9C", "action": "get_delivery"}), "trace")
        self.assertEqual(usage_sampler.classify({"foo": 1}), "")


if __name__ == "__main__":
    unittest.main()
