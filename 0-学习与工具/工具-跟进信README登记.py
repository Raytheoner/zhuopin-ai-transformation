"""跟进信 README 登记 CLI（`followup-readme-phase2` D1，队列 §一 `#490`）。

## 它解决的问题

登记/改状态跟进信 README 此前只能靠人工 `Edit` 直改——而工具约束下 `Edit`
前必须先 `Read` 全文，每登记一封信就吞掉一次全表字节（改造前 177.7 KB）。
本 CLI 是唯一登记入口：`append`（新增一行，写前列数校验、写后回读、字段
长度上限）与 `set-status`（改写既有行状态列，状态值受 `followup_gate` 权威
判据集合校验）。两者都经 `工具-共享文档编辑锁.py --file <README>` 单文件
锁，用完立刻释放。

## 复用而非重造

- 表格解析／写单元格：`aibot_service.readme_table`（`iter_rows`／
  `write_cells`／`_join_row`）——**不新造第二份 README 解析器**。
- 状态判据：`zhuopin_platform.shared_tools.followup_gate`（`classify_status`
  ／`normalize_status`）——**不自持一份独立于权威判据的状态字面量枚举**，
  避免与 `followup_gate` 漂移（同 `wecom-followup-review-state` 能力既有
  教训）。
- 部门下一个可用号：importlib 复用 `工具-跟进闸查询.py::_next_available_number`
  ——同一件事只应有一份算法，本工具不重算。
- 编辑锁：以子进程调用 `工具-共享文档编辑锁.py acquire/release`，把它当
  作真实外部依赖使用，不深入其内部实现细节（同人工调用方式一致）。
- 信件 frontmatter 解析与 `决策点:` 形态判据：importlib 复用
  `工具-跟进信frontmatter校验.py`（`parse_frontmatter`／`RE_DECISION`）——
  **不新造第二份 frontmatter 解析器，更不自持一份独立的 `决策点:` 正则**。
  该模块的 S3 判据刻意只做前缀锚定（`^\\d+\\s*项`）而非全串锚定，理由（全串
  锚定会误杀 `IT部#5` 的真实取值「2 项（FO…／PO…），或告知已有的替代查询
  方式」，而一条把真实合法语料判成违规的判据第一次跑就会被人加豁免绕开）
  写在它自己的 docstring S3 节里；本 CLI 复用它即自动继承该理由，不各锚各的。

## `append` 的 `决策点:` 前置校验（队列 §一 `#436` ⑶「2026-09-06 派出」(i)）

`append` 要求 `--letter-path` 指向本次待登记的信件 `.md`，登记前读其 frontmatter：
`决策点:` **缺失／为空／取值形态不合判据**者一律拒登记（退出码 1），拒绝文案给
出路（按 skill `zhuopin-followup-letter` v3.8 §5 步骤 1bis 写）。

**为什么 `--letter-path` 是必填而不是「给了才查」**：该字段 2026-08-11 起 27 封
无一封写、覆盖率 70%→0%，根因不是人忘了写，而是**漏写不产生任何信号**
（见 `工具-跟进信frontmatter校验.py` docstring 三处失血表 ⑴）。一个「不传路径
即绕过」的闸，等于把同一个静默失效原样重造一遍。

**口径来源**：`1-转型规划/0-全景路线图/design审前置-口径点台账三开放点收敛-2026-09-01.md`
§2.3 拆点判据 P1–P4 —— P1（一个点＝一个能被单独批复的待定判断，判别式「专员
只答这一条能否成立」）／P2（判例行是点的证据不是点本身，实测约 3:1）／P3（边界
的现成载体＝字段括号内以 `/` 分隔的每一项）／P4（点的类型决定能否默认生效，
判据类永不默认生效）。🔴 **本 CLI 只守「写没写」与「形态对不对」，不判点数对
不对**——拆点是起草侧按 P1 做的专家判断，机器守不了，硬判会逼出假数据。

## O1–O3 与「事实日／补记日」（队列 §一 `#447`，Shao Peishen 2026-09-07 答合审材料 §10 (a)）

- **O1**：`set-status --status` 的取值收敛为闭集＝**判据版八态 ＋ 第九态**
  （`CLI_STATUS_CLOSED_SET`），其余一律拒。它比原先的
  `classify_status != "unknown"` 更窄——后者还认得已退役的 `✅ 已发`
  （README 主表实测 6 行、全部 2026-07，**不回改**，此后不许再写）。
- **O2**：`append --recipient-cell` 须为 `部门 · 姓名`，姓名以人员名录正本为准
  （取数走 `editlock.PERSON_GENDER_ROSTER`，不运行时解析散文正本，理由同那份
  常量自己的注释）；并与 `--department` 一致（不一致会把号取到别的部门序列里
  且不报错）。实测 45 行主表零误杀。
- **O3**：`append` 拒收 frontmatter 仍带 `开放点计数:`／`开放点:` 的信件，
  `决策点:` 为唯一正本。落点刻意在登记 CLI 而非全目录 lint（3 封历史件不追改）。
- **⑵ 事实日／补记日**：`set-status` 新增 `--fact-date`，转
  `✅ 已推送`／`📥 已回件并回灌`／`📨 已确认闭环`／第九态 时**必填**；不可考写
  字面量 `事实日未知`（与点级台账同一份常量）。**补记日由工具取本机当天、不接受
  传参**——能传即可倒填，而它正是量「补记滞后」的那一半。两者以规范尾标
  `〔事实日 X ／ 补记日 Y〕` 落在状态单元格（不新增表列，理由见常量区注释）。
  🔴 **事实日一经写入不得被后续补记覆盖**：已有具体日期时改值即拒，逃生阀是
  在 `--status` 文本里显式写 `事实日更正：`（留痕在单元格里、可被检索）。
  成因＝2026-08-23 有 12 封信被批量补转态，真实回件日在那一刻被覆盖式销毁，
  代理指标中位数由 2 天漂到 7 天而底层事实一天没变，**全程不产生任何信号**。
  度量侧配套＝`0-学习与工具/工具-跟进信往返度量.py`（`事实日未知` 与「无标注」
  两类各自单列，不混入中位数）。

## 用法

    python 0-学习与工具/工具-跟进信README登记.py append \\
        --who "CC-OP0906A" --department 采购部 --recipient-cell "采购部 · 姚祖怡" \\
        --date 2026-09-06 --topic "…" --deadline-note "…" \\
        --letter-path "6-人才与组织/部门AI专员跟进/采购部-姚祖怡-跟进-2026-09-06-….md"

    python 0-学习与工具/工具-跟进信README登记.py set-status \\
        --who "CC-OP0906A" --number 采购部#19 --status "📥 已回件并回灌（…）" \\
        --fact-date 2026-09-05        # 回件真正到达那一天；查不出来写 事实日未知

两个子命令均支持 `--dry-run`（不取锁、不写文件，只跑校验并打印结果）。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_editlock_spec = importlib.util.spec_from_file_location(
    "_followup_registry_editlock_reuse", _EDIT_LOCK_SCRIPT
)
editlock = importlib.util.module_from_spec(_editlock_spec)
sys.modules[_editlock_spec.name] = editlock  # dataclass 在 Python 3.14 下需要能在 sys.modules 解析到所属模块
_editlock_spec.loader.exec_module(editlock)

_GATE_QUERY_SCRIPT = _TOOLS_DIR / "工具-跟进闸查询.py"
_gate_query_spec = importlib.util.spec_from_file_location(
    "_followup_registry_gatequery_reuse", _GATE_QUERY_SCRIPT
)
gate_query = importlib.util.module_from_spec(_gate_query_spec)
sys.modules[_gate_query_spec.name] = gate_query
_gate_query_spec.loader.exec_module(gate_query)

# 信件 frontmatter 解析＋`决策点:` 形态判据的唯一来源（见模块 docstring
# 「复用而非重造」）——同目录既定的 importlib 手法。
_LETTER_FM_SCRIPT = _TOOLS_DIR / "工具-跟进信frontmatter校验.py"
_letter_fm_spec = importlib.util.spec_from_file_location(
    "_followup_registry_letterfm_reuse", _LETTER_FM_SCRIPT
)
letter_fm = importlib.util.module_from_spec(_letter_fm_spec)
sys.modules[_letter_fm_spec.name] = letter_fm
_letter_fm_spec.loader.exec_module(letter_fm)

REPO_ROOT: Path = editlock.REPO_ROOT
README_REL = gate_query.README_REL

_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools import followup_gate  # noqa: E402
# 🔴 `事实日未知` 字面量的唯一来源＝点级台账（`#439`）已落的 SCHEMA §二。
# 信级（本 CLI）与点级是同一条判据的两个落点，**字面量只此一份**——两处各写
# 一个字符串，度量脚本按哪一个筛都会漏掉另一半，而漏掉不报错。
from zhuopin_platform.coverage_point_ledger.models import (  # noqa: E402
    FACT_DATE_UNKNOWN,
)

_AIBOT_PATH = _REPO_GUESS / "5-平台底座" / "wecom-aibot-service"
if not _AIBOT_PATH.is_dir():
    _AIBOT_PATH = REPO_ROOT / "5-平台底座" / "wecom-aibot-service"
if _AIBOT_PATH.is_dir() and str(_AIBOT_PATH) not in sys.path:
    sys.path.insert(0, str(_AIBOT_PATH))
from aibot_service import readme_table  # noqa: E402
from aibot_service.readme_table import (  # noqa: E402
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    column_index,
    iter_rows,
    split_department_and_name,
    write_cells,
)

DRAFT_STATUS = "⏳ 待你审"
TOPIC_MAX_BYTES = 600
DEADLINE_NOTE_MAX_BYTES = 400
UNNUMBERED_ANNOTATION = "（待你审，暂不占号）"

DECISION_FIELD = "决策点"
# O3（Shao Peishen 2026-09-07 答合审材料 §10 (a)）：`决策点:` 为唯一正本，
# 两个旧字段停写。**落点刻意在登记 CLI 而不在 `工具-跟进信frontmatter校验.py`**：
# 后者扫全目录，把 3 封历史件（`质量部#9`／`质量部#11`／`采购部#16`）判成永久
# 违规，而「历史件不追改」是既定纪律 ⇒ 一条恒红的校验只会被人加豁免绕开。
# 登记 CLI 只看**本次要登记的那一封**，天然只约束新件。
LEGACY_DECISION_FIELDS = ("开放点计数", "开放点")

# 拒绝文案统一的「出路」尾句——四种拒绝形态共用一份，措辞只有一处可改。
DECISION_HINT = (
    "出路：按 skill `zhuopin-followup-letter` v3.8 §5 步骤 1bis 在信件 frontmatter "
    "写一行 `决策点: N 项（a / b / c）`，按 P1 判别式拆点（专员只答这一条、"
    "完全不答其他条，这一条能否成立 ⇒ 能即独立一点）；B 类通报信写 "
    "`决策点: 0 项（结果通报＋请验收，无需其决策）`。"
)

# ---------------------------------------------------------------------------
# O1：`--status` 取值闭集（Shao Peishen 2026-09-07 答合审材料 §10 (a)）
# ---------------------------------------------------------------------------
# 判据版八态（`6-人才与组织/部门AI专员跟进/跟进机制-判据版.md` §二 原文顺序）。
# 闭环三态是它的子集（📥／✅ 无需回复／📨 已确认闭环），不另立一份。
CANONICAL_EIGHT_STATUS_PREFIXES: tuple[str, ...] = (
    "⏳ 待你审",
    "🆕 待发",
    "⏸ 暂缓",
    "✅ 已推送",
    "📥 已回件并回灌",
    "✅ 无需回复",
    "📨 已确认闭环",
    "❌ 已作废",
)
# 🔴 第九态 `📨 回件已到，待拆件` 一并纳入闭集，**这不是放宽 O1**：它是 `#366`
# M1 落地、由 S4 桥一实际写进同一列的权威状态，判据版 §二 只是成文早于它。
# 把它排除在外的后果不是「拦住了一种乱写」，而是「唯一合法登记入口写不出一个
# 合法状态」——人只会绕开 CLI 裸手 Edit，正是本 CLI 存在的理由被绕过。
# ⚠️ 若哪天判据版 §二 改写九态成文，此处删掉本行、直接引 §二即可。
CLI_STATUS_CLOSED_SET: tuple[str, ...] = CANONICAL_EIGHT_STATUS_PREFIXES + (
    followup_gate.REPLY_ARRIVED_STATUS,
)
# 闭集之外、但 `followup_gate` 仍认得的历史写法（`✅ 已发`，README 主表实测
# 6 行、全部 2026-07）。它们**不回改**（历史行不追改），只是此后不许再写。
STATUS_HINT = (
    "出路：改用判据版八态之一（`跟进机制-判据版.md` §二）作为前缀，括注随便写；"
    f"回件物理到达但尚未拆件写 `{followup_gate.REPLY_ARRIVED_STATUS}`。"
    "⚠️ 历史写法 `✅ 已发` 已退役（README 主表 6 行、全部 2026-07，不回改），"
    "此后一律写 `✅ 已推送 <时刻>`。"
)

# ---------------------------------------------------------------------------
# ⑵：事实日／补记日（队列 §一 `#447` ⑵；判据正本＝
#     `design审前置-口径点台账三开放点收敛-2026-09-01.md` §4.5 与 §5.3
#     Requirement「事实日期一经写入不得被补记覆盖」）
# ---------------------------------------------------------------------------
# 🔴 成因（一句话）：2026-08-23 有 12 封信被批量「补转态」，状态列只留下补记
# 当天，**真实回件日在那一刻被覆盖式销毁**；代理指标中位数由 2 天漂到 7 天，
# 底层事实一天没变。销毁不产生任何信号，是本仓库反复吃过的那一族。
#
# **为什么落在状态单元格的规范尾标、而不是新增一列**：新增列要改主表表头，
# 45 行历史行与四个解析方（`readme_table`／查询／闸／桥）全部要跟；而状态列
# **今天已经在写日期**（`📥 已回件并回灌 2026-08-24（回件到达 2026-08-…`），
# 问题从来不是没地方写，是写下来的那个日期分不清是事实日还是补记日。规范
# 尾标只把这两者**分开**，不动表形态。历史行天然没有尾标 ⇒ 度量脚本据此把
# 它们单列，而它们恰好就是被污染的那批样本。
FACT_MARK_OPEN = "〔"
FACT_MARK_CLOSE = "〕"
FACT_MARK_RE = re.compile(
    r"〔事实日\s*(?P<fact>事实日未知|\d{4}-\d{2}-\d{2})\s*／\s*补记日\s*(?P<rec>\d{4}-\d{2}-\d{2})\s*〕"
)
# 承载事实日的状态：判据版 §二 里**取值形态自带日期/时刻**的那几个，加第九态。
# `✅ 无需回复`／`❌ 已作废`／三个未发态不强制——前两者是我方当场的判定、
# 后三者对方还没看到这封信，都不存在「事实发生在别的一天」这回事。
FACT_DATE_REQUIRED_PREFIXES: tuple[str, ...] = (
    "✅ 已推送",
    "📥 已回件并回灌",
    "📨 已确认闭环",
    followup_gate.REPLY_ARRIVED_STATUS,
)
# 事实日已写入后要改，唯一合法通道：在 `--status` 文本里显式写这个标记。
# 同 `串行豁免：`／`转态豁免：` 的既有房规——逃生阀留在单元格里、可被检索，
# 而不是一个命令行开关（开关跑完就没了，谁也看不出这行被改过）。
FACT_DATE_AMEND_MARKER = "事实日更正："
FACT_DATE_HINT = (
    f"出路：`--fact-date YYYY-MM-DD` 写**事实发生那一天**（回件到达日／确认闭环日／"
    f"推送日）；查不出来就写 `--fact-date {FACT_DATE_UNKNOWN}`。"
    f"🔴 **不得拿今天顶替**——顶替一次，这封信的真实日期就永久没了，"
    f"而且不报错（`#447` ⑵ 的 12 封信实证）。补记日由本工具取本机当天，不接受传参。"
)

# ---------------------------------------------------------------------------
# O2：`--recipient-cell` 取值形态（Shao Peishen 2026-09-07 答合审材料 §10 (a)）
# ---------------------------------------------------------------------------
# 姓名正本＝`6-人才与组织/人员名录-称谓与性别-正本.md`。**取数走
# `editlock.PERSON_GENDER_ROSTER`，不在此运行时解析正本散文**——理由是那份
# 常量自己写着的那条（正本 §一 是每周都在变的散文，措辞一变就抽不到人名，
# 判据随即恒真、零信息量且没有任何东西会报错），且编辑锁侧已有一条同步用例
# 保证「正本 §一 ⊆ 该常量」，名录扩了没跟当场变红。此处再解析一次＝第二份
# 会漂移的名录。
RECIPIENT_SEPARATOR = "·"
# 名录规模下限——防「解析到 0 个人名却把每个收信人都判成不在册」。取 15 是
# 相对当前 21 人的保守下限（正本 §一 明写「全员 21 人」）。
_ROSTER_FLOOR = 15
RECIPIENT_HINT = (
    '出路：`--recipient-cell "<部门> · <姓名>"`（中点两侧各一个半角空格），'
    "姓名须在 `6-人才与组织/人员名录-称谓与性别-正本.md` 在册。"
    "🔴 **名录里没有的人不许现编**——当场问 Shao Peishen 一次、补进正本再登记"
    "（禁从名字推断任何属性，猜错不产生信号）。"
)

# 归档件命名（`followup-readme-archive` 能力，2.3 落地后生效；本文件先兼容
# 「归档件尚不存在」的现状，`glob` 命中 0 个文件属正常）。
_ARCHIVE_GLOB = "README-归档-*.md"


class RegistryError(RuntimeError):
    """校验失败、拒绝写入——不区分子类，调用方统一按退出码 1 处理。"""


class LockAcquireFailedError(RuntimeError):
    """编辑锁获取失败（他人持锁），未做任何改动。"""


class ReadbackMismatchError(RuntimeError):
    """写后回读比对失败——按 spec 要求保留锁，不自动释放、不自动重试。"""


def _readme_path() -> Path:
    return REPO_ROOT / README_REL


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _assert_field_lengths(topic: str, deadline_note: str) -> None:
    topic_bytes = _byte_len(topic)
    if topic_bytes > TOPIC_MAX_BYTES:
        raise RegistryError(
            f"「主要事项」{topic_bytes} B，超 {TOPIC_MAX_BYTES} B 上限——"
            "请改用行长外置（`followup-readme-row-length-guard` 能力：压成摘要，"
            "原文写入 `跟进信行日志/<部门#N>.md`）后再登记摘要。"
        )
    note_bytes = _byte_len(deadline_note)
    if note_bytes > DEADLINE_NOTE_MAX_BYTES:
        raise RegistryError(
            f"「交期要点」{note_bytes} B，超 {DEADLINE_NOTE_MAX_BYTES} B 上限——"
            "请精简后再登记。"
        )


def _parse_rows(text: str, section: str | None = None) -> list:
    """解析表头与数据行；只保证表头可解析，**不对历史行的列数做任何断言**
    ——校验范围限定为本次触碰的行，见 spec「写前列数校验与写后回读」
    2026-09-06 补充说明（`采购部#14` 历史行因未转义 `|` 被朴素分列多出一列，
    早于本能力存在，不应阻塞其它行的登记）。"""
    try:
        rows = iter_rows(text, section)
    except ReadmeTableError as exc:
        raise RegistryError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        raise RegistryError("README 主表没有任何数据行，拒绝在此基础上继续")
    return rows


def _assert_row_column_count(cells: list[str], header: list[str], row_label: str) -> None:
    """本次待写入/待改写的那一行列数须与表头一致——只查这一行，不查全表。"""
    if len(cells) != len(header):
        raise RegistryError(
            f"「{row_label}」列数校验失败：{len(cells)} 列，表头 {len(header)} 列——"
            "拒绝写入"
        )


def _find_in_archives(number: str) -> str | None:
    """在归档件中查找编号，命中返回归档文件相对路径，未命中返回 None。

    `followup-readme-archive` 能力（2.3）落地前，归档件尚不存在，
    `glob` 天然返回空——本函数此时恒返回 None，行为等价于「archive 查找
    这一步暂时是空操作」，不是特殊分支。
    """
    readme_dir = _readme_path().parent
    for archive_path in sorted(readme_dir.glob(_ARCHIVE_GLOB)):
        try:
            text = archive_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            rows = iter_rows(text, MAIN_TABLE_SECTION)
        except ReadmeTableError:
            continue
        header = rows[0].header_cells if rows else []
        number_col = column_index(header, "编号")
        if number_col is None:
            continue
        for row in rows:
            if len(row.cells) <= number_col:
                continue
            parsed = followup_gate.parse_letter_number(row.cells[number_col])
            target_parsed = followup_gate.parse_letter_number(number)
            if parsed and target_parsed and parsed == target_parsed:
                return str(archive_path.relative_to(REPO_ROOT))
    return None


def _run_lock(action: str, who: str, note: str | None = None) -> bool:
    """返回是否成功。`acquire` 失败直接抛异常（未做任何改动，无需返回值）；
    `release` 被拒绝返回 `False`，由调用方决定如何呈现（不得报告成功）。"""
    cmd = [
        sys.executable, str(_EDIT_LOCK_SCRIPT), "--file", README_REL,
        action, "--who", who,
    ]
    if note and action == "acquire":
        cmd.extend(["--note", note])
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        if action == "acquire":
            raise LockAcquireFailedError(
                f"编辑锁获取失败（README）：\n{result.stdout}\n{result.stderr}"
            )
        # release 被拒绝——文件已写入，锁仍占用，调用方 MUST NOT 报告成功
        # （见 spec「编辑锁 release 失败不得报告为成功」，2026-09-06 实测发现：
        # 新增行触发既有「跟进信串行原则」release 校验时会走到这里）。
        print(f"✗ 编辑锁 release 被拒绝：\n{result.stdout}\n{result.stderr}", file=sys.stderr)
        return False
    print(result.stdout, end="")
    return True


def _write_readback(new_text: str, expected_cells: list[str], locate) -> None:
    """写盘后立即回读并比对，比对失败抛 `ReadbackMismatchError`（不释放锁）。"""
    _readme_path().write_text(new_text, encoding="utf-8")
    reread = _readme_path().read_text(encoding="utf-8")
    row = locate(reread)
    if row is None or row.cells != expected_cells:
        raise ReadbackMismatchError(
            "写后回读比对失败——文件内容与预期不一致，编辑锁保留，请人工排查"
            "（不自动重试、不自动回滚）。"
        )


def _assert_gate_open(recipient_cell: str, text: str) -> None:
    """append 前置串行闸检查——判据与 `工具-跟进闸查询.py` 同一份
    （`gate_query.build_report`，本身即 `followup_gate.classify_status`）。
    2026-09-06 实测发现补入：编辑锁 release 时的「跟进信串行原则」结构校验
    只在写入之后拦截，会留下「文件已改、release 被拒、锁未释放」的中间态；
    把同一判据前移到写入前可避免这种情形。"""
    _, name = split_department_and_name(recipient_cell)
    if not name:
        return  # 收信人姓名解析不出，交由既有 release 校验与人工判断兜底
    try:
        report = gate_query.build_report(name, text)
    except gate_query.GateQueryError:
        return  # 该收信人此前无任何行——视为闸开，无在途信可挡
    if not report.gate_open:
        raise RegistryError(
            f"收信人「{name}」当前闸锁——最新一封「{report.letter_number}」"
            f"（{followup_gate.normalize_status(report.letter_status)[:40]}）尚未闭环，"
            "拒绝新增草稿行。请先处理该在途信使其闭环，或改在队列登记"
            "「待前信闭环后发」。（同 `python 0-学习与工具/工具-跟进闸查询.py "
            f"--to {name}` 的判据）"
        )


def _assert_decision_points(letter_path: str) -> str:
    """`append` 前置：信件 frontmatter 必须带非空且形态合判据的 `决策点:`。

    命中即抛 `RegistryError`（退出码 1，未取锁、未写入）。返回读到的取值，
    供调用方回显——**让「守住了什么」在成功路径上也可见**，否则这条闸自己
    就成了下一个「不产生任何信号」的机制。

    四种拒绝形态（都给同一句出路，见 `DECISION_HINT`）：
      ⑴ 文件不存在／读不动；⑵ 非 frontmatter 开头；⑶ 字段缺失或为空；
      ⑷ 取值形态不合 `letter_fm.RE_DECISION`（前缀锚定 `^\\d+\\s*项`）。
    """
    raw = Path(letter_path)
    path = raw if raw.is_absolute() else REPO_ROOT / raw
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryError(
            f"读不到待登记信件「{letter_path}」（{exc.__class__.__name__}）——"
            "`--letter-path` 须指向本次要登记的那封信的 `.md`（仓库根相对路径或"
            f"绝对路径均可）。{DECISION_HINT}"
        ) from exc

    parsed = letter_fm.parse_frontmatter(text)
    if parsed is None:
        raise RegistryError(
            f"信件「{letter_path}」不以 frontmatter（首行 `---`）开头，无法读取 "
            f"`{DECISION_FIELD}:`——拒绝登记。{DECISION_HINT}"
        )
    fields, _order = parsed
    value = fields.get(DECISION_FIELD, "").strip()
    if not value:
        missing = "缺" if DECISION_FIELD not in fields else "为空"
        raise RegistryError(
            f"信件「{letter_path}」frontmatter {missing} `{DECISION_FIELD}:` 字段——"
            f"拒绝登记。{DECISION_HINT}"
        )
    if not letter_fm.RE_DECISION.match(value):
        raise RegistryError(
            f"信件「{letter_path}」的 `{DECISION_FIELD}: {value}` 形态不合判据——"
            "取值须以「数字＋项」开头（如 `0 项（…）`／`3 项（a / b / c）`）；"
            "括号内怎么写不校验（判据只做前缀锚定，理由见 "
            f"`工具-跟进信frontmatter校验.py` S3）。{DECISION_HINT}"
        )
    _assert_no_legacy_decision_fields(letter_path, fields)  # O3
    return value


def _assert_no_legacy_decision_fields(letter_path: str, fields: dict[str, str]) -> None:
    """O3：`开放点计数:`／`开放点:` 停写，`决策点:` 为唯一正本。

    两个旧字段与 `决策点:` 是**同一件事的三种写法**，并存时无法判定哪个为准；
    `开放点计数` 的实测取值还是整句散文（`本封要你定 4 件事（…）`），机器取不出
    点数。命中即拒登记，出路是把内容并进 `决策点:` 后删掉旧行。
    """
    hit = [f for f in LEGACY_DECISION_FIELDS if f in fields]
    if not hit:
        return
    listed = "／".join(f"`{f}:`" for f in hit)
    raise RegistryError(
        f"信件「{letter_path}」frontmatter 仍带已停写字段 {listed}——拒绝登记。"
        f"O3（Shao Peishen 2026-09-07 答合审材料 §10 (a)）：以 `{DECISION_FIELD}:` "
        "为唯一正本，两个旧字段停写。出路：把其内容按 P1 判别式并进 "
        f"`{DECISION_FIELD}: N 项（a / b / c）`，然后删掉旧行。"
        "（历史件不追改，本闸只看本次要登记的这一封。）"
    )


def _roster_names() -> set[str]:
    """姓名正本的机器面（见 `RECIPIENT_HINT` 上方注释：取编辑锁侧那份常量）。"""
    names = set(editlock.PERSON_GENDER_ROSTER)
    if len(names) < _ROSTER_FLOOR:
        # 🔑 「只读结果太干净先怀疑没读到对象」——名录突然只剩几个人，几乎必然
        # 是取数路径坏了，而不是公司少了十几个人。此时若照常判定，每个真实收
        # 信人都会被判成「不在册」，且错得非常自信。
        raise RegistryError(
            f"人员名录取数异常：只读到 {len(names)} 个姓名（下限 {_ROSTER_FLOOR}）——"
            "拒绝在此基础上判定收信人。请先查 `工具-共享文档编辑锁.py::"
            "PERSON_GENDER_ROSTER` 是否被改坏。"
        )
    return names


def _assert_recipient_cell(recipient_cell: str, department: str) -> tuple[str, str]:
    """O2：`收信人` ＝ `部门 · 姓名`，姓名以名录正本为准；返回 `(部门, 姓名)`。

    实测 45 行主表全部通过（`IT部 · 陈承`／`财务部 · 唐燕萍`／`质量部 · 陈忱`／
    `采购部 · 姚祖怡`），本闸对既有语料零误杀——它拦的是**下一封**里新出现的
    写法漂移（合审材料 §10 O2 点名的 16 种写法、部门名三种写法）。
    """
    if RECIPIENT_SEPARATOR not in recipient_cell:
        raise RegistryError(
            f"「收信人」取值 {recipient_cell!r} 不含分隔符 `{RECIPIENT_SEPARATOR}`"
            f"——拒绝登记。{RECIPIENT_HINT}"
        )
    dept, name = split_department_and_name(recipient_cell)
    if not dept or not name:
        raise RegistryError(
            f"「收信人」取值 {recipient_cell!r} 解析不出「部门」或「姓名」"
            f"——拒绝登记。{RECIPIENT_HINT}"
        )
    if name not in _roster_names():
        raise RegistryError(
            f"「收信人」姓名 {name!r} 不在人员名录正本在册名单内——拒绝登记。"
            f"{RECIPIENT_HINT}"
        )
    if dept != department:
        # 编号按部门连续编号（`_next_available_number` 取的就是 `--department`）。
        # 两处不一致 ⇒ 号取到别的部门序列里去，而登记完看不出来。
        raise RegistryError(
            f"`--department`（{department!r}）与「收信人」里的部门（{dept!r}）不一致"
            "——拒绝登记。编号按部门连续取号，两处不一致会把号取到另一个部门的"
            "序列里，且写完不报错。请改到一致后重试。"
        )
    return dept, name


def _assert_status_in_closed_set(status: str) -> str:
    """O1：`--status` 取值须以闭集之一为前缀；返回归一化后的取值。

    闭集＝判据版八态 ＋ 第九态（理由见 `CLI_STATUS_CLOSED_SET` 上方注释）。
    括注怎么写不校验——受约束的是**前缀**，那是闸／度量／桥三方唯一读的部分。
    """
    normalized = followup_gate.normalize_status(status)
    if not any(normalized.startswith(p) for p in CLI_STATUS_CLOSED_SET):
        listed = "／".join(f"`{p}`" for p in CLI_STATUS_CLOSED_SET)
        kind = followup_gate.classify_status(normalized)
        extra = (
            "（该写法 `followup_gate` 认得、但不在闭集内——O1 收敛后已退役）"
            if kind != "unknown" else "（`followup_gate` 也不认得这个写法）"
        )
        raise RegistryError(
            f"状态值「{status}」不属登记 CLI 闭集{extra}，拒绝写入。"
            f"闭集＝{listed}。{STATUS_HINT}"
        )
    return normalized


def _today() -> str:
    """补记日＝本机当天。**独立成函数只为可注入**（单测要一个确定的今天）；
    生产路径永远走 `date.today()`，不接受命令行传参——一个能传的补记日等于
    可以被倒填，而它正是用来量「补记滞后」的那一半。"""
    return date.today().isoformat()


def _parse_fact_mark(status_cell: str) -> tuple[str, str] | None:
    """从状态单元格取 `(事实日, 补记日)`；无规范尾标返回 `None`。

    `None` ＝「这一行没标注」，**与「事实日未知」是两回事**：前者是历史行
    （尾标机制之前写的，真实日期未必丢了，只是没记），后者是有人明确记下了
    「查不出来」。度量脚本必须把两者分开列，混在一起就等于把「没记」洗成
    「记了不知道」。
    """
    m = FACT_MARK_RE.search(status_cell)
    if not m:
        return None
    return m.group("fact"), m.group("rec")


def _render_fact_mark(fact_date: str, recorded_on: str) -> str:
    return f"{FACT_MARK_OPEN}事实日 {fact_date} ／ 补记日 {recorded_on}{FACT_MARK_CLOSE}"


def _assert_fact_date(fact_date: str | None, normalized_status: str) -> str | None:
    """校验 `--fact-date` 的必填与形态；返回规范化取值（不需要时返回 `None`）。"""
    required = any(normalized_status.startswith(p) for p in FACT_DATE_REQUIRED_PREFIXES)
    value = (fact_date or "").strip()
    if not value:
        if required:
            listed = "／".join(f"`{p}`" for p in FACT_DATE_REQUIRED_PREFIXES)
            raise RegistryError(
                f"状态「{normalized_status[:24]}」承载事实日期（{listed} 一族），"
                f"`--fact-date` 必填——拒绝写入。{FACT_DATE_HINT}"
            )
        return None
    if value == FACT_DATE_UNKNOWN:
        return value
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RegistryError(
            f"`--fact-date {value}` 不是 YYYY-MM-DD 形态、或这一天并不存在（{exc}）。"
            f"{FACT_DATE_HINT}"
        ) from exc
    if parsed.isoformat() > _today():
        raise RegistryError(
            f"`--fact-date {value}` 晚于本机当天（{_today()}）——事实不会发生在未来。"
            f"{FACT_DATE_HINT}"
        )
    return parsed.isoformat()


def _status_prefix(status_cell: str) -> str | None:
    """状态单元格命中闭集里的哪一个前缀；都不命中返回 `None`（历史写法）。"""
    normalized = followup_gate.normalize_status(status_cell)
    for prefix in CLI_STATUS_CLOSED_SET:
        if normalized.startswith(prefix):
            return prefix
    return None


def _resolve_fact_mark(
    old_status_cell: str, new_status: str, new_fact_date: str | None
) -> tuple[str, str] | None:
    """定出本次要写的 `(事实日, 补记日)`；不需要尾标时返回 `None`。

    🔴 **事实日是「当前这个状态」的属性，不是「这一行」的属性**——`📥 已回件并
    回灌` 的事实日是回件到达日，`📨 已确认闭环` 的是我方确认那一刻，两者本就
    不同。曾经把它写成「一行只有一个事实日、转态时沿用」，单测当场撞出矛盾：
    转闭环时要么被逼着重复填回件日，要么把回件日当成确认日。故：

      ⑴ **同一状态前缀** ＋ 旧尾标已有具体日期 ＋ 本次给的不同 ⇒ **拒绝覆盖**
         （design §5.3 第三条 Requirement）；逃生阀＝`--status` 里显式写
         `事实日更正：`，留痕在单元格里、可被检索。
      ⑵ **换了状态前缀** ⇒ 新事实、新日期，不算覆盖，放行。
      ⑶ 旧尾标是 `事实日未知`、本次给出具体日期 ⇒ 放行。这是**找回信息**，
         与销毁信息方向相反。
      ⑷ 本次状态不承载事实日（如 `❌ 已作废`）而旧行有尾标 ⇒ **原样带过**
         （连同它原来的补记日），不因一次不相干的转态把它冲掉。
    """
    old = _parse_fact_mark(old_status_cell)
    if new_fact_date is None:
        return old  # ⑷ 有就原样带过，没有就不写尾标
    if old is not None:
        old_fact, _old_rec = old
        same_status = _status_prefix(old_status_cell) == _status_prefix(new_status)
        if (
            same_status
            and old_fact != FACT_DATE_UNKNOWN
            and new_fact_date != old_fact
            and FACT_DATE_AMEND_MARKER not in new_status
        ):
            raise RegistryError(
                f"该行在同一状态下已记有事实日 `{old_fact}`，本次 "
                f"`--fact-date {new_fact_date}` 与之不同——拒绝覆盖。"
                "🔴 事实日一经写入不得被后续补记覆盖"
                "（`design审前置-口径点台账三开放点收敛-2026-09-01.md` §5.3 第三条 "
                "Requirement；成因＝12 封信的真实回件日已被 2026-08-23 的批量补转态"
                f"永久销毁）。确属记错要改：在 `--status` 文本里写 "
                f"`{FACT_DATE_AMEND_MARKER}原记 {old_fact}，依据…`，"
                "逃生阀留痕在单元格里、可被检索。"
            )
    return new_fact_date, _today()


def _apply_fact_mark(status: str, mark: tuple[str, str] | None) -> str:
    """把规范尾标写进状态文本（已有的先摘掉，避免叠加两枚）。"""
    if mark is None:
        return status
    stripped = FACT_MARK_RE.sub("", status).rstrip()
    return f"{stripped} {_render_fact_mark(*mark)}"


def _catches_registry_errors(func):
    """`RegistryError`／`LockAcquireFailedError` 统一在这里落成「打印 + 退出码
    1」——`cmd_append`／`cmd_set_status` 本身可被直接调用（单测既定手法），
    不依赖只在 `main()` 里包一层 try/except（那样直接调用 `cmd_*` 的测试会
    看到裸异常，而不是真实 CLI 用户会看到的行为）。"""
    def _wrapped(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except (RegistryError, LockAcquireFailedError) as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
    _wrapped.__name__ = func.__name__
    return _wrapped


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------

@_catches_registry_errors
def cmd_append(args: argparse.Namespace) -> int:
    _assert_field_lengths(args.topic, args.deadline_note)
    # 纯输入校验，排在读 README 之前——拒绝时连主表都不必读。
    _assert_recipient_cell(args.recipient_cell, args.department)  # O2
    decision_value = _assert_decision_points(args.letter_path)

    text = _readme_path().read_text(encoding="utf-8")
    _assert_gate_open(args.recipient_cell, text)
    rows = _parse_rows(text)
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    if number_col is None:
        raise RegistryError("README 表头缺「编号」列")

    next_number = gate_query._next_available_number(rows, number_col, args.department)
    if next_number is None:
        raise RegistryError(f"无法为部门「{args.department}」推算下一个可用号")
    number_cell = f"{next_number}{UNNUMBERED_ANNOTATION}"

    new_cells = [number_cell, args.date, args.recipient_cell, args.topic, args.deadline_note, DRAFT_STATUS]
    _assert_row_column_count(new_cells, header, number_cell)

    print(
        f"[PLAN] append：{number_cell} ｜ {args.date} ｜ {args.recipient_cell} ｜"
        f" 状态={DRAFT_STATUS} ｜ {DECISION_FIELD}={decision_value}"
    )
    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    _run_lock("acquire", args.who, note=f"登记 append：{next_number}")
    try:
        lines = text.splitlines()
        insert_at = rows[-1].line_index + 1
        lines.insert(insert_at, readme_table._join_row(new_cells))
        newline = "\n" if text.endswith("\n") else ""
        new_text = "\n".join(lines) + newline

        def _locate(t: str):
            try:
                for r in iter_rows(t):
                    if r.cells[number_col] == number_cell:
                        return r
            except ReadmeTableError:
                return None
            return None

        _write_readback(new_text, new_cells, _locate)
    except ReadbackMismatchError as exc:
        print(f"[READBACK-FAILED] {exc}", file=sys.stderr)
        return 1
    else:
        if not _run_lock("release", args.who):
            print(
                f"[WRITTEN-LOCK-HELD] 已写入 {number_cell}，但编辑锁 release 被拒绝"
                "（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
                "不得视为登记已完成。",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] 已追加：{number_cell}")
        return 0


# ---------------------------------------------------------------------------
# set-status
# ---------------------------------------------------------------------------

@_catches_registry_errors
def cmd_set_status(args: argparse.Namespace) -> int:
    # O1：闭集校验（比 `followup_gate.classify_status != "unknown"` 更窄——后者
    # 还认得已退役的 `✅ 已发`）。
    normalized = _assert_status_in_closed_set(args.status)
    # ⑵：事实日必填与形态（覆盖判定要读到旧单元格，放在取到行之后）。
    fact_date = _assert_fact_date(args.fact_date, normalized)

    text = _readme_path().read_text(encoding="utf-8")
    rows = _parse_rows(text)
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    if number_col is None:
        raise RegistryError("README 表头缺「编号」列")

    target_parsed = followup_gate.parse_letter_number(args.number)
    match = None
    for row in rows:
        if len(row.cells) <= number_col:
            continue
        cell = row.cells[number_col]
        if cell == args.number or (
            target_parsed and followup_gate.parse_letter_number(cell) == target_parsed
        ):
            match = row
            break

    if match is None:
        archived_at = _find_in_archives(args.number)
        if archived_at:
            raise RegistryError(
                f"编号「{args.number}」已归档（{archived_at}），不可再用本命令改状态——"
                "该行已进入终态历史，如需订正请人工处理归档件。"
            )
        raise RegistryError(f"编号「{args.number}」在主表与归档件中均不存在")

    _assert_row_column_count(match.cells, header, match.cells[number_col])

    old_status_cell = match.cells[match.status_col_index]
    mark = _resolve_fact_mark(old_status_cell, args.status, fact_date)
    final_status = _apply_fact_mark(args.status, mark)

    print(f"[PLAN] set-status：{args.number} → {final_status}")
    if mark is None:
        print("[PLAN] 该状态不承载事实日期，未写事实日／补记日尾标。")
    elif mark[0] == FACT_DATE_UNKNOWN:
        print(
            f"[PLAN] 事实日＝`{FACT_DATE_UNKNOWN}`（补记日 {mark[1]}）——"
            "本样本将由度量脚本单列，不混入中位数。"
        )
    else:
        effective_fact_date, recorded_on = mark
        lag = (date.fromisoformat(recorded_on) - date.fromisoformat(effective_fact_date)).days
        print(f"[PLAN] 事实日 {effective_fact_date} ／ 补记日 {recorded_on} ｜ 补记滞后 {lag} 天。")
        if lag >= 14:
            # 🔴 这行字就是 2026-08-23 那次批量补转态**当时没有**的那个信号：
            # 12 封信滞后 20–27 天、屏幕上一切正常。
            print(
                f"[NOTE] 补记滞后 {lag} 天（≥14）——属迟到补记。事实日已按你给的值"
                "留存，不会被补记日顶替；若这个事实日本身是猜的，改写 "
                f"`--fact-date {FACT_DATE_UNKNOWN}` 比填一个假日期强。"
            )
    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    _run_lock("acquire", args.who, note=f"登记 set-status：{args.number}")
    try:
        new_text = write_cells(text, match, {match.status_col_index: final_status})
        expected_cells = match.cells.copy()
        expected_cells[match.status_col_index] = final_status

        def _locate(t: str):
            try:
                for r in iter_rows(t):
                    if len(r.cells) > number_col and r.cells[number_col] == match.cells[number_col]:
                        return r
            except ReadmeTableError:
                return None
            return None

        _write_readback(new_text, expected_cells, _locate)
    except ReadbackMismatchError as exc:
        print(f"[READBACK-FAILED] {exc}", file=sys.stderr)
        return 1
    else:
        if not _run_lock("release", args.who):
            print(
                f"[WRITTEN-LOCK-HELD] 已改写 {args.number}，但编辑锁 release 被拒绝"
                "（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
                "不得视为登记已完成。",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] 已改写：{args.number} → {final_status}")
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跟进信 README 登记 CLI（唯一登记入口，取代裸手 Edit 直改）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append", help="新增一行（发送状态恒为待审草稿态）")
    p_append.add_argument("--who", required=True, help="会话标识，透传给编辑锁")
    p_append.add_argument("--department", required=True, help="如 采购部")
    p_append.add_argument("--recipient-cell", required=True, help='如 "采购部 · 姚祖怡"')
    p_append.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_append.add_argument("--topic", required=True, help="主要事项（≤600 B）")
    p_append.add_argument("--deadline-note", required=True, help="交期要点（≤400 B）")
    p_append.add_argument(
        "--letter-path", required=True,
        help="本次待登记信件的 .md（仓库根相对或绝对路径）；其 frontmatter 必须"
             "带非空 `决策点:`，缺则拒登记",
    )
    p_append.add_argument("--dry-run", action="store_true")
    p_append.set_defaults(func=cmd_append)

    p_status = sub.add_parser("set-status", help="按编号改写发送状态列")
    p_status.add_argument("--who", required=True)
    p_status.add_argument("--number", required=True, help="如 采购部#19")
    p_status.add_argument(
        "--status", required=True,
        help="新的发送状态值；前缀须属判据版八态＋第九态闭集（O1），括注随便写",
    )
    p_status.add_argument(
        "--fact-date", default=None,
        help=f"事实发生那一天（YYYY-MM-DD），不可考写 `{FACT_DATE_UNKNOWN}`。"
             "转 `✅ 已推送`／`📥 已回件并回灌`／`📨 已确认闭环`／`📨 回件已到，待拆件` "
             "时必填。补记日由本工具取本机当天，不接受传参（能传即可倒填）",
    )
    p_status.add_argument("--dry-run", action="store_true")
    p_status.set_defaults(func=cmd_set_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
