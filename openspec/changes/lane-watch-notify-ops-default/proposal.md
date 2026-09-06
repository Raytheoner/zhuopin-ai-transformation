# lane-watch-notify-ops-default Proposal

> 归属：队列 §一 `#492`（从 `#452` 母行拎出独立成行，2026-09-06 Shao Peishen 改定「发运维群」，`OP-0906-B` 业务总线派发）。
> 类别：**机制/环境类变更包**（守护本仓库泳道看护工具自身），受 `openspec/config.yaml` 两条 MANDATORY 约束，见下文。

## Why（为什么做）

**一句话**：`工具-泳道看护状态机.py` 的泳道决策提示（等人／看门狗）默认推送目标是 `.env` 的裸键 `WECOM_WEBHOOK_URL`（17 人「跨部门AI建设群」），**没有任何目标选择能力**；本变更把默认目标改为运维逃生通道 `WECOM_WEBHOOK_URL_OPS`（Shao Peishen ＋陈承二人群），且在该键未配置或发送失败时 fail-closed（不发＋标记），绝不回落业务群。

**这不是潜在风险，是已发生两次的既成事实**：2026-09-02 首跑，泳道 C 一条含 `.pth`／`site-packages`／`change_criteria` 等内部技术细节的决策提示被发进 17 人大群，专员不该看到、也无法撤回；止血靠人守——`pause`／`check-heartbeat` 调用方一律手工带 `--no-notify`（`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`「推送目标」节）。2026-09-06 09:52，`B1` 波次 1 泳道 A 的三条提示（等人×2、看门狗×1）**又推进大群**，且是**由 Shao Peishen 本人截图发现，不是机制发现**。队列 `#284` 计数⑨已记两次违反，与 `#282`（sweep 侧同类事故，已修）同族——**「参数化的规避手段」本身就是失败模式**，正确修法是改默认值，不是再加一条要记得传的参数。

**为什么现在能做**：目标群 `WECOM_WEBHOOK_URL_OPS` 已在 `#282`（`sweep-ops-webhook-cutover`）验证为可用去向（`.51` 真发出过完整消息，`errcode=0`），本变更只是把泳道看护这一个新的调用方接进同一个已验通的键，不新增通道、不新建凭据。

**架构依据**：`3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2 判据——泳道决策提示的主题是「一个内部机制在等待决策」，不是面向专员的业务内容，属该判据「运维逃生通道」一侧。

### 守卫退休问答（MANDATORY · 协议〇.9 措施 B / one-in-one-out）

**本次退休一条既有的「人守」约定，且不新增任何守卫代码。**

**退休对象**：`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`「🔴 推送目标」节的人守约定——「🔴 所有 `pause` / `check-heartbeat` 一律带 `--no-notify`，无一例外」。

**为什么必须退休它，而不是放着不管**：这条约定本身就是队列 `#284` 计数⑨记录的两次违反的**成因**——它要求每一个起草 opener／每一次手工调用的人**都记得多传一个参数**，而「记得传参数」在本项目已被反复证明不是可靠的失败防线（同 `#284` ⑦⑧ 同族：批次清单／暂存区核对，均属「靠人记得核一眼」）。本变更把默认行为改为安全（不带 `--no-notify` 也不会发到业务群），这条约定不但不再必要，**继续保留它会误导读者以为"不传参数很危险"**——而事实是传不传都安全，唯一仍需 `--no-notify` 的场景收窄为「联调/测试时连运维群也不想发」，与原文「无一例外」的强度不符，必须改写。

**为什么不新增守卫代码**：本变更的正确形态同样是**结构性消除**——把「目标由调用方参数决定」改为「目标由代码固定为 `WECOM_WEBHOOK_URL_OPS`，`--no-notify` 只是完全跳过发送的联调开关」，安全性不再依赖任何人记得做什么，因而不需要一条守卫去检查"有没有人忘了带参数"。

### 伴生文件的 .gitignore 覆盖问答（MANDATORY · 队列 #328 子项②）

**不适用：本变更不新增任何自动生成的文件名形态。** 本变更只在既有状态文件 `reports/lane-watch-state.json` 的既有 lane 记录结构里新增一个字段 `notify_failures`（推送失败/OPS 未配置时的标记留痕），不新增锁文件、快照、独立日志文件或备份副本。该状态文件本身已被 `.gitignore` 覆盖（`git check-ignore -v reports/lane-watch-state.json` 命中 `.gitignore:35:**/reports/`），字段级新增不改变文件名形态，忽略规则沿用现状、不受影响。

## What Changes（改什么）

**① `0-学习与工具/工具-泳道看护状态机.py`**：

- 新增常量 `LANE_WATCH_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL_OPS"` ＋ 新函数 `_load_ops_webhook_url()`——读 `REPO_ROOT/.env` 中该键，**匹配须带 `=`**（防 `WECOM_WEBHOOK_URL` 真前缀误命中，同 `工具-落库sweep.py::_load_webhook_url` 既有判据），未配置时返回 `None`。
- `_load_wecom_sender()` 改为**只复用 `发企微.py::send_markdown` 的网络发送逻辑**，不再调用其 `load_webhook()`（那读的是默认业务群裸键）；目标 URL 一律取自 `_load_ops_webhook_url()`。取不到值时抛 `_OpsWebhookUnavailable`（模块内部异常，不外传）。
- `_notify_best_effort()` 新增 fail-closed 分支：OPS 未配置或发送抛任何异常，一律不回落默认群，改为落 `notify_failures` 标记（`_mark_notify_failure`，写入对应 lane 的状态记录）＋ stderr 留痕，`pause_lane`／`transfer_out_lane`／`check_heartbeat` 三个调用方无需各自处理。
- `summary` 子命令新增一行 `本批企微通知失败 N 次`（`count_notify_failures`／`format_notify_failure_line`），供收工汇总现取报出；`check-heartbeat` 本身走同一条 `_notify_best_effort`，其自身推送失败时同样落标记并在 stderr 报出（看门狗侧的报出口径）。

**② `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`**「🔴 推送目标」节：退休「一律带 `--no-notify`，无一例外」为一行指针，指向本变更＋新默认行为；原文不删（历史记录不追改），旧版原文保留、标注已被取代。

**③ 明确不回落默认群（语义硬约束，配单测）**——`WECOM_WEBHOOK_URL_OPS` 缺失或发送失败时，一律标记失败并跳过，**MUST NOT** 使用裸 `WECOM_WEBHOOK_URL` 发送。比照 `#282`（`sweep-ops-webhook-cutover`）与 FI2 `resolve_alert_webhook()` 同款语义。

**④ 通知失败不得影响调用方本身的返回值/状态落盘**——`pause_lane`／`transfer_out_lane`／`check_heartbeat` 的状态写入发生在通知之前，通知失败只追加 `notify_failures` 标记，不改变函数返回值、不抛出到调用方。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - **「泳道决策提示该发去哪个群」这条判据**：此前只存在于 2026-09-02 那次事故后临时定的人守约定（`--no-notify` 参数）里，本变更是它第一次落到代码默认值上——`架构决策件 §4.2` 的判据（机制自陈 → 运维群）在此之前只用于 sweep，本变更把它推广到泳道看护这第二个调用方。
   - **阈值/尺度类**：无新增阈值；沿用 `#282` 已验通的 `WECOM_WEBHOOK_URL_OPS` 键与前缀匹配判据。
2. **由谁显性化？** 持有人 **Shao Peishen**（2026-09-06 拍板「改发运维群」，架构决策件 §4.2 出自其本人 2026-08-06 拍板）；backup **陈承**（IT，运维群另一名成员）。
3. **用什么方法提取？** **历史案例反推**——依据队列 `#284` 计数⑨记录的两次真实事故（2026-09-02 泳道 C、2026-09-06 泳道 A），比对 `#282` 已验证有效的同类修法（改默认值而非加参数），确认可直接复用同一套判据与实现模式。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：**档 1（mock 验证）**。本变更全部单测走注入替身与假 `.env` 夹具，不发真实企微请求（触碰区硬约束：不真发企微消息）；真实链路验证留待 Shao Peishen 在场时另做（真实投递验证不在本变更范围内，属后续晋档 2 的前提）。
- **晋下一档的条件**：
  1. 真实触发一次泳道 `pause`／`check-heartbeat`，确认提示进的是运维群（Shao Peishen ＋ 陈承二人群），且业务部门群未收到。
  2. 全量回归零漂移；`openspec validate --strict` 全绿（本包自身）。
- **价值指标**（风险型）：
  - **基线**：`#284` 计数⑨记录 2 次真实事故（业务部门群误收内部技术细节的决策提示）。
  - **目标值**：本变更生效后，业务部门群新增泳道决策提示 **= 0 条**（结构上不可能——目标已从"可配置参数"改为代码固定值）。
  - **基线确认人**：Shao Peishen。
- **LLM 判据黄金集**：**不适用**。本变更不含任何 LLM 运行时判断，全部为确定性的环境变量读取与状态标记。

## Impact（影响面）

**受影响 specs**：新增能力 `lane-watch-notify-routing`（本包 delta spec）；关联但**不修改** `lane-watch`（其决策点/四档判据与本变更的通知目标路由是两个正交维度，原 spec 未显式约定通知目标，故不改写既有 requirement，只新增一份）。

**受影响代码**：`0-学习与工具/工具-泳道看护状态机.py`（新增函数与常量、改写 `_load_wecom_sender`/`_notify_best_effort`）、`0-学习与工具/test_工具-泳道看护状态机.py`（新增用例）、`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`（「推送目标」节改判）。

**明确不受影响、且刻意不动的**：
- `0-学习与工具/发企微.py` —— 其群通道本体（`load_webhook`／`send_markdown`）不改，本变更只复用其 `send_markdown` 的网络发送逻辑，不调用其 `load_webhook()`。
- `0-学习与工具/工具-落库sweep.py` —— 已在 `#282` 独立完成同类切换，本变更不重复其改动，只是同一份判据在第二个调用方上的复用。

**红线核对**：
- **mock 先行**：单测层用注入的假 `.env` 覆盖分流逻辑与 fail-closed 分支，不发真实网络请求；真实投递验证另行安排。
- **audit 留痕**：`notify_failures` 标记写入 `reports/lane-watch-state.json`（既有留痕载体），不新增留痕形态。
- **OEM 隔离**：不涉及——不含任何 OEM 技术数据。
- **L2 门禁**：不涉及——本变更收窄的是内部机制通知的受众，不产生对客外发。
- **ISO 26262**：不涉及——非安全相关代码。
- **凭据纪律**：本包全部产出**不含任何 URL 值**；`.env` 已由 `.gitignore` 覆盖。
