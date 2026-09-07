# followup-approval-cooldown-5min Proposal

> **状态：propose 出件，等 design 审。** 本包**不得** apply，直到 Shao Peishen 完成 design 审。
> **来源**：Shao Peishen 2026-09-07 当日提出「冷静期，能否都可调整为 5 分钟」，并于同日答 (a) 认可减半；随后在得知本包门槛后再答「推荐」＝**回滚就地改动、改走 openspec**。
> **openspec 门槛核对**（`.claude/rules/场景建造与合规.md` §二「机制／工具类模块的 openspec 门槛」）：命中 **①「改变全项目口径（取号／编号／**判据**／状态语义）」**——冷却窗口是批准闸的**判据阈值**，作用于全项目每一封跟进信的批准流程。⇒ **必须走 openspec 且必须含 design 审。**

## Why

### 这道闸现在拦住的是谁

冷却窗口（`aibot_service/approval.py::DEFAULT_COOLDOWN_MINUTES = 10`）由 design 审后 Shao Peishen 追加要求① 引入，目的写在代码注释里：**堵住「起草→release→立刻批准」这种同一 actor、中间没有真人的两步连做**。

**2026-09-07 当天的实测**：他为 `财务部#17` 与那封致歉补件**各等了一次完整的 10 分钟**，而两封信的内容他都早已逐句看过——第二封甚至是他连答两轮定夺（`1a，2a` ＋ `发`）之后才开始计时的。**这道闸这一天拦住的不是仓促，是他本人的时间。**

### 为什么 5 分钟仍然成立

这道闸的真实功能是**给人留出看信的时间**，而它上下游各有一道**更硬、且不依赖时长**的关卡：

| 位置 | 关卡 | 性质 |
|---|---|---|
| 上游 | `approve_followup_letter.py --quote` **必填批准依据**（写的是他的放行原话） | 结构性必填，缺即 `ValueError` |
| 本闸 | 冷却窗口 | **时长型**，唯一一道靠"等"生效的 |
| 下游 | skill `zhuopin-send-followup` §0 铁律：发送前**必须读回「收信人＋编号＋标题」并等他回一个「发」** | 人守，但钉在最后一个不可逆动作前 |

**5 分钟仍然拦得住注释里写的那个原始场景**（同一 actor 起草完一秒内顺手批准）——它挡的从来不是恶意，是**仓促**；而"顺手一起做掉"与"刻意等五分钟"之间的界线，5 分钟与 10 分钟画在同一侧。

### 为什么不能就地改（本包存在的直接原因）

`openspec/specs/wecom-followup-review-state/spec.md` 的 **Requirement:批准冷却窗口** 正文里**写死了"默认 10 分钟"**。

⇒ **就地改代码会让 spec 与实现悄悄漂开**：spec 说 10、代码是 5，**而没有任何机制会因此报错**——`openspec validate` 不比对常量值，测试只测行为不测文档。这正是本项目反复吃亏的那一族形态：**错误不产生任何信号**。**改 spec 与改代码必须是同一次动作，这是 openspec 门槛①存在的具体理由，不是形式。**

📌 **本包的诞生过程本身即一次实证**：2026-09-07 `OP-0907-L3` 会话在**未读 `.claude/rules/场景建造与合规.md` 的情况下就地改了这三个文件**（代码 ＋ 脚本文档串 ＋ 两个被阈值钉死的用例，相关单测 83 passed），事后补读规则才发现命中门槛①，当场如实上报并按 Shao Peishen 的裁决**全量回滚**。⚠️ **值得记下的不是"改错了"，而是：那次就地改动测试全绿、行为正确、理由充分——唯独 spec 没跟着动，而没有任何一个检查会告诉你这件事。**

## What Changes

- **`DEFAULT_COOLDOWN_MINUTES` 由 10 改为 5**（`5-平台底座/wecom-aibot-service/aibot_service/approval.py`），并在常量上方注释写明改动理由、已知代价与"不再往下调"的下限判据。
- **`openspec/specs/wecom-followup-review-state/spec.md` 的「批准冷却窗口」Requirement 同步改为 5 分钟**（本包 spec delta 走 `MODIFIED`）。
- **`scripts/approve_followup_letter.py` 模块文档串**里的「10 分钟」同步改口，并指向常量处的理由注释。
- **两个被旧阈值钉死的用例同步改**（`tests/test_approval.py`）：`test_approve_still_blocked_before_cooldown_elapses` 的 5 分钟改 3 分钟（旧值在新阈值下正好"已满"，会当场变红——**这是正确的失败，它钉的就是阈值**）；`test_approve_succeeds_after_cooldown_elapsed` 的 11 分钟改 6 分钟（旧值在新阈值下照样通过 ⇒ **不会变红、也就不再钉住任何东西**）。改完这一对用例（3 分钟拒 / 6 分钟放）继续**从两侧夹住 5** 这个阈值本身。
- **`--cooldown-minutes` 参数保持不变**，仍供测试与特殊场景按次覆盖。

## 不做什么

- ❌ **不动 `check_cooldown` 的算法与状态文件格式**——只改默认值，行为语义一字不改。
- ❌ **不改 `--quote` 必填、不改读回铁律**——它们是本包"减半仍安全"这个论证的前提，动了前提就不成立。
- ❌ **不把用例写成 `DEFAULT_COOLDOWN_MINUTES - 2` 这类相对式**——那样阈值再改时用例自动跟着漂，而**这一对用例的全部价值就在于阈值一动它就报**。
- ❌ **不下调到 3 分钟或更短**（Shao Peishen 2026-09-07 同批否决）：3 分钟内起草＋批准是完全做得到的，那这道闸只剩形式。

## Impact

- **受影响 spec**：`wecom-followup-review-state`（MODIFIED 一条 Requirement）。
- **受影响代码**：`aibot_service/approval.py`（1 个常量 ＋ 注释）／`scripts/approve_followup_letter.py`（文档串）／`tests/test_approval.py`（2 个用例的时间点）。
- **对外行为改变**：同一行在首次观测后第 5～10 分钟之间调用批准，**由拒绝变为放行**。这是本包唯一的对外语义变化，也是它必须走 design 审的原因。
- **不受影响**：发送侧四条链路、派发任务、补件表判据（`需回复` 必填）、状态四态语义。
