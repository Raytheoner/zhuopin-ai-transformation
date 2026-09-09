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

import importlib.util
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.queue_table import (
    QUEUE_BUSINESS_PATH_REL,
    QUEUE_MECHANISM_PATH_REL,
    split_row_cells,
)

from aibot_service.queue_appender import (
    HIGH_WATER_MARK_SOURCE_FILENAME,
    _next_task_id,
    _section_bounds,
    append_pending_task,
    resolve_high_water_mark_path,
    resolve_row_domain,
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


# ── ④ 域字段（队列 #532）───────────────────────────────────────────────────
#
# `#341` 让写入侧按域**路由**（新行落哪份物理文件）；本组管紧随其后的另一半：
# 把那个**已经做出的**域判定写进状态列的机器字段。两者是同一事实的两种载体
# ——文件位置（机器要靠路径推）与 `[D:]` 字段（机器直读）。缺后者的实际代价：
# 缺域的**可动**行不计入协议〇.9 措施 C 的机制类 WIP ⇒ **WIP 算少 ＝ 该拦的
# 没拦、超限行照立**（`#523` 立行实证 ／ `#532` 治写入侧）。


def _status_cell_of(row: str) -> str:
    """从整行取「状态」列（第 6 列）——走 `queue_table.split_row_cells` 的共享
    解析，不在测试里自己 `split("|")`（那正是 #305 列偏移一族的成因）。"""
    cells = split_row_cells(row)
    assert cells is not None, f"整行未能解析成 §一 表格行：{row!r}"
    return cells[5]


def test_resolve_row_domain_maps_both_official_queue_filenames(tmp_path: Path):
    """域＝写入目标文件名查表，两份正式队列文件各一支；判据是**文件名**而非
    路径全等（目录随 checkout／worktree／`.51` 部署而变，文件名不变）。"""
    assert resolve_row_domain(tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name) == "机"
    assert resolve_row_domain(tmp_path / Path(QUEUE_BUSINESS_PATH_REL).name) == "业"
    # 换个目录仍成立（钉住"看文件名不看全路径"）
    assert resolve_row_domain(Path("/另一个/checkout") / Path(QUEUE_BUSINESS_PATH_REL).name) == "业"
    # 不是这两份 ⇒ None，且**不抛异常**：抛了会让一条本能进队列的反馈整条丢失
    assert resolve_row_domain(tmp_path / "queue.md") is None


def test_append_to_business_file_writes_business_domain_field(tmp_path: Path):
    """写业务场景文件 ⇒ `[S:open][D:业]`（生产默认路径，见
    `DEFAULT_QUEUE_RELATIVE_PATH`）。"""
    _mechanism, business = _dual_queue_files(tmp_path)

    row = append_pending_task(
        business,
        description="企微反馈自动归档：某专员 发来文本反馈",
        owner="采购专线",
        input_pointer="`7-外部文档/采购部/x.md`",
        expected_output="核实内容并按需处理",
        date_str="2026-09-09",
    )

    assert _status_cell_of(row) == "[S:open][D:业] 待领"
    assert "[S:open][D:业] 待领" in business.read_text(encoding="utf-8")


def test_append_to_mechanism_file_writes_mechanism_domain_field(tmp_path: Path):
    """写机制环境文件 ⇒ `[S:open][D:机]`（单文件历史部署／`WECOM_AIBOT_QUEUE_
    PATH` 钉在机制环境文件的形态）。这一支正是"域字段缺失致机制类 WIP 算少"
    真会发生的那一支。"""
    mechanism = tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name
    mechanism.write_text(_MECHANISM_WITH_HWM, encoding="utf-8")

    row = append_pending_task(
        mechanism, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-09",
    )

    assert _status_cell_of(row) == "[S:open][D:机] 待领"
    assert "[S:open][D:机] 待领" in mechanism.read_text(encoding="utf-8")


def test_domain_field_does_not_change_column_count(tmp_path: Path):
    """零回归护栏：多写一个 `[D:]` 字段**不得**改变列数——`[D:机]` 里没有裸
    竖线，但这条把"新增字段没撑列"钉死，形态同 #305。"""
    _mechanism, business = _dual_queue_files(tmp_path)
    row = append_pending_task(
        business, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-09",
    )
    assert row.count("|") == 9  # 8 列 ＝ 首尾各 1 条 + 7 条分隔
    assert len(split_row_cells(row) or []) == 8


def test_unknown_queue_filename_falls_back_without_domain_and_audits(tmp_path: Path):
    """写入目标不是两份正式队列文件之一（历史单文件部署／单测夹具）⇒ 判不出
    域，回落"不写 `[D:]`"（＝本次改动前的行为，无新增失败模式），但**不静默**
    ——记一条 `queue_row_domain_unresolved`，与
    `queue_high_water_mark_parse_failed` 同一范式。"""
    lone = tmp_path / "queue.md"
    lone.write_text(_BUSINESS_WITHOUT_HWM, encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"

    row = append_pending_task(
        lone, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-09",
        audit=AuditLogger.jsonl(audit_path),
    )

    assert _status_cell_of(row) == "[S:open] 待领"
    assert "[D:" not in row
    recorded = audit_path.read_text(encoding="utf-8")
    assert "queue_row_domain_unresolved" in recorded
    assert "queue_filename" in recorded


# ── ④bis 跨工具一致性：机器人写出的行必须过得了人工写侧那道守卫 ──────────
#
# 🔴 状态列的语法（`[S:x][D:y]` 紧邻、其间无空格）由
# `0-学习与工具/工具-共享文档编辑锁.py` 的 `STATUS_FIELD_RE` 单方面定义，本
# 服务这边是**第二处实现**。两处各写各的正则／各拼各的字符串，就是"同一个
# 口径两份实现，改一处忘一处"的经典形态——下面这几条把它们钉在一起：**用
# 编辑锁自己的守卫去验机器人的产物**，而不是在这边复述一遍它的语法。


def _load_editlock_module():
    """按路径加载编辑锁 CLI（文件名是中文，不能走普通 import）。

    找不到该文件 ＝ 本服务被单独 checkout（无 `0-学习与工具/`）⇒ skip；
    **只对"文件不存在"skip**，不 try/except 兜住导入期的任何其它失败——那种
    兜法会让这组守卫在真出问题时静默变成 no-op。
    """
    repo_root = Path(__file__).resolve().parents[3]
    tool_path = repo_root / "0-学习与工具" / "工具-共享文档编辑锁.py"
    if not tool_path.is_file():
        pytest.skip(f"未找到编辑锁工具（本服务被单独 checkout？）：{tool_path}")
    spec = importlib.util.spec_from_file_location("_editlock_for_test", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bot_rows_pass_editlock_write_side_domain_guard(tmp_path: Path):
    """机器人写出的两份文件各一行，喂进编辑锁写侧守卫
    `_section_one_domain_field_violations` 必须**零告警**；同一守卫喂改动前
    的缺域行必须**报**——后半句是变异验证，证明前半句不是空转。"""
    editlock = _load_editlock_module()
    mechanism, business = _dual_queue_files(tmp_path)

    rows = [
        append_pending_task(
            business, description="d", owner="o", input_pointer="i",
            expected_output="e", date_str="2026-09-09",
        ),
        append_pending_task(
            mechanism, description="d", owner="o", input_pointer="i",
            expected_output="e", date_str="2026-09-09",
        ),
    ]
    for row in rows:
        cells = split_row_cells(row)
        assert editlock._section_one_domain_field_violations(cells) == [], row

    # 变异：改动前的产物（缺 `[D:]` 的可动行）必须被同一道守卫拦下
    legacy_cells = split_row_cells(
        "| 999 | d | o | i | e | [S:open] 待领 | — | 2026-09-09 |"
    )
    assert editlock._section_one_domain_field_violations(legacy_cells) != []


def test_bot_written_mechanism_row_counts_into_mechanism_wip(tmp_path: Path):
    """队列 `#532` 期望产出⑷：补域后复跑 `_count_mechanism_wip` —— 机器人写进
    机制环境文件的行必须**计入** WIP 且**零**「已跳过 WIP 计数」降级日志。

    变异对照：把域字段去掉（＝改动前的产物）⇒ 计数掉到 0 且冒出降级日志，
    正是 `#523` 说的"WIP 算少 ＝ 该拦的没拦"。

    🔴 本用例不复用 `_dual_queue_files`：那份夹具里的既有行 `#7` 本身就写着
    `[S:open]` 无域（它是 `#341` 那组用例的夹具，与域字段无关），沿用会让
    "零降级日志"这句断言永远为假、且假得与本次改动无关。
    """
    editlock = _load_editlock_module()
    mechanism = tmp_path / Path(QUEUE_MECHANISM_PATH_REL).name
    mechanism.write_text(
        "> **编号高水位线：§一 #500 ｜ §四 #36**\n"
        "\n"
        "## 一、任务看板\n"
        "\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 7 | 既有机制域可动行 | CC | p | e | [S:open][D:机] 待领 | — | 09-01 |\n",
        encoding="utf-8",
    )

    append_pending_task(
        mechanism, description="d", owner="o", input_pointer="i",
        expected_output="e", date_str="2026-09-09",
    )
    section_one = mechanism.read_text(encoding="utf-8")

    count, degraded = editlock._count_mechanism_wip(section_one)
    assert count == 2, section_one  # 既有 #7 + 机器人新写的 #501
    assert not any("已跳过 WIP 计数" in line for line in degraded), degraded

    legacy = section_one.replace("[S:open][D:机] ", "[S:open] ")
    legacy_count, legacy_degraded = editlock._count_mechanism_wip(legacy)
    assert legacy_count == 0
    assert sum("已跳过 WIP 计数" in line for line in legacy_degraded) == 2
