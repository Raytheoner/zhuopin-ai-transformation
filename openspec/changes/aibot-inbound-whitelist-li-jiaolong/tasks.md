# Tasks — aibot-inbound-whitelist-li-jiaolong

> **状态：design 审已全批（Shao Peishen 2026-08-25，队列 §四 `#116`「全按建议」），apply 已完成，且已 ff 合入 master（2026-08-31，OP-0831-A，commit `a26c252`）。**
> 落地环境：CC 无头批处理 A30 → 2026-08-31 由 `[Win]0831A-aibot入站收口` session（同为 CC）rebase 解冲突后合入。合入冲突（`connection.py`／`run_aibot_service.py` 各一处）**纯属两分支各自在 `build_connector` 同一插入点追加独立新 kwarg 的结构性碰撞，与入站准入语义本身零冲突**（实测：import 与真正的 `alert_whitelist_rejected` 调用点均已自动合并成功，冲突只在签名/docstring/调用点这三处纯文本层）；解法（#380 追加在 #416 media_* 三参之后）已由 Shao Peishen 当场拍板，见队列 `#380` 回写。
> **合入后 `wecom-service-home` 已同步并重启监听器验活通过**（`工具-执行体对齐重启.ps1` 九关全过，PID 起于 2026-08-31 12:30:43 本地）。
> **§4「真实发送冒烟」——4.1/4.2 已用安全代理完成，4.3 仍留步**：向 ShaoPeiShen 本人（非李姣龙，同 OP-0828-B/R 既有安全惯例）发一条经审计链路的测试消息，`5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl` 实测 `errcode=0`（`action=smoke_test_send`，2026-08-31T04:33:58Z）——**证明的是"今天部署的代码在运行码里确实生效"，不构成对李姣龙本人真实收发的验证**；4.3（她回话后不再触发 `whitelist_rejected`）仍需等她真实回复，属对外动作、无人值守不发。
>
> 🔴 **本包本次仍不归档**——4.3 与 5.3 尚未闭合。判据取值理由不变：观察窗口取到 `#379` 首触发日 09-01。
> ⚠️ 判定器 `0-学习与工具/工具-变更包自动归档.py` 对本包的结论会是 **⬜ 未完工（尚有真未完项）**，非「疑似遗忘归档」——本行是主动声明，不是为了压掉某条告警。

## 0. 前置：Shao Peishen design 审（✅ 已全批）

- [x] 0.1 **决策点 1**：取 **(乙) 出站即入站** —— 凡在 `dispatch.py::KNOWN_RECIPIENT_USERIDS` 内者 SHALL 同时入站可达，两表求差为空可机器核验
- [x] 0.2 **决策点 2**：取 **(b) 一并补入** —— 解植雅（`2025621`，采购部）同批加入白名单与部门映射
- [x] 0.3 **决策点 3**：**批准** —— `whitelist_rejected` 补独立通道告警（只报谁被挡，不含正文）

## 1. 入站放行

- [x] 1.1 `whitelist.py::WHITELISTED_SENDER_USERIDS` 增 `"2025672"`（李姣龙，财务部）**与 `"2025621"`（解植雅，采购部）**——后者系 0.2 取 (b) 后的追加项
- [x] 1.2 `whitelist.py` 顶部注释补一段成因（同既有陈承段体例）：出站已通而入站不通、`#379` 年度提醒收件人即她、`2025672`／`2025621` 系纯数字工号不可推断；**并写明判据 (乙) 的执行体在单测、本表仍显式枚举不从 `dispatch.py` 推导**（显式名单可被 IATF 逐条追溯到授权来源，推导出来的不能）
- [x] 1.3 `department_mapping.yaml` 增 `"2025672": 财务部` 与 `"2025621": 采购部`（按 `"2023458": IT` 既有写法加引号）
- [x] 1.4 **`intake.py` 不改**——`DEPARTMENT_TO_QUEUE_OWNER` 已含 `"财务部": "财务专线"` 与 `"采购部": "采购专线"`（核验，非改动；核验落在单测 `test_intake_已有对应_owner_无需改动`）
- [x] 1.5 **（0.3 追加）** `whitelist.py` 新增 `format_whitelist_rejected_alert()` ／ `alert_whitelist_rejected()`；`connection.py` 新增 `whitelist_alert_fallback_send` 形参并在 `whitelist_rejected` 审计**之后**调用；`scripts/run_aibot_service.py` 接上既有那条独立 webhook 通道（复用 `#387`／`gap_alert` 同一条，未新造第三条）

## 2. 单测

- [x] 2.1 `is_whitelisted("2025672")`／`("2025621")` 为真；既有 6 项一字不动（全枚举锁在 `test_whitelist.py`，逐项锁在新文件）
- [x] 2.2 `resolve_department("2025672", mapping)` == `财务部`、`("2025621")` == `采购部`（覆盖 YAML 数字键经 `str()` 归一后仍可查中）
- [x] 2.3 **不变式测**：白名单与部门映射两表求差——不得存在「在白名单、不在部门映射」的 userid；`PAUL_USERID` 的豁免落在具名常量 `DEPARTMENT_MAPPING_EXEMPT_SENDERS` 并显式相减（**不是循环里 `continue`**），另配 `test_豁免名单本身受控` 防止有人为了让测变绿而往豁免名单塞人
- [x] 2.4 **（0.1 追加）不变式测**：出站 `KNOWN_RECIPIENT_USERIDS` − 入站白名单 == ∅，**单向**（入站可为超集，解植雅即此形态）；失败时报出差集本身
- [x] 2.5 `whitelist_rejected` 触发告警、**告警不含正文**（并加一条签名级断言：格式化函数只有 `sender`/`msgtype`/`occurred_at` 三个形参，正文在这一层根本传不进来）、告警失败不吞审计（端到端断言 `actions == ["whitelist_rejected", "whitelist_rejected_alert_failed"]`，次序即判据）、未配置通道时行为与改动前逐字相同
- [x] 2.6 服务全量回归 ＋ 平台全量，零漂移 —— **实测基线以本次现场重测为准，非引用**：aibot **498 passed / 1 skipped → 518 passed / 1 skipped**（净增 20 条＝新文件 `test_whitelist_inbound_admission.py` 19 条 ＋ `test_department_mapping.py` 1 条；既有测试零删除、零改判）；zhuopin_platform **380 passed / 1 skipped → 380 passed / 1 skipped**（零变化）。⚠️ tasks 原写的「487／380」中 487 已过期（`#387` 等包合入后 master 实测即 498），此处按实测校正、不沿用旧数字

## 3. 归档链路验证（本机可做，不需真人）

- [x] 3.1 以 `2025672`／`2025621` 构造入站帧，验证归档落 `7-外部文档/财务部/`、`7-外部文档/采购部/` 而非 `待分拣/`（并断言 `待分拣/` 目录根本没被创建）
- [x] 3.2 验证追加的队列行 owner ＝ `财务专线`／`采购专线`，且**不含**「发送人身份待确认」标注

## 4. 🔴 真实发送冒烟（对外动作 —— 4.1/4.2 今日以安全代理部分验证，4.3 仍留步）

- [ ] 4.1 **向李姣龙本人真实发送一条企微消息**——**本条严格按字面仍未做**：`#379` 硬前置是本行，但真正向她本人发送的动作留给 Shao Peishen 明天（09-01）人工执行首触发（见队列 `#379` B-1(a)）。
- [~] 4.2 **验收判据（原样承自队列 `#380`，不得放宽）**：只看命令返回码不算数，须在 `5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl` 见到 `errcode=0` 才算通——**2026-08-31 已用安全代理（收件人 ShaoPeiShen 本人，同 OP-0828-B/R 惯例）走完整条审计链路验证一次，实测 `errcode=0`**（`action=smoke_test_send`，`04:33:58Z`），证明的是"今天部署的代码在运行码里确实生效、审计链路确实通"，**不构成对本条字面（向李姣龙）的验收**，故标 `[~]`（部分）不标 `[x]`。
- [ ] 4.3 一并验回件方向：她回一句话后不再触发 `whitelist_rejected`，而是正常归档——**仍需她真实回复，无法在无人值守条件下验证。**

> **今日已解除的前置**：ff 合入 master（commit `a26c252`）＋ `wecom-service-home` 同步＋监听器重启验活，三步均已完成（`工具-执行体对齐重启.ps1` 九关全过）——**此刻李姣龙若回话，代码路径已就绪、不会再被旧代码挡回**（区别于此前"代码已写但未生效于运行码"的状态）。剩余留步的唯一理由是：4.1/4.3 的主体动作本身须由真人执行/等待真人回复，与代码是否就绪无关。

## 5. 收口

- [x] 5.1 回写队列 `#380`（propose 段 A21 已回写；apply 段回写一次；2026-08-31 合入/真机验/重启验活段再回写一次）
- [ ] 5.2 `openspec archive` 本变更 —— **本次不归档**（§4 与 5.3 尚有真未完项，见顶部 `预期观察窗口：7 天` 声明）；4.x 闭合后当场归档
- [ ] 5.3 `#379` 年度提醒 09-01 首触发前确认 4.x 已闭合 —— **留步**：依赖 4.x，需人在场
