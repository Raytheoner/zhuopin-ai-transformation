"""队列 #341：写侧按域路由 ＋ 取号来源与写入目标解耦（openspec 变更包
`queue-domain-routing` 决策点 2，Shao Peishen 2026-09-05 拍板采纳默认项）。

机器人的写入目标由本次改判从机制环境文件改回**业务场景文件**，而"编号
高水位线"标注行按 `queue-dual-file-topology` 的章节归属 Requirement **只
存在于机制环境文件**。若取号仍读"正在写入的那份文件自身"，就会静默回落
成"业务场景文件 §一 可见最大号 +1"——与真实全局高水位线脱钩，**撞号**。

本文件的用例分三组：
  ① 路由：`DEFAULT_QUEUE_RELATIVE_PATH` 必须是业务场景文件（tasks 1.4，
     与 `#336` 形态对称的回归护栏——钉住"不得写回机制环境文件"）；
  ② 取号解耦：新逻辑取对号、且高水位线回写落在机制环境文件（tasks 1.5）；
  ③ **变异验证**：把改判前的算法喂给同一份数据必须撞号——证明 ② 不是空转。
"""
from __future__ import annotations

from pathlib import Path

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.queue_table import (
    QUEUE_BUSINESS_PATH_REL,
    QUEUE_MECHANISM_PATH_REL,
)

from aibot_service.queue_appender import (
    HIGH_WATER_MARK_SOURCE_FILENAME,
    _next_task_id,
    _section_bounds,
    append_pending_task,
    resolve_high_water_mark_path,
)
from aibot_service.repo_paths import (
    DEFAULT_QUEUE_RELATIVE_PATH,
    QUEUE_MECHANISM_RELATIVE_PATH,
)

_MECHANISM_WITH_HWM = """\
> **编号高水位线：§一 #500 ｜ §四 #36**

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 7 | 机制域任务 | CC | p | e | [S:open] 待领 | — | 09-01 |

## 四、需 Shao Peishen 的动作

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
"""

_BUSINESS_WITHOUT_HWM = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 300 | 业务域任务 | 采购专线 | p | e | [S:open] 待领 | — | 09-01 |

## 二、待 commit 批次
"""


def _dual_queue_files(tmp_path: Path) -> tuple[Path, Path]:
    """复刻生产拓扑：两份物理队列文件同目录，只有机制环境文件有高水位线行。"""
    mechanism = tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name
    business = tmp_path / Path(QUEUE_BUSINESS_PATH_REL).name
    mechanism.write_text(_MECHANISM_WITH_HWM, encoding="utf-8")
    business.write_text(_BUSINESS_WITHOUT_HWM, encoding="utf-8")
    return mechanism, business


# ── ① 路由（tasks 1.4）────────────────────────────────────────────────────


def test_queue_appender_targets_business_file():
    """🔴 反例护栏：机器人的默认写入目标 **MUST NOT** 是机制环境文件。

    `#336`（`[D:业]` 却躺在机制环境文件里）就是 2026-08-11 那次止血
    （`DEFAULT_QUEUE_RELATIVE_PATH` 临时改指机制环境文件）的直接副作用。
    这条用例与那个形态对称：谁把常量改回去，这里当场变红。
    """
    assert DEFAULT_QUEUE_RELATIVE_PATH.as_posix() == QUEUE_BUSINESS_PATH_REL
    assert DEFAULT_QUEUE_RELATIVE_PATH != QUEUE_MECHANISM_RELATIVE_PATH


def test_mechanism_relative_path_constant_is_the_mechanism_file():
    """§四／协议〇／高水位线的读侧常量必须仍指机制环境文件——它与写入目标
    刻意是两个常量，合并回一个就会重演"读侧只跟一份"那一族缺陷。"""
    assert QUEUE_MECHANISM_RELATIVE_PATH.as_posix() == QUEUE_MECHANISM_PATH_REL
    assert QUEUE_MECHANISM_RELATIVE_PATH.name == HIGH_WATER_MARK_SOURCE_FILENAME


def test_resolve_high_water_mark_path_defaults_to_mechanism_sibling(tmp_path: Path):
    mechanism, business = _dual_queue_files(tmp_path)
    assert resolve_high_water_mark_path(business) == mechanism
    explicit = tmp_path / "另指一份.md"
    assert resolve_high_water_mark_path(business, explicit) == explicit


def test_resolve_high_water_mark_path_falls_back_when_sibling_absent(tmp_path: Path):
    """同目录没有机制环境文件（单测夹具／历史部署形态）——回落 `queue_path`
    自身，行为与本次改动前逐字一致，不引入新的失败模式。"""
    lone = tmp_path / "queue.md"
    lone.write_text(_BUSINESS_WITHOUT_HWM, encoding="utf-8")
    assert resolve_high_water_mark_path(lone) == lone


# ── ② 取号解耦（tasks 1.5）──────────────────────────────────────────────


def test_queue_appender_high_water_mark_decoupled_from_write_target(tmp_path: Path):
    """机制环境高水位线已推进到 500、业务场景文件可见最大号仍是 300 ——
    新编号必须是 max(500, 300) + 1 = 501；高水位线的回写落在**机制环境
    文件**，业务场景文件不得凭空长出第二条高水位线声明。"""
    mechanism, business = _dual_queue_files(tmp_path)

    row = append_pending_task(
        business,
        description="企微反馈自动归档：某专员 发来文本反馈",
        owner="采购专线",
        input_pointer="`7-外部文档/采购部/x.md`",
        expected_output="核实内容并按需处理",
        date_str="2026-09-05",
    )

    assert row.startswith("| 501 |")
    business_text = business.read_text(encoding="utf-8")
    mechanism_text = mechanism.read_text(encoding="utf-8")
    assert "| 501 |" in business_text
    assert "| 501 |" not in mechanism_text
    assert "§一 #501" in mechanism_text
    assert "编号高水位线" not in business_text


def test_queue_appender_audit_records_fallback_when_mechanism_lacks_marker(
    tmp_path: Path,
):
    """机制环境文件在、但标注行格式漂移 —— 按既有口径回落"可见最大号 +1"，
    并记一条 `queue_high_water_mark_parse_failed`（含来源文件路径），不静默
    发生（`aibot-queue-domain-routing` spec 的回落 Scenario）。"""
    mechanism = tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name
    business = tmp_path / Path(QUEUE_BUSINESS_PATH_REL).name
    mechanism.write_text("> **编号高水位线：格式已变，无法解析**\n", encoding="utf-8")
    business.write_text(_BUSINESS_WITHOUT_HWM, encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"

    row = append_pending_task(
        business, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-05",
        audit=AuditLogger.jsonl(audit_path),
    )

    assert row.startswith("| 301 |")
    recorded = audit_path.read_text(encoding="utf-8")
    assert "queue_high_water_mark_parse_failed" in recorded
    assert "high_water_mark_path" in recorded


def test_queue_appender_single_file_deployment_is_unaffected(tmp_path: Path):
    """零回归护栏：写入目标本身就是机制环境文件时 `hwm_path == queue_path`，
    仍是一次读改写，行为与本次改动前完全一致（不产生第二条标注行）。"""
    mechanism = tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name
    mechanism.write_text(_MECHANISM_WITH_HWM, encoding="utf-8")

    row = append_pending_task(
        mechanism, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-05",
    )

    text = mechanism.read_text(encoding="utf-8")
    assert row.startswith("| 501 |")
    assert "| 501 |" in text
    assert "§一 #501" in text
    assert text.count("编号高水位线") == 1


# ── ②bis 常驻服务入口：锚点 ≠ 写入目标（源码断言）──────────────────────


def test_run_aibot_service_derives_write_target_from_constant_not_anchor():
    """🔴 常驻监听入口 MUST 把"仓库根锚点"与"写入目标"分开算。

    `WECOM_AIBOT_QUEUE_PATH` 在其余全部入口的文件头里都写着"**可选，仓库根解析
    锚点**"；只有 `run_aibot_service` 历史上把它同时当成了写入目标（拆分前只有
    一份队列文件，两者恰好重合）。而常驻监听 `ZhuopinAibotDevListener` 的启动
    脚本 `start-aibot-service-dev.ps1` 把该变量钉在**机制环境文件**上——沿用
    旧写法则 `#341` 的写入目标切换在生产上**完全不生效且不报错**。

    这条判据故意读源码而非跑 `main()`：`main()` 会建 WS 长连接、读 `.env`，
    在隔离单测环境里跑不起来；而本判据要钉的恰恰是一行**赋值语句的来源**。
    """
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_aibot_service.py"
    ).read_text(encoding="utf-8")

    # 写入目标必须由仓库根 + 常量拼出
    assert "queue_path = resolved_repo_root / DEFAULT_QUEUE_RELATIVE_PATH" in source
    # 🔴 不得回到"锚点即写入目标"的旧写法
    assert "queue_path = resolve_default_queue_anchor(" not in source
    # 锚点本身仍走环境变量解析（#126／#269 语义不得被顺手改掉）
    assert "queue_anchor = resolve_default_queue_anchor(" in source


# ── ③ 变异验证：证明 ② 不是空转 ─────────────────────────────────────────


def test_old_in_file_numbering_would_collide(tmp_path: Path):
    """把改判**前**的取号算法（只读"正在写入的那份文件自身"）喂给同一份
    数据，必须取到 301 —— 一个 ≤ 机制环境高水位线 500 的重复编号，正是
    `#341` 要消灭的撞号。这条用例的唯一职责是证明上面那条会真的变红。"""
    _mechanism, business = _dual_queue_files(tmp_path)
    lines = business.read_text(encoding="utf-8").splitlines()
    header_idx = next(
        i for i, line in enumerate(lines) if line.strip() == "## 一、任务看板"
    )
    start, end = _section_bounds(lines, header_idx)

    # 旧行为：缺省 `high_water_mark_lines` ⇒ 读 `lines` 自身（该文件无标注行）
    assert _next_task_id(lines, start, end) == 301
    # 新行为：高水位线取自机制环境文件
    hwm_lines = _MECHANISM_WITH_HWM.splitlines()
    assert _next_task_id(lines, start, end, high_water_mark_lines=hwm_lines) == 501
