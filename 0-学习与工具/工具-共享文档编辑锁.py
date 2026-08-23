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
              🔴 **「不接受预拼好的整行字符串」这一句于 2026-08-23 被复核后
              维持**（队列 §一 #351 ⑵-b，Shao Peishen 拍板否决新增
              `--row-md`）。**被否的提案本身是有道理的**：人以「行」为单位
              思考、天然打竖线，而现接口要求手工拆成 N 个 `--cell`，这道
              转换本身就是错误来源（6 次复发里至少 2 次由它造成）。**否决
              的理由是代价更大**——`--row-md` 会新增第二条写入路径，而第二
              条路径正是 #164／#225／#258 那一族缺陷的滋生地。**改走退而
              求其次**：报错时直接给出一条修正后的完整命令行供复制，见
              `_arity_failure_message`。

  release ⑥  队列 §一/§四 行"暂缓结论"与跟进信 README 发送状态的交叉
              一致性校验——命中"**当前结论段**含暂不发/暂缓/压着/不发字样
              + 反引号 .md 文件名引用"的行，若该信在 README 中仍是终态
              `🆕 待发`（机制唯一认可的可发送标记），拒绝 release。治
              2026-08-06 01:30 UTC 真实误发（#150：队列行决定"暂不发"但未
              同步移出 README 的可发送标记，`ZhuopinFollowupDispatchDaily`
              照发，信不可撤回）。

队列 #324 ＋ §四 #58 ⑶（2026-08-17，openspec 变更包
editlock-hold-scope-and-wip-block，Shao Peishen 当日审 design 六个决策点
全按默认）：`release` 咽喉上的两处已实测失效同车修复——

  ⑥ 收窄  暂缓关键词的扫描面由"整个单元格"收窄为按 `━━━` 切出的**首段**
          （当前结论段）。队列单元格按「历史记录不追改」长期沉积多轮登记，
          把整格当作"这一行此刻的结论"会使误报率随沉积单调上升：2026-08-10
          §四 #52 那格 4062 字符／11 段，四个暂缓关键词**全部落在历史段**，
          ⑥ 却据此拒绝了一封当日刚获批准待发的信。同批**退休 ⑥ 的反向告警
          半边**（协议〇.9 措施 B 一进一出）。
  ⑨ 阻断  机制类可动 WIP 超上限由"提示不阻断"改为**拒绝 release**，带
          `--force-mechanism-wip` ＋ 行内 `WIP豁免：<理由>` 双条件逃生阀。
          成因＝观察周实测 6 次新立机制行 6 次越过提示（详见
          `_validate_release_structure` ⑨ 段）。**apply 当天起立刻见效**：
          存量 24／16 已超限，此后任何新建机制行的 session 都会当场撞上
          这道门——这是预期效果，不是回归。

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

队列 §四 #80（判据 J4，派单件 OP-0821-C，2026-08-21）：`--file` 指向仓库根
`CLAUDE.md` 时，`release` 前对**本次持锁窗口内新增的顶部进度条目**做一项
独立校验——条目含未闭合项措辞（词表见 `CLAUDE_PROGRESS_OPEN_ITEM_WORDS`）
却未点名任何队列行号即拒绝释放。逃生阀 `进度豁免：<理由>` 写在条目正文内
（理由同批落进锁的 `history` 留痕；空豁免不接受）。
**为什么加这一项**：「顶部进度段只留最近一批」这条人守规则 2026-08-09／
08-16 两次瘦身两次失效，5-6 天内超额长回、回涨速率由 3.4 KB/天升到
7.7 KB/天。根因不是执行力——顶部段**同时承担「进度记录」与「未闭合项的
唯一跨会话载体」两个职能**（SC2 那两条自己在正文里写着「本段是本任务仅有
的跨会话载体」），迁走即丢，于是执行的人每次都在同一处卡死、整段一起不迁。
CI 侧的 J1/J2/J3（`工具-CLAUDE进度段lint.py`）都是事后收拾，**本项是唯一
在源头阻止这个二职合一继续新增的那条**。条目切分由本模块的
`_claude_progress_entries` 唯一实现，lint 侧委托它，两处不各写一套。

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

#333（2026-08-12，openspec 变更包 `editlock-aibot-intake-reservation-
exemption`）：③预留归属校验此前未识别协议〇.10 ⑶ 早已定义的"企微机器人
收件登记路径豁免"（`queue_appender.py::_next_task_id` 走独立取号路径、
不经 `--reserve`），导致机器人 `release` 必被③拒绝、锁保持占用直到 30
分钟陈旧接管——三方（③校验／机器人不检查 returncode／协议〇.10 豁免）
各自按设计工作，问题出在组合上。修法：③新增豁免分支（见
`AIBOT_LOCK_WHO`/`AIBOT_INTAKE_TASK_PREFIX` 定义处与 `_validate_release_
structure` 文档），不是放宽校验，是让校验认得这条既有豁免。
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
from pathlib import Path, PurePosixPath

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
    # 队列 #366 / S4：跟进信闭环判据的权威实现（本文件、`工具-跟进闸查询.py`、
    # `aibot_service` 三处共用同一份）。与 queue_table 同一套引导与兜底惯例。
    from zhuopin_platform.shared_tools import followup_gate  # noqa: E402
else:
    followup_gate = None  # 隔离环境（测试把本脚本复制到无平台包的临时目录）
    class queue_table:  # type: ignore[no-redef]
        """隔离环境兜底桩——取值须与 zhuopin_platform.shared_tools.queue_table
        保持一致，见该模块。"""

        SECTION_COLUMN_COUNTS = {"一": 8, "二": 4, "四": 4}
        QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
        # 队列 #315：拆分后两份物理文件路径，隔离桩同样须与权威实现保持一致。
        QUEUE_MECHANISM_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
        QUEUE_BUSINESS_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

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
DEFAULT_TARGET = queue_table.QUEUE_PATH_REL  # 队列 #313：收拢自本地字面量；
# 队列 #315（apply，2026-08-11）：拆分后本路径转为纯指针文件，不再是权威
# 内容承载，但仍是"调用方未显式传 --file"这一信号的判据值——`args.file ==
# DEFAULT_TARGET` 即代表"面向队列系统本体"，触发下方的双文件路由逻辑，
# 与"显式 --file 指向其它共享文件（如跟进信 README）"完全不同的处理路径
# （后者行为不受本次改动影响，见 `_is_queue_system_target`）。
# 本模块自身持有一份局部绑定（而不是处处直接写 `queue_table.QUEUE_
# MECHANISM_PATH_REL`），与 `DEFAULT_TARGET` 收拢自 `queue_table.
# QUEUE_PATH_REL` 同一惯例——测试用例按既有模式 monkeypatch 本模块的
# 这几个名字即可隔离到临时目录，不需要同时 monkeypatch `queue_table`
# 模块本身（该模块被本进程内多处独立 import，各自持有互不相干的绑定）。
QUEUE_MECHANISM_PATH_REL = queue_table.QUEUE_MECHANISM_PATH_REL
QUEUE_BUSINESS_PATH_REL = queue_table.QUEUE_BUSINESS_PATH_REL
QUEUE_LOCK_ANCHOR = QUEUE_MECHANISM_PATH_REL  # design.md 决策点7：迁移期
# 两份物理队列文件共用同一把协作锁与同一个互斥原语——真正跨文件共享的
# 可变状态只有编号高水位线（决策点2：维持单一编号空间，只存机制文件），
# 若两份文件各自独立加锁，域机/域业两个并发 acquire 会各自进入临界区、
# 对高水位线产生真实竞态。"两份文件各自独立锁"这一优化留待真实使用数据
# 支持后再评估（design.md 决策点7 Open Questions 原文），本次选安全的
# 保守项。
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
# 队列 #324（2026-08-17，openspec 变更包 editlock-hold-scope-and-wip-block，
# design.md 决策点 1/2，Shao Peishen 当日选默认 (甲)）：⑥ 的暂缓关键词扫描
# 面由"整个单元格"收窄为"当前结论段"——队列单元格按「历史记录不追改」会
# 长期沉积多轮登记，把整格一视同仁当作"这一行此刻的结论"会使误报率随沉积
# 单调上升。2026-08-10 §四 #52 真实误报：该格 4062 字符、按 `━━━` 切出 11
# 段，头段仅 447 字符，四个暂缓关键词**全部落在历史段、头段一个都没有**，
# ⑥ 却把"历史里的暂缓"与"今天新起草的那封信"配成了一对并拒绝放行。
#
# 分隔符取 `━━━`（U+3013 重横线）——它是**现存文本里已经存在的**段落惯例，
# 不需要任何人回头改写历史即可识别。刻意**不复用** `_leading_status_segment`
# （⑤ 用）：那一个还会在「。」「——」处切断，对 ⑥ 太激进（一句话里写完
# "本信暂不发"很常见，切到句号前会把结论本身切掉）；两者判据目的不同，
# 各自独立实现，不互相牵动。
#
# 🔴 已知残余风险（design.md 决策点 2 原样声明，不掩饰）：本项目往 `━━━`
# 之后追加内容有**两种**形态——「`━━━ 以下为…原文 ━━━`」＝历史下压（新
# 结论在头段，本判据判对）；「`━━━ ➕ 20xx-xx-xx 并入…`」＝并入新子项
# （内容是新的、却在头段之后，本判据**判不到**）。即"决定暂缓某封信"若只
# 写在 `➕ 并入` 段里而头段完全没提，⑥ 会漏。评估为可接受且**刻意不加特
# 例**：加了就等于回到逐段扫描（design 决策点 1 的候选 (丙)），实测命中集
# 反而由 9 涨到 14（收窄变放宽）。这是惯例假设、不是机器保证。
CONCLUSION_SEGMENT_SEPARATOR = "━━━"

# 队列 #225：release 时对跨桌任务队列.md 做结构校验，仅当锁定目标是这个
# 默认队列文件时才跑（§一/§二/§三/§四 的语义只对它成立，--file 指向其他
# 共享文件时这套校验没有意义）。
ARCHIVE_GLOB = "跨桌任务队列-归档-*.md"
# 队列 #306：改为委托 zhuopin_platform.shared_tools.queue_table 的权威
# 常量，不再本地独立定义（原值 {"一": 8, "二": 4, "四": 4} 与其一致）。
SECTION_COLUMN_COUNTS = queue_table.SECTION_COLUMN_COUNTS
ROW_NUMBER_SECTIONS = ("一", "四")
# 队列 #333②：③预留归属校验对"企微机器人收件登记"路径开口——协议〇.10 ⑶
# 早已明文豁免这条路径的并入审核（"收件登记≠建任务，且机器无法判断并入"），
# 但 #308 落地的③预留归属校验从未识别这条既有豁免，导致机器人 release 必
# 被拒（锁卡满 30 分钟才被陈旧接管，见 #333 真实事故）。判据取协议〇.10 ⑶
# 自带的代理判据（who=企微机器人 且新增行任务列以该前缀开头），与
# `queue_appender.py::append_pending_task` 实际写入的行内容严格对应——不是
# 放宽校验，是让校验认得这条协议早已承认的合法路径；若这条豁免被人冒用
# （伪造 who 走机器人通道绕开并入审核），豁免立即失效由值周巡检对账时留意
# （协议〇.10 ⑶ 自带的失效条款，本判据不重复实现监测，只实现判据本身）。
AIBOT_LOCK_WHO = "企微机器人"
AIBOT_INTAKE_TASK_PREFIX = "企微反馈自动归档："
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
#
# 16 → 24（Shao Peishen 2026-08-19 两次拍板，《机制类可动 WIP 盘点-2026-08-18》
# §五 定夺 1 先答 (a) 定 20，同日 CC 实测报出差额后改定 24）。
#
# 🔴 **上调的真实理由不是"超限了就抬杠"，是这个上限与在办量之间已无余量**：
# 2026-08-19 实测可动 WIP ＝ **19**（加 🛑 前 23——同日按定夺 2(a) 给 #284／
# #170／#282／#122 四行加 `🛑` 首标记后降为 19），其中光"真在办"就有 15 行；
# 而排队待立的 4 条**各自对应一次真实事故或一个已确认的生产不可用缺陷**，
# **压着不立 ＝ 让那些事故保持可复发状态**，与措施 C 控风险的目的方向相反。
# 论证见该盘点件 §三。
#
# ⚠️ **为什么是 24 而不是盘点件推荐的 20——一处算术前提当天被实测推翻**：
# 盘点件 §五 写"真在办 15 ＋ 排队 4 ＝ 19，留 1 格余量"，**其前提是 A 类四行
# （#68／#234／#270／#279）已销号**；而定夺 3 答 (a) 把销号交给了下周值周巡检、
# **尚未执行 ⇒ 当天的 19 里仍含这 4 行**，四条新行全部立进来是 **19+4=23**，
# 按 20 会被 release 硬阻断。**故不是"又抬了一次杠"，是原推荐值建立在一个
# 尚未发生的前提上。** 24 ＝ 23 ＋ 1 格余量。
#
# 🔑 **随之而来的一件事，值周巡检须盯住**：A 类四行销号后本值应回落一档
# （23−4＝19 ⇒ 20 即够）。**若销号做完而本常量没跟着降，那就成了一个靠"忘了
# 收回"维持的上限** —— 这正是措施 C 要防的那类松弛。
#
# 24 → 22（2026-08-20，CC OP-0820-A，Shao Peishen 2026-08-19 答「摘 🛑 ＋ 销 A
# 类四行 ＋ 按回收条款降上限」(a)）：**上面那条回收条款已被兑现** —— A 类四行
# #68／#234／#270／#279 当日逐条复核后全部销号（**非照抄 2026-08-12～08-17 的前序
# 建议**，四行实证均已重跑；其中 #68③ 的卡点是直接查 Windows 任务计划实测
# ZhuopinCommitSweep 当日 State=Ready／LastTaskResult=0，而非引用 07-30 的旧体检
# 记录），同批摘掉 #282 的 🛑 首标记（该行 ⑴ 包已 apply、正在动，🛑「结构性不可
# 动」的原义不再成立，留着会让 WIP 判断持续偏松）。
#
# 🔴 **本次刻意不沿用上面那个预设的 20，改用销号后的实测值** —— 2026-08-19 的 20
# 之所以被推翻，正是因为它建立在「A 类四行已销号」这个尚未发生的前提上。**故本次
# 算式的三个数各自都有出处**：
#   N ＝ **21** —— 做完「摘 🛑 ＋ 销四行」之后，用本文件 `_count_mechanism_wip`
#     自身对两份队列真身实测（沿革：24 → 摘 🛑 后 25 → 销四行后 21）；
#   M ＝ **0** —— 排队待立但尚未落行的机制类行条数：08-19 排队的四条已取号落成
#     §一 #351-#354，08-20 拆件巡逻新建行 0 条，接力件「⏳ 队列更新待补」节无待补
#     机制行；
#   余量 ＝ **1** 格。
# **⇒ 22 ＝ 21 ＋ 0 ＋ 1。**
MECHANISM_WIP_CAP_DEFAULT = 22
# 子项 G（队列 #308 决策点 10）：跟进信串行原则闸——"前一封"发送状态属
# **闭环四态**之一即视为已闭环；新增行任一单元格含此逃生阀标记即放行但留痕。
#
# 🔴 队列 #366 / S4（2026-08-21）把这条判据从「只认 `📥` 一个前缀」改为
# 「闭环四态」，并收归 `zhuopin_platform.shared_tools.followup_gate` 权威实现。
# **这是在修一处真实的判据分裂，不是放宽门禁**：README 串行原则段 2026-08-18
# 起写的就是四态（`📥 已回件并回灌`／`✅ 无需回复`／`📨 已确认闭环`／
# `❌ 已作废`），而本文件一直只认第一个。代价是实测过的——质量部#7 形态为
# `✅ 无需回复`、按纪律闸早已打开，机器却不认，起草下一封时只能编一条
# `串行豁免：` 去绕过它，**等于拿逃生阀去绕它本来要拦的那件事**；根
# CLAUDE.md §5 把这条边界原样记了下来。判据分裂时，该改的是偏离书面纪律的
# 那一侧。
#
# 下方两个常量保留为模块级名字（既有测试与外部引用按名取值），取值一律从
# 权威模块取，隔离环境（无平台包）回落到与权威模块逐字一致的字面量。
FOLLOWUP_SERIAL_CLOSED_PREFIXES = (
    followup_gate.CLOSED_STATUS_PREFIXES if followup_gate is not None
    else ("📥 已回件并回灌", "✅ 无需回复", "📨 已确认闭环", "❌ 已作废")
)
# 保留单数名以兼容既有文案/测试引用；语义收窄为"闭环四态里最典型的那一个"，
# 只用于提示文案，**不再作为判定用的唯一前缀**。
FOLLOWUP_SERIAL_CLOSED_PREFIX = FOLLOWUP_SERIAL_CLOSED_PREFIXES[0]
FOLLOWUP_SERIAL_WAIVER_MARKER = "串行豁免："
# 队列 #366 / S4 桥二：拆件已完成但确有理由暂不转闭环态时的逃生阀。
FOLLOWUP_STATE_SYNC_WAIVER_MARKER = "转态豁免："
# 队列 #366 / S4 桥二：入信行的识别标记（与 `aibot_service.intake` 里
# `task_desc` 的固定前缀一致；那边改了这边就配不上，故两处都写明对方）。
FOLLOWUP_INTAKE_TASK_MARKER = "企微反馈自动归档"
FOLLOWUP_EXTERNAL_DOCS_POINTER_RE = re.compile(r"`(7-外部文档/[^`]+)`")


def _followup_status_is_closed(status_value: str) -> bool:
    """闭环四态判定的唯一入口（本文件内部用）。隔离环境无平台包时按同一份
    字面量前缀比对，行为与权威实现一致。"""
    if followup_gate is not None:
        return followup_gate.is_closed_status(status_value)
    normalized = status_value.replace("*", "").strip("*　 \t")
    return any(normalized.startswith(p) for p in FOLLOWUP_SERIAL_CLOSED_PREFIXES)
# 队列 §四 #58 ⑶（2026-08-17，openspec 变更包 editlock-hold-scope-and-wip-
# block，design.md 决策点 5，Shao Peishen 当日选默认 (c)）：⑨ 由非阻断提示
# 改为阻断后配套的逃生阀标记——完全复用 `串行豁免：` 既有范式（标记写在行
# 里、零新增写盘路径）。
#
# 🔴 **理由的唯一真源是行内标记，不是 CLI 参数**：`--force-mechanism-wip`
# 开关**刻意不携带理由文本**，只表达"我知道我在越过一条规则"这个显式意图；
# 理由必须写进本次新增那条机制行的状态列。命令行里的字符串是会话级的、随
# 窗口关闭即消失，而这条逃生阀要治的恰恰是"越过之后没人知道为什么"；写在
# 行里则进 git、被 `工具-队列结构lint.py` 与值周巡检看得见。
#
# 为何不让工具把理由自动追写进队列行（design 决策点 5 的选项 a）：那会给
# 编辑锁**新增一条自己改写队列正文的写盘路径**，而本项目刚被这类路径咬过
# 两次——#326 投递链路绕开编辑锁直接写 README 并自行 commit；#322 为编辑锁
# 加"删不掉就改名"退路，改名这个动作凭空造出一种没人回头看的文件形态，
# 企微群连响 17.1 小时。为一个逃生阀新增写盘路径，收益与风险不成比例。
#
# **监测方式**：`WIP豁免：` 在队列全文的出现次数可 grep 计数——若它开始批量
# 出现，说明上限本身定错了，应回 §四 #58 重议上限，而不是继续加豁免。
MECHANISM_WIP_WAIVER_MARKER = "WIP豁免："

# ── 判据 J4（队列 §四 #80 / 派单件 OP-0821-C）：根 CLAUDE.md 顶部进度段
#    新增条目时的未闭合项拦截。lint 侧的 J1/J2/J3 在
#    `工具-CLAUDE进度段lint.py`；**J4 才是治本的那条**——J1/J2/J3 都是事后
#    收拾，J4 在源头不让「顶部进度段兼任未闭合项载体」这件事再发生。
#
# 成因：「顶部进度段只留最近一批」这条人守规则两次瘦身两次失效，而根因
# 不是执行力——顶部段同时承担「进度记录」与「未闭合项的唯一跨会话载体」
# 两个职能，SC2 那两条自己在正文里写着「本段是本任务仅有的跨会话载体」，
# 迁走即丢。只要新增条目时就逼它点名一个队列行，这个二职合一就不再新增。
CLAUDE_PROGRESS_TARGET = "CLAUDE.md"

# 结构锚点：进度条目区 ＝ `> **当前进度**` 头行之后 → `📦` 迁移指针行之前。
# 🔴 **不能只靠「像条目的行」这个形状**——2026-08-21 实测，`📦` 迁移指针行
# 与「memory 层已收割并停用」元说明行在结构上与真进度条目**完全无法区分**
# （都是「`> **` ＋ 粗体标题 ＋（日期）」），裸正则数出 4 条而真值是 2 条。
CLAUDE_PROGRESS_HEADER_RE = re.compile(r"^>\s*\*\*当前进度\*\*")
CLAUDE_PROGRESS_POINTER_RE = re.compile(r"^>\s*\*\*📦")
# 🔴 两种前缀都要匹配：2026-08-21 两份输入件都因只匹配 `> **`（漏掉
# `> 🔴 **`）而把 12 条数成 15 条／9 条——两次都错、且错得看起来很确定。
CLAUDE_PROGRESS_ENTRY_RE = re.compile(r"^>\s*(?:🔴\s*)?\*\*")
CLAUDE_PROGRESS_DATE_RE = re.compile(r"[（(]20\d\d-\d\d-\d\d")
CLAUDE_PROGRESS_ROW_ID_RE = re.compile(r"#(\d{1,4})\b")

# 未闭合措辞词表。
# ⚠️ **只当筛子、不当判官**：2026-08-21 逐行读原文才发现它漏掉了「未结」
# 「未接线」两个说法（已补入）。**命中即要求补载体，未命中不代表安全**
# ——故 J4 只拦不放，不据此宣称「没命中即已闭合」。
CLAUDE_PROGRESS_OPEN_ITEM_WORDS = (
    "仍不做", "未执行", "留待", "留给", "未完成", "尚未", "阻塞", "下一轮",
    "待办", "待补", "未做", "如实登记", "未闭合", "悬置", "待定", "后续会话",
    "暂不", "未结", "未接线", "未部署",
)
# 逃生阀：完全复用 `串行豁免：`／`WIP豁免：` 既有范式——标记连同理由写在
# **条目正文里**（进 git、被 lint 与值周巡检看得见），release 额外把这条
# 理由追加进锁的 `history` 留痕。
CLAUDE_PROGRESS_WAIVER_MARKER = "进度豁免："


def _claude_progress_entries(text: str) -> list[tuple[int, str]]:
    """切出根 CLAUDE.md 顶部进度段的条目，返回 `[(行号, 条目正文), …]`。

    顶部段 ＝ 文件开头 → 第一条**独占一行**的 `---` 之前（该 `---` 是 §1 前
    的分隔线，本项目根 CLAUDE.md 没有 frontmatter）。条目区 ＝ 段内
    `> **当前进度**` 头行之后 → `📦` 迁移指针行之前；头行不存在时返回空表
    （结构不符即不判，不猜）。

    `工具-CLAUDE进度段lint.py::parse_structure_a` 委托本函数，两处不各写
    一套——同 `_table_data_rows` 自身 docstring 的既有原则。
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            lines = lines[:i]
            break

    header_idx = next(
        (i for i, ln in enumerate(lines) if CLAUDE_PROGRESS_HEADER_RE.match(ln)), None
    )
    if header_idx is None:
        return []
    pointer_idx = next(
        (i for i, ln in enumerate(lines)
         if i > header_idx and CLAUDE_PROGRESS_POINTER_RE.match(ln)),
        len(lines),
    )

    entries: list[tuple[int, str]] = []
    for i in range(header_idx + 1, min(pointer_idx, len(lines))):
        line = lines[i]
        if CLAUDE_PROGRESS_ENTRY_RE.match(line) and CLAUDE_PROGRESS_DATE_RE.search(line):
            entries.append((i + 1, re.sub(r"^>\s?", "", line)))
    return entries


def _is_claude_progress_target(file_arg: str) -> bool:
    """`--file` 是否指向仓库根 `CLAUDE.md`。归一化为绝对路径后比较，不只比
    字符串字面量——同 `_is_queue_system_target` 的既有教训（机器人常驻服务
    传绝对路径，字面量恒不相等会让判据永不触发、且零报错）。"""
    if file_arg == CLAUDE_PROGRESS_TARGET:
        return True
    try:
        return Path(file_arg).resolve() == (REPO_ROOT / CLAUDE_PROGRESS_TARGET).resolve()
    except OSError:
        return False


def _validate_claude_progress_open_item(
    current_text: str, snapshot_text: str,
) -> tuple[list[str], list[str]]:
    """判据 J4：本次持锁窗口内新增的顶部进度条目，若含未闭合措辞却未点名
    任何队列行号，拒绝 release。返回 `(违规说明列表, 逃生阀留痕文本列表)`。

    新增判定 ＝ 条目正文不在 acquire 快照的条目集合里（**按正文比对、不按
    行号**——上方插入一条会让所有既有条目行号整体下移，按行号比对会把整段
    历史条目误判成新增，与 `_validate_release_structure` 只对本次改动生效
    的既有口径一致）。

    逃生阀 `进度豁免：<理由>` 写在条目正文内即放行，但理由必须能被读出来
    ——写了标记却没写理由（标记后为空）仍判违规，不接受空豁免。
    """
    old_bodies = {body.strip() for _line_no, body in _claude_progress_entries(snapshot_text)}
    violations: list[str] = []
    waiver_notes: list[str] = []

    for line_no, body in _claude_progress_entries(current_text):
        if body.strip() in old_bodies:
            continue  # 历史条目不追溯
        hits = [w for w in CLAUDE_PROGRESS_OPEN_ITEM_WORDS if w in body]
        if not hits:
            continue

        preview = body[:60].replace("\n", " ")
        if CLAUDE_PROGRESS_WAIVER_MARKER in body:
            reason = body.split(CLAUDE_PROGRESS_WAIVER_MARKER, 1)[1].strip()
            reason = re.split(r"[。\n]", reason, maxsplit=1)[0].strip()
            if not reason:
                violations.append(
                    f"第 {line_no} 行新增的进度条目写了「{CLAUDE_PROGRESS_WAIVER_MARKER}」"
                    f"但未写明理由——空豁免不接受，理由必须写在条目正文里：{preview}…"
                )
                continue
            waiver_notes.append(f"{CLAUDE_PROGRESS_WAIVER_MARKER}{reason}（第 {line_no} 行）")
            print(f"✓ 检测到进度豁免声明，已放行：{reason}")
            continue

        if CLAUDE_PROGRESS_ROW_ID_RE.search(body):
            continue

        violations.append(
            f"第 {line_no} 行新增的进度条目含未闭合项措辞"
            f"（命中「{'」「'.join(hits[:3])}」）但未点名队列行，不得只写进 "
            f"CLAUDE.md 顶部。请先立队列行并在条目内点名其行号（`#N`）；"
            f"确属无须承接的，写「{CLAUDE_PROGRESS_WAIVER_MARKER}<理由>」放行：{preview}…"
        )
    return violations, waiver_notes


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


def _is_queue_system_target(file_arg: str) -> bool:
    """`file_arg` 是否为"未显式覆盖，面向队列系统本体"这一信号值（队列
    #315）。为 True 时，acquire/release/status 走双文件路由；为 False 时
    （显式 `--file` 指向其它共享文件，如跟进信 README）行为完全不受本次
    改动影响。

    队列 #315（apply 中途追加，Shao Peishen 2026-08-11 现时风险提醒）：
    字符串字面量相等（`file_arg == DEFAULT_TARGET`，比较的是相对路径）只
    覆盖"调用方压根没传 --file"这一种情形。企微机器人常驻服务
    （`SubprocessQueueEditLock`）为跨 checkout 稳定，构造的是一个绝对路径
    传给 --file——字面量恒不相等，双文件路由永不触发，机器人这把锁与人类
    会话默认拿的锁分别锚定两个不同判据，互相看不见（"锁域分裂"，协议〇.7
    的保护在迁移期实际失效）。改为：字面量相等仍走最快路径；否则把
    `file_arg` 归一化解析为绝对路径，与 `DEFAULT_TARGET`／机制文件／业务
    文件三者的绝对路径逐一比较——命中任一个都判定为"面向队列系统本体"，
    不论调用方传来的是相对写法、绝对写法，还是（迁移期）仍指着旧指针文件
    这三种历史写法中的哪一种。文件尚不存在时 `Path.resolve()`
    不要求存在，纯字符串层面归一化，不受"文件还没创建"影响。"""
    if file_arg == DEFAULT_TARGET:
        return True
    try:
        resolved = Path(file_arg).resolve()
    except OSError:
        return False
    for candidate in (DEFAULT_TARGET, QUEUE_MECHANISM_PATH_REL, QUEUE_BUSINESS_PATH_REL):
        if resolved == (REPO_ROOT / candidate).resolve():
            return True
    return False


def _iter_queue_paths() -> list[str]:
    """本模块版本的"遍历两份队列文件路径"——读本模块顶部的局部绑定
    （`QUEUE_MECHANISM_PATH_REL`/`QUEUE_BUSINESS_PATH_REL`），不直接调
    `queue_table.iter_queue_paths()`，使测试用例按既有 `DEFAULT_TARGET`
    monkeypatch 惯例也能隔离这两个路径到临时目录（见两常量定义处注释）。
    """
    return [QUEUE_MECHANISM_PATH_REL, QUEUE_BUSINESS_PATH_REL]


def _resolve_queue_path_for_domain(domain: str) -> str:
    """同上，本模块版本的按域解析——语义与 `queue_table.resolve_queue_path`
    一致（非法域值 fail-loud），只是读本模块的局部绑定。"""
    if domain == "机":
        return QUEUE_MECHANISM_PATH_REL
    if domain == "业":
        return QUEUE_BUSINESS_PATH_REL
    raise ValueError(f"未知域值 {domain!r}，仅接受 \"机\"／\"业\"（不静默回退任一份文件）")


def _resolve_append_target(section: str, domain: str | None) -> tuple[str, bool]:
    """`append-row` 实际写入哪份物理文件（队列 #315 决策点3/5）。

    返回 `(目标路径, 是否使用了向后兼容默认值)`——§一/§二 按域路由到对应
    文件，§四 恒定写机制环境文件（该分区体量小、不纳入域字段范围，见
    #308 design.md Non-Goals，本次拆分沿用不改）。

    **迁移期妥协（apply 阶段发现，design.md 原定"未声明域 MUST 拒绝"在此
    处放宽，不是纸面推演）**：§一/§二 未显式传 `--domain` 时不 fail-loud，
    改为默认落机制环境文件并由调用方在返回值第二项拿到"用了默认值"这个
    信号自行决定是否提示——本机同一时刻有大量并发 session 使用尚未加
    `--domain` 参数的既有 opener/定时任务 prompt，若立即改为强制拒绝，
    会在部署的瞬间让所有这些在途调用当场失败。字段本身（`[D:机/业]`）
    仍需人工在状态列内正确书写，本函数只决定"写去哪个物理文件"这一层，
    与内容是否诚实是两回事。"""
    if section == "四":
        return QUEUE_MECHANISM_PATH_REL, False
    resolved_domain = domain or "机"
    return _resolve_queue_path_for_domain(resolved_domain), domain is None


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


def _detect_shadow_copy(target: str) -> str | None:
    """幽灵副本漂移检测（队列 #315 决策点5，子项⑥，直接承接 2026-08-10
    #321 真实事故）。

    `REPO_ROOT` 恒定按 `git rev-parse --git-common-dir` 解析到主工作区
    （模块文档已述），但本脚本自身当前运行所在的 worktree——若正巧不是
    主工作区——很可能在 `<该 worktree 根>/<target>` 这个相对路径下也存在
    一份物理不同的文件（同一份仓库内容的另一 checkout）。#321 事故正是
    "锁 CLI 恒定写主工作区，通用 Edit 工具按 worktree 本地路径改"两者操作
    了不同物理文件、其中一次编辑变成谁也看不到的幽灵。

    只读检测：若当前脚本所在 worktree 根与 `REPO_ROOT` 物理不同
    （`os.path.samefile`，处理"当前就在主工作区"这一正常情形，不误报），
    且该 worktree 本地存在同相对路径的文件、且内容与 `REPO_ROOT` 下的权威
    文件不一致，返回一句可读的警告文案；否则返回 `None`。不自动删除、
    覆盖或合并任何一方内容（同 #322/`sweep-ff-sync-batch-reorder` 已确立
    的"止血不硬解"哲学）。
    """
    script_dir = Path(__file__).resolve().parents[1]
    if script_dir == REPO_ROOT:
        return None
    try:
        if script_dir.samefile(REPO_ROOT):
            return None
    except OSError:
        pass  # 两者之一不存在时 samefile 会抛错——按"不同"处理，继续往下判

    local_path = script_dir / target
    if not local_path.exists():
        return None
    authoritative_path = _target_path(target)
    try:
        local_content = local_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        authoritative_content = authoritative_path.read_text(encoding="utf-8")
    except OSError:
        authoritative_content = ""
    if local_content == authoritative_content:
        return None
    return (
        f"⚠️ 检测到本地影子副本：{local_path} 与权威文件 {authoritative_path} "
        "内容不一致。\n"
        "   你的编辑器/Edit 工具若正在操作前者，改动不会被本工具看到，也不会被\n"
        "   release 校验，极可能造成幽灵副本（同 2026-08-10 #321 事故）。\n"
        "   请改为直接编辑绝对路径指向的文件，或改用 append-row 子命令写入。"
    )


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


def _reserve_ids(
    target: str, section: str, count: int, *, extra_collision_texts: list[str] | None = None,
) -> list[int]:
    """在持锁窗口内原子完成"读高水位线→分配 count 个连续编号→回写高水位
    线"，返回分配到的字面编号列表（升序，供调用方直接使用，不需要再 +1）。

    只信高水位线行本身，**不**回落扫描表格内可见最大行号（那正是 fail-loud
    要拒绝的替代路径——见 `ReserveFailedError`）。未使用完的预留号允许留
    空洞（协议〇.8：编号永不复用），本函数不做任何"释放未用编号"的操作，
    调用方也不需要。

    `extra_collision_texts`（队列 #315 决策点2）：拆分为双文件后，编号
    空间仍单一、高水位线仍只存机制环境文件，但 §一 的可见行分散在两份
    物理文件里——单纯核对 `target` 自身内容不够，会漏掉"该编号已被分配
    在另一份文件里"这种情形。调用方（`cmd_acquire`）在队列系统模式下传入
    另一份文件此刻的正文，本函数把两者的 §{section} 可见编号合并后再做
    碰撞检测，`target` 自身仍是唯一被实际改写（写回高水位线）的文件。
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
    for extra_text in extra_collision_texts or []:
        live_numbers |= {
            int(cells[0])
            for _, cells in _table_data_rows(_split_live_sections(extra_text).get(section, ""))
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


def _shell_quote(value: str) -> str:
    """把字段值包成一个可直接粘进命令行的双引号参数。只做最小必要转义
    ——目标是"可复制"，不是"覆盖所有 shell 方言"。"""
    escaped = value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))
    return chr(34) + escaped + chr(34)


def _arity_failure_message(
    section: str, number: str | None, cells: list[str], expected: int,
) -> str:
    """队列 §一 #351 ⑵-a：arity 失败时**顺带**扫一遍裸竖线，把两条诊断合并。

    🔴 **这是本项目"守卫被自己前面那道检查遮蔽"的教科书案例**：`len(cells)
    != expected` 的 arity 检查排在裸竖线检查之前且失败即 raise，而裸竖线最
    高频的形态——漏写 `--cell` 分隔符、竖线连同下一列内容粘进上一个 cell
    ——**必然同时使 cell 数变少 ⇒ arity 先失败 ⇒ 裸竖线检查永不执行**。
    作者看到的诊断是"收到 N 个"，指向"数数"；真因是那根竖线。这就是
    #164／#225／#258 装了守卫却仍在 2026-08-19 第 6 次复发的机制解释。
    （#351 行内自带的证伪命令已跑，实测 `True`，断言成立。）

    ⑵-b（新增 `--row-md` 直传整行 markdown）**已由 Shao Peishen 2026-08-23
    拍板否决**，改走本函数这条"退而求其次"：报错时直接给出一条修正后的
    完整命令行供复制。理由是第二条写入路径正是 #164／#225／#258 那一族缺陷
    的滋生地，而模块 docstring L116「不接受预拼好的整行字符串」是刻意定的。
    """
    base = f"§{section} 需要 {expected} 个 --cell（不含编号列），收到 {len(cells)} 个"
    piped = [i for i, cell in enumerate(cells, start=1) if _cell_has_bare_pipe(cell)]
    if not piped:
        return base  # 纯数数问题，不添噪音

    shown = "、".join(f"第 {i} 个" for i in piped)
    merged = (
        f"{base}；且 {shown} --cell 内含裸竖线「|」"
        f"——**极可能是漏写了 `--cell` 分隔符、把两列粘成了一列**"
        f"（这是裸竖线最高频的形态，也是 arity 与裸竖线两条诊断此前互相遮蔽的原因）。"
    )

    # 尝试恢复原意：按裸竖线拆开重数。只在**恰好**等于预期列数时才给命令行
    # ——宁可少给，不给一条错的。
    recovered = [part.strip() for cell in cells for part in cell.split("|")]
    recovered = [part for part in recovered if part]
    if len(recovered) != expected:
        return merged + " 按裸竖线拆分后仍不等于预期列数，无法可靠恢复原意，故不给修正命令行。"

    parts = ["python 0-学习与工具/工具-共享文档编辑锁.py append-row", f"--section {section}"]
    if number is not None:
        parts.append(f"--number {number}")
    parts.extend(f"--cell {_shell_quote(part)}" for part in recovered)
    hint = ("按上述成因恢复出的完整命令行"
            "（**请核对后再执行，工具不会自动跑它**）：")
    return merged + chr(10) + "  " + hint + chr(10) + "  " + " ".join(parts)


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
        raise AppendRowFailedError(_arity_failure_message(section, number, cells, expected))
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


def _append_row_ownership_violation(args: argparse.Namespace) -> str | None:
    """队列 §一 #351 ⑴：`append-row` 的锁归属校验。返回拒绝文案；放行返回 None。

    🔴 **成因是一次真实事故，形态很值得记住**（2026-08-18，12 分钟内触发两次）：
    `acquire` / `append-row` / `release` 被打包成一条命令、中间不查退出码——
    `acquire` **已被正确拒绝**（锁在别人手上），而脚本照跑照写，**在他人持锁
    期间写入两次**。`acquire` 与 `release` 两侧都校验归属，**唯独中间真正写盘
    的这个不校验**；那道被绕过的门禁其实工作正常，只是没人拦住它后面那一步。

    ⇒ 所以「只在 `--who` 与持锁人不符时拒绝」是不够的：**那次调用根本没有
    `--who` 可比**。`--who` 缺失同样必须拒绝——工具无法证明调用方是持锁人，
    就不能替它假定。

    **边界（刻意不做的事）**：无有效锁时**不阻断**，只打印一行提示。协议〇.7
    一贯是协作性质而非硬互斥，opener §〇.7 明文「不强制所有新行都必须走
    `append-row`，直接在编辑器里手写整行仍是允许的」。把 `append-row` 变成
    「必须先持锁」属**改变全项目口径**（CLAUDE.md §5 机制类门槛第①条），须
    另走 openspec。**本项要修的是「锁归属不校验」，不是「无锁写入」。**
    """
    lock_path = _lock_path(
        QUEUE_LOCK_ANCHOR if _is_queue_system_target(args.file) else args.file
    )
    existing = _read_lock(lock_path)
    if existing is None or _age_minutes(existing) >= STALE_MINUTES:
        # 无锁／已释放／已陈旧——陈旧锁等价于无锁，与 acquire 的既有接管口径一致。
        print("ℹ 本次为无锁写入（目标当前无有效锁）——协议〇.7 允许，但改队列前"
              "先 acquire 仍是既有纪律。")
        return None
    holder = existing.get("who", "未知")
    who = getattr(args, "who", None) or ""
    if who == holder:
        return None
    if not who:
        return (f"目标当前被「{holder}」持锁（{existing.get('note', '') or '无备注'}），"
                f"而本次 append-row 未传 --who，工具无法证明你就是持锁人 ⇒ 拒绝写入。"
                f"若你就是持锁人，加 `--who {holder}` 重试；"
                f"若不是，请勿在他人持锁期间写入（2026-08-18 真实事故：acquire 已被"
                f"正确拒绝、脚本照跑照写，12 分钟内在他人锁下写入两次）。")
    return (f"目标当前被「{holder}」持锁（{existing.get('note', '') or '无备注'}），"
            f"与你传入的「{who}」不同 ⇒ 拒绝写入。"
            f"若确认对方已异常退出，等其自然陈旧（{STALE_MINUTES} 分钟）后重试。")


def cmd_append_row(args: argparse.Namespace) -> int:
    # 队列 #315 决策点3/5：队列系统模式下按 --domain 路由到对应物理文件
    # （§四恒定机制环境文件，见 `_resolve_append_target`）；显式 --file
    # 覆盖时（罕见，主要用于测试/特殊场景）原样使用，不做路由。
    if _is_queue_system_target(args.file):
        resolved_target, used_default = _resolve_append_target(args.section, args.domain)
        if used_default:
            print(f"ℹ 未显式声明 --domain，按向后兼容默认值写入机制环境文件"
                  f"（{resolved_target}）——建议此后显式传 --domain 机|业，"
                  "见队列 #315 决策点3/5。")
        args = argparse.Namespace(**vars(args))
        args.file = resolved_target

    # 队列 §一 #351 ⑴：锁归属校验——放在最前，锁不归你就什么都不做。
    ownership_problem = _append_row_ownership_violation(args)
    if ownership_problem:
        print(f"✗ {ownership_problem}")
        return 1

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

    # 队列 §一 #351 ⑶⑸：§二 专属的两条写入前校验——文件清单路径格式、
    # 批次号前缀查重。两者都是"写入即拒绝"，取代此前"事后读 sweep 日志才
    # 发现"（⑶）与"完全无人校验"（⑸）。
    if args.section == "二":
        queue_texts = {p: _read_target_text(p) for p in _iter_queue_paths()}
        # 目标不在队列系统内（显式 --file 覆盖）时，至少把它自己算进来。
        if args.file not in queue_texts:
            queue_texts[args.file] = text
        section_two_problems = _file_list_path_violations(parsed_cells, REPO_ROOT)
        collision = _batch_prefix_collision(parsed_cells[0], queue_texts)
        if collision:
            section_two_problems.append(collision)
        if section_two_problems:
            print(f"✗ §二 写入被拒绝（{len(section_two_problems)} 项，未修改目标文件）：")
            for problem in section_two_problems:
                print(f"  - {problem}")
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
            if _followup_status_is_closed(prior_status):
                continue  # 前一封已闭环（闭环四态，队列 #366 / S4）
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
                f"发送状态为「{prior_status}」尚未闭环，请先据实把它改为闭环四态"
                f"之一（{'／'.join(FOLLOWUP_SERIAL_CLOSED_PREFIXES)}），或在本行内写明"
                f"「{FOLLOWUP_SERIAL_WAIVER_MARKER}〈理由〉」：{preview}"
            )

    return violations


def _leading_conclusion_segment(cell_text: str) -> str:
    """单元格的「当前结论段」——按 `━━━` 切分后的首段（队列 #324 决策点 2）。

    单元格不含 `━━━` 时返回整格，行为与收窄前逐字一致（既有短单元格不受
    本次改动影响）。与 `_leading_status_segment()`（⑤ 用）是两条独立判据，
    切法不同、互不复用，理由见 `CONCLUSION_SEGMENT_SEPARATOR` 定义处。
    """
    idx = cell_text.find(CONCLUSION_SEGMENT_SEPARATOR)
    if idx == -1:
        return cell_text
    return cell_text[:idx]


def _row_hold_language_status(cells: list[str], section: str) -> tuple[bool, str | None]:
    """判定一个 §一/§四 行是否"点名了跟进信且结论为暂缓"（队列 #258 正向
    Requirement）：**当前结论段**（§一 状态列 cells[5]／§四 无独立状态列，
    回落事项列 cells[1]；两者均按 `━━━` 取首段，见
    `_leading_conclusion_segment`）含暂缓关键词，且行内（§一：cells[3]输入
    指针+cells[6]触碰区，**整格不收窄**；§四：cells[1]事项的**同一首段**）
    能提取出一个反引号包裹的 `.md` 文件名引用。返回
    (是否命中暂缓关键词, 提取到的文件名 basename 或 None——未提取到文件名
    时第二个返回值为 None，调用方据此判定"仅关键词无文件名不触发"）。

    队列 #324（2026-08-17）收窄了扫描面，两处**不对称是刻意的**（design.md
    决策点 3，有实测支撑，非疏漏）：
    - §四 的关键词与文件名本就同在 cells[1] 一格，只收窄其一会自相矛盾，
      故同步收窄到首段；
    - §一 的文件名来自 cells[3]（输入指针）与 cells[6]（触碰区）两列，这两
      列**不沉积历史**（无 `━━━`），不是本次误报的成因；收窄它们不解决任何
      已知问题，却会削掉 #150 那一类唯一的真命中路径（实测 9 次命中的 §一
      文件名 9/9 全部来自 cells[3]）。`cells[6]` 虽实测零贡献也不删——
      "实测零贡献"不等于"设计上不该有"，删它属于拿快照当规律。
    """
    if section == "一":
        status_text = _leading_conclusion_segment(cells[5] if len(cells) > 5 else "")
        filename_sources = [cells[3] if len(cells) > 3 else "", cells[6] if len(cells) > 6 else ""]
    elif section == "四":
        segment = _leading_conclusion_segment(cells[1] if len(cells) > 1 else "")
        status_text = segment
        filename_sources = [segment]
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
    `ZhuopinFollowupDispatchDaily` 唯一认可的可发送标记）拒绝 release。

    🔴 **反向告警半边已于 2026-08-17 退休**（队列 #324，openspec 变更包
    `editlock-hold-scope-and-wip-block`，协议〇.9 措施 B 的一进一出）：原
    `elif` 分支在 README 已是"已推送"类终态而队列文本仍称暂缓时打印告警。
    删除的三条理由——① **它设计上就会对自己承认合法的写法报警**：现网唯一
    命中是 §一 #150，而 #150 恰恰是本能力 spec 自己明文列为合法的那一种
    （事故后新增文本、如实记录"本应暂缓却已被机制误发"的经过）；一条只在
    合法写法上响的规则，产出的不是约束是噪音。② 它正属 §四 #58（2026-08-17
    复评）刚判定"信息量为零"的非阻断提示形态，而本变更包同批正把 ⑨ 从这一
    形态里拿掉——留着同形态存量，退休制在同一个包里就自相矛盾了。③ 风险
    不对称：正向拦的是"照发一封已决定暂缓的信"（对外、不可撤回、有
    2026-08-06 01:30 UTC 真实事故），反向管的只是"队列文本滞后于 README"
    （纯内部、可事后改、无外部后果）。**不新增替代守卫**——该情形此后由值
    周巡检对账（既有职责，skill `zhuopin-queue-audit`）承接。
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
        # 反向情形（status 为"已推送"类终态）此处**刻意不做任何事**——既不
        # 拒绝也不打印，见本函数文档的退休说明（队列 #324，2026-08-17）。
    return violations


# ---------------------------------------------------------------------------
# 队列 #366 / S4 桥二：回灌完成 ⇒ 强制 README 转态
# ---------------------------------------------------------------------------

def _followup_intake_records(queue_text: str, queue_file: str) -> list:
    """从一份队列文件的 §一 里取出全部「企微反馈自动归档」入信行。

    🔴 逐份解析后合并（调用方负责），**不得先把多份文本拼接再解析一次**
    ——`_split_live_sections` 按标题定位、同名 label 后写覆盖先写，拼接会把
    第一份的 §一 静默顶掉（队列 #312 缺口一踩过一模一样的坑，症状是"结果
    看起来很正常，只是少了一半"）。
    """
    if followup_gate is None:
        return []
    records = []
    section_one = _split_live_sections(queue_text).get("一", "")
    for _, cells in _table_data_rows(section_one):
        if len(cells) < 6 or FOLLOWUP_INTAKE_TASK_MARKER not in cells[1]:
            continue
        m = FOLLOWUP_EXTERNAL_DOCS_POINTER_RE.search(cells[3])
        if not m:
            continue
        status_value, _, _ = _parse_status_domain_fields(cells[5])
        records.append(followup_gate.IntakeRecord(
            row_id=cells[0],
            queue_file=queue_file,
            archived_filename=m.group(1).rsplit("/", 1)[-1],
            dismantled=(status_value == "done"),
        ))
    return records


def _followup_letter_records(readme_text: str) -> list:
    """README「现有跟进信清单」的行 → `followup_gate.LetterRecord`。
    复用 `_followup_readme_rows`／`FOLLOWUP_TARGET_FILE_RE` 两处既有实现。"""
    if followup_gate is None:
        return []
    records = []
    for _, cells, status_col_index in _followup_readme_rows(readme_text):
        topic_cell = cells[3] if len(cells) > 3 else ""
        m = FOLLOWUP_TARGET_FILE_RE.search(topic_cell)
        records.append(followup_gate.LetterRecord(
            number=cells[0] if cells else "?",
            target_filename=m.group(1) if m else None,
            status=cells[status_col_index],
        ))
    return records


def _followup_readme_rows_indexed(text: str) -> list[tuple[int, list[str], int]]:
    """同 `_followup_readme_rows`，但返回**物理行号**而不是行文本——写回时
    需要它。两者共用同一套表头/分隔行判定，此处不另立判据。"""
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
    rows: list[tuple[int, list[str], int]] = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= status_col_index:
            continue
        rows.append((i, cells, status_col_index))
    return rows


def _build_reply_closed_status(
    previous_status: str, intake_ids: list[str], channel: str, today: str,
) -> str:
    """桥二写进状态列的新值。

    形态与桥一的第九态完全对齐：**新前缀在前、原状态原样接在后**。原状态
    不删的理由同桥一——「这封信何时推送／回件何时到达」在这一格之外没有任何
    副本，而覆盖式写入会把它弄丢。

    日期用**本机本地日期**（根 CLAUDE.md §5 写侧硬规则：写进文档的日期一律
    本机当场取，不用 UTC 日期、不估算）。
    """
    ids = "／".join(f"§一 #{i}" for i in intake_ids)
    return (
        f"{FOLLOWUP_SERIAL_CLOSED_PREFIX} {today}"
        f"（S4 桥二自动转态：{ids} 已 `[S:done]`，配对通道 `{channel}`；"
        f"本次由机器代写，未经人工逐字确认——如与事实不符请当场改回并记因）"
        f"　━━━　原状态 ━━━　{previous_status}"
    )


def _machine_write_followup_readme(new_text: str, who: str, note: str) -> str | None:
    """占跟进信 README 的编辑锁做一次机器写入；成功返回 None，否则返回原因。

    🔴 **为什么必须自己占一次锁**：桥二挂在**队列系统**目标的 release 上，
    此刻持有的是队列那把锁，README 是另一个目标、另一把锁。不占就写，正是
    协议〇.7 要禁的裸改——而且下一次有人 acquire README 时，#200 绕锁检测会
    如实把它报成「被直接改写过」，等于我们自己制造了一条假警报。

    锁被别人占用时**不抢、不等**：返回原因，由调用方转成一条 release 违规
    （fail-loud）。桥二的价值是"人不必手写状态列"，不是"无论如何都要写成"。
    """
    lock_path = _lock_path(FOLLOWUP_README_TARGET)
    try:
        with _acquire_mutex(lock_path):
            existing = _read_lock(lock_path)
            if existing is not None and _age_minutes(existing) < STALE_MINUTES:
                return (
                    f"README 编辑锁被「{existing.get('who', '未知')}」占用中"
                    f"（{existing.get('note', '')}，{_age_minutes(existing):.0f} 分钟前）"
                )
            now = _now()
            held_since = now.isoformat()
            history = _prune_history(_read_history(lock_path), now) + [
                {"who": who, "note": note, "at": held_since}
            ]
            _atomic_write_json(lock_path, {
                "who": who, "note": note, "held_since": held_since,
                "history": history, "reserved": {}, "domains": {},
                "dirty_at_acquire": None,
            })
            try:
                path = _target_path(FOLLOWUP_README_TARGET)
                path.write_text(new_text, encoding="utf-8")
                # 写后回读（#197 纪律：不信"写成功了"）
                if path.read_text(encoding="utf-8") != new_text:
                    return "写后回读校验未通过（落盘内容与预期不符）"
                # #200 基准同步：不更新它，下一次 acquire 会把这次合法写入
                # 误报成"绕过锁直接改写"。
                _write_lastknown(FOLLOWUP_README_TARGET, new_text)
            finally:
                _write_released_marker(
                    lock_path, who, note, held_since, history=history,
                )
    except TimeoutError as exc:
        return f"内部互斥等待超时：{exc}"
    except OSError as exc:
        return f"写入失败：{exc}"
    return None


def _auto_sync_followup_reply_state(
    queue_texts: dict[str, str], repo_root: Path, waiver_sources: list[str], who: str,
) -> tuple[list[str], list[str]]:
    """S4 桥二（`OP-0823-D` 改判）：**拆件完成了，机器就把 README 转闭环态。**

    ## 相对改判前的真正增量

    改判前本函数只**校验**人有没有改（不改就 release 不掉）。现在改成
    **由机器代写**：人只需把 §一 入信行的状态字段改成 `[S:done]`——那就是
    「我回灌完了」这句声明本身——不必知道是哪封信，也不必手写状态列。

    🔴 **声明动作没有新增语法**：`[S:done]` 本来就是拆件回灌完成的既有记法。
    另造一个 `回灌完成：` 标记，等于让人多记一条规则去说一件他已经说过的事。

    ## 写不成时仍然拦

    README 锁被占、写盘失败 ⇒ 返回违规、拒绝 release（锁保持占用）。
    **机器代写是为了省掉人的手工步骤，不是为了在失败时假装什么都没发生。**

    ## 逃生阀

    本次持锁改动里任一处写明 `转态豁免：〈理由〉` ⇒ 既不写也不拦，打印留痕。

    ## 已知边界（**必须随文案一起说出去，不能让人以为零违规＝全同步**）

    配对只走两条**确定**通道（见 `followup_gate.find_unsynced_letters`）：
    stem 逐字相等，与桥一写下的第九态溯源回指。桥一没跑成的那些纯文字回件
    两条都对不上 ⇒ 本函数对它们零输出，仍需人手工转态。

    返回 `(violations, notes)`。
    """
    if followup_gate is None:
        # fail-loud：不静默跳过。真实环境里这条永远不该出现——CI 的
        # `queue-structure-lint` 有一条断言专盯"权威模块可 import"（#313 范式，
        # 本次已扩到 followup_gate），它红了才轮得到这里。
        print("⚠ 未能加载 zhuopin_platform.shared_tools.followup_gate，"
              "S4 桥二（回灌⇒README 转态）本次未执行——请核实平台底座包完整性。")
        return [], []

    readme_path = repo_root / FOLLOWUP_README_TARGET
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError:
        return [], []  # README 不在（隔离环境/新 clone）——判不出，不拦

    intakes: list = []
    for queue_file, queue_text in queue_texts.items():
        intakes.extend(_followup_intake_records(queue_text, queue_file))
    unsynced = followup_gate.find_unsynced_letters(
        intakes, _followup_letter_records(readme_text)
    )
    if not unsynced:
        return [], []

    waiver = next(
        (s for s in waiver_sources if FOLLOWUP_STATE_SYNC_WAIVER_MARKER in s), None
    )
    if waiver is not None:
        preview = waiver.strip()
        if len(preview) > 120:
            preview = preview[:120] + "…"
        return [], [
            f"✓ 检测到转态豁免声明，已放行 {len(unsynced)} 处未转态"
            f"（机器本次不代写）：{preview}"
        ]

    # —— 机器代写 ——
    by_number = {u.letter.number: u for u in unsynced}
    rows = _followup_readme_rows_indexed(readme_text)
    lines = readme_text.splitlines()
    # 🔴 本机本地日期，当场取（根 CLAUDE.md §5 写侧硬规则）
    today = datetime.now().strftime("%Y-%m-%d")

    written: list[str] = []
    violations: list[str] = []
    for line_index, cells, status_col_index in rows:
        number = cells[0] if cells else ""
        target = by_number.get(number)
        if target is None:
            continue
        previous = cells[status_col_index]
        cells = list(cells)
        cells[status_col_index] = _build_reply_closed_status(
            previous,
            [i.row_id for i in target.intakes],
            target.channel,
            today,
        )
        lines[line_index] = "| " + " | ".join(cells) + " |"
        written.append(
            f"「{number}」← {'／'.join('§一 #' + i.row_id for i in target.intakes)}"
            f"（通道 {target.channel}）"
        )
        by_number.pop(number, None)

    if by_number:
        # 判出来了却在表里找不到那一行——**不静默**。两处解析用的是同一套
        # 表头判定，走到这里说明有其它东西不对（如编号列重复），值得拦。
        violations.append(
            "S4 桥二：以下信判定为「已拆件但未转闭环」，却未能在 README 表格中"
            f"定位到对应行，本次未自动转态：{'、'.join(by_number)}"
            f"（改 {FOLLOWUP_README_TARGET}）"
        )

    if not written:
        return violations, []

    newline = "\n" if readme_text.endswith("\n") else ""
    new_text = "\n".join(lines) + newline
    failure = _machine_write_followup_readme(
        new_text,
        who="S4桥二自动转态",
        note=f"回灌完成自动转闭环态：{'；'.join(written)}",
    )
    if failure is not None:
        violations.append(
            f"S4 桥二本次未能自动转态（{failure}）——以下信仍停在非闭环态："
            f"{'；'.join(written)}。请稍后重试 release，或手工把它们改为闭环四态"
            f"（{'／'.join(FOLLOWUP_SERIAL_CLOSED_PREFIXES)}），"
            f"或在本次改动里写明「{FOLLOWUP_STATE_SYNC_WAIVER_MARKER}〈理由〉」"
            f"（改 {FOLLOWUP_README_TARGET}）"
        )
        return violations, []

    return violations, [
        f"✓ S4 桥二已自动把 {len(written)} 封信转为"
        f"「{FOLLOWUP_SERIAL_CLOSED_PREFIX}」并开闸：{'；'.join(written)}"
    ]


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
      🔴 **豁免（队列 #333②，2026-08-12）**：预留归属校验对"企微机器人
      收件登记"路径开口——`lock_data` 记录的持锁者为 `AIBOT_LOCK_WHO`
      （"企微机器人"）且该新增行任务列（cells[1]）以 `AIBOT_INTAKE_TASK_
      PREFIX`（"企微反馈自动归档："）开头时，即便未预留也不因本项拒绝。
      这不是新增豁免，是让本校验认得协议〇.10 ⑶ 早已定义的既有豁免——
      `queue_appender.py::_next_task_id` 走的是独立取号路径（不经
      `--reserve`），协议原文"收件登记≠建任务，且机器无法判断并入"正是
      这条豁免的依据；本判据仅在 §一 生效（机器人自动追行只写 §一），
      §四 不适用。**仅豁免本项（预留归属），不豁免同一循环内其它校验**
      （组内重复、与归档号重复等仍正常生效）。
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
      了跟进信且结论为暂缓"（**当前结论段**含暂缓关键词 + 反引号 `.md` 文件
      名引用）的行，若该信在 README 中「发送状态」仍为终态 `🆕 待发`，拒绝
      release——治 2026-08-06 01:30 UTC 真实误发（#150：队列称暂缓、README
      未同步移出待发标记，`ZhuopinFollowupDispatchDaily` 照发）。
      🔴 **扫描面已收窄（2026-08-17，队列 #324）**：关键词扫描面由整个状态列
      ／事项列收窄为该单元格按 `━━━` 切出的**首段**（§四 的文件名提取同步
      收窄；§一 的文件名来源 cells[3]/cells[6] 不变，两处不对称是刻意的，
      理由见 `_row_hold_language_status` 文档）。成因＝2026-08-10 §四 #52
      真实误报：4062 字符／11 段的单元格里，四个暂缓关键词全在历史段，⑥ 把
      "历史里的暂缓"与"今天新起草的信"配成一对并拒绝放行；**误报率随沉积
      单调上升**，那次是首次触发而非孤例。单元格不含 `━━━` 时行为逐字不变。
      🔴 **反向告警半边已退休**（协议〇.9 措施 B 一进一出，同批）——README
      已终态推送而队列仍称暂缓时不再打印任何东西，见
      `_validate_followup_hold_consistency` 文档的三条理由。
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
      WIP 计数；超过上限（默认 `MECHANISM_WIP_CAP_DEFAULT`＝22，
      `--mechanism-wip-cap` 可覆盖）即**拒绝 release**（进 violations，锁
      保持占用），除非逃生阀齐备。
      🔴 **2026-08-17 由"提示不阻断"改为阻断**（队列 §四 #58 ⑶，Shao
      Peishen 当日答《本周计划-2026-08-17》B-1 选 (a)）：2026-08-10→08-16
      观察周实测——可动 WIP 由 17／16 升至 24／16，周内新立机制行 6 条
      （#324/#326/#327/#328/#337/#338）**无一伴随关行**；而本提示只在
      `new_mechanism_rows` 非空那一刻响，**⇒ 它这 6 次每次都响了、每次都
      被越过。一个非阻断提示在连续 6 次被无视后，信息量已经是零。**
      🔴 **触发条件刻意保持原样不变——这是本项最容易出事的一处**：只在
      本次持锁期间**真正新增**了 `[D:机]` §一 行时才判。若改成"release 时
      超限即拒绝"，在存量已超限时（2026-08-17 实测 24／16）**此后每一次
      release 都会失败**，而编辑锁是全项目唯一写入咽喉——**连那个来关行
      降 WIP 的 session 也一起被挡在门外，规则会把自己的解法锁死。** 要压
      的是"新立机制行"这个动作，不是"改队列"这个动作。
      **逃生阀**：`--force-mechanism-wip` 开关 ＋ 新增行状态列内的
      `WIP豁免：<理由>` 标记，两者缺一即仍拒绝，见
      `_mechanism_wip_over_cap_violations` 与 `MECHANISM_WIP_WAIVER_MARKER`。
      **上限值 16 不动**（§四 #58 ⑴：第三次为迁就现状改口径即等于废掉措施
      C）；**存量 24／16 的清理不由本项代做**（§四 #58 ⑵ 交给"A 节收口后
      复核、仍超限则强制关行至 16"）。
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
    # ⑨用：本次新增的 [D:机] §一 行（编号, 状态列原文）——队列 #324 起由
    # bool 改为清单，因为逃生阀要逐行核对行内 `WIP豁免：` 标记，且拒绝文案
    # 须点名"本次新增的是哪一行"（design.md 决策点 6）。
    new_mechanism_rows: list[tuple[str, str]] = []

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

            # 队列 §一 #351 ⑷：人的属性（性别代词）校验——三个分区一律适用
            # （人名可能出现在 §一 任务行、§二 批次说明、§四 定夺项里）。
            violations.extend(_gender_pronoun_violations(label, cells, line))

            if label == "二":
                # 🔴 **校验②「文件清单须含队列文件自身路径」已于 2026-08-23
                # 退休**（协议〇.9 措施 B 一进一出，openspec 变更包
                # `editlock-chokepoint-six-fixes`）。理由：② 是一个**代理
                # 判据**——它真正想保证的是"你改了队列文件，队列文件就得进
                # 某个批次、别掉在地上"，却只能表达成"每一条新批次行都必须
                # 把队列文件写进自己的清单"。本次新增的 ⑹（`cmd_release`
                # 里的 `_registration_completeness_violations`）直接度量那件
                # 事本身：**全部脏文件都须被某个待处理 §二 批次覆盖**，覆盖面
                # 严格更大。② 残余的额外严格性（拒绝"新批次行只列代码文件、
                # 而队列文件已被另一条既有待处理批次覆盖"）拦的是一个不存在
                # 的问题——那种情形下队列文件确实会被提交。
                #
                # ⚠️ **退休的代价如实记在这里**：② 没有逃生阀，⑹ 有
                # （`登记豁免：`）⇒ 写了豁免的 session 同时也不再受 ② 约束。
                # 这是一次实质放松；接受它的理由是 ⑹ 的逃生阀要求把理由写进
                # 队列行（进 git、被值周巡检看得见），而 ② 的绝对性此前从未
                # 被验证是必要的。
                #
                # 队列 §一 #351 ⑶⑸：接管这一位置的两条新校验。
                violations.extend(_file_list_path_violations(cells, repo_root))
                if _section_two_status_is_ambiguous(cells[3]):
                    violations.append(
                        f"§二 批次「{cells[0]}」状态列开头片段既不含"
                        f"「待」也不含「✅」（会被 sweep 判为状态列模糊、每轮"
                        f"跳过并重复告警，见 #247）：{preview}"
                    )
                if cells[0] not in old_batch_names:
                    # 队列 §一 #351 ⑸：新增批次行的批次号前缀查重。
                    # `exclude_self_once=True`——此刻该行已在文件里，须把它
                    # 自己那一次出现扣掉再判重复。
                    collision = _batch_prefix_collision(
                        cells[0], {args.file: current_text}, exclude_self_once=True,
                    )
                    if collision:
                        violations.append(f"{collision}：{preview}")
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
                        # 队列 #333②：企微机器人收件登记路径豁免——见函数
                        # docstring ③段与 AIBOT_LOCK_WHO/AIBOT_INTAKE_TASK_
                        # PREFIX 定义处。仅豁免本项判定，组内重复/归档号
                        # 重复两项校验（上方）对这一行仍正常生效。
                        is_aibot_intake_row = (
                            label == "一"
                            and lock_data.get("who") == AIBOT_LOCK_WHO
                            and cells[1].strip().startswith(AIBOT_INTAKE_TASK_PREFIX)
                        )
                        if not is_aibot_intake_row:
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
                        new_mechanism_rows.append((cells[0], cells[5]))

            if label in ("一", "四"):
                touched_for_hold_consistency.append((line, cells, label))

    violations.extend(_validate_followup_hold_consistency(touched_for_hold_consistency, repo_root))

    if new_mechanism_rows:
        # ⑨ 阻断（队列 §四 #58 ⑶，2026-08-17）：超限进 violations，release 被
        # 拒绝、锁保持占用。**触发条件与改造前逐字不变**——仅在本次持锁期间
        # 真正新增了 [D:机] §一 行时才重算判定，理由见 docstring ⑨ 段那条
        # "把自己锁在门外"的红字。
        cap = args.mechanism_wip_cap
        wip_count, degraded = _count_mechanism_wip(new_sections.get("一", ""))
        for note in degraded:
            print(f"⚠ {note}")
        if wip_count > cap:
            violations.extend(
                _mechanism_wip_over_cap_violations(args, new_mechanism_rows, wip_count, cap)
            )

    return violations


def _mechanism_wip_over_cap_violations(
    args: argparse.Namespace, new_mechanism_rows: list[tuple[str, str]],
    wip_count: int, cap: int,
) -> list[str]:
    """⑨ 超限时的逃生阀判定与拒绝文案（队列 §四 #58 ⑶，design.md 决策点
    5/6）。逃生阀须**两个条件同时到位**才放行：① release 传入
    `--force-mechanism-wip` 开关（不携带理由文本）；② 本次新增的机制行状态
    列内写明 `WIP豁免：<理由>`。缺任一即拒绝，并指出缺的是哪一个。

    **一次新增多条机制行时，要求每一条都各自写明理由**（spec 原文按单条
    表述，此处是它在多行输入下的显式取舍，不是加码）：每一条新行都是一次
    独立的 WIP 增量，只在其中一条写理由会让后来的读者无从判断另一条凭什么
    立起来——而这条逃生阀存在的全部意义就是"越过之后有人知道为什么"。

    返回 violation 列表（空列表＝放行）。
    """
    # 直接取属性、不用 getattr 兜底：argparse 恒会设置该字段，兜底只会在
    # 调用方漏传时静默按"未越过"处理（工具静默回退家族，本项目已踩过多次）。
    forced = args.force_mechanism_wip
    missing_marker = [
        num for num, status in new_mechanism_rows
        if MECHANISM_WIP_WAIVER_MARKER not in status
    ]
    numbers = "／".join(f"#{num}" for num, _ in new_mechanism_rows)
    # 决策点 6：拒绝必须**可行动**，否则只是把噪音从"每次都响"换成"每次都
    # 堵"。文案含当前计数与上限、本次新增的是哪一行、两条出路的确切写法。
    head = (
        f"§一 机制类可动 WIP 当前 {wip_count}／{cap}，已超上限（协议〇.9 措施 C，"
        f"队列 §四 #58 ⑶：2026-08-17 起由提示改为阻断）——本次新增机制行 {numbers}。"
    )
    ways_out = (
        "两条出路："
        "⑴ 先关闭一条既有机制类可动行（把其状态字段改为 `[S:done]`，"
        "或让正文以 🛑 起首），使计数回到上限内后重试；"
        f"⑵ 若确属紧急必须此时立行，在本次新增行的状态列内写明"
        f"「{MECHANISM_WIP_WAIVER_MARKER}<理由>」，并给 release 加"
        f" `--force-mechanism-wip` 开关（两者缺一不可）。"
    )
    if not forced and missing_marker:
        return [f"{head} {ways_out}"]
    if not forced:
        # 行内已写理由、只差开关：越过必须是一次显式选择，不能顺手。
        return [
            f"{head} 已在行内读到「{MECHANISM_WIP_WAIVER_MARKER}」标记，"
            f"但 release 未传 `--force-mechanism-wip` 开关——请补上该开关以表明"
            f"这是一次有意越过（开关表达意图，行内标记承载理由，两者缺一不可）。"
        ]
    if missing_marker:
        shown = "／".join(f"#{num}" for num in missing_marker)
        return [
            f"{head} 已传 `--force-mechanism-wip`，但新增行 {shown} 的状态列内"
            f"未写明「{MECHANISM_WIP_WAIVER_MARKER}<理由>」——理由必须写在队列行里，"
            f"不能只写在命令行上（命令行参数随窗口关闭即消失，队列行进 git、"
            f"被 `工具-队列结构lint.py` 与值周巡检看得见）。"
        ]
    print(
        f"✓ 机制类可动 WIP {wip_count}／{cap} 已超上限，但检测到逃生阀齐备"
        f"（`--force-mechanism-wip` ＋ 行内「{MECHANISM_WIP_WAIVER_MARKER}」标记），"
        f"已放行 {numbers}——理由随该行落盘、进入版本历史。"
    )
    return []



# ═══════════════════════════════════════════════════════════════════════
# 队列 §一 #351 ⑶⑷⑸⑹（openspec 变更包 editlock-chokepoint-six-fixes，
# 2026-08-23）——`append-row`／`release` 这道咽喉上被发现的四处守卫缺位。
# ⑴⑵ 落在下方 `cmd_append_row`／`_build_append_row_line` 里，就近实现。
# ═══════════════════════════════════════════════════════════════════════

# ── ⑶ §二「文件清单」路径格式 ────────────────────────────────────────
# 判据只认**形态**，不认存在性。实测（2026-08-23，两份队列文件全量）：
# 形如路径的反引号片段 1371 个、格式违规 220 个（16.0%）；而若再加一条
# 存在性校验，**98 个格式合法的片段会变成误报**（合法的范围性速记，如
# `openspec/changes/.../{proposal,design,tasks}.md`、`X/tests/test_*.py`、
# `0-学习与工具/skills源码/<name>/SKILL.md`，以及"当时存在、后来移走"的
# 历史件）。7% 的误报会把逃生阀变成常规操作，而逃生阀一旦常规化，这道门禁
# 就废了（同 #351 ⑷ 那条 10% 误报的教训）。
#
# 🔴 **与 sweep 的关系（别当成两边判据打架）**：`工具-落库sweep.py::
# _resolve_batch_fragments` 的 docstring 明写它**刻意宽容**（后缀匹配、
# 不要求仓库根相对完整路径）。本项收紧的是**写者**、不是读者，是 Postel
# 原则的正用；且恰好消灭 sweep 那条宽容路径上的 `ambiguous` 失效形态
# （#234(1)：根 `CLAUDE.md` 与场景目录下同名文件同时脏 ⇒ 片段命中两个
# 候选 ⇒ 判歧义 ⇒ 连带跳过一个本已声明齐全的批次）。
PATH_LIKE_EXTENSIONS = frozenset({
    ".md", ".py", ".json", ".yaml", ".yml", ".txt", ".html", ".htm", ".ps1",
    ".docx", ".xlsx", ".csv", ".jsonl", ".sh", ".bat", ".cfg", ".toml",
    ".ini", ".js", ".ts", ".tsx", ".jsx", ".log", ".xml", ".sql", ".env",
    ".gitignore", ".db", ".sqlite", ".pdf", ".png", ".svg",
})
# 预登记批次豁免 ⑶：`queue-claim-time-preregistration` 的 Requirement
# 「预登记批次的内容与状态标识」明文允许其文件清单为"目录前缀或范围性
# 描述"。两条 spec 各守一段生命周期——该行走到"收工时精确化"那一步会被
# 重新触碰，届时不再是预登记态，⑶ 自然接管。


def _fragment_is_path_like(fragment: str) -> bool:
    """反引号片段是否"形如路径"——只认两种形态：以已知扩展名结尾，或以
    `/` 结尾（目录前缀）。

    🔴 **刻意不把"含斜杠"当作路径特征**：队列正文里 `采购/财务/质量`
    这类并列写法极常见，按"含斜杠"判会把它们全部拖进来。判据宁可窄，
    漏掉的形态由 sweep 孤儿告警兜住；判宽了则误报淹掉真报。
    """
    frag = fragment.strip()
    if not frag:
        return False
    if frag.endswith("/"):
        return True
    return PurePosixPath(frag.replace("\\", "/")).suffix.lower() in PATH_LIKE_EXTENSIONS


def _path_fragment_format_problem(fragment: str, repo_root: Path) -> str | None:
    """形如路径的片段若不是"仓库根相对完整路径"，返回一句问题描述；合规
    返回 `None`。

    裸文件名这一支必须查存在性，且**只查这一支**：根目录的 `CLAUDE.md`／
    `.gitignore` 的裸文件名**本身就是**合法的仓库根相对路径，一刀切拒绝
    会把它们误伤；而 `工具-落库sweep.py`（真身在 `0-学习与工具/` 下）这类
    速记正是要拦的对象。两者的唯一区别就是"根下有没有同名文件"。
    """
    frag = fragment.strip()
    if re.match(r"^[A-Za-z]:[\\/]", frag) or frag.startswith("/") or frag.startswith("\\"):
        return f"`{frag}` 是绝对路径，须改为仓库根相对路径"
    if "\\" in frag:
        return f"`{frag}` 用了反斜杠作分隔符，须改用正斜杠 `/`"
    if frag.startswith("./") or frag.startswith("../"):
        return f"`{frag}` 带 `./`／`../` 前缀，须改为从仓库根写起的完整路径"
    if "/" not in frag:
        if (repo_root / frag).exists():
            return None  # 根目录文件的裸文件名即完整路径，放行
        return (f"`{frag}` 是裸文件名且仓库根下无同名文件，须写仓库根相对完整路径"
                f"（速记会让 sweep 退化到后缀匹配，同名文件并存时判歧义、连带跳过整个批次，见 #234(1)）")
    return None


def _file_list_path_violations(cells: list[str], repo_root: Path) -> list[str]:
    """⑶：§二 一行的「文件清单」列（cells[1]）路径格式校验。预登记行豁免。"""
    if len(cells) < 4:
        return []
    if _leading_status_segment(cells[3]).startswith(PREREGISTERED_STATUS_PREFIX):
        return []
    problems = []
    for fragment in re.findall(r"`([^`]+)`", cells[1]):
        if not _fragment_is_path_like(fragment):
            continue
        problem = _path_fragment_format_problem(fragment, repo_root)
        if problem:
            problems.append(f"§二 批次「{cells[0]}」文件清单路径格式违规：{problem}")
    return problems


# ── ⑸ §二 批次号前缀查重 ────────────────────────────────────────────
# 实测（2026-08-23）：现存批次号前缀 174 个，**其中 27 个撞号（15.5%）**
# ——立行时以为是"同族第三次"，实际是第 27 次。根因＝批次号由各方自行读
# 高水位线 +1 自增，而 `append-row --section 二` 既不预留、也不校验重名
# （§一／§四 走 `acquire --reserve` 的路径不同，§二 是裸奔的）。
#
# 🔴 **判据模糊处如实登记**：批次号第二段**并非恒为流水号**——实测两种
# 写法并存（`B-0818_18_…` 的 18 是当日流水号，`B-0808_309_…` 的 309 是
# 队列行号）。故本项**只判前缀字面重复，不解释第二段语义**；提示里给的
# "建议序号"取同日已用的最大**纯数字**第二段 +1，并明写只是建议。
# **不为这件事再造一套命名判据**——那正是本项目反复吃亏的形态。
BATCH_NUMBER_PREFIX_RE = re.compile(r"^(B-\d{4}_[^_\s]+)")


def _batch_number_prefix(batch_name: str) -> str | None:
    match = BATCH_NUMBER_PREFIX_RE.match(batch_name.strip())
    return match.group(1) if match else None


def _all_section_two_batch_names(queue_texts: dict[str, str]) -> list[str]:
    names = []
    for text in queue_texts.values():
        for _, cells in _table_data_rows(_split_live_sections(text).get("二", "")):
            if cells and cells[0].strip():
                names.append(cells[0].strip())
    return names


def _suggest_next_batch_serial(prefix: str, existing_names: list[str]) -> str | None:
    """同日已用的最大纯数字第二段 +1。第二段非纯数字者不参与计算——它们
    走的是"队列行号"那套写法，本函数不去猜。"""
    day = prefix.split("_", 1)[0]
    used = []
    for name in existing_names:
        other = _batch_number_prefix(name)
        if not other or not other.startswith(day + "_"):
            continue
        tail = other.split("_", 1)[1]
        if tail.isdigit():
            used.append(int(tail))
    return f"{day}_{max(used) + 1}" if used else None


def _batch_prefix_collision(
    batch_name: str, queue_texts: dict[str, str], *, exclude_self_once: bool = False,
) -> str | None:
    """⑸：返回一句拒绝说明；无冲突返回 `None`。

    `exclude_self_once=True` 供 release 侧使用——那时待查的行**已经在文件
    里了**，须把它自己那一次出现扣掉再判重复。
    """
    prefix = _batch_number_prefix(batch_name)
    if prefix is None:
        return None  # 不符前缀形态的批次名不受本项约束
    existing = _all_section_two_batch_names(queue_texts)
    conflicts = [n for n in existing if _batch_number_prefix(n) == prefix]
    if exclude_self_once and batch_name.strip() in conflicts:
        conflicts.remove(batch_name.strip())
    if not conflicts:
        return None
    shown = "、".join(f"「{n}」" for n in conflicts[:3])
    suggestion = _suggest_next_batch_serial(prefix, existing)
    tail = (f"建议改用 `{suggestion}`（＝同日已用最大纯数字序号 +1，"
            f"**只是建议**：批次号第二段实测既有流水号写法也有队列行号写法，"
            f"你可自选任何不冲突的名字）" if suggestion
            else "请自选一个不冲突的批次名")
    return (f"§二 批次号前缀 `{prefix}` 已被占用：{shown}——"
            f"撞号后无法再用编号唯一指代某个批次（实测现存 27 处同族撞号）。{tail}")


# ── ⑷ 人的属性（性别代词）lint ───────────────────────────────────────
# 🔴 **本常量的唯一权威来源是根 `CLAUDE.md` §1**（人员名录与性别）。
# 名录变动一律先改那里，再改这里；`test_工具-共享文档编辑锁.py` 里有一条
# 同步用例会从 §1 抽取全部带性别标注的姓名与本常量对表，**名录扩了而这里
# 没跟，回归当场变红**。
#
# **刻意不在运行时解析 CLAUDE.md**：§1 是每周都在变的散文，措辞一变解析
# 就抽不到人名，判据随即变成**恒真、零信息量，而没有任何东西会报错**。
# 用一个失效不产生信号的实现，去做一条专为根治"错误不产生信号"而立的
# 校验，是原地打转。
PERSON_GENDER_ROSTER: dict[str, str] = {
    # 部门 AI 专员
    "姚祖怡": "男", "陈忱": "女", "唐燕萍": "女", "泓钦": "男", "陈承": "男",
    # 一线标注层与决策代理
    "朱映桦": "男", "解植雅": "男", "汤易水": "男", "孙涛": "男",
    # 财务部（在册六人全部为女性，唐燕萍已在上方）
    "李姣龙": "女", "钱婷": "女", "孙国庆": "女", "陶钰": "女", "朱云澜": "女",
    # IT 汇总的全员企微名录中此前未收录者
    "叶燕": "女", "齐奇": "女", "汤丽萍": "女",
    "袁洋": "男", "刘伟": "男", "聂鑫": "男",
    # 决策人本人（§1 中以「`邵培申` ＝ Shao Peishen 本人」形式记载，
    # 无「（男）」标注，故同步用例走「§1 ⊆ 常量」方向，不要求相等）
    "邵培申": "男",
}
GENDER_PRONOUN_WAIVER_MARKER = "性别豁免："
# 窗口取 25 是**实测定标**的（2026-08-23 两份队列文件全量）：
#   整行判据（#351 原文）65 行 ／ 40 字 19 行 ／ **25 字 18 行** ／ 15 字 13 行。
# 40→25 只差 1 行、已到平台期；15 开始漏掉正常语序（"姚祖怡在 8 月 12 日的
# 回件里说她…"）。
#
# 🔴 **为什么是"邻近窗口"而不是 #324 给校验⑥做的"首段收窄"**：⑥ 判的是
# "这一格当前的结论是什么"，结论就在首段；本项判的是"这个代词在指谁"，
# **指代关系是局部的、与段落位置无关**——写在第 7 段的"姚祖怡…她"同样是错
# 的。整行判据必然失败的原因也在这里：§一 单行常达数千字、跨多个话题，
# 一行里提到"唐燕萍"（在讲财务口径）、别处出现"他"（指 Shao Peishen），
# 整行判据必然把它们配成一对。
GENDER_PRONOUN_WINDOW = 25
# "他"的非代词用法。`其他` 在队列里极高频，不排除会把真报淹掉（#351 ⑷
# 行内已用红字点名这一条）。按长度降序遮蔽，避免 `其他人` 被 `其他` 先吃掉。
NON_PRONOUN_TA_WORDS = (
    "其他人", "他人", "其他", "其它", "他们", "他处", "他方", "他日", "他者",
)


def _mask_non_pronoun_ta(text: str) -> str:
    """把非代词用法的「他」遮成同长度的占位符——遮蔽而非删除，位置偏移
    才不会变，邻近窗口的距离计算才准。"""
    masked = text
    for word in NON_PRONOUN_TA_WORDS:
        masked = masked.replace(word, "〇" * len(word))
    return masked


def _gender_pronoun_violations(label: str, cells: list[str], line: str) -> list[str]:
    """⑷：行内人名与性别代词邻近矛盾即违规。行内写 `性别豁免：<理由>` 放行。

    逃生阀是**常态配套、不是异常出口**：实测残余命中里绝大多数是**引用
    规则条文本身**的行（`§一 #351`／`§四 #75` 的正文逐字写着"出现 `陈忱`／
    `唐燕萍`（女）且出现独立的 `他`"），这类命中必然发生且必然合法。
    """
    if GENDER_PRONOUN_WAIVER_MARKER in line:
        return []
    scan = _mask_non_pronoun_ta(line)
    row_id = cells[0].strip() if cells else "?"
    violations = []
    for name, gender in PERSON_GENDER_ROSTER.items():
        wrong = "她" if gender == "男" else "他"
        for match in re.finditer(re.escape(name), scan):
            window = scan[match.end():match.end() + GENDER_PRONOUN_WINDOW]
            idx = window.find(wrong)
            if idx == -1:
                continue
            # 中间隔着异性名字 ⇒ 代词多半指那个人，属合法情形。判据复刻
            # 2026-08-21 那次 244 处追改所用的脚本口径（"含姚祖怡、含她、
            # 且同行不含陈忱／唐燕萍"）。
            between = window[:idx]
            if any(other in between for other in PERSON_GENDER_ROSTER
                   if PERSON_GENDER_ROSTER[other] != gender):
                continue
            snippet = scan[max(0, match.start() - 12):match.end() + GENDER_PRONOUN_WINDOW]
            violations.append(
                f"§{label} {row_id} 行内「{name}」（{gender}）之后 {GENDER_PRONOUN_WINDOW} 字内"
                f"出现「{wrong}」：…{snippet}…"
                f"——人的属性一律以根 CLAUDE.md §1 名录为准，不得从名字推断；"
                f"确属合法情形（同行多人／引用规则条文本身）请在本行内写"
                f"「{GENDER_PRONOUN_WAIVER_MARKER}<理由>」放行。"
            )
            break  # 同一人名在同一行只报一次，不为一行刷屏
    return violations


# ── ⑹ release 登记完整性校验 ────────────────────────────────────────
# 🔴 **判据刻意不是 #351 原文写的「本次持锁窗口内新增的脏文件」（快照差集）
# ——取证证明那个判据抓不住它自己的立项实证。**
#
# `reports/sweep-commit.log` 实测：`OP-0822-E` 的六个孤儿文件在
# **2026-08-22 12:20 UTC** 那轮 sweep 就已全部报为脏，而 E 于 **12:26:16
# UTC** 才 acquire——**晚 6 分钟**。按差集口径它们在占锁那一刻已进基线，
# release 时差集为空、照样放行，缺陷原样复发。
#
# ⇒ 判据改为「release 时**全部**脏文件都须被某个待处理 §二 批次覆盖」，
# 这**不是新造判据**：它逐字等同 sweep 孤儿检测已在用的那一条，本项只是把
# 它从"只进日志的事后告警"前移到"有阻断力、且 session 还活着"的时点——
# 而这正是 #351 ⑹ 自己写下的设计意图（"sweep 的孤儿告警没有阻断力，
# 而 release 是唯一一个 session 还活着、且必然会被调用的时点"）。
# **原文的判据与它自己的设计意图不一致，此处以设计意图为准。**
#
# acquire 快照**保留但改变用途**：不再用于过滤，而用于**归因**。差集过滤
# 是让机器替人做一个它做不了的判断（这脏文件是谁造的）并默默判成"不是
# 你"；归因提示是把判断交还给人，同时把机器确实知道的那点信息（时间先后）
# 如实给出。
REGISTRATION_WAIVER_MARKER = "登记豁免："
# 🔴 **落库 sweep 身份豁免——不是开后门，是判据对它本就不成立。**
#
# `工具-落库sweep.py` 的持锁身份（其 `LOCK_WHO`）。sweep 在一次持锁窗口内做的
# 事是：`git add` 本批文件 → 把该批次行改成 `✅ 已完成` → release → commit。
# ⇒ **release 那一刻工作区必然是脏的**（刚 add 的文件 ＋ 刚改的队列文件），
# 而它刚把那条批次行标成完成 ⇒ 那条清单已不再是"待处理批次"⇒ ⑹ **必然判为
# 未覆盖、必然拒绝**。
#
# **后果不是"多一条告警"，是全项目停摆**：`_strike_off_rows` 在 `finally` 里
# 调 release 且**不看返回码**，被拒 ⇒ 锁保持占用 ⇒ 下一轮 sweep 的起跑探锁
# （`_abort_if_edit_lock_held`）判定"有人正在编辑"直接跳过 ⇒ **此后每一轮都
# 跳过，而 sweep 是唯一会 commit 队列改动的机制**。2026-08-23 本变更包
# apply 时由 `test_四种状态形态端到端` 当场撞出，未进生产。
#
# **为什么豁免在道理上成立**：⑹ 问的是"你改完东西有没有登记，好让 sweep 来
# 提交"；**而 sweep 就是那个来提交的人**。要求它先给自己登记一条批次，是让
# 消费者去写自己的待办清单——判据的适用对象从来不包括它。
#
# 同族先例：`AIBOT_LOCK_WHO`（企微机器人收件登记豁免预留归属校验，队列 #333②）
# ——同样是"让校验认得一条既有的、结构性的例外"，不是新开豁免。
SWEEP_LOCK_WHO = "sweep-commit"


def _is_inside_git_work_tree(repo_root: Path) -> bool:
    """`repo_root` 是否位于一棵 git 工作树内。

    🔴 **这条判断存在的意义，是把两种「取不到脏文件」区分开**——⑹ 对它们的
    处置完全相反，混为一谈就必然错一边：
      ⑴ **根本不在工作树内**（隔离测试的临时目录、非仓库副本）⇒ "脏文件"
         这个概念不成立，⑹ **判据的适用前提不成立**，跳过是正确的，且会
         打印一行明示；
      ⑵ **在工作树内、但 `git status` 失败**（git 挂了／超时／索引锁）⇒
         这是**该有答案却没拿到**，必须 fail-closed 拒绝 release。
    把 ⑵ 也按"跳过"处理，就正是本项目反复吃亏的"工具静默回退"。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _local_git_status_paths(repo_root: Path) -> list[str] | None:
    """本机 git 的工作区脏路径清单；取数失败返回 `None`（与"干净"区分开）。

    🔴 **两个参数都不是可选优化**：
    ⑴ `-c core.quotepath=false`——git 默认把非 ASCII 路径转义成八进制
       （`"1-\\350\\275\\254\\345\\236\\213…"`）。**本项目全部路径都是中文**，
       不加这个参数拿到的路径与 §二 清单里的字面**永远对不上**，而命令
       退出码 0、输出看起来完全正常 ⇒ 典型的"工具静默回退"，且方向是
       "所有文件都未被覆盖"这种整体性误报。
    ⑵ `--untracked-files=all`——新建但未 add 的文件正是孤儿的主要形态。

    🔴 **必须是本机 git，不得是沙箱 git**（§四 #98）：本机 `core.autocrlf`
    来自 Windows system 级配置，沙箱 git 读不到，同一工作区两个 git 会给出
    相反答案（967 份"已修改" vs 干净）。本工具由 CC 在本机执行，`subprocess`
    起的就是本机 git，天然满足——**这行注释是写给下一位想把它挪到沙箱侧跑
    的读者的。**
    """
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status",
             "--porcelain=v1", "--untracked-files=all"],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    paths = []
    for raw in result.stdout.splitlines():
        if not raw.strip():
            continue
        rest = raw[3:]
        if " -> " in rest:  # 重命名取新路径
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        if rest:
            paths.append(rest)
    return paths


def _pending_batch_fragments(queue_texts: dict[str, str]) -> list[str]:
    """两份物理队列文件里**全部待处理** §二 批次行的文件清单片段。

    "待处理"口径复用既有 `_leading_status_segment`（#248 锚定），涵盖
    `待处理` 与 `在办（预登记，收工时精确化）` 两态——**不新造判据**。
    已完成（开头片段含 ✅）的批次不会再被 sweep 取活，其清单不构成归属。
    """
    fragments = []
    for text in queue_texts.values():
        for _, cells in _table_data_rows(_split_live_sections(text).get("二", "")):
            if len(cells) < 4:
                continue
            if "✅" in _leading_status_segment(cells[3]):
                continue
            fragments.extend(re.findall(r"`([^`]+)`", cells[1]))
    return fragments


def _dirty_path_is_covered(path: str, fragments: list[str]) -> bool:
    """覆盖判定 —— 逐字复刻 `工具-落库sweep.py::_resolve_batch_fragments`
    的后缀匹配口径（`p == f` 或 `p.endswith("/" + f)`）。

    **刻意不实现 sweep 那套"一个片段命中多个候选即判歧义"**：sweep 需要它
    是因为它要决定 `git add` 哪个文件（选错会 add 错东西）；本项只需回答
    "这个脏文件有没有归属"，一个片段同时覆盖多个脏文件对该问题无害。
    **能不抄的复杂度就不抄。**
    """
    return any(path == frag or path.endswith("/" + frag) for frag in fragments)


def _registration_completeness_violations(
    queue_texts: dict[str, str], lock_data: dict, repo_root: Path,
    waiver_sources: list[str],
) -> list[str]:
    """⑹：release 时全部脏文件须被某个待处理 §二 批次覆盖，否则拒绝。"""
    if lock_data.get("who") == SWEEP_LOCK_WHO:
        # 见 SWEEP_LOCK_WHO 定义处的长注释：sweep 是"来提交的那个人"，
        # 判据的适用对象不含它。仅豁免本项，不影响它仍须通过的其它校验。
        return []

    if not _is_inside_git_work_tree(repo_root):
        print("ℹ 仓库根不在 git 工作树内，⑹ 登记完整性校验的适用前提不成立，"
              "本次跳过（这不是回退——没有工作树就没有『脏文件』这回事）。")
        return []

    dirty_now = _local_git_status_paths(repo_root)
    waiver = next(
        (s for s in waiver_sources if REGISTRATION_WAIVER_MARKER in s), None
    )

    if dirty_now is None:
        # fail-closed：本变更同批退休了校验②（协议〇.9 措施 B 一进一出），
        # 取数失败若静默放行，这道咽喉上将什么都不剩。
        if waiver is not None:
            print(f"✓ 工作区状态取数失败，但检测到登记豁免声明，已放行：{waiver.strip()[:120]}")
            return []
        return [
            "无法取得工作区脏文件状态（非 git 仓库／git 不可用／超时），"
            "⑹ 登记完整性校验无法执行 ⇒ 拒绝 release（fail-closed，不静默放行）。"
            f"确需放行请在本次 note 或本次触碰的队列行内写「{REGISTRATION_WAIVER_MARKER}<理由>」。"
        ]

    fragments = _pending_batch_fragments(queue_texts)
    uncovered = [
        p for p in dirty_now
        if ".editlock" not in p and not _dirty_path_is_covered(p, fragments)
    ]
    if not uncovered:
        return []

    if waiver is not None:
        print(f"✓ 检测到登记豁免声明，已放行 {len(uncovered)} 个未登记脏文件："
              f"{waiver.strip()[:120]}")
        return []

    snapshot = lock_data.get("dirty_at_acquire")
    if snapshot is None:
        grouped = [("（无 acquire 快照，无法判定出现时刻）", uncovered)]
    else:
        before = set(snapshot)
        grouped = [
            ("本次持锁期间新出现", [p for p in uncovered if p not in before]),
            ("acquire 之前就已经脏（可能来自并发 session）",
             [p for p in uncovered if p in before]),
        ]

    lines = [
        f"⑹ 登记完整性：{len(uncovered)} 个脏文件不属于任何待处理 §二 批次的文件清单"
        f"——它们不会被 sweep 提交，会静默掉在地上（`OP-0822-E` 2026-08-22 实证："
        f"acquire 的 note 写了「分三批登记」，那三条批次行从未出现在任何一个提交里）。"
    ]
    for title, paths in grouped:
        if not paths:
            continue
        lines.append(f"  【{title}】")
        lines.extend(f"    - {p}" for p in paths)
    lines.append(
        f"  两条出路：⑴ 为它们登记 §二 批次（`append-row --section 二`，"
        f"文件清单写仓库根相对完整路径）；"
        f"⑵ 确不该登记的，在本次 note 或本次触碰的队列行内写"
        f"「{REGISTRATION_WAIVER_MARKER}<理由>」。"
    )
    return ["\n".join(lines)]


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

    lock_path = _lock_path(
        QUEUE_LOCK_ANCHOR if _is_queue_system_target(args.file) else args.file
    )
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
    """`_acquire_mutex` 保护下执行的 acquire 逻辑。

    队列 #315（apply）：队列系统模式（`args.file == DEFAULT_TARGET`）下，
    锁本身锚定在 `QUEUE_LOCK_ANCHOR`（机制环境文件，见模块顶部注释，
    `lock_path` 已由 `cmd_acquire` 按此计算好传入），但内容层面的快照／
    绕锁检测（#200）／幽灵副本检测（决策点5）覆盖两份物理队列文件——
    持锁窗口内两份文件均可能被编辑，`cmd_release` 对两者分别做结构校验。
    非队列系统目标（如跟进信 README）行为与改造前完全一致，仅多一步写后
    回读校验（#197：不信"写成功了"，CLAUDE.md §5 既有纪律）。"""
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

    # 队列 §一 #351 ⑹：占锁瞬间记一份工作区脏文件清单。**它不再用于过滤**
    # （原设想的"差集"判据已被取证推翻，见 `_registration_completeness_
    # violations` 的红字），只用于 release 拒绝时的**归因**——把未覆盖路径
    # 分成"本次持锁期间新出现"与"acquire 之前就已经脏"两组。取数失败不阻断
    # 占锁（返回 None，release 侧按"无快照"处理，不臆断）。
    dirty_at_acquire = _local_git_status_paths(REPO_ROOT)

    _atomic_write_json(
        lock_path, {
            "who": args.who, "note": args.note or "", "held_since": held_since,
            "history": new_history, "reserved": {}, "domains": {},
            "dirty_at_acquire": dirty_at_acquire,
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

    is_queue_system = _is_queue_system_target(args.file)
    content_targets = _iter_queue_paths() if is_queue_system else [args.file]

    for content_target in content_targets:
        current_content = _read_target_text(content_target)

        # 队列 #225：目标文件此刻内容存一份快照，release 时据此 diff 出本次
        # 持锁期间新增/修改的行，结构校验只对这些行生效。
        _write_snapshot(content_target, current_content)

        # 队列 #200：与"上次 release 时记录的内容"比对，检测两次合法
        # release/acquire 之间是否发生过绕锁直接改写。不阻断——协议〇.7 一贯
        # 是协作性质而非硬互斥（见模块文档），只回显+（队列系统目标时）留痕。
        lastknown = _read_lastknown(content_target)
        if lastknown is not None and current_content != lastknown:
            diff_summary = _summarize_content_diff(lastknown, current_content)
            print(
                f"⚠ 检测到 {content_target} 在上次 release 之后被直接改写（未经本工具 "
                f"acquire/release，{diff_summary}）——可能绕过协议〇.7 锁保护写入，"
                "请核查改动是否符合预期（队列 #200）。"
            )
            if is_queue_system:
                _record_bypass_detection(REPO_ROOT, content_target, args.who, diff_summary)

        # 决策点5（队列 #315 子项⑥，2026-08-10 #321 真实事故）：本地影子
        # 副本漂移检测——只读警告，不自动处理。
        shadow_warning = _detect_shadow_copy(content_target)
        if shadow_warning:
            print(shadow_warning)

    print(f"✓ 已占锁：{args.who}（{args.note or '无备注'}）→ {lock_path.name}")
    # 决策点5：绝对路径打印，供操作方核对接下来要打开的编辑器路径是否
    # 与此一致（此前只回显相对路径/文件名，是 #321 事故未被及时发现的
    # 一个诱因——两个不同的相对路径字符串"看起来都合理"）。
    for content_target in content_targets:
        print(f"📍 权威物理路径：{_target_path(content_target)}")

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
        reservation_target = (
            QUEUE_MECHANISM_PATH_REL if is_queue_system else args.file
        )
        reserved_map: dict[str, list[int]] = {}
        for section, count in reserve_requests:
            try:
                extra_texts = (
                    [_read_target_text(QUEUE_BUSINESS_PATH_REL)]
                    if is_queue_system else None
                )
                reserved_map[section] = _reserve_ids(
                    reservation_target, section, count, extra_collision_texts=extra_texts,
                )
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
                # 🔴 二次写锁必须把 ⑹ 的快照带上——漏了它，凡走 --reserve 的
                # session 都会在 release 时退化到"无快照"分支（归因失效，但
                # 校验本身仍生效）。这类"第二处写入忘了带上第一处刚加的字段"
                # 是本文件已有前例的失效形态。
                "dirty_at_acquire": dirty_at_acquire,
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

    # 高水位线声明恒定只存机制环境文件（决策点1/2），队列系统模式下不论
    # args.file 解析到哪一份都读机制环境文件。
    hwm_source = QUEUE_MECHANISM_PATH_REL if is_queue_system else args.file
    hwm = _read_high_water_mark(hwm_source)
    if hwm:
        print(f"📍 持锁瞬间高水位线：{hwm}——新行编号从此值 +1 续排，"
              "勿用 acquire 之前读到的旧值（见协议〇.7）。")
    print("  改完请立刻 release，不要跨整个 session 持有。")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock_path = _lock_path(
        QUEUE_LOCK_ANCHOR if _is_queue_system_target(args.file) else args.file
    )
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

    # 队列 #225：锁定目标是队列系统本体时，release 前做结构校验——不通过
    # 则拒绝释放（锁保持占用，逼持有者原地修正后重试），不对其他 `--file`
    # 目标生效（§一/§二/§三/§四 语义只对队列文件成立）。队列 #315（apply）：
    # 拆分后对两份物理文件分别校验、violations 汇总（§三/§四/协议〇只存于
    # 机制环境文件，业务场景文件里天然找不到这些分区、`_split_live_
    # sections` 返回空文本、`_diff_touched_rows` 判定零改动、优雅跳过，
    # 该函数无需为"文件缺某个分区"专门改造）。
    violations: list[str] = []
    progress_waiver_notes: list[str] = []
    if _is_queue_system_target(args.file):
        queue_texts: dict[str, str] = {}
        for content_target in _iter_queue_paths():
            file_args = argparse.Namespace(**vars(args))
            file_args.file = content_target
            file_violations = _validate_release_structure(file_args, existing, REPO_ROOT)
            violations.extend(f"[{content_target}] {v}" for v in file_violations)
            queue_texts[content_target] = _read_target_text(content_target)
        # 队列 #366 / S4 桥二：拆件完成（§一 入信行转 `[S:done]`）而 README
        # 未转闭环态 ⇒ 拒绝 release。挂在**队列系统**的 release 上而不是
        # README 的 release 上，是因为拆件回灌这个动作本身就发生在队列这一侧
        # ——把校验放在动作发生的那一刻，才谈得上"拆件的人不可能忘"。
        #
        # 🔴 逃生阀取材面 ＝ 本次持锁的 note ＋ **本次持锁期间触碰过的队列行**，
        # 刻意**不**含队列文件全文：`转态豁免：` 一旦写进这两份 1.9 MB 的文件
        # 任何一处，全文匹配就等于把这道门禁永久关掉，且此后没有任何人会发现
        # ——逃生阀必须一次一用，不能变成一个写一次就长期生效的开关。
        # 与 `串行豁免：`（只看新增行自身的单元格）同一收敛方向。
        waiver_sources = [existing.get("note", "") or ""]
        for content_target, queue_text in queue_texts.items():
            snapshot_sections = _split_live_sections(_read_snapshot(content_target))
            current_sections = _split_live_sections(queue_text)
            for label in current_sections:
                waiver_sources.extend(
                    line for line, _ in _diff_touched_rows(
                        snapshot_sections.get(label, ""), current_sections[label]
                    )
                )
        # `OP-0823-D`：由「校验人有没有改」改为「机器代写」——人只需把 §一
        # 入信行改成 `[S:done]`，README 那一格由本函数写。写不成仍然拦。
        # ⚠️ 写入发生在其它校验项判定之后、release 决定之前：即便本次 release
        # 因别的结构问题被拒，这次转态**已经落盘**。这是有意的——「拆件回灌
        # 完成」是既成事实，不该因为同一次持锁里另有一处格式问题就退回去；
        # 且重跑幂等（已闭环的信不会被再写一次）。
        sync_violations, sync_notes = _auto_sync_followup_reply_state(
            queue_texts, REPO_ROOT, waiver_sources, args.who or "未知",
        )
        violations.extend(sync_violations)
        for note in sync_notes:
            print(note)
        # 队列 §一 #351 ⑹：登记完整性。逃生阀取材面与 `转态豁免：` 完全一致
        # （本次 note ＋ 本次触碰过的队列行，**不含队列全文**）——理由同上方
        # 那段红字：豁免标记一旦写进这两份 1.9 MB 的文件任何一处，全文匹配
        # 就等于把门禁永久关掉，且此后没有任何人会发现。
        violations.extend(_registration_completeness_violations(
            queue_texts, existing, REPO_ROOT, waiver_sources,
        ))
    elif args.file == FOLLOWUP_README_TARGET:
        # 队列 #124 阶段二（design.md D1）：跟进信 README 两态语义结构性
        # 拦截，与上面那套队列专属校验各自独立、互不干扰。
        violations = _validate_followup_readme_release(_read_target_text(args.file), _read_snapshot(args.file))
    elif _is_claude_progress_target(args.file):
        # 判据 J4（队列 §四 #80）：根 CLAUDE.md 顶部进度段新增条目时的未闭合
        # 项拦截，同样是一张与队列表格无关的独立判据，见
        # `_validate_claude_progress_open_item`。
        violations, progress_waiver_notes = _validate_claude_progress_open_item(
            _read_target_text(args.file), _read_snapshot(args.file),
        )
    if violations:
        print(f"✗ release 被拒绝（{len(violations)} 项结构问题，锁保持占用，请修正后重试）：")
        for v in violations:
            print(f"  - {v}")
        return 1

    # 队列 #200：把"正式交还"的目标文件内容记为基准——下一次 acquire 据此
    # 判断这期间文件是否被绕过锁直接改写过。放在结构校验通过之后（不通过
    # 时不算真正 release，不应更新基准）。
    lastknown_targets = _iter_queue_paths() if _is_queue_system_target(args.file) else [args.file]
    for content_target in lastknown_targets:
        _write_lastknown(content_target, _read_target_text(content_target))

    # 改写为 released 标记而非 unlink（#121(a)）：Cowork 沙箱挂载对本文件
    # unlink 会返回 PermissionError（acquire 建文件正常，release 删不掉），
    # 改写规避了这个问题，且本地/CC 环境同样适用——不需要按环境分叉代码路径。
    # released 标记等价于"无锁"（见 _read_lock），下一次 acquire 当空锁立即成功。
    # 判据 J4 逃生阀留痕：`进度豁免：<理由>` 的理由同时落进锁的 `history`
    # ——正文里那份进 git（长期），history 这份给下一次 acquire 的回显看见
    # （短期，`HISTORY_RETENTION_MINUTES` 后自然过期）。**两者不是冗余**：
    # 前者答"当初为什么放行"，后者答"刚才谁在这把锁上放行过"。
    released_history = list(existing.get("history", []))
    for note in progress_waiver_notes:
        released_history.append(
            {"who": existing.get("who", ""), "note": note, "at": _now().isoformat()}
        )

    _write_released_marker(
        lock_path, existing.get("who", ""), existing.get("note", ""),
        existing.get("held_since", ""), history=released_history,
    )
    print("✓ 已释放（改写为释放标记，未删除文件——沙箱环境亦可用）")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    lock_path = _lock_path(
        QUEUE_LOCK_ANCHOR if _is_queue_system_target(args.file) else args.file
    )
    # 决策点5：status 是最低成本的高频只读检查（本机常用于"开工前先核实
    # 无锁"），幽灵副本检测放在这里同样生效，不必等到 acquire 才第一次
    # 被提醒。
    status_targets = _iter_queue_paths() if _is_queue_system_target(args.file) else [args.file]
    for content_target in status_targets:
        shadow_warning = _detect_shadow_copy(content_target)
        if shadow_warning:
            print(shadow_warning)
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
    parser.add_argument(
        "--file", default=DEFAULT_TARGET,
        help=f"目标文件相对仓库根路径（默认 {DEFAULT_TARGET}——队列 #315 起，"
             "这一默认值触发队列系统双文件路由：acquire/release/status 覆盖"
             "机制环境与业务场景两份物理文件、共用一把锁；append-row 按 "
             "--domain 路由到其中一份。显式传其它路径（如跟进信 README）时"
             "行为与拆分前完全一致，单文件单锁）",
    )
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
             "对齐协议〇.9 措施 C）。本次持锁期间新增了 [D:机] 的 §一 行且重算后"
             "超限时，release 被拒绝（队列 §四 #58 ⑶，2026-08-17 起由提示改为"
             f"阻断）——见 --force-mechanism-wip",
    )
    p_release.add_argument(
        "--force-mechanism-wip", action="store_true",
        help="队列 §四 #58 ⑶ 逃生阀开关（不携带理由文本）：确属紧急必须在超限时"
             f"新立机制行时传入。**须与行内标记同时到位**——本次新增行的状态列内"
             f"还须写明「{MECHANISM_WIP_WAIVER_MARKER}<理由>」，缺任一即仍拒绝。"
             "理由的唯一真源是行内标记（进 git、被 lint 与值周巡检看得见），"
             "本开关只表达「我知道我在越过一条规则」这个显式意图",
    )
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="查看锁状态，无副作用")
    p_status.set_defaults(func=cmd_status)

    p_append_row = sub.add_parser(
        "append-row",
        help="队列 #258：追加一行到指定分区，插入位置/列数/裸竖线由工具保证",
    )
    p_append_row.add_argument(
        "--who", default="",
        help="队列 §一 #351 ⑴：调用方身份，须与当前持锁人一致。目标存在**有效锁**"
             "而本参数缺失或不符时拒绝写入（2026-08-18 真实事故：acquire 已被正确"
             "拒绝、打包命令照跑照写，在他人持锁期间写入两次）。目标无有效锁时不"
             "要求本参数，只打印一行无锁写入提示——协议〇.7 是协作性质，不因本项"
             "变成硬互斥",
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
             "（批次/文件清单/建议 message/状态，首个即批次号）、§四 3 个（事项/等谁/截止）",
    )
    p_append_row.add_argument(
        "--domain", choices=("机", "业"), default=None,
        help="队列 #315 决策点3/5：§一/§二 写入哪份物理队列文件（机制环境／"
             "业务场景）；§四 恒定写机制环境文件，本参数对 §四 无效果。未给出"
             "时向后兼容默认落机制环境文件（迁移期妥协，见函数"
             "`_resolve_append_target` 文档）",
    )
    p_append_row.set_defaults(func=cmd_append_row)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
