# -*- coding: utf-8 -*-
"""根 `CLAUDE.md` 超阈值由「告警」改「拒绝」（队列 §一 `#583` 同族，2026-09-20 `OP-0919-K`）。

🔴 **成因是实测**：2026-09-20 现取根文件 13,148 B，超 `CLAUDE_MD_ROOT_BYTE_CAP`（12,288 B）860 B，
而这道守卫只进第 4 类常驻状态告警——**告警没有消费者，于是它超了十几天没人知道**。
**判词：一条只会说话、不会拦人的守卫，和没有守卫的区别只在于它会积累未读消息。**

本文件守三个方向：**该拒的拒**（清单含根 CLAUDE.md 且超阈值）、**不该拒的不拒**
（未超／清单不含它／场景级 CLAUDE.md），以及**测不出来时不判违规**（读不到尺寸 ⇒ None）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().with_name("工具-落库sweep.py")


def _mod():
    spec = importlib.util.spec_from_file_location("_sweep_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def sweep():
    return _mod()


class TestClaudeMdRootOverCap:
    def test_超阈值时返回超出字节数(self, sweep, tmp_path):
        (tmp_path / "CLAUDE.md").write_bytes(b"x" * (sweep.CLAUDE_MD_ROOT_BYTE_CAP + 860))
        assert sweep.claude_md_root_over_cap(tmp_path) == 860

    def test_恰好等于阈值不算超(self, sweep, tmp_path):
        """边界：`>` 不是 `>=`——恰好卡在阈值上是合规的，否则瘦身到刚好达标也会被拒。"""
        (tmp_path / "CLAUDE.md").write_bytes(b"x" * sweep.CLAUDE_MD_ROOT_BYTE_CAP)
        assert sweep.claude_md_root_over_cap(tmp_path) is None

    def test_读不到尺寸时不判违规(self, sweep, tmp_path):
        """测不出来 ⇒ None，不据不可用的测量拦人（同本文件「尺寸未取到 ⇒ 不据此判为合规」的反面）。"""
        assert sweep.claude_md_root_over_cap(tmp_path) is None


class TestBatchTouchesClaudeMdRoot:
    def test_清单含根CLAUDE命中(self, sweep):
        assert sweep.batch_touches_claude_md_root(["CLAUDE.md", "0-学习与工具/x.py"]) is True

    def test_反斜杠写法也命中(self, sweep):
        assert sweep.batch_touches_claude_md_root(["CLAUDE.md".replace("/", "\\")]) is True

    def test_场景级CLAUDE不命中_只认根那一份(self, sweep):
        """🔴 射程守卫：场景级 `CLAUDE.md` 有自己的阈值，不该被根文件的超限连坐。"""
        assert sweep.batch_touches_claude_md_root([
            "4-数字员工/财务部/FI3-付款申请自动校验/CLAUDE.md",
            ".claude/rules/队列与落库.md",
        ]) is False

    def test_空清单不命中(self, sweep):
        assert sweep.batch_touches_claude_md_root([]) is False
        assert sweep.batch_touches_claude_md_root(None) is False


class TestGuardScope:
    """射程：拒绝只落在「含根 CLAUDE.md 且超阈值」这一个交叉点上。"""

    @pytest.mark.parametrize(
        "over,touches,should_refuse",
        [
            (860, True, True),     # 超 ＋ 含 ⇒ 拒
            (None, True, False),   # 未超 ＋ 含 ⇒ 放
            (860, False, False),   # 超 ＋ 不含 ⇒ 放（同轮其它批次不受连坐）
            (None, False, False),
        ],
    )
    def test_四种组合只有一种拒(self, over, touches, should_refuse):
        assert bool(over is not None and touches) is should_refuse


class TestGuardIsActuallyWired:
    """🔴 **「守卫建成但没人调」是本项目反复踩的形状**（`#610` 聊天旁路／`#312` 建成没接线／
    `#398`⑷ 扫描器无轮次调用）。上面几个类只证明纯函数对，本类证明它**真的接在落库主路径上**。"""

    def test_两个判据都被normal_rows循环调用(self):
        src = SCRIPT.read_text(encoding="utf-8")
        loop = src.split("for row, resolved, coverage_note in normal_rows:", 1)
        assert len(loop) == 2, "没找到 §二 正常批次落库循环——接线点变了，本用例须同步更新"
        body = loop[1].split("if straggler_rows:", 1)[0]
        assert "claude_md_root_over_cap(" in body, "拒绝判据没接进落库循环＝建成没接线"
        assert "batch_touches_claude_md_root(" in body, "射程判据没接进落库循环＝会连坐同轮其它批次"
        assert "continue" in body, "拒绝路径必须 continue（只报不动、不进 touched_paths）"
