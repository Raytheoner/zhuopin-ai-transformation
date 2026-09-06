# lane-watch-notify-ops-default Design

> openspec 门槛判定：命中根 `CLAUDE.md` §5 **③改变既有模块对外语义**——`pause`／`transfer-out`／`check-heartbeat` 三个命令在相同输入（不传 `--no-notify`）下的推送去向由「17 人业务群」变为「运维二人群」，且新增 fail-closed 分支（此前是「找不到脚本就降级仅落状态」，现在还多了「脚本在但目标键未配置/发送失败」两种新分支）。
> 四条判据正本＝队列 `#492` 行内原文，本 design 只记落地时的取舍，判据本身不复述第二份。

## 一、决策点

### 决策点 1 · 用什么手段读 `WECOM_WEBHOOK_URL_OPS`

`发企微.py::load_webhook()` 硬编码只读裸键 `WECOM_WEBHOOK_URL=`，不能直接复用去读另一个键。

- **(a) 在本模块内新写一个同形状的 `_load_ops_webhook_url()`，只复用 `发企微.py::send_markdown` 的网络发送逻辑〔推荐 · 默认〕**
  与 `工具-落库sweep.py::_load_webhook_url` 完全同一判据（`REPO_ROOT/.env` 逐行匹配 `"<KEY>="` 精确前缀，未命中返回 `None`）——**该判据已在 sweep 侧真实验证过前缀碰撞不会误命中**（`WECOM_WEBHOOK_URL` 是 `WECOM_WEBHOOK_URL_OPS` 的真前缀，`=` 必须在前缀内）。`send_markdown(url, content)` 是纯粹的「给一个 URL 发一段 markdown」，与目标群无关，复用它不违反「不新增通道」——通道还是企微 webhook 这一种，只是 URL 参数换了来源。
  **代价**：与 sweep 侧存在两份几乎相同的读取函数（本模块一份、`工具-落库sweep.py` 一份）。
  **收益**：不改 `发企微.py`（触碰区明确禁止碰它的群通道本体），不引入模块间依赖（本模块只在需要发送时才 `importlib` 动态加载 `发企微.py`，这是模块既有手法，见 `_load_wecom_sender` 原文档「4.2：接入既有推送通道，不新建」）。
- **(b) 改 `发企微.py::load_webhook()` 接受一个可选 key 参数**
  **代价**：🔴 触碰区明确写「不碰 `发企微.py` 的群通道本体（其他用途仍用它）」——`发企微.py` 是 Cowork／CC 手动发送业务简报的独立工具，改它的公共函数签名会影响其现有调用方（`main()` 自身），且需要重新验证「不传参数时行为不变」，超出本变更授权范围。
- **(c) 把两处读取函数合并成一个共享工具模块**
  **代价**：本次改动范围应收窄到"止住两次真实事故"，抽公共模块是架构层面的更大改动，且 `工具-落库sweep.py` 模块文档明确记载它"刻意零依赖 `zhuopin_platform`"这一取向，合并前须先核实是否与该取向冲突——不在本变更授权与时间范围内，如实登记为后续可选项，不擅自扩大范围。

**推荐 (a)。** 两份判据相同但物理隔离的函数，比一次跨模块重构的风险小；`WECOM_WEBHOOK_ENV_KEY`/`LANE_WATCH_WEBHOOK_ENV_KEY` 命名刻意不同名，避免误改一处以为改了两处。

### 决策点 2 · fail-closed 标记落在哪个粒度

四条判据 ⑶ 要求「不发 ＋ 标记，由看门狗与收工汇总报出」。

- **(a) 标记写入触发失败的那个 lane 的状态记录（`lanes.<lane>.notify_failures`），append-only，不做"已读/已处理"状态流转〔推荐 · 默认〕**
  与状态文件既有的 `history`／`transfers`／`lock_hits` 三个字段同一形状（都是"事件流水账"，不是"当前态"）。`summary` 现取时用 `count_notify_failures()` 汇总全部 lane 的条数，与 `count_lock_hits` 同一模式；`check-heartbeat` 本身若这次触发的通知恰好失败，会走同一条 `_notify_best_effort`，失败即落一条记录并在 stderr 报出——**它不需要额外去查"还有没有未处理的旧标记"**，因为看门狗的职责是"这次心跳还好吗"，不是"翻旧账"，旧标记的翻查交给收工 `summary`。
  **代价**：`notify_failures` 条目不会被自动清除，需靠收工汇总人工过一眼；多批之间会累积。
  **收益**：结构最简单，不新增"标记已读"这类需要额外维护的状态机；与既有三个 append-only 字段一致，不引入新的心智模型。
- **(b) 全局单一标记（不分 lane）**
  **代价**：多个泳道并发时会互相覆盖，且 `summary --batch` 现有的「只看这一批」过滤能力会失效（`notify_failures` 若不挂在 lane 下就没有天然的 batch 归属路径）。
- **(c) 标记后自动触发二次重试**
  **代价**：本次事故的根因是「目标错」不是「网络抖动」，重试对目标错误没有意义；对真正的网络故障，重试策略应是独立能力，不应绑在这次止血范围内，超出四条判据要求。

**推荐 (a)。**

### 决策点 3 · `--no-notify` 人守条目退休后怎么写

原文「🔴 所有 `pause` / `check-heartbeat` 一律带 `--no-notify`，无一例外」在默认目标改为 OPS 后失去存在理由（不传参数也不会发到业务群）。

- **(a) 降为一行指针，标注取代关系，原文保留不删〔推荐 · 默认，同 `#282` 对架构决策件 §5.1 的处理手法〕**
- **(b) 直接删除该节**
  **代价**：违反「历史记录不追改」——`--no-notify` 这条约定曾经是真实生效过的止血手段，直接删除会让后来者查不到"当初为什么要这样写"，与 `#282` 处理 §5.1 时的手法（就地标注取代关系，不删原文）不一致。

**推荐 (a)。**

## 二、状态 schema 变更（供实现与单测对照）

```jsonc
// reports/lane-watch-state.json，lanes.<lane> 新增一个 append-only 字段
{
  "lanes": {
    "A": {
      // ……既有字段（status/history/transfers/lock_hits……）不变
      "notify_failures": [
        {"at": "2026-09-06T09:52:00Z", "reason": "`.env` 未配置 WECOM_WEBHOOK_URL_OPS"}
      ]
    }
  }
}
```

字段缺失时（既有状态文件/旧记录）一律按空列表处理，不做迁移脚本——`lane_state.setdefault("notify_failures", [])` 与既有 `history`/`transfers` 的处理手法一致，旧状态文件天然兼容。
