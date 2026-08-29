# lan-closeout-skill Proposal

> **状态：propose ＋ design 出件，等 Shao Peishen design 审。🛑 审过前不安装不启用。**
> **来源**：Shao Peishen 2026-08-29 原话「我回 lan 以后只要说一声『我已回Lan』就把 lan 留步全部收口」；承接既有缺口「LAN 留步无承接方」（B-0826_21 登记族）与 sweep「回 LAN 翻转推送」的行动半边。
> **openspec 门槛核对**：命中 ①「改变全项目口径」（回 LAN 收口由"人翻清单逐项派"改为"一句触发词自动收口"）且**正职触碰 `.51` 生产面** ⇒ 必须走 openspec 含 design 审。

## Why（一段）

off-LAN 工作法已闭环（留步登记＝扫描器形态 1＋行内标注；回 LAN 检测＝sweep 翻转推送），但**行动侧无承接**：留步清单曾一个月无人扫（0828 看护件 §一ter 点名的反例）。clearpool 已证明"触发词→白名单→波次→无头链→心跳→汇总"这条骨架可靠（灰度三判据全过），本 skill 复用同一骨架，只换白名单方向与波次纪律。

## What Changes

新建**引用式 skill `zhuopin-lan-closeout`**（指针模式同 clearpool）。触发词＝Shao Peishen 说「**我已回Lan**」（及近义）。链条＝**先探针实证真的在 LAN**（ping `.51` 与源系统，触发词声称≠事实）→ 汇集三源留步清单（扫描器形态 1／队列行内「LAN 留步」标记／看护件 LAN 留步节）→ 白名单选件 → 排波落档看护件 → 无头 CC 泳道逐项收口（按「发布即收口」部署段判据验收）→ 心跳＋企微推送 → 汇总。

## Non-Goals

- **不代签一切人工门禁**：L2 门禁、对客外发开闸、专员复核的"发信请人"半步（收口到**可复核态**即停，通知走信件线）；
- 不改合规红线、不动 OEM 隔离边界；
- 不处理非 LAN 欠账（那是 clearpool 的地盘，两 skill 互不越界）。

## Impact

派发口径新增回 LAN 半边；新增 capability `lan-closeout`；`.51` 触碰纪律收紧为"默认串行＋逐项冒烟＋回滚在位"（见 design D2）。
