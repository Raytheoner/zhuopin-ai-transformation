# aibot-receipt-route-by-source-group Tasks

> 🔴 **本包在无人值守批处理中 apply，design 未经 Shao Peishen 审**（见 design.md 顶部声明）。
> **预期观察窗口：7 天** —— 归档前置＝design 实现层决策点 2-7 签认 ＋ 3.4／4.4／7.4／8.4 四项需人在场的动作。
>
> ⚠️ **刻意用「预期观察窗口」而不是「暂不归档」**：后者是「作者对未来的永久声明」，会让 sweep 此后**永远不再提**这个包——而本包缺的恰恰是一次签认，它**应该**被反复提起直到签完。用会到期升级的那一档，等于给这次未签认留了一个会自己响的闹钟。

## 1. 前置取证

- [x] 1.1 主工作区 `reports/wecom_aibot_audit.jsonl` 实测两条 `group_notify_skipped ｜ department=IT ｜ reason=group_not_configured`（13:06:27／13:21:06 UTC），与同日唐燕萍两条 `group_notified` 对照
- [x] 1.2 实测确认陈承那条 @ 的来源 `chatid` ＝ `wrvDL_DAAAva1MWrKjLmuDWOu1BNxHaA`（财务部群，映射表里早有）——坐实「补 IT 映射也修不好」
- [x] 1.3 实测确认 `InboundMessage.chatid`/`.chattype` 自 `#279` 起已存在且一路传到 `connection.py` 调用点，从未被 `group_notify` 消费
- [x] 1.4 实测 `department_mapping.yaml` 中 IT 的值是 `IT`（非 `IT部`）——群映射表键名须逐字一致

## 2. 主修法 ⑶ · 回执按来源群回

- [x] 2.1 `notify_department_group_via_chatid` 增 `source_chatid`/`source_chattype` 两参（默认 None，既有调用方零影响）
- [x] 2.2 群消息路径：`chattype == "group"` 且 `chatid` 非空 ⇒ 直接回该 chatid，**不查映射表、不看 `matched`**
- [x] 2.3 私聊路径：判据一字未改，原样保留为回落
- [x] 2.4 `group_notified`/`group_notify_skipped` 审计增 `route` 与 `chatid` 两项留痕
- [x] 2.5 `connection.py` 调用点传入 `message.chatid`/`message.chattype`
- [x] 2.6 单测：**IT 群已配好、陈承在财务群 @ ⇒ 必须回财务群且 MUST NOT 回 IT 群**（事故反例锁）／群消息不查映射表／未命中发送人在群里仍回原群／私聊回落部门群／`chattype=group` 但无 chatid 时回落／新参数不传时行为同改动前

## 3. 辅修法 ⑵ · IT 群 chatid 补配置

- [x] 3.1 `department_group_chatid_mapping.yaml` 增 `IT: wrvDL_DAAARjP0BlFLup5e1Cv3vcCvMQ`，附「为何不用 webhook」注释（`#270`/`#279`/`#281` 已迁 chatid，webhook 单向会让陈承的回复再次掉黑洞）
- [x] 3.2 既有用例 `test_default_mapping_file_declares_four_departments_all_captured` 改名并改断言为 5 键精确相等 ＋ 新增 `IT部 not in mapping` 断言
- [x] 3.3 单测：真实映射文件含 `IT` 键、键名与 `department_mapping.yaml` 的值逐字一致
- [ ] 3.4 🔴 **待人在场**：首次真实发送时对着运维部AI保障群看一眼，反查该 chatid 确系该群（采集只证明「机器人收到了来自这个 chatid 的消息」，不证明它就是那个群）

## 4. 静默跳过改为跳过并告警

- [x] 4.1 新增 `ALERTABLE_SKIP_REASONS`（仅 `group_not_configured`/`group_webhook_not_configured`）与 `_alert_skip`
- [x] 4.2 `build_connector` 增 `group_notify_alert_fallback_send`；`run_aibot_service.py` 接既有 `WECOM_WEBHOOK_URL` 通道
- [x] 4.3 单测：两类配置缺口各自告警／`sender_unmatched` 不告警／告警失败不上抛且留痕／未配通道时行为同改动前
- [ ] 4.4 🔴 **待人在场**：真实群冒烟——构造一次配置缺口，确认告警真的进了群（本项目已有先例：`#82` 两类告警建成 9 天、每天在跑、一次都没真的响过）

## 5. ⑷ IT 域队列 owner

- [x] 5.1 `DEPARTMENT_TO_QUEUE_OWNER` 增 `"IT": "业务总线"`（不造 `IT专线`——`whitelist.py` 明文禁止）
- [x] 5.2 既有用例 `test_archive_matched_department_outside_four_domains_falls_back_to_paul_owner` 改名并改断言（它把「IT 回落 Paul」钉成了期望行为）
- [x] 5.3 单测：IT 行 owner ＝业务总线／未命中仍回落 Paul／owner 集合内无 `IT专线`

## 6. ⑸ 本人入站不建队列行

- [x] 6.1 `IntakeResult` 增 `queue_append_skipped` 独立字段（不复用 `queue_append_deferred`，见 design 决策点 6）
- [x] 6.2 `intake.py` 在 `append_pending_task` 之前判 `sender == PAUL_USERID` ⇒ 记 `queue_append_skipped` 审计并直接返回；**归档本体保留**
- [x] 6.3 `connection.py` 的 `sync_after_archive` 触发条件同时排除 `queue_append_skipped`
- [x] 6.4 单测：不建行且队列文件逐字未变／归档仍成功／skipped 与 deferred 不混淆／判据与 `forwarding.should_forward` 同源／其他发送人不受影响

## 7. ⑹ 补录侧幂等

- [x] 7.1 新增 `input_pointer_already_in_queue(repo_root, queue_path, input_pointer)`，走 `queue_table.iter_queue_paths()` 扫全部物理队列文件
- [x] 7.2 `flush_pending_git_sync_appends` 在每条记录补录前判重，命中即丢弃并记 `queue_sync_pending_skipped_duplicate`
- [x] 7.3 单测：命中本份／命中另一份／未命中照常补录／反引号归一化／空指针不匹配／文件缺失时 fail-open 不阻断
- [ ] 7.4 🔴 **待人在场**：清掉生产 `reports/pending_queue_appends.jsonl` 里 15:30:53 那条重复记录（对应行即 §一 `#389`，已实测存在）——该文件是机器人状态文件、且服务常驻，动它前须确认服务当刻未在写

## 8. 队列 #380 · 李姣龙接入可达白名单（同车，非本包 spec 范围）

- [x] 8.1 `dispatch.py::KNOWN_RECIPIENT_USERIDS` 增 `"李姣龙": "2025672"`
- [x] 8.2 财务部门映射核对（结论：她**不在** `department_mapping.yaml`／`whitelist.py`，即出站可达、入站不可达——已如实上报，未擅自扩入站面）
- [x] 8.3 单测：可达／userid 是纯数字工号非拼音猜测／既有六项不变
- [ ] 8.4 🔴 **待人在场**：一次真实发送冒烟——须在 `reports/wecom_aibot_audit.jsonl` 见到 `errcode=0` 才算通（只看命令返回码不算数）。**向真人发消息属对外动作，无人值守不做。**

## 9. 回归与验收

- [x] 9.1 `wecom-aibot-service` 全量回归：**487 passed, 1 skipped**（改动前 485 passed + 2 failed，两条失败均是钉住旧行为的既有用例，已按 3.2／5.2 改判）
- [x] 9.2 `zhuopin_platform` 平台全量回归：**380 passed, 1 skipped**，零漂移
- [x] 9.3 `openspec validate --strict`
- [ ] 9.4 🔴 **待人在场**：design 决策点 2-7 签认（决策点 1 已由他 2026-08-24 当场确认）
