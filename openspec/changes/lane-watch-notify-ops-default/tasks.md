# lane-watch-notify-ops-default Tasks

> 队列 `#492` 四条判据缺一不算完；本清单逐条对应，完工后回写 `#492` 与 `#284` 计数⑨。

## 1. 主体改动（`0-学习与工具/工具-泳道看护状态机.py`）

- [x] 1.1 新增常量 `LANE_WATCH_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL_OPS"` ＋ `_load_ops_webhook_url()`（判据 ⑵：匹配须带 `=`，防前缀误命中）
- [x] 1.2 `_load_wecom_sender()` 改为只复用 `发企微.py::send_markdown`，不调用其 `load_webhook()`；目标固定取自 `_load_ops_webhook_url()`（判据 ⑴：默认目标，不是多一个参数）
- [x] 1.3 新增 `_OpsWebhookUnavailable` 内部异常 ＋ `_mark_notify_failure(lane, reason)`（写入 `lanes.<lane>.notify_failures`）
- [x] 1.4 `_notify_best_effort()` 签名加 `lane` 参数，三个调用方（`pause_lane`／`transfer_out_lane`／`check_heartbeat`）同步传入；失败分支一律调用 `_mark_notify_failure`，不回落默认群（判据 ⑶）
- [x] 1.5 新增 `count_notify_failures()`／`format_notify_failure_line()`，接入 `_cmd_summary`（判据 ⑶「由看门狗与收工汇总报出」的收工汇总一侧）

## 2. 单测（`0-学习与工具/test_工具-泳道看护状态机.py`）

- [x] 2.1 默认目标＝OPS：真实 `_load_wecom_sender()`（未注入 `notify_fn`）在 `.env` 只配置 OPS 键时，请求发到 OPS webhook（拦截 `urllib.request.urlopen` 断言 URL，不出网）
- [x] 2.2 OPS 不可用时不回落默认群且已标记：`.env` 只有裸键、无 OPS 键时，`pause_lane(notify_fn=None)` 不发生任何网络请求（拦截 `urlopen` 断言从未调用）、状态正常落盘、`notify_failures` 记一条
- [x] 2.3 `_load_ops_webhook_url` 两键并存时只取 OPS（键名前缀不误命中）
- [x] 2.4 既有 64 例回归全绿（新增前基线：64 passed）

## 3. SKILL.md 改判

- [x] 3.1 `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`「🔴 推送目标」节：「一律带 `--no-notify`，无一例外」退休为一行指针，标注取代关系，原文保留不删

## 4. 收口

- [x] 4.1 回写队列 `#492`：状态改为已完成，附本变更包名与关键 commit
- [x] 4.2 回写队列 `#284` 计数⑨：处置结论＝机制化（改默认值），去向＝本变更包
- [ ] 4.3 `/opsx:archive lane-watch-notify-ops-default -y`（全部 [x] 后执行）
- [ ] 4.4 真实投递验证（晋档 2 前提）——不在本变更范围，留待 Shao Peishen 在场时另做，如实登记不假装闭合
