"""跨桌任务队列只读查询 CLI（队列 #268，2026-08-06）。

背景：2026-08-05 一天内业务总线自己 6 次"读状态列只读了一部分"——抽读行尾
420 字符、只读开头 40 字符——把已完成/已拍板的行当待办重提，最要紧的不是
次数，是其中两次发生在**同一天上午已把"读状态一律读完整个单元格"写进
批次记录与接力文件之后**。按 CLAUDE.md §5 规则退休制，"人守"条目被违反
3 次即须机制化或删除，本条 6 次远超阈值——根因不是记性，是取样面：状态列
动辄 800-2000 字符，任何截断读法（裸 grep 命中一行、只看行首/行尾若干
字符）都会在"头尾结论不一致"的行上系统性给出反向答案，且不报错（同
CLAUDE.md §5"工具静默回退"）。#248 刚落地的 release 校验只治"写"的一侧
（写完整、写对位置），"读"的一侧仍缺一个唯一合法通道。

本工具只读、零副作用：给定行号（§一/§四）或批次号（§二），返回状态列
全文（默认不截断），并在开头片段与其余文本出现互斥关键词（已完成/已拍板
类 vs 待领/待你审/在办类）时显式打印一行冲突警告——头尾不一致以晚出内容
为准（较早的 CLAUDE.md 判据惯例），但本工具的职责只是"让人看见冲突"，
不代替人做判断。

判据实现指针（队列 #307，2026-08-09）：表格切分／开头片段提取一律 import
`zhuopin_platform.shared_tools.queue_table`，不再新起独立实现；本文件历史
上曾把"独立实现是本项目一贯做法"写在这里（理由是本目录多个 `.py` 文件名
含中文/连字符、不是标准可 import 的模块路径），该理由已被证伪——
`zhuopin_platform` 本就是可安装包，见 #306。本工具目前列数校验已切换至该
模块（见文件顶部 import）；表格切分/开头片段提取因 #308 状态机器字段
落地已大部分作废，不在 #306 权威化范围内，本文件按需继续本地实现。历史上
的独立实现清单及其成因见队列 #306。

用法：
  python 0-学习与工具/工具-队列查询.py --row 258
  python 0-学习与工具/工具-队列查询.py --row 150 --section 一
  python 0-学习与工具/工具-队列查询.py --row B-0806_xxx --section 二
  python 0-学习与工具/工具-队列查询.py --row 51 --section 四
  python 0-学习与工具/工具-队列查询.py --row 258 --field all
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 队列 #306：本脚本自身所在的 worktree 本地路径找 zhuopin_platform（同
# 工具-共享文档编辑锁.py 既有引导，与队列 #300 conftest.py 同一原则）。
# 仅当目录真实存在时才尝试 import，缺失时（隔离环境）用本地兜底桩。
_QUEUE_TABLE_SEARCH_ROOT = Path(__file__).resolve().parents[1]
_PLATFORM_PATH = _QUEUE_TABLE_SEARCH_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir():
    if str(_PLATFORM_PATH) not in sys.path:
        sys.path.insert(0, str(_PLATFORM_PATH))
    from zhuopin_platform.shared_tools import queue_table  # noqa: E402
else:
    class queue_table:  # type: ignore[no-redef]
        """隔离环境兜底桩——取值须与 zhuopin_platform.shared_tools.queue_table
        保持一致，见该模块。"""

        SECTION_COLUMN_COUNTS = {"一": 8, "二": 4, "四": 4}
        QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
        # 队列 #315：拆分后两份物理文件路径，隔离桩同样须与权威实现保持一致。
        QUEUE_MECHANISM_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
        QUEUE_BUSINESS_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

        # 简化近似，非逐字节镜像——权威实现按 CommonMark 反引号游程规则
        # 配对（见 queue_table.py::_mask_backtick_spans，队列 #314 apply
        # 阶段真实数据踩坑后从单反引号正则升级而来）；本桩只保证隔离测试
        # 环境（无 5-平台底座/zhuopin_platform 目录）不崩、能正确处理最
        # 常见的单反引号跨度，不追求对双反引号转义单反引号这类少见写法
        # 字节级一致——隔离测试从不喂这类内容，为一个仅覆盖降级路径的
        # 桩复刻完整算法是过度实现。
        _BACKTICK_SPAN_RE = re.compile(r"`[^`]*`")
        _PROTECTED_PIPE_SENTINEL = ""

        @staticmethod
        def split_row_cells(line: str) -> list[str] | None:
            s = line.strip()
            if not s.startswith("|"):
                return None
            sentinel = queue_table._PROTECTED_PIPE_SENTINEL
            protected = queue_table._BACKTICK_SPAN_RE.sub(
                lambda m: m.group(0).replace("|", sentinel), s,
            )
            return [
                c.replace(sentinel, "|").strip()
                for c in protected.strip("|").split("|")
            ]


def _resolve_repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip()).parent
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return Path(__file__).resolve().parents[1]


REPO_ROOT = _resolve_repo_root()
DEFAULT_TARGET = queue_table.QUEUE_PATH_REL  # 队列 #313：收拢自本地字面量
# 队列 #315（apply）：拆分后本路径转为纯指针文件；`--file` 未显式覆盖时
# （即等于本值）触发双文件查询——见 main() 与 `_is_queue_system_target`。
QUEUE_MECHANISM_PATH_REL = queue_table.QUEUE_MECHANISM_PATH_REL
QUEUE_BUSINESS_PATH_REL = queue_table.QUEUE_BUSINESS_PATH_REL


def _is_queue_system_target(file_arg: str) -> bool:
    return file_arg == DEFAULT_TARGET

LIVE_SECTION_HEADING_RE = re.compile(r"^## ([一二三四])、", re.MULTILINE)
_TABLE_HEADER_FIRST_CELLS = ("#", "批次", "")

# §一/§二/§四 各自的列结构——用于定位"状态列"（§四 无独立状态列，取"事项"
# 列展示，见 SECTION_STATUS_LABEL 与 main() 里的提示文案）。列名语义仍本地
# 维护（展示用，非 #306 权威化范围）；列数一致性见下方断言。
SECTION_COLUMNS = {
    "一": ["#", "任务", "领取方", "输入（指针）", "期望产出", "状态", "触碰区", "登记"],
    "二": ["批次", "文件清单", "说明", "状态"],
    "四": ["#", "事项", "等谁", "截止"],
}
# 队列 #306：与权威列数常量保持一致——若两者漂移，说明本文件的列名列表
# 与共享模块的列数定义已不同步，模块加载时即报错，不留到运行期误判。
assert {k: len(v) for k, v in SECTION_COLUMNS.items()} == queue_table.SECTION_COLUMN_COUNTS, (
    "SECTION_COLUMNS 列数与 queue_table.SECTION_COLUMN_COUNTS 不一致，请核对"
)
SECTION_STATUS_INDEX = {"一": 5, "二": 3, "四": 1}
SECTION_STATUS_LABEL = {"一": "状态", "二": "状态", "四": "事项（§四无独立状态列，取本列展示）"}
ROW_NUMBER_SECTIONS = ("一", "四")

# 队列 #248 锚定口径（与编辑锁/sweep 两处独立实现保持同一算法，见模块文档）。
LEADING_STRIP_CHARS = "* \t　"
LEADING_SEGMENT_SEPARATORS = ("。", "——", "━━━")

DONE_MARKERS = ("✅", "已完成", "已拍板")
PENDING_MARKERS = ("待领", "待你审", "在办")

# 队列 #308（2026-08-09，决策点 4）：§一 状态列开头机器可读字段——本工具
# 与编辑锁/sweep 两处各自独立实现一份解析（同 #248 既有惯例）。仅 §一
# 适用，§二/§四 继续沿用上面既有的 DONE_MARKERS/PENDING_MARKERS 头尾冲突
# 检测（不在本次机器字段范围内，见 design.md Non-Goals）。
STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)


def _parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    """解析 §一 状态列开头的机器字段，返回 (状态取值或 None, 域取值或
    None, 字段之后的自然语言正文)。缺失/非法时返回 (None, None, 原文)。"""
    stripped = status_cell.lstrip(LEADING_STRIP_CHARS)
    m = STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    return m.group(1), m.group(2), stripped[m.end():]


def _leading_segment(cell_text: str) -> str:
    stripped = cell_text.lstrip(LEADING_STRIP_CHARS)
    cut = len(stripped)
    for sep in LEADING_SEGMENT_SEPARATORS:
        idx = stripped.find(sep)
        if idx != -1:
            cut = min(cut, idx)
    return stripped[:cut]


def _split_live_sections(text: str) -> dict[str, str]:
    matches = list(LIVE_SECTION_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[label] = text[start:end]
    return sections


def _table_data_rows(section_text: str) -> list[list[str]]:
    """队列 #314①（2026-08-09 实测复现：`--row 313` 曾报"未找到"）：结尾
    被外部工具整段吞掉的行此前会被行尾检查静默排除。队列 #314（openspec
    变更包 `queue-table-backtick-aware-split`）：切列实现改为委托
    `queue_table.split_row_cells`（反引号感知，行首要求／行尾不作要求的
    既有口径随委托一并继承，不在本函数重复实现）。"""
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        cells = queue_table.split_row_cells(line)
        if cells is None:
            continue
        first = cells[0]
        if first in _TABLE_HEADER_FIRST_CELLS:
            continue
        if set(first) <= {"-", " "}:
            continue
        rows.append(cells)
    return rows


def _find_rows(text: str, row_id: str, section: str | None) -> list[tuple[str, list[str]]]:
    """按行号/批次号在指定（或全部候选）分区里查找匹配行，返回
    [(分区标签, 单元格列表), ...]——可能不止一个匹配（如 §一/§四 各自独立
    计数，同一数字可能同时是两个分区的合法编号），调用方据此决定是报告
    冲突还是直接使用唯一匹配。"""
    sections = _split_live_sections(text)
    candidates = [section] if section else list(SECTION_COLUMNS)
    hits: list[tuple[str, list[str]]] = []
    for label in candidates:
        section_text = sections.get(label, "")
        for cells in _table_data_rows(section_text):
            if cells and cells[0] == row_id:
                hits.append((label, cells))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="跨桌任务队列只读查询——默认返回状态列全文、不截断，"
                     "头尾出现互斥关键词时打印冲突警告（队列 #268）",
    )
    parser.add_argument("--row", required=True, help="行号（§一/§四）或批次号（§二），如 258 / B-0806_xxx")
    parser.add_argument("--section", choices=sorted(SECTION_COLUMNS), default=None,
                        help="限定查询分区；不给则在 §一/§二/§四 全部搜索，"
                             "多个分区命中同一编号时须显式指定以消歧")
    parser.add_argument("--field", choices=("status", "all"), default="status",
                        help="status=只打印状态列全文（默认）；all=打印整行全部列")
    parser.add_argument(
        "--file", default=DEFAULT_TARGET,
        help=f"目标文件（默认 {DEFAULT_TARGET}——队列 #315 起，这一默认值触发"
             "机制环境/业务场景两份物理文件的联合查询；显式传其它路径时只查"
             "该文件，行为与拆分前一致）",
    )
    args = parser.parse_args()

    # 队列 #315：查询系统模式下遍历两份物理文件，聚合命中结果并标注来源
    # 文件——编号空间单一（决策点2），两份文件不会有同编号的两条不同数据
    # 行，但调用方仍需要知道命中落在哪一份，便于核对/后续编辑时定位。
    query_paths = (
        [QUEUE_MECHANISM_PATH_REL, QUEUE_BUSINESS_PATH_REL]
        if _is_queue_system_target(args.file) else [args.file]
    )
    hits: list[tuple[str, str, list[str]]] = []  # (来源文件, 分区标签, 单元格)
    read_errors: list[str] = []
    for query_path in query_paths:
        target_path = (REPO_ROOT / query_path).resolve()
        try:
            text = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            if len(query_paths) == 1:
                # 显式单文件目标（非队列系统模式）读取失败——保持拆分前的
                # 既有直接报错语义，不落入下方"聚合未命中"的框架式措辞。
                print(f"✗ 读取目标文件失败：{target_path}（{exc}）")
                return 1
            read_errors.append(f"{target_path}（{exc}）")
            continue
        for label, cells in _find_rows(text, args.row, args.section):
            hits.append((query_path, label, cells))

    if not hits:
        scope = f"§{args.section}" if args.section else "§一／§二／§四"
        files_desc = "、".join(query_paths)
        print(f"✗ 未找到 {scope} 中编号/批次为「{args.row}」的行"
              f"（已查：{files_desc}）。")
        if read_errors:
            print("  以下文件读取失败，如实登记：")
            for err in read_errors:
                print(f"  - {err}")
        return 1
    if read_errors:
        for err in read_errors:
            print(f"⚠ 读取失败（不影响已命中结果，如实登记）：{err}")
    if len(hits) > 1:
        labels = "、".join(f"{p}:§{label}" for p, label, _ in hits)
        print(f"✗ 「{args.row}」在多个分区命中（{labels}）——请加 --section 消歧，不猜测取哪一个。")
        return 1

    query_path, label, cells = hits[0]
    if _is_queue_system_target(args.file):
        print(f"【命中于：{query_path}】")
    columns = SECTION_COLUMNS[label]
    if len(cells) != len(columns):
        print(f"⚠ §{label} 该行实际列数（{len(cells)}）与预期（{len(columns)}）不符，"
              "可能存在列偏移（如 #164 裸竖线），以下按实际单元格顺序展示：")

    if args.field == "all":
        for i, cell in enumerate(cells):
            col_name = columns[i] if i < len(columns) else f"列{i}"
            print(f"【{col_name}】\n{cell}\n")
        return 0

    status_index = SECTION_STATUS_INDEX[label]
    if status_index >= len(cells):
        print(f"✗ 该行列数不足以取到{SECTION_STATUS_LABEL[label]}列（索引 {status_index}）。")
        return 1
    status_text = cells[status_index]

    print(f"【§{label} #{args.row} · {SECTION_STATUS_LABEL[label]}列全文】")
    print(status_text)

    natural_text = status_text
    if label == "一":
        # 队列 #308 决策点 4：§一 优先展示机器字段解析结果——这是判据应
        # 该读取的权威值，不需要再靠头尾关键词猜测；关键词冲突检测仍对
        # 字段之后的自然语言正文生效（正文内部前后打架仍是有用信号，见
        # 编辑锁 F2 同一立场），不再对整段状态列（含字段本身）扫描。
        status_value, domain_value, natural_text = _parse_status_domain_fields(status_text)
        if status_value is None:
            print("\n⚠ 未识别到 [S:...] 机器字段（缺失/非法，回退关键词判据展示）——"
                  "见队列 #308「非静默降级」。")
        else:
            domain_desc = f"，域 {domain_value}" if domain_value else "（域字段缺失）"
            print(f"\n【机器字段解析】状态＝{status_value}{domain_desc}")

    leading = _leading_segment(natural_text)
    remainder = natural_text[len(leading):]
    head_done = any(m in leading for m in DONE_MARKERS)
    head_pending = any(m in leading for m in PENDING_MARKERS)
    tail_done = any(m in remainder for m in DONE_MARKERS)
    tail_pending = any(m in remainder for m in PENDING_MARKERS)

    if (head_done and tail_pending) or (head_pending and tail_done):
        print("\n⚠ 冲突警告：开头片段与其余文本出现互斥关键词"
              "（已完成/已拍板类 vs 待领/待你审/在办类）——"
              "只读开头或只读片段会得到相反结论，请通读全文再判断"
              "（同 2026-08-05 业务总线 6 次误判的成因，见队列 #268）。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
