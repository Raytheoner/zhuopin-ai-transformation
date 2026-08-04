# wecom-followup-dispatch-automation Proposal

## Why

跟进信从"Shao Peishen 审阅通过"到"实际发出"之间，现状唯一的把关动作是一次人工触发（CC/专线手动跑 `push_followup_letter.py`）——这件事本身低风险、机械，但每次都要求有人开一个 session 才能完成。队列 #124 记录的痛点：2026-07-27 一天内积压 4 封定稿待发信，全部只差"有人跑一次脚本"；2026-08-04 Shao Peishen 就阶段二正式拍板选 (a)（Cowork 起草 ＋ 你审完后由机制直接发送），触发原因是本周 A1/A2 两条 Cowork 专线各自都要再开一个 CC session 才能把已审信发出去。

但把"实际发出"这一步交给机制自动执行之前，必须先补一个安全内核：**现状 README「发送状态」列是单态语义**——起草者（CC/Cowork 专线）自己既可以写草稿标记，也可以直接写"🆕 待发"（既有 gate②——`gates.assert_finalized`——唯一认的终态标记），"是否已获 Shao Peishen 真实审阅通过"完全靠聊天记录里一句话、无任何机制层面的证据要求。当前这个风险被一个隐藏的人工兜底盖住：即使起草者标错了"🆕 待发"，实际发送仍需要 CC 手动开 session 跑脚本，人工触发这一步天然是最后一道人眼复核。**一旦发送自动化，这道隐藏兜底消失**——README 状态列会直接决定是否真的把消息发给专员/群，"专线自己标待发、Shao Peishen 未必读过就可能被发出"这条现状风险从"总有人工介入"退化为"完全无人介入"。

本变更包在自动化落地前，先把 README 状态语义从单态改为两态（起草只能写草稿态，唯一的批准转换路径强制留痕批准依据），并让结构性拦截而非自觉遵守来保证这条边界，然后才建造发信自动化外壳。本变更同时命中 CLAUDE.md §5「机制/工具类模块的 openspec 触发门槛」两条——「改变既有模块对外语义」（它改的是「对外发送」这一动作的授权语义，是本项目最硬红线「对外发送永不进池」的具体实现）与「涉授权」——按约定必须走 openspec 变更包 + design 审，design 审通过前不得 apply（同队列 #159／#162 既例）。

## What Changes

- README-跟进机制与命名约定.md 新增「两态语义」规范章节：起草（人工专线／CC 建造会话／未来的 #122 自动化）新增登记行时，「发送状态」列只能写 `⏳ 待你审`；转换为终态 `🆕 待发` 仅能通过新增批准脚本 `approve_followup_letter.py` 完成，该脚本强制要求调用方提供批准依据摘录（如 Shao Peishen 的放行原话）并写入独立于聊天记录的审计事件。
- `工具-共享文档编辑锁.py::_validate_release_structure`（#225 已引入的结构性校验框架）新增一个专属分支：锁定目标为跟进信 README 文件时，拒绝"本次持锁窗口内新增的行、状态列即为 `🆕 待发`"这一反模式——起草物理上不能一步到位写终态。
- 新增独立每日定时任务 `ZhuopinFollowupDispatchDaily`（笔记本本地，工作日固定时刻），复用既有 `push_followup` 逻辑扫描并发送 README 中状态严格等于 `🆕 待发`、且未标注 `🔒人工发送` 的行；单行失败不阻塞其余行；采用"不承诺准点、只承诺下次开机即发"的可靠性模型（`-StartWhenAvailable`，同 #172/#189/#199 先例）。
- README 新增 `🔒人工发送` 标记约定：硬截止交付的跟进信（如 #59 那类）起草时须显式标注，自动发信任务结构性跳过这类行，仍走人工触发（`push_followup_letter.py`）保证可控时限。
- #122（Dispatch v0.6 起草类任务自动化，尚未建造）复用本变更定义的"起草只能产出 `⏳ 待你审`"契约，不新定义自己的一套安全约定——本变更把这条约定一次性定死，08-06 评估 #122 时无需在这一维度重新讨论。
- **BREAKING**：无。既有 `gates.assert_finalized`（gate②）、`delivery.push_followup`、`readme_table.locate_row/write_status` 均不改变现有行为契约，本变更只在其"前面"新增一层写入约束与一个消费者（批处理任务）。

## Capabilities

### New Capabilities

- `wecom-followup-review-state`：跟进信 README「发送状态」列两态语义（草稿态/终态）、唯一合法批准转换路径、批准留痕、结构性拦截、硬截止标记、起草契约对起草来源一视同仁。
- `wecom-followup-auto-dispatch`：每日定时批处理发信任务的扫描范围、硬截止跳过、单行失败隔离、时限承诺、部署位置约束。

### Modified Capabilities

（无——`wecom-followup-delivery`（gate②/`push_followup` 现有契约）位于尚未 `/opsx:archive` 的 `wecom-aibot-channel` 变更包内（tasks.md 仍有 8 项未完成），本变更不对其做跨包 delta，只在 design.md Context/Risks 中说明依赖与协调方式，避免对一个仍在演进的活跃变更包做脆弱耦合。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 三处：① "什么算已获得 Shao Peishen 的真实放行"——目前完全在聊天记录里，无固定句式（"选(a)照发"/"确认"/"可以发"等表述不一），需要人工判断；② "哪些跟进信属于硬截止交付"——目前也是人工判断（如 #59 那类），无固定标注规则，起草者凭经验识别；③ 发信班次的运行时刻怎么选，才能既不与既有 sweep（每小时）/值周巡检（周一10:00）/决策提醒（每日08:30）/拆件巡逻（9:00 13:00）撞车，又能覆盖典型审批发生的时间窗——目前是人工经验判断（工作日下午/傍晚居多）。
2. **由谁显性化？** 本变更为平台机制/工具类模块（非对客业务场景），无部门专员对口；持有人＝环境保障线（Cowork，负责判据设计与规范文本）+ CC 建造车间（负责机检落地与部署验证），backup／唯一拍板方＝Shao Peishen 本人（其 2026-08-04 已就阶段二启动方式、§四#48 心跳探测取舍两项拍板；design 内其余取舍需其审过后方可 apply）。
3. **用什么方法提取？** 历史案例反推——直接复用三个已在本仓库验证过的套路，不重新发明：#225（编辑锁 `release` 结构性校验框架）、#172（`decision_reminder` 状态持久化+独立审计留痕）、#189/#199（笔记本本地+每日+对外发送的计划任务部署范式：`LogonType=Interactive`/`-StartWhenAvailable`/VBS 隐藏启动器）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：不适用四档"对客交付"口径（机制/工具类模块，无部门专员对口）；套用最接近的档位描述＝**档3 内部服务扩展**（发信动作本身已是内部服务`wecom-aibot-service`的既有能力，本次是给它加安全内核+自动化外壳，非首次上线）。
- **晋下一档的条件**：不适用"晋档"概念；改用**验收标准**——① design 审通过（Shao Peishen 明确批准）方可进入 apply，本变更包止步于 propose+design；② apply 阶段的验收标准见 design.md「Migration Plan」（全量回归零漂移 + 真实部署 + 真实构造一次"起草→批准→自动发送→回填"端到端场景验证 + 硬截止标记行确认被跳过）。
- **价值指标**（工时型）：消除"审批完信件仍需专线/CC 额外开一个 session 手动触发"这一中间人工步骤——基线＝当前每封信从「README 标 🆕 待发」到「实际推送」之间的真实间隔（历史上从几小时到跨天不等，取决于何时有人下次开 CC session，见 README「现有跟进信清单」各行"✅ 已推送"时间戳与其对应"起草日期"的落差作为参照样本）；目标＝自动化上线后该间隔收窄至"至多一个班次周期内"（工作日 24 小时内），硬截止信仍走人工快速通道不受影响。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断，README 状态转换与批处理扫描均为确定性规则）。

## Impact

- 受影响文件（apply 阶段）：`6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`（新增"两态语义"章节 + `🔒人工发送` 标记约定）；根 `CLAUDE.md` §5 场景固定流程第 8 步（措辞更新为"起草只写 `⏳ 待你审`"）；`5-平台底座/wecom-aibot-service/aibot_service/readme_table.py`（新增草稿态断言辅助函数）；新增 `5-平台底座/wecom-aibot-service/scripts/approve_followup_letter.py`；新增 `5-平台底座/wecom-aibot-service/scripts/dispatch_followup_letters.py`；`0-学习与工具/工具-共享文档编辑锁.py`（`_validate_release_structure` 新增 README 专属分支）；新增 Windows 计划任务 `ZhuopinFollowupDispatchDaily`。既有 `gates.py`/`delivery.py` 不改动。
- 受影响计划任务：新增 `ZhuopinFollowupDispatchDaily`（笔记本本地，工作日），与 `ZhuopinAibotDevListener`/`ZhuopinDecisionReminderDaily`/`ZhuopinCommitSweep` 同机部署，不新增服务器/端口。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——新增 `followup_approved`/`followup_auto_dispatch_*` 审计事件，写入既有 `wecom_aibot_audit.jsonl`；OEM 隔离——不适用；L2 人工确认门禁——不适用（专员均内部人员，本变更不涉及 `CUSTOMER_OUTBOUND_ENABLED`）；ISO 26262——不适用。**唯一实质性红线**：本变更修订的是"对外发送"这一动作的授权语义，是项目最硬红线"对外发送永不进池"的具体实现，design 必须经 Shao Peishen 明确批准方可 apply（同 #159／#162 既例）。
