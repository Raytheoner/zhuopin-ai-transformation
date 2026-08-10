"""共享文档编辑锁（协议〇.7，Paul 2026-07-23 定）。

背景：跨桌任务队列.md 是 Cowork（总线/域专线）× CC 两桌共享的唯一协调文件，
但两桌各自的"开工读→改→收工写"是本地文件读写，不经 git、没有互斥——
2026-07-23 QD-B 极简版发布收口当天，先后撞了两次：财务专线（FI2）与 QD-B
各自不知情地把 #79 用掉；随后采购专线一次会话在编辑期间被另一处 `git stash`
重置了工作区文件，它没感知到、继续用内存里的旧内容写回，导致自己刚追加的
"已完成"实质内容被当占位符覆盖——两次都靠 CC 收工时手工读 git 历史逐行
比对、按"真实最大号之后续排"重新编号才救回内容，未丢失但过程繁琐易错。

本工具把"编辑前占一个位、编辑完立刻让位"这件事固化下来，效果上等价于
"发现对方在场就等一等"，不需要人工介入修复：

  acquire  编辑跨桌任务队列.md 前先占锁；被占用（且新鲜）则拒绝——本次改为把
           要登记的内容写进自己的域接力文件，注明"队列更新待补"，不要硬写。
           成功占锁时会回显**持锁瞬间**从目标文件读到的"编号高水位线"行（若
           目标文件含该行）——新行编号务必从这个回显值 +1 续排，不要用
           acquire 之前读到的旧值（#121(c)：编号在 acquire 之前算，锁只保护
           "写"这一小段，用旧值续排仍会撞号；协议〇.7 同步补一句"编号一律在
           持锁后重算"）。

           **`--reserve N --section 一|四`（队列 #163）**：与其显示高水位线
           让人自己 +1 续排（人读对了值也可能算错/抄错——2026-07-29 #162 就是
           回显明明白白打在眼前、业务总线仍看漏），不如工具直接**分配并返回
           字面编号**，调用方拿返回值填空，不再自己"读了再算"。同一次持锁
           窗口内原子完成"读高水位线→分配→回写高水位线"，比先 acquire 再
           单独读值续排更彻底地关闭撞号——见模块内 `_reserve_ids` 文档。
  release  编辑完立刻释放（持锁窗口应短——只包住"读入→改→写出"这一小段，
           不要跨整个 session 持有）。带 --who 且与当前持有者不符时拒绝释放
           （只告警不改，防误传 --who 顶掉别人的在办锁）；不带 --who 则无条件释放。
           **释放方式是改写为"released"标记，不是删除文件**（#121(a)：Cowork
           沙箱挂载对 `.editlock` 文件 unlink 会返回 PermissionError，acquire
           能建文件但 release 删不掉；改写标记规避了这个问题，本地/CC 环境同样
           适用，不需要区分环境分支）——released 标记等价于"无锁"，下一次
           acquire 会当作空锁立即成功，不会误判为陈旧锁走接管提示
  status   查看当前锁状态，不产生副作用

队列 #230-1c（2026-08-04）：`acquire` 成功时会顺带回显"最近 120 分钟内
还有哪些其它身份 acquire 过本锁"——并发 session 互不可见是本项目反复出现
的实证风险（如 #221 错定 P1、批次被并发线未声明脏文件阻塞），本回显不
解决"两线各自推理数小时"的问题，只让"对方最近也在场"这件事在场者可见，
纯回显、零新增状态文件（复用 `.editlock` 自身的 `history` 字段）。

队列 #225（2026-08-04）：锁定目标是默认队列文件（跨桌任务队列.md）时，
`release` 前会对**本次持锁期间新增/修改**的行做结构校验（不通过则
拒绝释放，锁保持占用，逼原地修正）：①§一 行须 8 列、§二/§四 行须 4 列
（含反引号内裸竖线致列偏移）；②新增 §二 批次须在"文件清单"里声明队列
文件自身路径；③新增 §一/§四 行编号不得与现役/归档件重复，且须属于本次
`--reserve` 预留的编号集合；④**状态列**同时含 P0/P1 定级与"未核／未做的
核实"字样即拒绝（标注未核不等于可据此下结论，见 #221 教训；只检查状态
列本身——本项目约定优先级标注写在状态列，任务描述列提到这两个词多半是
在叙述/讨论相关内容，不是该行当前的权威结论，按整行扫描会误拦）；
⑤（队列 #247②，2026-08-06）**§二状态列**开头片段既不含"待"也不含"✅"
即拒绝——这类写法会被 sweep 判为"状态列模糊"、每轮跳过并重复告警（#247①
实测最长 49 轮），在写入那一刻挡住比事后修法更彻底；显式放行 #236(1)
"在办（预登记……）"约定文本，不误伤这一合法新状态。
历史行不追溯，见
`_validate_release_structure`。

队列 #200（2026-08-04）：`acquire` 成功授予（新锁或接管陈旧锁）时，会把
目标文件此刻内容与"上次 release 时记录的内容"比对——不同即说明文件在
两次合法 release/acquire 之间被直接改写过（未经本工具），大概率是绕过
协议〇.7 锁保护的直接写入。检测到即打印警告（不阻断 acquire，锁仍照常
授予——协议〇.7 一贯是协作性质而非硬互斥，见下），锁定默认队列文件时还
落一条持久审计记录到 `reports/queue_edit_lock_bypass.jsonl`（终端输出转瞬
即逝，调用方未必是人在盯屏幕）。机制通用（任意 `--file` 均生效，复用
`.editlock.lastknown` 这一每目标文件独立的小状态文件），只有落盘审计
记录这一步限定默认队列文件（避免任意 `--file` 都写 `REPO_ROOT/reports/`
在测试等场景污染真实项目目录）。

队列 #185（2026-08-04）：`--reserve N --section 一|四` 原本一次只能预留一个
分区的号，而"同时要 §一/§四 两套号"是最高频的消费场景之一（值周巡检等
每次都得手工分两次取、或自行 +1 续排另一套，2026-08-03/08-04 连续多次
真实撞见）——新增 `--reserve-multi 一:2 四:1` 形式一次性跨多分区预留，
与 `--reserve`/`--section` 互斥（选一种方式）。**竞态防护（同日实测）**：
若高水位线本身已滞后于文件实际内容（如 #200 描述的绕锁直写场景，写入了
新行但没同步推高水位线），单纯"高水位线+1"会算出一个其实已被占用的号
——`_reserve_ids` 现在写回高水位线之前，额外核对即将分配的号是否已出现
在当前文件同分区的可见行里，命中即 fail-loud（不静默跳过冲突号、不改用
"扫描可见最大值"这类会撞已归档编号的替代路径），逼调用方先核实文件真实
状态再重试。

锁本地存在于文件系统（gitignore，不入库、不需要 git commit 才生效）。
REPO_ROOT 按 `git rev-parse --git-common-dir` 定位——所有 git worktree
共享同一个 `.git`，故不论从主工作区还是任一 `.claude/worktrees/<name>/`
里跑本脚本，锁都落在同一个物理文件上，彼此可见（2026-07-23 曾用
`Path(__file__).resolve()` 推算，会按各 worktree 自己的 checkout 路径
各算各的锁、互相看不见，已修复，见交接说明）。

④断言门槛引号剔除（队列 #248，openspec 变更包
`sweep-editlock-status-keyword-anchoring`，2026-08-05）：2026-08-03 落地
的④断言门槛（见上，成因 #221）已把扫描范围从整行收窄到状态列本身，但
仍是状态列内的整体子串扫描——真实取证：队列 §一 #221 行状态列当前就带着
未加引号保护的 P1 定级 token，与被「」引号包裹的"未做的核实"字样（该行
讲述的是它自己被"未做的核实如实登记"这条纪律救回的正面案例，是在
**引用/复述**这条规则，不是在**断言**当前判断未核实）——若该行被再次
编辑触发本校验，会被误拦。改为扫描前先剔除被「」/『』（现存生产队列
文件里出现 339/339、9/9 次，完全均衡，是稳定且专用于引用语境的书写
惯例）完整包裹的片段，只对剩余文本做原有的 P0/P1+未核实共现检测——
真正未加引号保护、共现于状态列的断言仍被正确拦截，见 `_strip_quoted_
spans` 与 `test_quoted_unverified_phrase_alongside_unquoted_p1_does_
not_block`/`test_unquoted_unverified_phrase_outside_quotes_still_
blocks` 两个反向配对用例。同批同源修法见 sweep 侧
`_leading_status_segment`（两处判据历史上都经历过"整行扫描→只查状态列"
这一次收窄，本次是该收窄路径的下一步；两处具体实现不同，design.md
完整论证了原因）。

队列 #258（2026-08-07，接管 #294 修法⑵，openspec 变更包
editlock-section-append-and-followup-consistency-guard）：两项加固。

  append-row  新增子命令——把"追加行到指定分区"这一动作的插入位置、列数、
              竖线合法性交给工具结构化保证，替代此前"用全文最后一个
              # 数字 形态的行定位分区末尾"这一启发式（#248/#254 同一根因
              两次插错分区）。调用方按分区列序传结构化 `--cell` 字段（不
              含首列编号，另用 `--number` 单独传），工具拼装+定位+校验，
              不接受预拼好的整行字符串。字段值含任何竖线 `|`（不论是否
              反引号包裹）一律拒绝写入——本项目现有表格解析对反引号无
              感知，`_validate_release_structure` ①列数校验本就把"反引号
              内裸竖线"列为要抓的失效形态，本子命令口径与其一致，不引入
              一个 release 校验不认可的豁免（apply 阶段发现并修正，见该
              openspec 变更包 design.md）。

  release ⑥  队列 §一/§四 行"暂缓结论"与跟进信 README 发送状态的交叉
              一致性校验——命中"状态列/事项列含暂不发/暂缓/压着/不发字样
              + 反引号 .md 文件名引用"的行，若该信在 README 中仍是终态
              `🆕 待发`（机制唯一认可的可发送标记），拒绝 release；反向
              （README 已是"已推送"类终态而队列仍称暂缓，多半是事后如实
              追述）仅告警不阻断。治 2026-08-06 01:30 UTC 真实误发（#150：
              队列行决定"暂不发"但未同步移出 README 的可发送标记，
              `ZhuopinFollowupDispatchDaily` 照发，信不可撤回）。

队列 #285（因果断言证伪命令，openspec 变更包
editlock-causal-assertion-falsifiability-gate）：④断言门槛新增一项独立
检测——§一 状态列（剔除引号包裹片段后）一旦出现 P0/P1 定级 token，须在
同一单元格内找到至少一处反引号包裹的非空片段（"如果这个断言错了，哪
一条命令会证明它错"），缺失即拒绝 release。沿用既有的"只查状态列"边界
与 #248 引号剔除逻辑，不新增扫描面。**边界声明（须原样保留，不得表述
为质量保证）**：本项检测只判"有没有"证伪命令片段，判不了"对不对"（片段
内容是否真的具备证伪能力）——覆盖"根本没想过怎么证伪"这一形态（2/3），
防不住"想过但用了错的证据"这一形态（1/3，见 #221）。人守条目原文（曾称
"防线4"）已降为指针，见 `专线opander模板库.md`。

队列 #306＋#307（转义与列数校验收归权威模块，openspec 变更包
queue-table-shared-parser-consolidation）：`SECTION_COLUMN_COUNTS` 常量
与 `_cell_has_bare_pipe` 的检测逻辑改为从
`zhuopin_platform.shared_tools.queue_table` 导入/委托，不再本地独立定义
——该模块是队列表格"转义"与"列数校验"两件事的唯一权威实现，供本文件
及其余五处消费者共用（详见该 openspec 变更包 proposal.md 的取证与范围）。

用法：
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "CC-QD-B" --note "登记#87完成"
  python 0-学习与工具/工具-共享文档编辑锁.py release
  python 0-学习与工具/工具-共享文档编辑锁.py status

  # 队列 #258：追加一行到 §一（编号通常来自上面 --reserve 的返回值）
  python 0-学习与工具/工具-共享文档编辑锁.py append-row --section 一 --number 299 \
    --cell "任务描述" --cell "CC" --cell "输入指针" --cell "期望产出" \
    --cell "待领" --cell "触碰区" --cell "2026-08-07"

  # 默认锁跨桌任务队列.md；--file 可指向其他高频撞车的共享文件复用本机制
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --file 1-转型规划/其他共享文件.md --who "..."

  # 队列 #163：预留取号，直接拿字面编号，不再自己读高水位线 +1
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "Cowork-采购专线" --note "v2.4 回灌" --reserve 2 --section 一

  # 队列 #185：一次性跨 §一/§四 两个分区预留（与 --reserve/--section 互斥）
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "值周巡检" --note "本周计划" --reserve-multi 一:2 四:1

陈旧锁判定：超过 STALE_MINUTES（默认 30 分钟）未释放的锁视为会话异常退出的
遗留物，下一个 acquire 会打印警告后接管，不会死锁。

#197（2026-08-01 环境保障线只读审计取证，2026-08-02 CC 修复）：acquire 原
实现是"读判定→写"两步、中间无任何互斥——两个进程若在同一窗口内调用，会
双双读到"无锁"、双双写入成功、双方都相信自己持锁，正是协议〇.7 要防的
静默覆盖，只不过这次发生在锁自己身上。单纯把"创建"那一步换成 O_EXCL 治
不了根：release 按 #121(a) 改写为 released 标记而不删除文件，锁文件此后
永久存在，O_EXCL 对着一个永久存在的文件只会永远 FileExistsError。真正
需要原子化的是"读判定→写"整段临界区。修法：用一个与 `.editlock` 完全
独立、生命周期仅限单次 acquire 调用（创建→用完即删）的互斥标记文件
（`.editlock.mutex`）包住这段临界区——它不需要像 `.editlock` 那样永久
保留可查询，因此可以放心复用 `O_CREAT|O_EXCL`"不存在才创建"的原子语义，
不受 #121(a)"永久文件不能删"的限制约束（见 `_acquire_mutex`）；写入本身
改用临时文件 + `os.replace` 原子换入（避免 `write_text` 直接截断写入被
并发读到半截内容），并在写完后立即回读校验（不信"写成功了"）。

#322（2026-08-10 拆件巡逻实测坐实，openspec 变更包
`editlock-mutex-stale-cleanup-resilience`）：`_acquire_mutex` 判定 mutex
陈旧后原实现是"尝试 unlink → 无论成败都 continue"——Cowork 沙箱对挂载
目录没有删除权限（`unlink` 恒 `PermissionError`，但 `rename` 可用），于
是这个 continue 永远命中、永远跳过紧随其后的 deadline 判断，
`MUTEX_WAIT_TIMEOUT_SECONDS` 形同虚设：不是超时报错，是无限循环、零输
出的死锁；release 的 `finally` 块是同一模式，只是后果是"遗留"而非"死
循环"。修法（Shao Peishen 2026-08-10 拍板选 design.md 决策点 1 候选
A）：新增 `_discard_mutex_path` 助手，`unlink` 优先，失败则退路为
`os.replace` 原子改名到固定的 `.stale` 伴生路径（同一目标复用同一文件
名，不随每次清理事件新增文件）；stale 清理分支与 release 均改用此助
手，仅路径确认清空才重试/视为已释放，两条退路都失败时不再无条件
continue，落回既有 deadline 判断——fail-loud，不得静默死循环。互斥保证
本身仍完全来自 `O_CREAT|O_EXCL`，改名只是清空路径这一个动作，不改变谁
能在 canonical 路径抢到创建权，故不引入双持有风险（论证见
`_discard_mutex_path` 文档字符串与 design.md）。
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# 队列 #306：本脚本自身所在的 worktree 本地路径找 zhuopin_platform（而非
# 经 REPO_ROOT——那按 git-common-dir 解析总是指向主工作区，见本文件顶部
# REPO_ROOT 文档），与队列 #300 conftest.py 的 worktree 隔离引导同一原则：
# import 结果与全局 editable 安装当前指向谁无关。
#
# 仅当本脚本所在目录旁真实存在 5-平台底座/zhuopin_platform 时才尝试 import
# ——若目录确实缺失（如测试把本脚本单独复制到不含平台包的隔离临时目录，
# 见 test_工具-共享文档编辑锁.py::EditLockCrossWorktreeTests），改用与
# queue_table 模块完全一致的本地取值兜底，不因隔离环境改变行为；若目录
# 存在但 import 本身失败（如包损坏），则如实抛出，不静默吞掉真实错误。
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

        @staticmethod
        def has_bare_pipe(cell: str) -> bool:
            return "|" in cell

        # 简化近似，非逐字节镜像——权威实现按 CommonMark 反引号游程规则
        # 配对（见 queue_table.py::_mask_backtick_spans，队列 #314 apply
        # 阶段真实数据踩坑后从单反引号正则升级而来）；本桩只保证隔离测试
        # 环境（无 5-平台底座/zhuopin_platform 目录，见 `EditLockCross
        # WorktreeTests`）不崩、能正确处理最常见的单反引号跨度，不追求
        # 对双反引号转义单反引号这类少见写法字节级一致——隔离测试从不
        # 喂这类内容，为一个仅覆盖降级路径的桩复刻完整算法是过度实现。
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
    """定位主工作区根目录（所有 git worktree 共享同一把锁的关键）。

    `git rev-parse --git-common-dir` 不论在主工作区还是任一 linked
    worktree 里跑，都会解到同一个共享 `.git` 目录，其父目录即为主工作区
    根——由此不同 worktree 里的本脚本都算出同一个锁文件路径。跑不了 git
    （非仓库/未装 git）时退回按脚本自身路径推算，保底不崩。
    """
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
STALE_MINUTES = 30
HIGH_WATER_MARK_PATTERN = re.compile(r"编号高水位线[：:]\s*(.+?)\*\*")
HIGH_WATER_MARK_LINE_PATTERN = re.compile(r"编号高水位线")
# 队列 #163：分区号——每个分区在高水位线行里各自的 "§X #NNN" 片段，独立计数
# （§一/§四 互不干扰，见分析件 §一 设计要点②）。新增分区时在此登记正则即可。
SECTION_NUMBER_PATTERNS = {
    "一": re.compile(r"(§一\s*#\s*)(\d+)"),
    "四": re.compile(r"(§四\s*#\s*)(\d+)"),
}

# #197：互斥标记的陈旧判定用秒级——它只需要包住"读判定→写"这一小段临界区
# （正常毫秒级完成），不是 STALE_MINUTES 那种"人可能真忘了 release"的场景。
MUTEX_STALE_SECONDS = 10
MUTEX_POLL_SECONDS = 0.02
MUTEX_WAIT_TIMEOUT_SECONDS = 5.0

# 队列 #230-1c：acquire 成功时回显"最近 N 分钟内还有哪些身份 acquire 过"。
# 历史记录本身保留更久（RETENTION），只是展示窗口固定 120 分钟——保留窗口
# 留出余量，避免恰好卡在展示窗口边界的条目因保留期过短而提前被裁掉。
RECENT_ACQUIRE_WINDOW_MINUTES = 120
HISTORY_RETENTION_MINUTES = 24 * 60

# 队列 #124 阶段二（design.md D1）：跟进信 README 的两态语义结构性拦截——
# release 时锁定目标是这个文件才跑（判定逻辑与 §一/§二/§三/§四 那套无关，
# 是完全独立的一张单表，见 `_validate_followup_readme_release`）。
FOLLOWUP_README_TARGET = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
FOLLOWUP_DRAFT_STATUS = "⏳ 待你审"
FOLLOWUP_FINALIZED_STATUS = "🆕 待发"

# 队列 #258（接管 #294 修法⑵，openspec 变更包
# editlock-section-append-and-followup-consistency-guard）：release 时对
# 队列 §一/§四 行的"暂缓结论"与 README 跟进信状态做交叉一致性校验——独立
# 实现 README 目标文件标注提取正则（不 import aibot_service 包，同
# `_followup_readme_rows` 既有惯例），口径与
# aibot_service/readme_table.py::_TARGET_FILE_RE 保持一致。
FOLLOWUP_TARGET_FILE_RE = re.compile(r"目标文件[^`]*`([^`]+\.md)`")
# 派单件原文给出的四词（队列 #294 建议⑵原文），design.md 决策点5：不扩大
# 范围（"不发"是"暂不发"的子串，保留全部四词只为与派单件原文一一对应，
# 不影响判定结果）。
HOLD_LANGUAGE_PHRASES = ("暂不发", "暂缓", "压着", "不发")
# 判定 README 行是否处于非终态（⏳待你审／🆕待发／#294 新增的 ⏸暂缓 均视为
# 非终态，其余取值视为"已推送"类终态）——用于反向告警判据（design.md 决策
# 点4）。#294 落地后已核对：本判据"非🆕待发即放行"的正向口径前瞻性覆盖了
# ⏸暂缓，无需改动，仅此处补列举供反向判据引用。
FOLLOWUP_NON_TERMINAL_STATUSES = (FOLLOWUP_DRAFT_STATUS, FOLLOWUP_FINALIZED_STATUS, "⏸ 暂缓")

# 队列 #225：release 时对跨桌任务队列.md 做结构校验，仅当锁定目标是这个
# 默认队列文件时才跑（§一/§二/§三/§四 的语义只对它成立，--file 指向其他
# 共享文件时这套校验没有意义）。
ARCHIVE_GLOB = "跨桌任务队列-归档-*.md"
# 队列 #306：改为委托 zhuopin_platform.shared_tools.queue_table 的权威
# 常量，不再本地独立定义（原值 {"一": 8, "二": 4, "四": 4} 与其一致）。
SECTION_COLUMN_COUNTS = queue_table.SECTION_COLUMN_COUNTS
ROW_NUMBER_SECTIONS = ("一", "四")
# ④ 断言门槛（咽喉4甲案，2026-08-03 拍板，成因见 #221）：P0/P1 定级行内
# 若含"未核／未做的核实"字样即拒绝 release——标注未核不等于可据此下结论。
UNVERIFIED_ROW_PHRASES = ("未核", "未做的核实")
P0_P1_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])P[01](?![A-Za-z0-9])")
# 队列 #248（2026-08-05）：④断言门槛扫描前先剔除中文引号包裹的片段——现存
# 生产队列文件里「」出现 339/339 次、『』出现 9/9 次，完全均衡，是稳定且
# 专用于"引用/复述一段话"的书写惯例（区别于英文直引号 `"` 在本项目里 1000
# 次高频出现但大量用于路径/代码片段等无关语境、且不成对，纳入会有误伤真实
# 断言文本的风险，故不在剔除范围内）。真实取证：队列 §一 #221 行状态列
# 当前就带着未加引号保护的 P1 定级 token，与被「」包裹的"未做的核实"字样
# （该行讲述的是它自己被"未核实如实登记"这条纪律救回的正面案例，是在引用
# /复述这条规则，不是在断言当前判断未核实）——若该行被再次编辑触发本校验，
# 剔除引号片段前会被误拦；剔除后不再命中，与人工判断一致（详见 openspec
# 变更包 `sweep-editlock-status-keyword-anchoring` design.md「历史兼容核对」）。
QUOTED_SPAN_RE = re.compile(r"「[^」]*」|『[^』]*』")


def _strip_quoted_spans(text: str) -> str:
    """剔除文本中被「」/『』完整包裹的片段，仅用于④断言门槛的扫描预处理。"""
    return QUOTED_SPAN_RE.sub("", text)


# 队列 #247②：§二 批次状态列若既不含"待"也不含"✅"，会被 sweep 判为"状态列
# 模糊"、每轮跳过并重复告警（#247①实测最长 49 轮）。比起"发生后修法"，在
# 写入那一刻（release）就挡住这种中间态写法更彻底——见 #247「更佳」选项。
# 判据复刻 sweep `_leading_status_segment`/`_classify_section_two_rows` 的
# 锚定口径（开头片段＝去除前导强调符/空白后、第一个句级分隔符之前的文本），
# 两处各自独立实现（同 P0/P1 判据一样刻意不跨文件 import，避免多 worktree
# 共享 editable install 的静默劫持风险；若锚定口径未来变化，两处需同步改，
# 见 sweep 侧同名常量的注释）。
STATUS_LEADING_STRIP_CHARS = "* \t　"
STATUS_LEADING_SEGMENT_SEPARATORS = ("。", "——", "━━━")
# 队列 #236(1)：认领即预登记批次——协议〇.1 新增"认领时先登记预登记批次
# 行"，状态列固定文案以此为前缀（design.md 已给出的约定文本）。这类行既不
# 含"✅"也不含"待"，是有意为之（sweep 不应把预登记批次误当"待处理"去
# add+commit），本校验须放行，不能把这个合法新状态当模糊态拦下。
PREREGISTERED_STATUS_PREFIX = "在办（预登记"


def _leading_status_segment(status_cell: str) -> str:
    """§二 状态列"开头片段"——与 sweep `_leading_status_segment()` 同一口径
    （独立实现，理由见上）。"""
    stripped = status_cell.lstrip(STATUS_LEADING_STRIP_CHARS)
    cut = len(stripped)
    for sep in STATUS_LEADING_SEGMENT_SEPARATORS:
        idx = stripped.find(sep)
        if idx != -1:
            cut = min(cut, idx)
    return stripped[:cut]


def _section_two_status_is_ambiguous(status_cell: str) -> bool:
    """判定§二状态列是否会落进 sweep 的"模糊状态"桶（不含"✅"也不含"待"），
    但放行 #236(1) 的预登记约定文本——那是有意为之的第三态，不是需要拦截
    的中间态误写。"""
    leading = _leading_status_segment(status_cell)
    if leading.startswith(PREREGISTERED_STATUS_PREFIX):
        return False
    return "待" not in leading and "✅" not in leading


# 队列 #308（2026-08-09，openspec 变更包 queue-status-machine-field）：§一
# 状态列开头机器可读字段，消灭"用正则猜中文"这一整族判据（design.md
# Context 完整列出源头与四个衍生 bug 家族）。语法固定为
# `[S:<value>][D:<value>]`——状态字段在前、域字段可选紧随其后，字段之后的
# 自然语言正文完全自由、不受本字段语法约束，且回填/新增该字段 MUST NOT
# 改写正文一字（design.md 决策点 1 范围红线）。字段仅适用于 §一，§二/§四
# 状态语义不变（design.md Non-Goals）。
STATUS_FIELD_VALUES = ("done", "open", "partial", "hold", "blocked")
STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)
# 协议〇.9 措施 C（队列 #308 决策点 6）：机制类可动 WIP 上限，可通过
# release 的 --mechanism-wip-cap 覆盖（避免上限值本身未来调整时要改代码）。
# 8 → 16（Shao Peishen 2026-08-09 拍板 (b)，队列 #313 顺带项）：旧值 8 系
# 2026-08-08 人工数出且只数了"待领"一档的低估基准；#308 机器字段落地后
# 实测机制类可动 WIP（open+partial+hold 且不以 🛑 起首）为 16，按新口径
# 冻结一周观察，协议正文与值周巡检 prompt 两处已同批改完，本处补最后一处。
MECHANISM_WIP_CAP_DEFAULT = 16
# 子项 G（队列 #308 决策点 10）：跟进信串行原则闸——"前一封"发送状态以此
# 前缀开头即视为已闭环；新增行任一单元格含此逃生阀标记即放行但留痕。
FOLLOWUP_SERIAL_CLOSED_PREFIX = "📥 已回件并回灌"
FOLLOWUP_SERIAL_WAIVER_MARKER = "串行豁免："


def _parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    """解析 §一 状态列开头的 `[S:...][D:...]` 机器字段（队列 #308 决策点
    1/2）。返回 (状态取值或 None, 域取值或 None, 字段之后的自然语言正文)。

    字段缺失或不匹配语法时返回 (None, None, 原始整段文本)——消费方须据此
    走"非静默降级"路径（design.md 决策点 1：不得静默套用字段缺失前的旧
    关键词判据结果而不留痕迹，须显式记录降级日志），本函数本身只负责
    解析、不代消费方决定降级行为。
    """
    stripped = status_cell.lstrip(STATUS_LEADING_STRIP_CHARS)
    m = STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    status_value = m.group(1)
    domain_value = m.group(2)
    rest = stripped[m.end():]
    return status_value, domain_value, rest


def _count_mechanism_wip(section_one_text: str) -> tuple[int, list[str]]:
    """协议〇.9 措施 C：机制类可动 WIP 计数（队列 #308 决策点 6）。统计
    满足以下全部条件的 §一 行：域字段为「机」；状态字段取值属于
    open/partial/hold 三者之一；自然语言正文不以 🛑 开头。`blocked`/
    `timed=`/`done` 结构性排除，无需再判断自然语言正文（对齐
    `queue-row-domain-field` 能力定义的口径）。

    返回 (计数, 降级日志列表)——状态字段缺失/非法的行不计入计数，且不静默
    跳过：每一行都产出一条降级日志交调用方按需打印（design.md 决策点 1
    "非静默降级"）。
    """
    count = 0
    degraded: list[str] = []
    for line, cells in _table_data_rows(section_one_text):
        if len(cells) <= 5:
            continue
        row_id = cells[0] if cells and cells[0] else "?"
        status_value, domain_value, rest = _parse_status_domain_fields(cells[5])
        if status_value is None:
            degraded.append(f"§一 #{row_id} 状态字段缺失/非法，已跳过 WIP 计数（非静默降级）")
            continue
        if domain_value != "机":
            continue
        if status_value == "done" or status_value == "blocked" or status_value.startswith("timed="):
            continue
        natural_text = rest.lstrip(STATUS_LEADING_STRIP_CHARS)
        if natural_text.startswith("🛑"):
            continue
        count += 1
    return count, degraded


LIVE_SECTION_HEADING_RE = re.compile(r"^## ([一二三四])、", re.MULTILINE)
# §一/§四 表头首列 "#"、§二 表头首列 "批次"；分隔行首列全为 "-"/空白。
_TABLE_HEADER_FIRST_CELLS = ("#", "批次", "")

# 队列 #200：绕过锁直接改写的持久审计记录（仅锁定默认队列文件时落盘，
# 见模块文档）。
BYPASS_LOG_REL = "reports/queue_edit_lock_bypass.jsonl"


def _mutex_path(lock_path: Path) -> Path:
    return lock_path.with_name(lock_path.name + ".mutex")


def _discard_mutex_path(mutex_path: Path) -> bool:
    """让 `mutex_path` 这个 canonical 路径不再存在，供调用方据此判断能否
    立即重试 `O_CREAT|O_EXCL`（队列 #322，openspec 变更包
    `editlock-mutex-stale-cleanup-resilience` 决策点 1，Shao Peishen
    2026-08-10 拍板选候选 A）。

    优先 `unlink()`；失败（如 Cowork 沙箱挂载目录无删除权限，实测连自建
    临时文件都 `PermissionError`，但 `rename` 可用）则退路为 `os.replace`
    原子改名到同一目标固定复用的 `.stale` 伴生路径——固定文件名，不随每
    次调用生成新文件，避免无界堆积。两条路都失败返回 `False`，调用方
    MUST NOT 据此假定路径已清空、也 MUST NOT 无条件重试，交回既有的
    deadline 判断处理（不得再现 #322 的死循环：旧实现在这里无论成败都
    `continue`，跳过了紧随其后的超时检查）。

    正确性论证（为何改名不会破坏互斥语义）：真正的互斥保证来自
    `O_CREAT|O_EXCL` 在 canonical 路径上的原子创建，本函数只负责"清空
    路径"这一个动作，不改变谁能在 canonical 路径成功创建的判定规则。
    并发场景下若两个等待者同时调用本函数，至多一个能真正搬空源文件，
    另一个会因源文件已不存在而收到 `OSError`（`FileNotFoundError` 是其
    子类），返回 `False`——它不会因此误判自己已清空路径，下一轮循环会
    看到一枚年龄很小的新鲜 mutex，老实排队，不会导致双持有。
    """
    try:
        mutex_path.unlink()
        return True
    except OSError:
        pass
    try:
        os.replace(str(mutex_path), str(mutex_path) + ".stale")
        return True
    except OSError:
        return False


@contextlib.contextmanager
def _acquire_mutex(lock_path: Path):
    """包住 acquire 内部"读判定→写"临界区，确保同一时刻只有一个进程执行
    这段逻辑（#197）。与 `.editlock` 本身完全独立——本文件创建于进入临界
    区之时、清空于离开之时，不像 `.editlock` 需要"released 标记永久可
    查询"，因此可以放心用 `O_CREAT|O_EXCL` 的原子创建语义。

    队列 #322（2026-08-10）：陈旧 mutex 清理与 release 释放均统一改用
    `_discard_mutex_path`——无删除权限环境下退路为改名而非放弃，清理
    失败时不得跳过下方的 deadline 判断（否则复现 #322 的无限循环、零
    输出的死锁）。
    """
    mutex_path = _mutex_path(lock_path)
    deadline = time.monotonic() + MUTEX_WAIT_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(str(mutex_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            age = None
            try:
                age = time.time() - mutex_path.stat().st_mtime
            except OSError:
                pass  # 竞态：文件在 stat 前被对方删了，直接重试即可
            if age is not None and age > MUTEX_STALE_SECONDS:
                # 正常临界区仅毫秒级，超此判定为异常退出遗留，强制清理重试。
                # 仅当路径确认已清空才重试；清理失败不得无条件 continue
                # （#322：那会跳过下面的 deadline 判断，变成无限循环）。
                if _discard_mutex_path(mutex_path):
                    continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"等待锁内部互斥超时（{MUTEX_WAIT_TIMEOUT_SECONDS}s）：{mutex_path}"
                )
            time.sleep(MUTEX_POLL_SECONDS)
    try:
        yield
    finally:
        # Cowork 沙箱下 unlink 恒失败时，退路改名能让 canonical 路径立即
        # 清空——下一次 acquire 直接命中快路径，不必等满 MUTEX_STALE_SECONDS
        # 才触发上面的陈旧清理分支（#322）。
        _discard_mutex_path(mutex_path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """写临时文件后 `os.replace` 原子换入（POSIX/Windows 均保证原子），
    避免 `write_text` 直接截断写入可能被并发读到半截内容的风险。"""
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp_path, path)


def _target_path(target: str) -> Path:
    return (REPO_ROOT / target).resolve()


def _lock_path(target: str) -> Path:
    target_path = _target_path(target)
    return target_path.with_name(target_path.name + ".editlock")


def _read_high_water_mark(target: str) -> str | None:
    """持锁瞬间读一次目标文件里的"编号高水位线"行，供 acquire 回显（#121(c)）。

    只读、不解析语义，找不到该行（目标非队列类文件/格式变了/文件不存在）时
    静默返回 None——回显是"锦上添花"的提示，不是锁语义的一部分，不应因此让
    acquire 失败。
    """
    try:
        text = _target_path(target).read_text(encoding="utf-8")
    except OSError:
        return None
    match = HIGH_WATER_MARK_PATTERN.search(text)
    return match.group(1).strip() if match else None


def _read_target_text(target: str) -> str:
    """读取目标文件此刻内容；不存在（如 `--file` 指向尚未创建的新共享
    文件）时返回空串，不视为错误——多处（快照/lastknown 比对）共用同一个
    读取口径。"""
    try:
        return _target_path(target).read_text(encoding="utf-8")
    except OSError:
        return ""


def _snapshot_path(target: str) -> Path:
    lock_path = _lock_path(target)
    return lock_path.with_name(lock_path.name + ".snapshot")


def _write_snapshot(target: str, content: str) -> None:
    """acquire 成功时把目标文件此刻内容存一份快照（队列 #225）——release 时
    据此 diff 出"本次持锁期间新增/修改"的行，结构校验只对这些行生效，不
    对历史行秋后算账。"""
    _snapshot_path(target).write_text(content, encoding="utf-8")


def _read_snapshot(target: str) -> str:
    try:
        return _snapshot_path(target).read_text(encoding="utf-8")
    except OSError:
        return ""


def _lastknown_path(target: str) -> Path:
    lock_path = _lock_path(target)
    return lock_path.with_name(lock_path.name + ".lastknown")


def _read_lastknown(target: str) -> str | None:
    """读取"上次成功 release 时的目标文件内容"——队列 #200 绕锁检测的比对
    基准。文件不存在（从未有过一次经本工具完成的 release，如首次使用）
    时返回 `None`，与"内容为空字符串"区分开，避免把"从未记录过"误判为
    "内容被清空"。"""
    path = _lastknown_path(target)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_lastknown(target: str, content: str) -> None:
    """release 成功时把"正式交还"的目标文件内容存一份（队列 #200）——下一次
    acquire 据此判断这期间文件是否被绕过锁直接改写过。"""
    _lastknown_path(target).write_text(content, encoding="utf-8")


def _summarize_content_diff(old: str, new: str) -> str:
    """轻量摘要两段文本的差异规模，不做真正的逐行 diff（那是给人看的，
    这里只需要一个"变化有多大"的量级提示）。"""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    changed = len(set(old_lines) ^ set(new_lines))
    return f"{len(old_lines)}→{len(new_lines)} 行，约 {changed} 行不同"


def _record_bypass_detection(repo_root: Path, target: str, who: str, diff_summary: str) -> None:
    """队列 #200：检测到绕过锁的直接改写时，落一条持久审计记录——终端
    输出转瞬即逝，调用方未必是人在盯屏幕（如子进程调用），只回显不留痕
    等于没有检测。写入失败不应影响 acquire 本身（best-effort，同 sweep 里
    审计/告警失败不影响主流程退出码的既有惯例）。"""
    log_path = repo_root / BYPASS_LOG_REL
    entry = {
        "detected_at": _now().isoformat(),
        "target": target,
        "acquiring_who": who,
        "diff_summary": diff_summary,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_raw_lock(lock_path: Path) -> dict:
    """读取锁文件的完整原始 JSON，不做"released 即无锁"的语义过滤（那是
    `_read_lock` 的职责）——供 `history`/`reserved` 等元数据字段读取，这些
    字段需要跨越 acquire→release 的整个生命周期保留，不随锁被释放而消失。"""
    if not lock_path.exists():
        return {}
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_history(lock_path: Path) -> list[dict]:
    history = _read_raw_lock(lock_path).get("history")
    return history if isinstance(history, list) else []


def _prune_history(history: list[dict], now: datetime) -> list[dict]:
    kept = []
    for entry in history:
        try:
            at = datetime.fromisoformat(entry["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if (now - at).total_seconds() / 60 <= HISTORY_RETENTION_MINUTES:
            kept.append(entry)
    return kept


def _recent_entries(history: list[dict], now: datetime, window_minutes: float) -> list[dict]:
    """筛出 `history` 里"距今 window_minutes 以内"的条目，附带算好的
    `age_minutes`（供 acquire 回显用）。"""
    result = []
    for entry in history:
        try:
            at = datetime.fromisoformat(entry["at"])
        except (KeyError, TypeError, ValueError):
            continue
        age = (now - at).total_seconds() / 60
        if 0 <= age <= window_minutes:
            result.append({**entry, "age_minutes": age})
    return result


class ReserveFailedError(RuntimeError):
    """预留取号失败——高水位线行缺失/格式漂移，或目标文件读取失败。

    调用方（`cmd_acquire`）据此**回滚整个 acquire**（改写为释放标记）并非
    零退出，绝不静默回落"文内可见最大号+1"之类的替代计算——分析件 §一
    设计要点⑤："解析失败必须 fail-loud"：清扫后表格内早已看不到历史最大
    号，任何回落值都必然撞已归档编号（#99(a) 已实证过同款故障）。宁可让
    调用方明确知道"这次没预留到、重试或人工处理"，也不可返回一个看似
    正常、实则可能撞号的编号。
    """


def _reserve_ids(target: str, section: str, count: int) -> list[int]:
    """在持锁窗口内原子完成"读高水位线→分配 count 个连续编号→回写高水位
    线"，返回分配到的字面编号列表（升序，供调用方直接使用，不需要再 +1）。

    只信高水位线行本身，**不**回落扫描表格内可见最大行号（那正是 fail-loud
    要拒绝的替代路径——见 `ReserveFailedError`）。未使用完的预留号允许留
    空洞（协议〇.8：编号永不复用），本函数不做任何"释放未用编号"的操作，
    调用方也不需要。
    """
    if section not in SECTION_NUMBER_PATTERNS:
        raise ReserveFailedError(
            f"未知分区 {section!r}，仅支持 {sorted(SECTION_NUMBER_PATTERNS)}"
        )
    path = _target_path(target)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReserveFailedError(f"读取目标文件失败，拒绝预留：{path}（{exc}）") from exc

    line_match = HIGH_WATER_MARK_LINE_PATTERN.search(text)
    if line_match is None:
        raise ReserveFailedError(f"目标文件不含「编号高水位线」标注行，拒绝预留：{path}")

    line_start = text.rfind("\n", 0, line_match.start()) + 1
    line_end = text.find("\n", line_match.end())
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]

    section_match = SECTION_NUMBER_PATTERNS[section].search(line)
    if section_match is None:
        raise ReserveFailedError(
            f"高水位线行不含 §{section} 编号（格式漂移），拒绝预留：{line!r}"
        )

    current = int(section_match.group(2))
    reserved = list(range(current + 1, current + 1 + count))

    # 队列 #185（2026-08-04 实测竞态）：高水位线可能已经滞后于文件实际
    # 内容——例如有人绕过编辑锁直接写入了一行新编号（见 #200），却没有
    # 同步推高水位线；此时单纯"高水位线+1"会算出一个其实已被占用的号。
    # 写回高水位线之前，核对即将分配的号是否已出现在当前文件同分区的
    # 可见行里——命中即 fail-loud（不静默跳过冲突号、不改用"扫描可见
    # 最大值"这类会撞已归档编号的替代路径，见本函数一贯的 fail-loud 原则
    # 与 ReserveFailedError 文档），逼调用方先核实文件真实状态再重试。
    live_numbers = {
        int(cells[0])
        for _, cells in _table_data_rows(_split_live_sections(text).get(section, ""))
        if cells[0].isdigit()
    }
    collided = sorted(set(reserved) & live_numbers)
    if collided:
        raise ReserveFailedError(
            f"拒绝预留：即将分配的编号 {collided} 已存在于当前文件 §{section} "
            f"可见行中（高水位线={current}，落后于文件实际内容——很可能有绕过"
            "编辑锁的直接写入，见队列 #200/#233）。请先核实文件真实状态后再重试。"
        )

    new_value = reserved[-1]
    new_line = (
        line[:section_match.start(2)] + str(new_value) + line[section_match.end(2):]
    )
    new_text = text[:line_start] + new_line + text[line_end:]
    path.write_text(new_text, encoding="utf-8")
    return reserved


def _split_live_sections(text: str) -> dict[str, str]:
    """按 `## 一、`/`## 二、`/`## 三、`/`## 四、` 切分跨桌任务队列.md 正文
    （只用于活文件本身——归档件历次标题措辞不统一，见 `_archive_row_numbers`
    改用不依赖标题的按列数分类法）。"""
    matches = list(LIVE_SECTION_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[label] = text[start:end]
    return sections


def _table_data_rows(section_text: str) -> list[tuple[str, list[str]]]:
    """提取表格数据行（原始行文本 + 拆分后的单元格），跳过表头/分隔行。

    判据与 `工具-落库sweep.py::_parse_section_two` 保持一致（首列等于表头
    已知取值，或首列仅由 "-"/空白组成即视为分隔行）——同一份文件、同一套
    表格约定，两处判据不该各写一套。裸竖线致列数偏移的行（#164/#225①要
    抓的那种）不会被这里过滤掉，会原样进入返回列表、留给调用方按列数校验。

    队列 #314①（2026-08-09 实测坐实）：切列曾要求行首行尾都必须是 `|`，
    导致结尾被外部工具整段吞掉的行（#313 真实事故）连本函数返回列表都
    进不去，是"lint 放行"与"release③误判为新增行拒绝"两处真实故障的
    共同根因，完整实测记录见队列 #313/#314。

    队列 #314（openspec 变更包 `queue-table-backtick-aware-split`）：切列
    实现改为委托 `queue_table.split_row_cells`（反引号感知——反引号跨度
    内的竖线不再被误当列分隔符，如 #313 行状态列里 `git grep` 正则交替符
    那样的合法内容），行首要求／行尾不作要求的既有口径随委托一并继承，
    不在本函数重复实现。
    """
    rows: list[tuple[str, list[str]]] = []
    for line in section_text.splitlines():
        cells = queue_table.split_row_cells(line)
        if cells is None:
            continue
        first = cells[0]
        if first in _TABLE_HEADER_FIRST_CELLS:
            continue
        if set(first) <= {"-", " "}:
            continue
        rows.append((line, cells))
    return rows


# 队列 #258：append-row 子命令——把插入位置/列数/裸竖线校验交给工具，替代
# 此前"用全文最后一个 # 数字 形态的行定位分区末尾"这一容易插错分区的启发式
# （#248/#254 同一根因两次踩坑，见 openspec 变更包
# editlock-section-append-and-followup-consistency-guard）。
BACKTICK_SPAN_RE = re.compile(r"`[^`]*`")
SECTION_APPEND_CONTENT_COUNTS = {"一": 7, "二": 4, "四": 3}


class AppendRowFailedError(RuntimeError):
    """append-row 校验失败——不写入任何内容（同 `ReserveFailedError` 的
    fail-loud 原则：宁可让调用方明确知道，也不可返回一个可能有问题的结果）。
    """


def _cell_has_bare_pipe(cell: str) -> bool:
    """检测字段值中是否含竖线 `|`（队列 #258，援引 #164 教训）。

    apply 阶段修正（design.md 有完整记录）：不对反引号包裹的片段做豁免——
    本项目现有表格解析（`_table_data_rows` 等）对整行做原样 `split("|")`，
    不具备反引号感知能力，`_validate_release_structure` ①列数校验本就把
    "反引号内裸竖线致列偏移"列为要抓的失效形态，本函数口径须与其一致，
    不得引入一个 release 校验不认可的"反引号豁免"。

    队列 #306：实现委托 `queue_table.has_bare_pipe`（权威模块，口径一致），
    本函数保留作薄封装——docstring 记录的历史成因对本文件的读者仍有价值，
    不因委托而删除。
    """
    return queue_table.has_bare_pipe(cell)


def _build_append_row_line(section: str, number: str | None, cells: list[str]) -> str:
    """按分区列序把结构化字段拼装成一条完整的 Markdown 表格行文本（不含
    首尾换行符）。校验失败抛 `AppendRowFailedError`，调用方据此不写入任何
    内容——同 `_reserve_ids`/`ReserveFailedError` 一贯的"校验失败不制造
    半成品状态"原则。
    """
    if section not in SECTION_APPEND_CONTENT_COUNTS:
        raise AppendRowFailedError(f"未知分区 {section!r}，仅支持 {sorted(SECTION_APPEND_CONTENT_COUNTS)}")
    expected = SECTION_APPEND_CONTENT_COUNTS[section]
    if len(cells) != expected:
        raise AppendRowFailedError(
            f"§{section} 需要 {expected} 个 --cell（不含编号列），收到 {len(cells)} 个"
        )
    for i, cell in enumerate(cells, start=1):
        if _cell_has_bare_pipe(cell):
            preview = cell if len(cell) <= 60 else cell[:60] + "…"
            raise AppendRowFailedError(
                f"第 {i} 个 --cell 含竖线「|」（不论是否被反引号包裹均拒绝，"
                f"改用全角「｜」或改写措辞）：{preview}"
            )
    if section in ROW_NUMBER_SECTIONS:
        if number is None:
            raise AppendRowFailedError(f"§{section} 需要 --number（行编号，通常来自 acquire --reserve 的返回值）")
        row_cells = [number] + cells
    else:
        if number is not None:
            raise AppendRowFailedError(f"§{section} 不使用编号列，不应提供 --number")
        row_cells = cells
    return "| " + " | ".join(row_cells) + " |"


def _section_bounds(text: str, section: str) -> tuple[int, int] | None:
    """定位分区标题在**全文**中的正文起止偏移（复用 `LIVE_SECTION_HEADING_RE`，
    与 `_split_live_sections` 同一套匹配逻辑，额外返回偏移供插入定位用）。"""
    matches = list(LIVE_SECTION_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1) == section:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return start, end
    return None


def _last_table_line_end_offset(section_text: str) -> int | None:
    """分区正文内最后一条 `|` 开头且以 `|` 结尾的行（表头/分隔行/数据行
    均算）结束位置的相对偏移（含其后换行符）。分区内一条表格行都没有
    （结构异常）时返回 None，交调用方 fail-loud。"""
    offset = 0
    last_end = None
    for line in section_text.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            last_end = offset + len(line)
        offset += len(line)
    return last_end


def cmd_append_row(args: argparse.Namespace) -> int:
    target_path = _target_path(args.file)
    try:
        text = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ 读取目标文件失败：{target_path}（{exc}）")
        return 1

    try:
        new_line = _build_append_row_line(args.section, args.number, args.cell)
    except AppendRowFailedError as exc:
        print(f"✗ {exc}")
        return 1

    # 写入前最终校验：拼装结果按 | 切分列数应等于分区预期总列数（含编号列，
    # 若有）——与既有 `_validate_release_structure` ①校验同一把尺子。
    parsed_cells = [c.strip() for c in new_line.strip("|").split("|")]
    expected_total = SECTION_COLUMN_COUNTS[args.section]
    if len(parsed_cells) != expected_total:
        print(f"✗ 拼装结果列数为 {len(parsed_cells)}（应为 {expected_total}），拒绝写入——请核查字段内容。")
        return 1

    bounds = _section_bounds(text, args.section)
    if bounds is None:
        print(f"✗ 目标文件不含 §{args.section} 分区标题，拒绝写入。")
        return 1
    start, end = bounds
    section_text = text[start:end]
    last_end = _last_table_line_end_offset(section_text)
    if last_end is None:
        print(f"✗ §{args.section} 分区内未找到任何表格行（含表头），拒绝写入——分区结构异常需人工核实。")
        return 1

    insert_at = start + last_end
    prefix = text[:insert_at]
    suffix = text[insert_at:]
    if not prefix.endswith("\n"):
        prefix += "\n"
    new_text = prefix + new_line + "\n" + suffix

    target_path.write_text(new_text, encoding="utf-8")
    print(f"✓ 已追加一行到 §{args.section}：{new_line}")
    return 0


def _archive_row_numbers(repo_root: Path) -> dict[str, set[int]]:
    """扫描所有《跨桌任务队列-归档-YYYYMM.md》，按列数分类出已用编号——
    §一（8 列）归一类、§四（4 列且首列纯数字，与 §二 的 "B-xxx" 批次行区分
    开）归另一类。不依赖归档件标题措辞：202607 档用"一、任务看板（已完成
    行）"，202608 档用"§一 任务看板 · ... 迁入"，写法并不统一，按列数+首列
    形态分类比按标题正则更稳。"""
    numbers: dict[str, set[int]] = {"一": set(), "四": set()}
    archive_dir = repo_root / Path(DEFAULT_TARGET).parent
    if not archive_dir.is_dir():
        return numbers
    for path in sorted(archive_dir.glob(ARCHIVE_GLOB)):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            s = line.strip()
            if not (s.startswith("|") and s.endswith("|")):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            first = cells[0]
            if not first.isdigit():
                continue
            if len(cells) == 8:
                numbers["一"].add(int(first))
            elif len(cells) == 4:
                numbers["四"].add(int(first))
    return numbers


def _diff_touched_rows(
    old_section_text: str, new_section_text: str,
) -> list[tuple[str, list[str]]]:
    """本次持锁期间"新增或内容有变化"的数据行——凡当前行原文在快照的同一
    分区文本里逐字找不到，即视为触碰过（新增/编辑均算，未改动的行原样
    保留、逐字可命中，不会被误判）。"""
    old_lines = set(old_section_text.splitlines())
    return [
        (line, cells) for line, cells in _table_data_rows(new_section_text)
        if line not in old_lines
    ]


def _followup_readme_rows(text: str) -> list[tuple[str, list[str], int]]:
    """跟进信 README「现有跟进信清单」表的数据行——(原始行文本, 单元格,
    状态列索引) 三元组列表。判定逻辑与 `aibot_service.readme_table.iter_rows`
    一致（本工具不 import aibot_service 包，独立实现一份，避免额外的跨包
    耦合——两处各自维护成本极低，均为几行纯文本切分）：表头＝任意以 `|`
    开头且含"发送状态"字样的行；其后跳过 `|---|...` 分隔行，直到第一条非
    `|` 开头的行为止都是数据行。目标文件不存在/无此表时返回空列表。
    """
    lines = text.splitlines()
    header_idx = None
    status_col_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            for j, cell in enumerate(header_cells):
                if cell.startswith("发送状态"):
                    status_col_index = j
                    break
            header_idx = i
            break
    if header_idx is None or status_col_index < 0:
        return []

    rows: list[tuple[str, list[str], int]] = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= status_col_index:
            continue
        rows.append((line, cells, status_col_index))
    return rows


def _followup_row_identity(cells: list[str], status_col_index: int) -> tuple[str, ...]:
    """行身份＝除状态列外全部单元格——只要其余内容不变，状态列如何转换
    都指向同一行（与 `approval.py._row_identity` 同一判据，两处独立实现
    但语义必须一致，否则"既有行合法转终态"会被这里误判为"新增行"）。"""
    return tuple(c for i, c in enumerate(cells) if i != status_col_index)


def _followup_header_col_index(text: str, label: str) -> int:
    """跟进信 README 清单表头按列名前缀定位列索引，未找到返回 -1（队列
    #308 子项 G 复用 `_followup_readme_rows` 已确立的"按表头字样定位"手法，
    独立于其固定返回的状态列索引，供收信人列定位复用，避免改动该函数
    既有签名与其两个既有调用方）。"""
    for line in text.splitlines():
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            for j, cell in enumerate(header_cells):
                if cell.startswith(label):
                    return j
            return -1
    return -1


def _validate_followup_readme_release(current_text: str, snapshot_text: str) -> list[str]:
    """队列 #124 阶段二（design.md D1）：跟进信 README 两态语义的结构性
    拦截"新建即终态"反模式。比对 acquire 快照与当前内容，若某行的"非状态
    列身份"在快照里不存在（本次持锁窗口内新增），且当前状态列值为终态
    标记 `🆕 待发`，判违规——起草物理上不能一步到位写终态，必须先写
    `⏳ 待你审`，再经独立的 `approve_followup_letter.py` 转终态（该脚本
    在专属的另一次持锁窗口外运行，不改队列文件锁，不受本函数约束）。
    既有行从 `⏳ 待你审` 转为 `🆕 待发`（批准脚本的合法产物，其身份在
    快照里能找到）不受影响，正常放行。

    队列 #308 子项 G（决策点 10）：同批新增跟进信串行原则闸——本次持锁
    窗口内新增了某收信人的登记行时，回查该收信人此前最靠近的一行（表格
    顺序上排在新增行之前）；若其发送状态不以 `📥 已回件并回灌` 开头（视为
    非闭环），MUST 拒绝 release，除非新增行任一单元格显式含
    `串行豁免：〈理由〉`（放行但打印留痕提示，不静默）。该收信人历史上
    首次出现（无"前一封"可比对）不受本项约束。判别新增行的方法复用上面
    两态语义检查已用的 `_followup_row_identity`，历史行不追溯。
    """
    violations: list[str] = []
    old_rows = _followup_readme_rows(snapshot_text)
    old_identities = {
        _followup_row_identity(cells, idx) for _, cells, idx in old_rows
    }

    for line, cells, status_col_index in _followup_readme_rows(current_text):
        status_value = cells[status_col_index]
        if status_value != FOLLOWUP_FINALIZED_STATUS:
            continue
        identity = _followup_row_identity(cells, status_col_index)
        if identity not in old_identities:
            preview = line.strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"
            violations.append(
                f"新增行状态列直接写终态「{FOLLOWUP_FINALIZED_STATUS}」，违反两态语义"
                f"（起草只能写「{FOLLOWUP_DRAFT_STATUS}」，转终态须经独立的 "
                f"approve_followup_letter.py）：{preview}"
            )

    recipient_col_index = _followup_header_col_index(current_text, "收信人")
    if recipient_col_index >= 0:
        current_rows = _followup_readme_rows(current_text)
        for idx, (line, cells, status_col_index) in enumerate(current_rows):
            identity = _followup_row_identity(cells, status_col_index)
            if identity in old_identities:
                continue  # 既有行的状态转换不受本项约束
            if len(cells) <= recipient_col_index:
                continue
            recipient = cells[recipient_col_index]
            prior_status = None
            prior_preview = None
            for j in range(idx - 1, -1, -1):
                prior_cells = current_rows[j][1]
                if len(prior_cells) <= recipient_col_index:
                    continue
                if prior_cells[recipient_col_index] == recipient:
                    prior_status = prior_cells[current_rows[j][2]]
                    prior_preview = current_rows[j][0].strip()
                    if len(prior_preview) > 80:
                        prior_preview = prior_preview[:80] + "…"
                    break
            if prior_status is None:
                continue  # 该收信人历史上首次出现，不受串行原则约束
            if prior_status.startswith(FOLLOWUP_SERIAL_CLOSED_PREFIX):
                continue  # 前一封已闭环
            waiver_cell = next((c for c in cells if FOLLOWUP_SERIAL_WAIVER_MARKER in c), None)
            if waiver_cell is not None:
                waiver_text = waiver_cell.strip()
                if len(waiver_text) > 80:
                    waiver_text = waiver_text[:80] + "…"
                print(f"✓ 检测到串行豁免声明，已放行：{waiver_text}")
                continue
            preview = line.strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"
            violations.append(
                f"跟进信串行原则：新增行收信人「{recipient}」前一封（{prior_preview}）"
                f"发送状态为「{prior_status}」尚未闭环，请先据实把它改为"
                f"「{FOLLOWUP_SERIAL_CLOSED_PREFIX} <日期>」，或在本行内写明"
                f"「{FOLLOWUP_SERIAL_WAIVER_MARKER}〈理由〉」：{preview}"
            )

    return violations


def _row_hold_language_status(cells: list[str], section: str) -> tuple[bool, str | None]:
    """判定一个 §一/§四 行是否"点名了跟进信且结论为暂缓"（队列 #258 正向
    Requirement）：状态列（§一 cells[5]；§四 无独立状态列，回落事项列
    cells[1]）含暂缓关键词，且行内（§一：cells[3]输入指针+cells[6]触碰区；
    §四：cells[1]事项）能提取出一个反引号包裹的 `.md` 文件名引用。返回
    (是否命中暂缓关键词, 提取到的文件名 basename 或 None——未提取到文件名
    时第二个返回值为 None，调用方据此判定"仅关键词无文件名不触发"）。"""
    if section == "一":
        status_text = cells[5] if len(cells) > 5 else ""
        filename_sources = [cells[3] if len(cells) > 3 else "", cells[6] if len(cells) > 6 else ""]
    elif section == "四":
        status_text = cells[1] if len(cells) > 1 else ""
        filename_sources = [cells[1] if len(cells) > 1 else ""]
    else:
        return False, None

    if not any(phrase in status_text for phrase in HOLD_LANGUAGE_PHRASES):
        return False, None

    for source in filename_sources:
        found = re.findall(r"`([^`]+\.md)`", source)
        if found:
            return True, Path(found[0]).name
    return True, None


def _followup_status_by_filename(readme_text: str) -> dict[str, str]:
    """README「现有跟进信清单」表按目标文件标注建立 文件名(basename) → 发送
    状态 的映射（队列 #258，独立实现，正则口径同
    `aibot_service/readme_table.py::_TARGET_FILE_RE`，不 import 该包，同
    `_followup_readme_rows` 既有惯例）。未标注目标文件的行不在映射内——本
    校验只认结构化引用（design.md 决策点3），判不出就不拦。"""
    mapping: dict[str, str] = {}
    for _, cells, status_col_index in _followup_readme_rows(readme_text):
        topic_cell = cells[3] if len(cells) > 3 else ""
        m = FOLLOWUP_TARGET_FILE_RE.search(topic_cell)
        if not m:
            continue
        mapping[Path(m.group(1)).name] = cells[status_col_index]
    return mapping


def _validate_followup_hold_consistency(
    touched_rows: list[tuple[str, list[str], str]], repo_root: Path,
) -> list[str]:
    """队列 #258（接管 #294 修法⑵，openspec 变更包
    editlock-section-append-and-followup-consistency-guard）：本次持锁期间
    新增/修改的 §一/§四 行中，"点名了跟进信且结论为暂缓"的行与 README 该信
    当前发送状态做交叉一致性核对。正向（README 仍为终态 `🆕 待发`，即
    `ZhuopinFollowupDispatchDaily` 唯一认可的可发送标记）拒绝 release；反向
    （README 已是"已推送"类终态而队列文本仍称暂缓，多半是事后如实追述整个
    事故经过，见 #150 真实案例）仅告警不阻断（design.md 决策点4）。
    """
    violations: list[str] = []
    hold_rows = []
    for line, cells, section in touched_rows:
        is_hold, filename = _row_hold_language_status(cells, section)
        if is_hold and filename:
            hold_rows.append((line, cells, section, filename))
    if not hold_rows:
        return violations

    readme_path = repo_root / FOLLOWUP_README_TARGET
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError:
        return violations  # README 读不到不阻断队列 release，本校验静默跳过
    status_map = _followup_status_by_filename(readme_text)

    for line, cells, section, filename in hold_rows:
        preview = line.strip()
        if len(preview) > 80:
            preview = preview[:80] + "…"
        status = status_map.get(filename)
        if status is None:
            continue  # README 未找到匹配行——判不出，不拦（design.md 决策点3）
        if status == FOLLOWUP_FINALIZED_STATUS:
            violations.append(
                f"§{section} 行点名跟进信「{filename}」且结论为暂缓，但该信在 README "
                f"中「发送状态」仍为「{FOLLOWUP_FINALIZED_STATUS}」（机制唯一认可的可"
                f"发送标记，见 #150/#294 真实事故）：{preview}"
            )
        elif status not in FOLLOWUP_NON_TERMINAL_STATUSES:
            print(
                f"⚠ §{section} 行点名跟进信「{filename}」仍称暂缓，但该信 README「发送"
                f"状态」已是「{status}」（疑似终态已推送，队列文本可能滞后，建议核实"
                f"是否为事后如实追述）：{preview}"
            )
    return violations


def _validate_release_structure(
    args: argparse.Namespace, lock_data: dict, repo_root: Path,
) -> list[str]:
    """队列 #225：release 时对跨桌任务队列.md 做结构校验（现已扩至六项，
    见⑥），只对本次持锁期间新增/修改的行生效（历史行不追溯）。返回违规
    说明列表，空列表即通过。

    ①列数：§一 行应为 8 列、§二/§四 行应为 4 列，不符即报（含反引号内裸
      竖线致列数偏移的情形——本函数按原样切分列，不做任何"容错"，这正是
      要抓的失效形态）。
    ②批次清单（仅 §二）：新增批次行的"文件清单"列须含队列文件自身路径——
      两种实现路径（① sweep 侧隐式声明 / ② 本处 release 时显式校验）二选
      一，本工具选②：在编辑发生的源头把关，比在消费端悄悄兜底更能让"文件
      清单"这一列本身保持诚实（消费端兜底会让人看着清单以为完整、实则不
      是，长期侵蚀 grep/审计工具对这份清单的信任）。
    ③编号（仅 §一/§四）：真正新增的行（编号此前不存在于快照同分区）不得
      与当前文件或归档件里任何既有编号重复，且必须属于本次持锁期间
      `--reserve` 预留的编号集合——协议〇.7（2026-07-31 补）已明文"此后新
      行编号一律用 --reserve 取"，未预留即新增编号视为违规，逼回正确路径。
    ④断言门槛（仅 §一，咽喉4甲）：**状态列本身**（cells[5]）同时含 P0/P1
      定级与"未核／未做的核实"字样即报——标注未核不等于可据此下结论（成因
      见 #221）。只检查状态列、不查整行：本项目约定优先级标注写在状态列
      （#219/#225/#234 等现存行逐一核对一致），任务描述列出现"P0/P1"多半
      是在叙述/讨论相关内容本身（如 #225/#230 两行正是在提议/记录这条
      规则），不是该行当前的权威结论——按整行扫描会把这类历史叙述误判为
      新违规，连"只把状态列改成已完成"这种收尾动作都拦下（2026-08-04
      dogfooding 本行改造时的真实案例，见 #225/#230 行）。队列 #248（2026-08-05）
      再收窄一层：扫描前剔除被「」/『』引号包裹的片段——只查状态列仍不够，
      状态列内引用/复述判据关键词本身（而非断言当前判断）同样不应触发，
      见 QUOTED_SPAN_RE 定义处的真实案例（#221 行）。
    ⑤模糊状态（仅 §二，队列 #247②）：状态列"开头片段"既不含"待"也不含
      "✅"，会被 sweep 判为"状态列模糊"、每轮跳过并重复告警（#247①实测
      最长 49 轮）——在写入那一刻挡住这种中间态写法，比"发生后修法"更
      彻底。判据复刻 sweep 侧的"开头片段"锚定口径（独立实现，见
      `_leading_status_segment`），并显式放行 #236(1) 引入的"在办（预登记
      ……）"约定文本——那是有意为之的第三态（sweep 也不该把它当"待处理"
      去 add+commit），不是需要拦截的误写。
    ⑥跟进信暂缓一致性（仅 §一/§四，队列 #258，接管 #294 修法⑵）：命中"点名
      了跟进信且结论为暂缓"（状态列/事项列含暂缓关键词 + 反引号 `.md` 文件
      名引用）的行，若该信在 README 中「发送状态」仍为终态 `🆕 待发`，拒绝
      release——治 2026-08-06 01:30 UTC 真实误发（#150：队列称暂缓、README
      未同步移出待发标记，`ZhuopinFollowupDispatchDaily` 照发）。反向（README
      已是"已推送"类终态而队列仍称暂缓）仅告警，见 `_validate_followup_
      hold_consistency` 文档。
    ⑦§二新增即终态防写（队列 #308 子项 F1）：新增批次行（identity＝批次名
      cells[0]，不存在于快照 §二 批次名集合）状态列开头片段以「✅」开头即
      拒绝——既有批次行合法转「✅」不受影响。治 `B-0728财务专线核实`／
      `B-0728队列#125回填` 两批因登记时写了 ✅ 被 sweep 判为已处理、内容
      石沉大海的真实事故。
    ⑧头尾不一致（**仅 §二**，队列 #308 子项 F2；§一 已于队列 #308 收尾
      session 退休，见下）：状态列含「✅」但不在开头片段内即拒绝——直接
      复用⑤已有的 `_leading_status_segment()`，零新造判据。治 2026-08-03
      一次性抓出的 6 行"行尾写完成、开头仍待领"真实事故（当时 §一/§二
      均无机器字段，只能靠这一正则判据）。
      🔴 **§一 范围已退休（2026-08-09，队列 #308 收尾 session，同批把
      F2 也算进措施 B「新增机制类变更包须答退休哪个既有守卫」的自我
      dogfooding）**：#308 落地机器字段后，§一 首次全量流经本校验命中
      9 行（#22/#67/#96/#98/#118/#170/#234/#240/#264，2026-08-09 复核，
      与主工作区分叉恢复那次的 13 行旧清单不同——#252/#267/#285/#308 等
      行同期已被改动，命中集随之变化，故每次都需重跑取最新集，不可复用
      旧清单），逐条核实后**全部为同一种假阳性**：行内出现的「✅」并非
      「「」/『』引号包裹的历史引文」（与 #221/#248 的成因不同源，比照
      不成立），而是长期累积的**带日期的子里程碑追记**（如"✅ 节奏已定
      （日期）"/"✅ G0 已获批准启动（日期）"）——只标记"这一件子事已办"，
      行的整体状态仍诚实地停在 `[S:partial]`/`[S:blocked]`/`[S:hold]`/
      `[S:open]`（9 行逐一核对，无一行整体其实已完成而字段未同步）。
      **未采用"加引号再剥离"的处置**：那需要对 9 行历史正文做 13 处精细
      标注编辑，且其本质是"新增一种正则识别的转义约定"——与 #308 全篇
      的源头治理方向（消灭"用正则猜中文"）背道而驰。**改用机器字段本身
      作为退休依据**：决策点 1 已确立 `[S:...]` 字段是 §一 状态的权威
      源，字段一旦解析成功（`_parse_status_domain_fields` 返回值非
      `None`），本判据对该行即为冗余——不论字段取值是否 `done`，字段本身
      已经把"这一行到底算不算完成"说清楚了，无需再去猜正文里某个位置的
      "✅"字符是不是在断言整行完成。**残余风险**（字段本身写错/写旧、
      正文却已诚实交代完成）不是无主之地：`open`/`partial`/`hold` 三态
      每轮由 sweep `_find_stale_pending_rows`（决策点 4，2. 已切换读字段）
      持续复核追问，比本处"仅在 release 那一刻查一次正文位置"更贴近
      "字段是否仍准确"这个真正要防的问题。字段解析失败（遗留行/未来
      新行漏挂字段）才回退到原判据——即便如此，`工具-队列结构lint.py`
      的 CI 硬门禁（决策点 4.3）已经把"§一 新行必须带字段"挡在更早的
      环节，本回退路径预期极少触发。**§二 无字段覆盖（decision.md
      Non-Goals），本判据原样保留、不受影响**。
    ⑨机制类可动 WIP 上限（仅 §一，队列 #308 决策点 6，协议〇.9 措施 C）：
      本次持锁期间新增了域为「机」的 §一 行时，重新计算全文当前的可动
      WIP 计数；超过上限（默认 8，`--mechanism-wip-cap` 可覆盖）**仅提示
      不阻断**——不加入返回的 violations，release 仍正常放行。
    ⑩因果断言证伪命令（仅 §一，队列 #285）：状态列（同④先剔除引号包裹
      片段）一旦含 P0/P1 定级 token，须在同一单元格内含至少一处反引号
      包裹的非空片段，缺失即报——与④是两条独立校验，一行可同时触发两者
      互不影响判定。**只判"有没有"，判不了"对不对"**：覆盖"根本没想过
      怎么证伪"（2/3），防不住"想过但用了错的证据"（1/3，见 #221），不得
      表述为质量保证。
    """
    violations: list[str] = []
    current_text = _read_target_text(args.file)
    snapshot_text = _read_snapshot(args.file)

    new_sections = _split_live_sections(current_text)
    old_sections = _split_live_sections(snapshot_text)
    reserved_map = lock_data.get("reserved") or {}
    archive_numbers: dict[str, set[int]] | None = None  # 惰性计算，仅在需要时扫描
    touched_for_hold_consistency: list[tuple[str, list[str], str]] = []  # ⑥用
    new_mechanism_row_added = False  # ⑨用：本次是否新增了 [D:机] 的 §一 行

    for label, expected_cols in SECTION_COLUMN_COUNTS.items():
        new_text = new_sections.get(label, "")
        old_text = old_sections.get(label, "")
        touched = _diff_touched_rows(old_text, new_text)
        if not touched:
            continue

        old_numbers: set[int] = set()
        current_number_counts: Counter = Counter()
        if label in ROW_NUMBER_SECTIONS:
            old_numbers = {
                int(old_cells[0]) for _, old_cells in _table_data_rows(old_text)
                if old_cells[0].isdigit()
            }
            current_number_counts = Counter(
                int(cells[0]) for _, cells in _table_data_rows(new_text) if cells[0].isdigit()
            )
        old_batch_names: set[str] = set()
        if label == "二":
            # ⑦用：§二 无编号列，identity＝批次名（cells[0]），与 ROW_NUMBER_
            # SECTIONS 的"编号不在 old_numbers ⇒ 新增"同构，只是 identity
            # 换成字符串。
            old_batch_names = {
                old_cells[0] for _, old_cells in _table_data_rows(old_text)
            }

        for line, cells in touched:
            preview = line.strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"

            if len(cells) != expected_cols:
                violations.append(
                    f"§{label} 行列数为 {len(cells)}（应为 {expected_cols}，"
                    f"含反引号内裸竖线等致列偏移的情形）：{preview}"
                )
                continue  # 列数都不对，按列取值的后续校验没有意义

            if label == "二":
                fragments = re.findall(r"`([^`]+)`", cells[1])
                declares_self = any(
                    frag == DEFAULT_TARGET
                    or frag == Path(DEFAULT_TARGET).name
                    or frag.endswith("/" + Path(DEFAULT_TARGET).name)
                    for frag in fragments
                )
                if not declares_self:
                    violations.append(
                        f"§二 批次「{cells[0]}」文件清单未声明队列文件自身路径"
                        f"（须含 `{DEFAULT_TARGET}`）：{preview}"
                    )
                if _section_two_status_is_ambiguous(cells[3]):
                    violations.append(
                        f"§二 批次「{cells[0]}」状态列开头片段既不含"
                        f"「待」也不含「✅」（会被 sweep 判为状态列模糊、每轮"
                        f"跳过并重复告警，见 #247）：{preview}"
                    )
                if cells[0] not in old_batch_names:
                    # ⑦ 队列 #308 子项 F1：新增批次行状态列不得以 ✅ 开头
                    # （既有批次合法转 ✅ 走上面 old_batch_names 判据放行）。
                    leading = _leading_status_segment(cells[3])
                    if leading.startswith("✅"):
                        violations.append(
                            f"§二 新增批次「{cells[0]}」状态列不得以「✅」开头"
                            f"（新建即终态，见 `B-0728财务专线核实` 等真实事故）：{preview}"
                        )

            # ⑧ 队列 #308 子项 F2：状态列含「✅」但不在开头片段即报。
            # 2026-08-09 收尾 session 把 §一 范围退休（详见函数 docstring
            # ⑧ 段）——§一 首次全量重跑本判据命中的 9 行逐条核实后全部是
            # "带日期子里程碑追记"假阳性，根因是本判据设计于机器字段落地
            # 之前；字段落地后，字段本身已是该行是否完成的权威源，本判据
            # 对 §一 变为冗余（且残余的"字段写旧"风险已有 sweep 侧持续
            # 复核兜底），故 §一 仅在字段解析失败（遗留/漏挂字段的行）时
            # 才回退到本判据；§二 无字段覆盖，原样保留、不受影响。
            if label == "二":
                status_cell = cells[3] if len(cells) > 3 else ""
                if "✅" in status_cell and "✅" not in _leading_status_segment(status_cell):
                    violations.append(
                        f"§二 行状态列含「✅」但不在开头片段（头尾不一致，"
                        f"见 2026-08-03 六行真实事故）：{preview}"
                    )
            elif label == "一":
                status_cell = cells[5] if len(cells) > 5 else ""
                status_value, _domain_value, _rest = _parse_status_domain_fields(status_cell)
                if status_value is None:
                    if "✅" in status_cell and "✅" not in _leading_status_segment(status_cell):
                        violations.append(
                            f"§一 行状态列含「✅」但不在开头片段（头尾不一致，"
                            f"见 2026-08-03 六行真实事故；本行无可解析的机器字段，"
                            f"回退旧判据）：{preview}"
                        )

            if label in ROW_NUMBER_SECTIONS and cells[0].isdigit():
                number = int(cells[0])
                # 组内重复：不论这个编号本身是"新增"还是"编辑既有行"，只要
                # 当前文件里它此刻出现超过一次，就是真实撞号——即便撞的
                # 对象是一行本次完全没碰过的历史行（如"新增一行沿用了某个
                # 已存在行的旧编号"），这条检查也必须抓住，不能因为该编号
                # 本身"不算新"就放过。
                if current_number_counts[number] > 1:
                    violations.append(f"§{label} #{number} 与当前文件内其它行编号重复：{preview}")
                if number not in old_numbers:  # 真正新增的行，才做归档去重+预留归属校验
                    if archive_numbers is None:
                        archive_numbers = _archive_row_numbers(repo_root)
                    if number in archive_numbers.get(label, set()):
                        violations.append(f"§{label} #{number} 与已归档行编号重复：{preview}")
                    reserved_here = set(reserved_map.get(label, []))
                    if number not in reserved_here:
                        shown = "、".join(str(n) for n in sorted(reserved_here)) or "本次未预留任何编号"
                        violations.append(
                            f"§{label} #{number} 不属于本次持锁期间 --reserve 预留的编号集合"
                            f"（{shown}）：{preview}"
                        )

            if label == "一":
                # ④ 断言门槛：只检查**状态列本身**（cells[5]），不是整行。
                # 三条真实现存行（#219/#225/#234，见 2026-08-04 实测）一致
                # 证实本项目约定把优先级标注（P0/P1/P2/P3）写在状态列，不是
                # 任务描述列——任务描述列里出现"P0/P1"多半是在叙述/讨论相关
                # 内容本身（如 #225/#230 两行正是在提议/记录这条规则，其
                # 未改动的任务描述天然含这两个词），不是该行的权威优先级
                # 断言。按整行扫描会把这类历史叙述误判为"新违规"，连"只把
                # 状态列改成已完成"这种收尾动作都拦下（2026-08-04 dogfooding
                # 本行改造时的真实案例）。状态列是本项目实际存放"当前结论"
                # 的地方，检查它才对应 #221 真正的失败模式：结论（P1）与
                # 免责声明（未核）同时出现在同一处"当前判断"里。
                status_cell = _strip_quoted_spans(cells[5])
                if P0_P1_TOKEN_RE.search(status_cell) and any(
                    p in status_cell for p in UNVERIFIED_ROW_PHRASES
                ):
                    violations.append(
                        f"§一 #{cells[0]} 状态列同时含 P0/P1 定级与「未核／未做的核实」字样"
                        f"（标注未核不等于可据此下结论，见 #221 教训，请补核实或改标「待核实」）："
                        f"{preview}"
                    )

                # ⑩ 因果断言证伪命令（队列 #285）：P0/P1 定级行须在状态列内
                # 含至少一处反引号包裹的证伪命令片段——沿用④既有的引号
                # 剔除文本与"只查状态列"边界，不新增扫描面。与④是两条
                # 独立的 violation 来源，一行可能同时触发两者，互不影响
                # 判定（不去重、不合并成一条消息）。**边界声明**：本项只判
                # "有没有"证伪命令片段，判不了"对不对"（片段内容是否真的
                # 具备证伪能力）——覆盖"根本没想过怎么证伪"（2/3），防不住
                # "想过但用了错的证据"（1/3，见 #221），不得表述为质量保证。
                if P0_P1_TOKEN_RE.search(status_cell) and not BACKTICK_SPAN_RE.search(status_cell):
                    violations.append(
                        f"§一 #{cells[0]} 状态列含 P0/P1 定级但缺证伪命令"
                        f"（须在状态列内附一条反引号包裹的命令片段，回答"
                        f"「如果我错了，哪一条命令会证明我错」，见 #285）："
                        f"{preview}"
                    )

                # ⑨ 队列 #308 决策点 6（协议〇.9 措施 C）：只在本次真正新增了
                # [D:机] 的 §一 行时才触发重新计数（不为纯编辑既有行的场景
                # 做无意义的全表重算）。
                if cells[0].isdigit() and int(cells[0]) not in old_numbers:
                    _, domain_value, _ = _parse_status_domain_fields(cells[5])
                    if domain_value == "机":
                        new_mechanism_row_added = True

            if label in ("一", "四"):
                touched_for_hold_consistency.append((line, cells, label))

    violations.extend(_validate_followup_hold_consistency(touched_for_hold_consistency, repo_root))

    if new_mechanism_row_added:
        # ⑨ 非阻断提示——不加入 violations，release 仍正常放行（协议〇.9
        # 措施 C 原文："提示不阻断"，上限用途是给建行踩刹车，不是精确会计）。
        cap = args.mechanism_wip_cap
        wip_count, degraded = _count_mechanism_wip(new_sections.get("一", ""))
        for note in degraded:
            print(f"⚠ {note}")
        if wip_count > cap:
            print(
                f"⚠ 机制类可动 WIP 当前 {wip_count}／{cap}，已超上限（协议〇.9 措施 C）——"
                "建议本次新增前先关闭一条，或在任务描述内说明为何必须此时新增。"
            )

    return violations


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_lock(lock_path: Path) -> dict | None:
    """读取锁文件；`released` 标记视为无锁（release 改写标记而非 unlink，见模块说明）。"""
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("released"):
        return None
    return data


def _age_minutes(lock: dict) -> float:
    try:
        held_since = datetime.fromisoformat(lock["held_since"])
    except (KeyError, ValueError):
        return float("inf")  # 格式都读不出来，直接当陈旧处理
    return (_now() - held_since).total_seconds() / 60


def _write_released_marker(
    lock_path: Path, who: str, note: str, held_since: str,
    history: list[dict] | None = None,
) -> None:
    """写released标记（release 与"预留失败回滚 acquire"共用同一写法）。

    `history`（队列 #230-1c）随标记一并写回、不丢弃——即便本次锁已释放，
    "谁在什么时候 acquire 过"这份记录仍需保留给下一次 acquire 用来回显
    "最近 120 分钟内还有哪些身份拿过锁"，released 之后并不代表这段历史
    失去意义。"""
    _atomic_write_json(lock_path, {
        "who": who, "note": note, "held_since": held_since,
        "released": True, "released_at": _now().isoformat(),
        "history": history or [],
    })


def _parse_reserve_multi(tokens: list[str]) -> list[tuple[str, int]]:
    """解析 `--reserve-multi 一:2 四:1` 形式的多分区预留请求（队列 #185）。
    校验失败抛 `ValueError`，由调用方转成用户可读的错误信息（连锁文件都
    不碰，同 `--reserve`/`--section` 既有的"校验失败不制造半成品状态"原则）。
    """
    requests: list[tuple[str, int]] = []
    seen_sections: set[str] = set()
    for token in tokens:
        if ":" not in token:
            raise ValueError(f"格式应为 分区:数量（如 一:2），收到 {token!r}")
        section, _, count_str = token.partition(":")
        if section not in SECTION_NUMBER_PATTERNS:
            raise ValueError(f"未知分区 {section!r}，仅支持 {sorted(SECTION_NUMBER_PATTERNS)}")
        if section in seen_sections:
            raise ValueError(f"分区 {section!r} 重复出现，每个分区只能指定一次")
        try:
            count = int(count_str)
        except ValueError:
            raise ValueError(f"数量应为整数，收到 {count_str!r}") from None
        if count <= 0:
            raise ValueError(f"数量须为正整数，收到 {count}")
        seen_sections.add(section)
        requests.append((section, count))
    return requests


def cmd_acquire(args: argparse.Namespace) -> int:
    # 队列 #163/#185：--reserve/--section 与 --reserve-multi 二选一，先做
    # 参数校验，校验失败时连锁文件都不碰（不制造"锁占了、但没预留成功"的
    # 半成品状态）。
    reserve_requests: list[tuple[str, int]] = []
    if args.reserve_multi is not None:
        if args.reserve is not None or args.section is not None:
            print("✗ --reserve-multi 不能与 --reserve/--section 同时使用（选一种方式）。")
            return 1
        try:
            reserve_requests = _parse_reserve_multi(args.reserve_multi)
        except ValueError as exc:
            print(f"✗ --reserve-multi 参数有误：{exc}")
            return 1
    elif args.reserve is not None:
        if args.section is None:
            print("✗ --reserve 必须同时指定 --section 一|四（工具不猜你要预留哪个分区的号）。")
            return 1
        if args.reserve <= 0:
            print(f"✗ --reserve 必须为正整数，收到 {args.reserve}。")
            return 1
        reserve_requests = [(args.section, args.reserve)]

    # 队列 #308 决策点 2：--domain 只对 §一 有意义（域字段范围红线仅 §一，
    # 见 design.md Non-Goals）；未随任何 §一 预留请求提供即用法错误，不静默
    # 忽略。
    if args.domain is not None and "一" not in {s for s, _ in reserve_requests}:
        print("✗ --domain 仅对 §一 预留请求生效，本次预留请求不含 §一（用法错误，"
              "不静默忽略该参数）。")
        return 1

    lock_path = _lock_path(args.file)
    # #197：以下"读判定→写"整段包进互斥临界区，防两个进程在同一窗口内都
    # 读到"无锁"、都写入成功、都相信自己持锁。
    try:
        with _acquire_mutex(lock_path):
            return _acquire_locked(args, lock_path, reserve_requests)
    except TimeoutError as exc:
        print(f"✗ {exc}——本次占锁放弃，请稍后重试（不代表锁被他人占用，"
              "只是内部互斥等待超时，理论上不应发生，出现即说明有异常并发压力）。")
        return 1


def _acquire_locked(
    args: argparse.Namespace, lock_path: Path, reserve_requests: list[tuple[str, int]],
) -> int:
    """`_acquire_mutex` 保护下执行的 acquire 逻辑，行为与改造前完全一致，
    仅多一步写后回读校验（#197：不信"写成功了"，CLAUDE.md §5 既有纪律）。"""
    existing = _read_lock(lock_path)
    if existing is not None:
        age = _age_minutes(existing)
        if age < STALE_MINUTES:
            print(f"✗ 占用中：{existing.get('who', '未知')}"
                  f"（{existing.get('note', '')}），"
                  f"{age:.0f} 分钟前开始持锁（<{STALE_MINUTES} 分钟视为有效）。")
            print("  本次请不要直接改队列文件——把要登记的内容先写进你自己的域接力文件，"
                  "注明「队列更新待补」，下次开工/收工时再回补。")
            return 1
        print(f"⚠ 发现陈旧锁（{existing.get('who', '未知')}，{age:.0f} 分钟前，"
              f"超过 {STALE_MINUTES} 分钟未释放，判定为异常退出遗留）——已接管。")

    now = _now()
    held_since = now.isoformat()

    # 队列 #230-1c：合并本次 acquire 进历史（无论后面是否走 --reserve、
    # 是否发生 reserve 失败回滚——"曾经 acquire 过"这件事本身就值得让下一
    # 位调用者看到），并计算"最近 120 分钟内还有哪些其它身份"供回显。
    prior_history = _prune_history(_read_history(lock_path), now)
    recent_others = _recent_entries(prior_history, now, RECENT_ACQUIRE_WINDOW_MINUTES)
    new_history = prior_history + [
        {"who": args.who, "note": args.note or "", "at": held_since}
    ]

    _atomic_write_json(
        lock_path, {
            "who": args.who, "note": args.note or "", "held_since": held_since,
            "history": new_history, "reserved": {}, "domains": {},
        }
    )

    # 写后回读校验（#197②）：互斥锁已确保本段不会与另一次 acquire 交叉
    # 执行，这里仍核验一次——既是"不信写成功了"的既有纪律，也对互斥锁
    # 实现本身出现意料外 bug 这层未知风险留一道网。
    verify = _read_lock(lock_path)
    if (verify is None or verify.get("who") != args.who
            or verify.get("held_since") != held_since):
        print("✗ 写入后回读校验未通过（占锁内容与预期不符）——本次占锁失败，请重试。")
        return 1

    current_content = _read_target_text(args.file)

    # 队列 #225：目标文件此刻内容存一份快照，release 时据此 diff 出本次
    # 持锁期间新增/修改的行，结构校验只对这些行生效。
    _write_snapshot(args.file, current_content)

    # 队列 #200：与"上次 release 时记录的内容"比对，检测两次合法
    # release/acquire 之间是否发生过绕锁直接改写。不阻断——协议〇.7 一贯
    # 是协作性质而非硬互斥（见模块文档），只回显+（默认队列文件时）留痕。
    lastknown = _read_lastknown(args.file)
    if lastknown is not None and current_content != lastknown:
        diff_summary = _summarize_content_diff(lastknown, current_content)
        print(
            f"⚠ 检测到目标文件在上次 release 之后被直接改写（未经本工具 "
            f"acquire/release，{diff_summary}）——可能绕过协议〇.7 锁保护写入，"
            "请核查改动是否符合预期（队列 #200）。"
        )
        if args.file == DEFAULT_TARGET:
            _record_bypass_detection(REPO_ROOT, args.file, args.who, diff_summary)

    print(f"✓ 已占锁：{args.who}（{args.note or '无备注'}）→ {lock_path.name}")

    if recent_others:
        others_desc = "、".join(
            f"{h['who']}（{h['age_minutes']:.0f} 分钟前，{h['note']}）" if h.get("note")
            else f"{h['who']}（{h['age_minutes']:.0f} 分钟前）"
            for h in recent_others
        )
        print(f"⚠ 最近 {RECENT_ACQUIRE_WINDOW_MINUTES} 分钟内还有其它身份 acquire 过本锁：{others_desc}")

    if reserve_requests:
        # 队列 #163/#185：直接分配并返回字面编号，同一次持锁窗口内原子
        # 回写高水位线——不再回显一个需要调用方自己 +1 的数（那正是
        # 2026-07-29 #162 撞号的成因：回显本身没错，人读的时候算错/抄错）。
        # 多个分区在同一次持锁窗口内依次预留（各分区在高水位线行里的号
        # 相互独立，见 SECTION_NUMBER_PATTERNS）；任一分区失败即整体回滚
        # （已成功预留的分区其高水位线不回退，允许留空洞，见协议〇.8）。
        reserved_map: dict[str, list[int]] = {}
        for section, count in reserve_requests:
            try:
                reserved_map[section] = _reserve_ids(args.file, section, count)
            except ReserveFailedError as exc:
                done = "、".join(reserved_map) or "无"
                print(f"✗ 预留取号失败（§{section}），本次 acquire 一并回滚（不留半成品锁；"
                      f"已成功预留的分区（{done}）高水位线不回退，允许留空洞）：{exc}")
                _write_released_marker(lock_path, args.who, args.note or "", held_since, history=new_history)
                return 1
        # 队列 #225 校验③：把本次预留的编号写回锁文件，release 时据此判定
        # "新增编号是否属于本次持锁期间实际预留过的集合"。
        # 队列 #308 决策点 2：--domain 声明随同写入（仅 §一 有意义，见上方
        # cmd_acquire 的用法校验）。
        domains_map: dict[str, str] = {}
        if args.domain is not None and "一" in reserved_map:
            domains_map["一"] = args.domain
        _atomic_write_json(
            lock_path, {
                "who": args.who, "note": args.note or "", "held_since": held_since,
                "history": new_history, "reserved": reserved_map, "domains": domains_map,
            }
        )
        nums = "；".join(
            "、".join(f"§{section} #{n}" for n in nums_list)
            for section, nums_list in reserved_map.items()
        )
        print(f"📍 已为你预留：{nums}")
        if domains_map:
            print(f"   域声明：{'；'.join(f'§{s}=[D:{d}]' for s, d in domains_map.items())}"
                  "（写行时请在状态列开头带上对应的 [D:...] 域字段）")
        print("   （顶部高水位线已同步回写；即使本次未写满，编号不复用、留空即可）")
        print("   改完请立刻 release。")
        return 0

    hwm = _read_high_water_mark(args.file)
    if hwm:
        print(f"📍 持锁瞬间高水位线：{hwm}——新行编号从此值 +1 续排，"
              "勿用 acquire 之前读到的旧值（见协议〇.7）。")
    print("  改完请立刻 release，不要跨整个 session 持有。")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock_path = _lock_path(args.file)
    existing = _read_lock(lock_path)
    if existing is None:
        print("（无锁，无需释放）")
        return 0
    if args.who and existing.get("who") != args.who:
        print(f"✗ 当前锁持有者是「{existing.get('who')}」，与你传入的「{args.who}」不同——"
              f"未释放（避免误传 --who 时顶掉别人的在办锁）。若确认对方已异常退出，"
              f"等其自然陈旧（{STALE_MINUTES} 分钟）由下一次 acquire 自动接管；"
              f"或确认后不带 --who 强制释放。")
        return 1

    # 队列 #225：锁定目标是默认队列文件时，release 前做四项结构校验——
    # 不通过则拒绝释放（锁保持占用，逼持有者原地修正后重试），不对其他
    # `--file` 目标生效（§一/§二/§三/§四 语义只对这份文件成立）。
    violations: list[str] = []
    if args.file == DEFAULT_TARGET:
        violations = _validate_release_structure(args, existing, REPO_ROOT)
    elif args.file == FOLLOWUP_README_TARGET:
        # 队列 #124 阶段二（design.md D1）：跟进信 README 两态语义结构性
        # 拦截，与上面那套队列专属校验各自独立、互不干扰。
        violations = _validate_followup_readme_release(_read_target_text(args.file), _read_snapshot(args.file))
    if violations:
        print(f"✗ release 被拒绝（{len(violations)} 项结构问题，锁保持占用，请修正后重试）：")
        for v in violations:
            print(f"  - {v}")
        return 1

    # 队列 #200：把"正式交还"的目标文件内容记为基准——下一次 acquire 据此
    # 判断这期间文件是否被绕过锁直接改写过。放在结构校验通过之后（不通过
    # 时不算真正 release，不应更新基准）。
    _write_lastknown(args.file, _read_target_text(args.file))

    # 改写为 released 标记而非 unlink（#121(a)）：Cowork 沙箱挂载对本文件
    # unlink 会返回 PermissionError（acquire 建文件正常，release 删不掉），
    # 改写规避了这个问题，且本地/CC 环境同样适用——不需要按环境分叉代码路径。
    # released 标记等价于"无锁"（见 _read_lock），下一次 acquire 当空锁立即成功。
    _write_released_marker(
        lock_path, existing.get("who", ""), existing.get("note", ""),
        existing.get("held_since", ""), history=existing.get("history", []),
    )
    print("✓ 已释放（改写为释放标记，未删除文件——沙箱环境亦可用）")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    lock_path = _lock_path(args.file)
    existing = _read_lock(lock_path)
    if existing is None:
        print("（无锁，可直接编辑）")
        return 0
    age = _age_minutes(existing)
    state = "有效" if age < STALE_MINUTES else "已陈旧（可接管）"
    print(f"占用方：{existing.get('who', '未知')}")
    print(f"备注　：{existing.get('note', '')}")
    print(f"已持锁：{age:.0f} 分钟（{state}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=DEFAULT_TARGET,
                        help=f"目标文件相对仓库根路径（默认 {DEFAULT_TARGET}）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_acquire = sub.add_parser("acquire", help="编辑前占锁")
    p_acquire.add_argument("--who", required=True, help="会话标识，如 'CC-QD-B'/'Cowork-财务专线'")
    p_acquire.add_argument("--note", default="", help="简短备注，便于其他会话看到占用原因")
    p_acquire.add_argument(
        "--reserve", type=int, default=None,
        help="队列 #163：直接预留 N 个字面编号并返回（须同时指定 --section），"
             "不再自己读高水位线 +1 续排",
    )
    p_acquire.add_argument(
        "--section", choices=sorted(SECTION_NUMBER_PATTERNS), default=None,
        help="--reserve 配套：要预留哪个分区的号（§一/§四 各自独立计数）",
    )
    p_acquire.add_argument(
        "--reserve-multi", nargs="+", default=None, metavar="SECTION:COUNT",
        help="队列 #185：一次性跨多分区预留（如 --reserve-multi 一:2 四:1），"
             "与 --reserve/--section 互斥",
    )
    p_acquire.add_argument(
        "--domain", choices=("机", "业"), default=None,
        help="队列 #308 决策点 2：预留 §一 编号时一并声明域（机制/环境类 或 "
             "业务场景类），随协议〇.10 并入审核门禁同一次交互完成；仅对本次"
             "预留请求中含 §一 的部分生效，§一 之外（如仅 §四）提供本参数视为用法错误",
    )
    p_acquire.set_defaults(func=cmd_acquire)

    p_release = sub.add_parser("release", help="编辑完立刻释放")
    p_release.add_argument("--who", default="", help="可选：校验释放的是自己占的锁")
    p_release.add_argument(
        "--mechanism-wip-cap", type=int, default=MECHANISM_WIP_CAP_DEFAULT,
        help=f"队列 #308 决策点 6：机制类可动 WIP 上限（默认 {MECHANISM_WIP_CAP_DEFAULT}，"
             "对齐协议〇.9 措施 C），超限仅提示不阻断",
    )
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="查看锁状态，无副作用")
    p_status.set_defaults(func=cmd_status)

    p_append_row = sub.add_parser(
        "append-row",
        help="队列 #258：追加一行到指定分区，插入位置/列数/裸竖线由工具保证",
    )
    p_append_row.add_argument(
        "--section", required=True, choices=sorted(SECTION_APPEND_CONTENT_COUNTS),
        help="目标分区（§一/§二/§四）",
    )
    p_append_row.add_argument(
        "--number", default=None,
        help="§一/§四 必填：行编号（字符串形式，通常来自 acquire --reserve 的返回值）；"
             "§二 不使用，不应提供",
    )
    p_append_row.add_argument(
        "--cell", action="append", default=[],
        help="按分区列序重复提供的字段值（不含首列编号）：§一 7 个"
             "（任务/领取方/输入指针/期望产出/状态/触碰区/登记）、§二 4 个"
             "（批次/文件清单/说明/状态，首个即批次号）、§四 3 个（事项/等谁/截止）",
    )
    p_append_row.set_defaults(func=cmd_append_row)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
