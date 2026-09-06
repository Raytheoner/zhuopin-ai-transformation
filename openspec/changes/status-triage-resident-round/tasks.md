# status-triage-resident-round Tasks

> **✅ design 审已过，apply 中（`OP-0906-N`，2026-09-06，CC worktree `agent-ab0e84fbde438eec9`，分支 `claude/op0906n-status-triage-apply-454`）。** §0 三项裁决由 Shao Peishen 于 2026-09-06 `OP-0906-G` 看护会话当场给出（原话「都按建议」）。

## 0. design 审前置（阻断全部后续项）

- [x] 0.1 **前置登记**：design D4 ＝ **(a)** —— 只检测＋告警＋给可粘贴的 `append-row` 草稿命令，**不自动写 §四**。裁决人 Shao Peishen，2026-09-06 `OP-0906-G`。理由（他认可的推荐理由）：精度 3/8 下 (b) 会把 5 条假阳性写进台账；且 (b) 等于给 sweep 新开一条机器写队列正文的路径，与 `#326`／`#322` 两次事故同族。⇒ spec 无须重写，按既有 (a) 版实现。
- [x] 0.2 **前置登记**：D3 ＝ **(a) 同意退休** release 校验 ⑨ 的候选接线，one-in-one-out。裁决人 Shao Peishen，2026-09-06。理由：不退休即「两套判据各自轮询」（`#366` 教训）；且 release ⑨ 实测此刻（WIP 21/22）根本不触发。
- [x] 0.3 **前置登记**：次序 ＝ **(a)** `#454` 先 apply、`#462` 随后按 `#454` 落定的第 12 类接线点接入。裁决人 Shao Peishen，2026-09-06。理由：`#454` design 已定义该接线点且明确排除挂 `#462`，而 `#462` 至今未起草 openspec。
- [x] 0.4 `openspec validate --strict status-triage-resident-round` 通过（2026-09-06 本 worktree 复跑，见 §7 收工记录）。

## 1. 否定词表与回测（前置 0.1/0.4）

- [x] 1.1 否定词表已定稿于 `工具-共享文档编辑锁.py::TRIAGE_NEGATION_PHRASES`，**九条、每条附一个真实来源行号**（`已闭合`→#340／`已解除`·`依赖解除`→#470／`误报`→#340／`假阳性`·`误命中`→#462／`已由 Shao Peishen`·`已答`·`已批准`→#470）。判定窗口 ＝ 命中措辞前后各 `TRIAGE_EXCERPT_CONTEXT_CHARS`(60) 字——**不是分诊器现行的 `idx-10/idx+len+20` 窄窗**：那个窄窗在 `#470`/`#471`/`#472` 上恰好在「已由」二字处截断，否定词落在窗外、四条全部漏降。**窗口宽度是本词表能生效的前提，不是显示参数。**
- [x] 1.2 **回测阻断项达标**（2026-09-06 对两份队列**真身**实跑 `triage-candidates`，非夹具）：4 条亚型 B 全降弱档 ✅、3 条真阳性全保强档 ✅。逐条见 1.3。
- [x] 1.3 回测结果原文（`python 0-学习与工具/工具-共享文档编辑锁.py triage-candidates [--queue …]`，2026-09-06 本 worktree 实跑输出）：

| # | 域 | 命中措辞 | design 预期 | 实测档位 | 降档因（实测） |
|---|---|---|---|---|---|
| `#455` | 机 | 待 Shao Peishen | 强 | **强** ✅ | — |
| `#394` | 业 | 待 Shao Peishen | 强 | **强** ✅ | — |
| `#418` | 业 | 留步 | 强 | **强** ✅ | — |
| `#340` | 业 | 留步 | 弱 | **弱** ✅ | `已闭合`／`误报` |
| `#470` | 业 | 留步 | 弱 | **弱** ✅ | `已由 Shao Peishen` |
| `#471` | 业 | 留步 | 弱 | **弱** ✅ | `已由 Shao Peishen` |
| `#472` | 业 | 留步 | 弱 | **弱** ✅ | `已由 Shao Peishen` |
| `#462` | 机 | 待 Shao Peishen | **强（design 预言本包解决不了它）** | **弱** | `假阳性` |
| `#454` | 机 | 留步 | **design 期未出现（新增）** | **弱** | `已闭合`／`已解除`／`已批准` |

🔴 **两条必须如实说明的偏差，不含糊过去**：

1. **`#462` 被降档，但亚型 A 并没有被解决。** design D2 明确预言「`#462` 这一条在本包上线后仍会误报为强档，这是如实承认的残留误差」。实测它落到弱档，**原因不是本包学会了判断主语，而是该行正文里恰好写着「日核假阳性」四个字、被否定词表顺手扫到**。换一行同样"引用他人阻塞状态"却不含否定词的行，仍会误报为强档。**这是巧合，不是能力**——单测 `test_亚型A本包不试图机器解决_但仍被如实登记为候选` 刻意只断言"它仍被产出且命中片段被原样附上"，不断言它被正确判为假阳性，就是为了不让这次巧合被后人误读成"亚型 A 已解决"。
2. **候选总数由 8 变 9，多出的正是 `#454` 自己。** 起因是 `OP-0906-G` 看护会话把 design 的实测结论回写进了 `#454` 的状态列，其中原样引用了「该留步已闭合/已解除/已批准」这句话。⇒ **本行的状态自陈被自己的判据命中了。** 它被正确降为弱档，是亚型 A（引文）与亚型 B（否定词）同时命中的一个现成实例。

## 2. 只读候选出口（编辑锁侧，前置 1.2）

- [x] 2.1 `工具-共享文档编辑锁.py` 新增只读子命令 `triage-candidates --queue <路径> [--json]`（`cmd_triage_candidates`）：扫指定队列 §一，输出 `candidates`／`awaiting_rows`／`row_ids`／`has_section_four`／`criteria_drift`。**不 acquire 任何锁、不写任何文件、连锁文件都不看一眼。** 刻意**一次只扫一份队列**——调用方需要知道每条候选来自哪份文件，合并输出会把来源从天然的调用边界降格成一个额外字段。
- [x] 2.2 复用 `_suggest_status_reclassification()`／`_table_data_rows()`／`_parse_status_domain_fields()`／`STALE_STATUS_PHRASES`，**不新写解析**。🔴 **候选集合的权威判定仍是 `_suggest_status_reclassification()`**：新函数 `_collect_triage_candidates()` 只对它已认定的行重新定位措辞、取宽窗、算档位；若两侧走出的行集不一致，**如实记进 `criteria_drift` 并以权威判定为准，不静默取其一**（本项目「工具静默回退」一族）。`_suggest_status_reclassification()` 与 `STALE_STATUS_PHRASES` **一个字未改**（spec MUST NOT）。
- [x] 2.3 单测（`TriageCandidatesCliTests`，5 例）：① `test_不acquire任何锁_运行后无锁文件`；② `test_运行后目标文件逐字节不变`（JSON 与人读两条路径各跑一次后逐字节比对）；③ `test_json出口含分档与自陈行` 覆盖两份队列各自可指定；另加 `test_目标文件缺失时不崩_如实报queue_exists为假`（不把"读不到"伪装成"没有候选"）。

## 3. sweep 第 12 类接线（前置 2.3、0.3）

- [x] 3.1 新增 `_check_status_triage_candidates()`（＋入口 `_check_status_triage_and_ledger()`、取数 `_collect_triage_payloads()`）：子进程调 2.1，按 JSON 的 `tier` 字段分强弱两桶，强档走 `_track_and_alert_standing_state`（key ＝ `队列文件名|行号|措辞`，节流 24h），弱档只回显。**sweep 侧不重算档位、不复制第二套判据**（design D5）。
- [x] 3.2 子进程不可用时按第 10 类同形告警「判据不可用」（`STATUS_TRIAGE_UNAVAILABLE_STATE_REL`），**不得判为零候选**。🔴 **apply 期实测撞出一处、就地修**：初版在判据不可用时仍打了一行「强档 0 条／弱档 0 条」——那句话与真的零候选在日志里**逐字相同**，而两者后果差一个量级（"没事" vs "本轮什么都没看"）。改为：全不可用时**根本不打计数行**、改打「未取到任何一份队列的候选」；部分不可用时计数行自带覆盖面「已扫 1／2 份队列，缺 1 份」。两条各有单测钉住。
- [x] 3.3 已接进 `main()` 非 dry-run 分支，**排在第 11 类 `_check_draft_gap_inventory` 之后**（单测 `test_本类不影响主流程退出码_异常被捕获` 用源码顺序断言钉住）；异常经 `_track_and_alert_standing_state` 既有 `except Exception` 捕获，不影响本轮退出码。
- [x] 3.4 单测 `test_wip未超限时候选仍被产出并进入渲染`（**派单件第 2 步点名的场景**）＋ `test_业务场景队列的候选被覆盖_原本结构性不可达`。🔴 夹具**真的把编辑锁脚本拷进临时仓库**跑子进程，不打桩——打桩只会验证"我写的桩返回了我写的值"。
- [x] 3.5 单测 `test_命中片段反引号成对`（sweep 侧，逐行断言反引号偶数）＋ `TriageExcerptBacktickGuardTests`（编辑锁侧 4 例，含 `_balance_backticks` 纯函数与端到端片段）。
- [x] 3.6 单测 `test_零候选时回显行仍出现`。

## 4. 决策台账缺口检测（前置 0.1 答 (a)；答 (b) 本节作废重写）

- [x] 4.1 新增 §四 结构化解析 `_section_four_covered_rows()`（sweep 此前无）：`_find_section_heading` 行首锚定 `## 四、`，取到下一个 `## ` 为止，`SECTION_FOUR_ROW_REF_RE` 抓全部 `#N`。**含已结案行**（design D7）。业务场景队列无 §四，覆盖面只从机制队列取。
- [x] 4.2 扫描面独立于分诊器：由编辑锁侧 `_collect_awaiting_decision_rows()` 提供，只排除 `done` 与 `timed=`，**覆盖 `blocked`**。单测 `test_blocked行的台账缺口被检出_扫描面独立于分诊器` 钉住"同一条 `blocked` 行不进改判候选、却进台账缺口"这一刻意的不对称。
- [x] 4.3 行号重叠时**报错并拒绝输出本轮缺口**（不静默按重叠结果匹配）——单测 `test_两份队列行号重叠时报错而非静默匹配`。2026-09-06 实测交集仍为空集（机制 §一 105 行、业务 §一 45 行）。
- [x] 4.4 `_render_ledger_append_draft()` 渲染**两步全给**的草稿命令（`acquire --reserve 1 --section 四` → `append-row --section 四 --set …` → `release`）；业务域来源在正文点明「🔴 跨文件登记……请先确认归属再执行」。**只给 `append-row` 那一半等于让人自己去想第一步，而那正是协议〇里最常被跳过的一步。**
- [x] 4.5 单测 `test_台账缺口被检出并给出可粘贴命令_但不写队列`（**派单件第 2 步点名的场景**）。
- [x] 4.6 单测 `test_台账已结案行提及即算已覆盖`。（用例名不用 `§`：Python 标识符不接受 U+00A7，apply 期实测报 `SyntaxError`。）
- [x] 4.7 单测：`test_台账缺口被检出并给出可粘贴命令_但不写队列` 断言运行后队列逐字节不变；编辑锁侧 `test_不acquire任何锁_运行后无锁文件` 断言零锁 acquire。真身侧另有 6.1 的 `git status --porcelain -- 1-转型规划` 空输出。

## 5. 退休 release ⑨ 接线（前置 0.2）

- [x] 5.1 已移除 release 校验 ⑨ 内的 `_suggest_status_reclassification()` 调用与 `_mechanism_wip_over_cap_violations()` 的 `reclass_candidates` 形参（原处留长注写明退休理由与去向）。
- [x] 5.2 三者原样保留在编辑锁模块，既有单测保留。`_render_reclassification_candidates()` 已无生产调用方，其 docstring 顶部加红字**明令不得当死代码删**（它与判据是同一份权威的一读一渲，删掉渲染侧会让将来任何一次复用去重新发明格式）；新增 `test_reclassification_helpers_survive_the_retirement` 钉住三者仍在且渲染格式仍可用。
- [x] 5.3 原用例 `test_mechanism_wip_rejection_carries_reclassification_candidates` **翻转**为 `test_mechanism_wip_rejection_no_longer_carries_candidates_but_keeps_ways_out`：断言拒绝文案不再含「改判候选清单」与候选行号，但**仍含 WIP 计数（`3／2`）与「两条出路」**——退候选接线不等于把拒绝文案退成不可行动的。`test_mechanism_wip_escape_hatch_messages_omit_candidates` 原样保留、原样通过。

## 6. 真实数据验证（前置 3.6、4.7、5.3）

- [x] 6.1 对两份队列**真身**实跑（2026-09-06，本 worktree）。🔴 **口径更正**：本类与第 4/6/7/9/10/11 类同形，**接在 `main()` 的非 dry-run 分支内**，故 `--dry-run` 恰恰跑不到它——tasks 原文写「跑一次 `--dry-run`」是起草期的口误。改为**直接调用 `_check_status_triage_and_ledger()` 打真身**（比 dry-run 更贴近生产路径，且同样零写入，已用 `git status --porcelain -- 1-转型规划` 空输出取证）。逐条比对：

| 指标 | design §1 实测（起草期） | 本次 apply 期实测 | 差异解释 |
|---|---|---|---|
| 候选总数 | 8（机 2 ＋ 业 6） | **9**（机 3 ＋ 业 6） | 多出 `#454` 自己——`OP-0906-G` 把 design 结论回写进它的状态列，原样引用了「该留步已闭合/已解除/已批准」⇒ 本行被自己的判据命中，正确降为弱档（见 1.3 偏差 2） |
| 强档 | 3 | **3** ✅ | `#455`／`#394`／`#418`，与 design 逐条一致 |
| 弱档 | 5 | **6** | ＝ design 的 5 条 ＋ 新增的 `#454`；其中 `#462` 由 design 预言的"强"变"弱"，是巧合非能力（见 1.3 偏差 1） |
| 自陈待他一次动作 | 16（机 15 ＋ 业 1） | **16** ✅ | 完全一致 |
| 台账缺口 | 5，扣假阳性后 ≤4 | **4**（`#337`/`#341`/`#455`/`#462`） | `#394` 已于起草与 apply 之间被登进机制队列 §四 ⇒ 按 D7「§四 提及即算覆盖」正确出列。落在 design 预测的 ≤4 区间内 |
| 机制类可动 WIP | 21／22 | **20／22** | 期间有行销号；不影响本包——**本类不以 WIP 为触发条件，这正是本包的要点** |
| §四 被 `#N` 提及的行号 | — | 174 | 新测项 |
| 两份队列行号交集 | 空集 | **空集** ✅（机 105／业 45） | design 记业务 §一 44 行，现 45 行（期间新立一行） |

- [x] 6.2 `0-学习与工具` 单测全量绿、**零回归**（2026-09-06 本 worktree 实跑，逐条记数）：`test_工具-共享文档编辑锁.py` **391 passed / 8 subtests**（含新增 18 例、翻转 1 例）；`test_工具-落库sweep.py` **424 passed / 51 subtests**（含新增 14 例）；另跑全部 10 个引用这两个模块的测试文件（`test_hooks-p3.py`／`test_hooks-pretooluse-queue-read-guard.py`／`test_hooks-哨兵.py`／`test_发企微.py`／`test_工具-CLAUDE进度段lint.py`／`test_工具-共享文档编辑锁-补件选表.py`／`test_工具-变更包自动归档.py`／`test_工具-引导样板lint.py`／`test_工具-跟进信README登记.py`／`test_工具-队列查询.py`）全绿。
- [ ] 6.3 企微推送**首次真实触发**留痕（运维群，非业务群）—— ⏭ **本项不由本泳道完成**：告警出口是 `WECOM_WEBHOOK_URL_OPS`，本 worktree 的 `.env` 无该键（实跑日志：「未在 .env 找到 WECOM_WEBHOOK_URL_OPS，跳过推送（仅留痕日志与状态文件）」）。首次真实推送将在**本包合入 master 后的第一轮 `ZhuopinCommitSweep`** 自然发生（当前真身有 3 条强档候选 ＋ 4 条台账缺口，必然触发）。⇒ 留痕核验交合入后的值周巡检，已写进队列回写。

## 7. 收口（前置 6.3）

- [x] 7.1 `工具-CI覆盖率护栏.py` —— **本地不可直跑**（它要 `--results-dir`，聚合的是 CI 各矩阵腿产出的 JUnit XML，不是本机能造的输入）。**按其三条下界逐条推演本包的影响方向**：① 总 passed **只增不减**（新增 32 例、零删除，翻转的那一例仍是一例）；② 总 skipped **不变**（本包新增用例无一处 `skipIf`／`skip`）；③ 矩阵腿数 **不变**（未增删子项目）。三条全部朝安全方向走 ⇒ 护栏不会因本包跌破。**真正的通过与否以合入后的 CI 运行为准，此处不冒充已跑过。**
- [x] 7.2 知识资产台账已登记：`1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md` §一.2 新增一行「**队列状态分诊三尺度**」——持有人 Shao Peishen／backup 孙涛，提取方法＝历史案例反推（主）＋ L2 改判判例累积（辅，满 5 条负例即回头收紧措辞表），显性化形态＝两份词表 ＋ **如实写明「§四 准入尺度至今无成文规则、本包不试图代拟」**。🔴 **该行是本表首条机制/环境类条目**（此前 9 行全是业务场景的专家默会经验），已在行内显式标注，避免后人把它当成一个漏填了场景号的业务条目。⚠️ 本文件不在 `#454` 行声明的触碰区内，是 proposal §知识资产三问第 3 条明令「本包 apply 时执行」的动作 —— 已在队列回写与 §二 批次里显式点名。
- [ ] 7.3 回写队列 `#454` ＋ 登记 §二 批次。🔴 **不写 `[S:done]`**：6.3（企微首次真实推送留痕）须待合入 master 后的第一轮 sweep 才能取证，本行按 `[S:partial]` 回写并点名该唯一留步项。
- [ ] 7.4 `/opsx:archive status-triage-resident-round -y` —— **待 6.3 留痕后**再归档：归档一条尚未验证过出口的告警类变更，等于把"它到底响没响"这个问题永久埋进 archive。

## 8. apply 期新增登记（不在原 tasks 内，如实补记）

- [x] 8.1 **状态文件多出一个**：proposal §.gitignore 覆盖节只点了 `sweep-status-triage-state.json`／`sweep-decision-ledger-gap-state.json` 两个；实现按第 10/11 类同形另需 `sweep-status-triage-unavailable-state.json`（判据不可用的出现/解除留痕）。**三者均已用 `git check-ignore -v` 实跑核实**，全部命中 `.gitignore:35:**/reports/`，`exit=0`。不重演 `#322` 的孤儿脏文件形态。
- [x] 8.2 **`#462` 的接线点已就位**（次序裁决 (a) 的下半句）：第 12 类的入口 `_check_status_triage_and_ledger(repo_root, log)` 即 `#462` 随后要挂的那个点，位于 `main()` 非 dry-run 分支末尾、第 11 类之后。`#462` 接入时应新增自己的 `_check_*` 并在同一处调用，**不新建独立轮次**。
- [x] 8.3 **两处此前登记过的 `edit-row` 写侧缺陷仍未立行**（design Q4 的可见性提醒）：反引号奇偶校验缺失、已塌列行的鸡生蛋。本包只在**输出侧**加了 `_balance_backticks`（防止告警引文被粘回去写坏行），**写侧守卫未动**——那属 `#455`／`#462` 触碰区，本包「不做什么」已排除。此处仅再提醒一次可见性。
