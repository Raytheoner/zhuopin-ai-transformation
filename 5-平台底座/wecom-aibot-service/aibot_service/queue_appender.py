"""归档后向跨桌任务队列 §一 追加"待领"行（design.md 对应 spec 场景②）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Protocol

from zhuopin_platform.audit import AuditEvent, AuditLogger

TABLE_HEADER_MARKER = "## 一、任务看板"
_ROW_ID_RE = re.compile(r"^\|\s*(\d+)\s*\|")
_SECTION_HEADING_RE = re.compile(r"^##\s")
_HIGH_WATER_MARK_LINE_RE = re.compile(r"编号高水位线")
_HIGH_WATER_MARK_SECTION_ONE_RE = re.compile(r"§一\s*#\s*(\d+)")


class QueueEditLock(Protocol):
    """队列文件本地写入前的占锁契约（队列 #168）。

    机器人此前直接读改写队列文件，完全绕过协议〇.7 的共享编辑锁——人类
    会话之间已经靠这把锁互斥，机器人却从未检查它：人类持锁编辑（读入内存
    的窗口可长达数分钟）期间，机器人若直接写盘追加一行，会在人类稍后把
    内存里那份（不含机器人新增行）整文件写回时被静默覆盖。生产实现见
    `queue_edit_lock.SubprocessQueueEditLock`（复用协议〇.7 既有 CLI 工具，
    不重新实现锁协议本身）；单测可注入任意满足这两个方法的替身，不必真的
    起子进程/依赖 git 仓库。"""

    def try_acquire(self) -> None:
        """占用中应抛出异常（约定用 `queue_edit_lock.QueueLockBusy`，本模块
        不关心具体异常类型，原样上抛交调用方处理）；成功则悄然返回。"""
        ...

    def release(self) -> None:
        """释放锁；实现不应因释放失败而向上抛出（不应因此掩盖追加本身是否
        成功），失败时自行记录即可。"""
        ...


def _section_bounds(lines: list[str], header_idx: int) -> tuple[int, int]:
    """返回 `header_idx` 所在表格的行范围 [start, end)，以下一个 `## ` 标题
    （或文件末尾）为界——**不得**越界扫到别的表格（2026-07-13 真实生产链路
    联调发现的严重 bug：原实现无边界，把行插进了 §四 的四列表格里，还借用
    了 §四 自己的独立编号序列，两处表格都被写坏）。"""
    end = len(lines)
    for i in range(header_idx + 1, len(lines)):
        if _SECTION_HEADING_RE.match(lines[i].strip()):
            end = i
            break
    return header_idx + 1, end


def _parse_section_one_high_water_mark(lines: list[str]) -> Optional[int]:
    """解析文件顶部"编号高水位线：§一 #NNN ｜ §四 #NNN"标注行（协议〇.8），
    返回 §一 对应的高水位线数字；找不到该标注行、或行内不含 §一 编号（格式
    有变/旧版文件无此行）时返回 `None`——调用方据此回落"仅取可见最大号+1"
    的既有行为，并按需审计留痕（见 `append_pending_task` docstring）。"""
    for line in lines:
        if _HIGH_WATER_MARK_LINE_RE.search(line):
            m = _HIGH_WATER_MARK_SECTION_ONE_RE.search(line)
            return int(m.group(1)) if m else None
    return None


def _next_task_id(lines: list[str], start: int, end: int) -> int:
    """新编号 = max(§一 表格内可见最大号, 顶部编号高水位线) + 1。

    2026-07-24 首次清扫（协议〇.8）起，已完成行会被整行迁出 §一 表格搬进
    《跨桌任务队列-归档-YYYYMM.md》——若只看"表格内可见最大号"，清扫把
    历史最高编号的行迁走后，下一条新行会从一个更小的基数重新编号，与已
    归档编号撞车（队列 #99）。顶部"编号高水位线"标注行在每次清扫时同步
    更新，取两者较大值可保证跨清扫后编号仍单调递增、不撞历史号。"""
    ids = [
        int(m.group(1))
        for line in lines[start:end]
        if (m := _ROW_ID_RE.match(line.strip()))
    ]
    visible_max = max(ids) if ids else 0
    high_water_mark = _parse_section_one_high_water_mark(lines)
    baseline = max(visible_max, high_water_mark) if high_water_mark is not None else visible_max
    return baseline + 1


def _bump_section_one_high_water_mark(lines: list[str], new_value: int) -> bool:
    """原地把顶部"编号高水位线"标注行的 §一 号更新为 `new_value`（本次追加
    确定的新 task_id），与追加同一次读改写、同一把乐观并发锁内完成——不分
    两步是为了避免"取号"和"回写"之间再开一个竞态窗口。

    队列 #146：`_next_task_id` 此前只读高水位线用于取号，取完从不回写，导致
    高水位线长期停滞在陈旧值——任何"按高水位线划定扫描范围"的下游消费方
    （拆件巡逻等）都会集体漏看高水位线之后、表格里已真实存在的新行。

    标注行不存在，或存在但 §一 号解析失败（格式漂移）时，原样返回 `lines`
    不做任何改动，返回 `False`——与 `_next_task_id`/`_parse_section_one_
    high_water_mark` 一致的"解析失败即回落，不新增风险"处理方式。返回
    `True` 表示已原地修改了某一行。"""
    for i, line in enumerate(lines):
        if _HIGH_WATER_MARK_LINE_RE.search(line):
            m = _HIGH_WATER_MARK_SECTION_ONE_RE.search(line)
            if m is None:
                return False
            lines[i] = f"{line[:m.start(1)]}{new_value}{line[m.end(1):]}"
            return True
    return False


def append_pending_task(
    queue_path: Path,
    *,
    description: str,
    owner: str,
    input_pointer: str,
    expected_output: str,
    date_str: str,
    touch_zone: str = "",
    max_retries: int = 5,
    audit: Optional[AuditLogger] = None,
    lock: Optional[QueueEditLock] = None,
) -> str:
    """在 §一 任务看板表格最后一行数据行之后插入一条新"待领"行，返回该行文本。

    `audit` 可选——提供时，若顶部"编号高水位线"标注行解析失败（缺失/格式
    有变，见 `_parse_section_one_high_water_mark`），在实际写入前记一条
    `queue_high_water_mark_parse_failed` 审计事件（回落行为不变，仍按"仅取
    §一 可见最大号+1"计算，只是把这一异常状态留痕，便于日后排查而不是静默
    发生，见队列 #99）。不提供 `audit` 时（如既有测试/未接线调用方）该步骤
    整体跳过，行为与未加此参数前完全一致。

    `lock` 可选（队列 #168）——提供时，在下方整个读改写重试循环**外层**先
    `lock.try_acquire()`（占用中由 lock 自身抛出异常，本函数不捕获、原样
    上抛给调用方——调用方据此决定是否转入"推迟补录"路径），循环无论正常
    返回还是异常退出，`finally` 都会 `lock.release()`，不会因为中途出错而
    死锁。不提供时（默认，既有调用方/测试）完全不涉及锁，行为与加这个参数
    前完全一致。

    编号与插入位置均严格限定在 §一 自己的表格范围内（不越界到后续其他
    `## ` 小节，即便那些小节也用 `| 数字 | ... |` 格式且有自己独立的编号）。

    乐观并发重试（2026-07-22，队列 #69/#70 事故后补）：本函数此前是纯粹的
    read-modify-write，无任何冲突检测——2026-07-21 唐燕萍那条归档触发的追加，
    审计日志确认本函数成功执行、`queue_appended` 事件已记录，但该行从未出现
    在队列文件的任何一次 git 提交里，说明追加落盘后、下一次提交前的窗口期内，
    被另一个并发写手（人工/CC 会话对同一文件的整段改写）静默覆盖——本文件与
    人工/Cowork/CC 会话共享同一份磁盘文件，没有锁、没有版本号。真正的文件锁
    对这种低频、人工节奏的编辑场景收益/复杂度不成正比（需处理跨进程锁残留、
    Windows 文件锁语义等），改用乐观并发重试：写入前重新读一次，若磁盘内容
    与本次计算所依据的初始内容不一致（说明计算期间被别人改过），放弃这次写入、
    用最新磁盘内容重新计算（重新定位插入点+重新编号），而不是拿旧计算结果盖掉
    别人的改动。仍无法做到 100% 杜绝竞态（重读检查和最终写入之间仍有微秒级
    窗口），但把原来"整个函数调用期间"的竞态窗口收窄到"最后一次读+写之间"，
    对本场景（人工编辑节奏为秒/分钟级）已是数量级的收窄。

    队列 #168：上述乐观并发重试只保护"本函数自己这次写入"不被另一个**同样
    走本函数**的写手覆盖——它保护不了"人类会话经编辑器整文件读改写"这条完全
    不同的路径（人类的写不经过这里，不会做写前核验）。`lock` 参数补的正是
    这一层：人类持锁编辑期间，本函数会被 `try_acquire()` 挡在门外，从根本上
    不让这次追加发生，而不是让它发生了再被动指望"写前核验"侥幸发现覆盖。
    """
    if lock is not None:
        lock.try_acquire()
    try:
        for _ in range(max_retries):
            text = queue_path.read_text(encoding="utf-8")
            lines = text.splitlines()

            header_idx = next(
                (i for i, l in enumerate(lines) if l.strip() == TABLE_HEADER_MARKER), None
            )
            if header_idx is None:
                raise LookupError(f'未找到队列表格标题行 "{TABLE_HEADER_MARKER}"：{queue_path}')

            start, end = _section_bounds(lines, header_idx)

            insert_at = header_idx
            for i in range(start, end):
                if _ROW_ID_RE.match(lines[i].strip()):
                    insert_at = i

            task_id = _next_task_id(lines, start, end)
            row = (
                f"| {task_id} | {description} | {owner} | {input_pointer} | "
                f"{expected_output} | 待领 | {touch_zone} | {date_str} |"
            )
            # 与追加同一次读改写内回写高水位线（队列 #146）——标注行不存在/解析
            # 失败时 _bump_section_one_high_water_mark 原样跳过，不影响追加本身。
            _bump_section_one_high_water_mark(lines, task_id)
            lines.insert(insert_at + 1, row)

            newline = "\n" if text.endswith("\n") else ""
            new_text = "\n".join(lines) + newline

            # 写入前最后核验一次：磁盘内容若已不是我们刚才读到的那份，说明有人在
            # 我们计算的这一瞬间又写了一次，放弃本轮写入、重新读取重算，不覆盖。
            if queue_path.read_text(encoding="utf-8") != text:
                continue
            if audit is not None and _parse_section_one_high_water_mark(lines) is None:
                audit.record(AuditEvent(
                    scenario="wecom-aibot", action="queue_high_water_mark_parse_failed",
                    evaluator="system", automation_level="L1",
                    decision={"fallback": "visible_max_only", "task_id": task_id},
                    data_sources={"queue_path": str(queue_path)},
                ))
            queue_path.write_text(new_text, encoding="utf-8")
            return row

        raise RuntimeError(
            f"append_pending_task：队列文件持续被并发写入，{max_retries} 次重试后仍未能安全追加："
            f"{queue_path}"
        )
    finally:
        if lock is not None:
            lock.release()
