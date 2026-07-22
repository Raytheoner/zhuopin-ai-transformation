"""归档后向跨桌任务队列 §一 追加"待领"行（design.md 对应 spec 场景②）。"""
from __future__ import annotations

import re
from pathlib import Path

TABLE_HEADER_MARKER = "## 一、任务看板"
_ROW_ID_RE = re.compile(r"^\|\s*(\d+)\s*\|")
_SECTION_HEADING_RE = re.compile(r"^##\s")


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


def _next_task_id(lines: list[str], start: int, end: int) -> int:
    ids = [
        int(m.group(1))
        for line in lines[start:end]
        if (m := _ROW_ID_RE.match(line.strip()))
    ]
    return (max(ids) + 1) if ids else 1


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
) -> str:
    """在 §一 任务看板表格最后一行数据行之后插入一条新"待领"行，返回该行文本。

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
    """
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
        lines.insert(insert_at + 1, row)

        newline = "\n" if text.endswith("\n") else ""
        new_text = "\n".join(lines) + newline

        # 写入前最后核验一次：磁盘内容若已不是我们刚才读到的那份，说明有人在
        # 我们计算的这一瞬间又写了一次，放弃本轮写入、重新读取重算，不覆盖。
        if queue_path.read_text(encoding="utf-8") != text:
            continue
        queue_path.write_text(new_text, encoding="utf-8")
        return row

    raise RuntimeError(
        f"append_pending_task：队列文件持续被并发写入，{max_retries} 次重试后仍未能安全追加："
        f"{queue_path}"
    )
