# lane-clearpool-skill Tasks

> 🛑 design 审通过前全部不得开工。执行环境标注见各条。
>
> 🔴 **2026-09-02 `OP-0902-C`：本包 skill 已由 `zhuopin-lane-watch` 吸收退休**（架构收敛，见
> `openspec/changes/lane-watch-mode/design.md`「架构收敛：三个 workflow → 两个」节）。
> 以下 2.1/2.2/2.3/3.3 四项未完成任务**全部已转承接**，不再由本包续做——逐项对照见
> `openspec/changes/lane-watch-mode/tasks.md` §5bis；本包因此可以归档，归档理由与去向
> 写在包内（`proposal.md` 尾注），不只标归档不写去向。

## 1. skill 本体

- [x] 1.1 定稿 `0-学习与工具/skills源码/zhuopin-lane-clearpool/SKILL.md`（2026-08-29 审过即定稿，status 转生效，首跑灰度条款补入步骤 2）【Cowork】
- [x] 1.2 save_skill 安装引用式指针（2026-08-29，skill_01Th7mHWBiWcAryfYzUTNnNJ，enabled）【Cowork】
- [x] 1.3 指针回读验证（安装后即出现在会话可用 skill 清单，名称与 description 触发词逐字核对一致）【Cowork】

## 2. 执行链接线

- [x] 2.1 🔁 **转承接** —— 核对 `工具-opener批处理执行v2.ps1` 的调用签名与无头 CC 参数（只读核对，不改它）：已被 `zhuopin-lane-watch` tasks 4.1 覆盖（同一件事，2026-09-02 `OP-0902-B` 已完成只读核对，`OPENER_PARTIAL` 不触发该脚本中断逻辑的结论仍成立，见 `zhuopin-lane-watch/SKILL.md` 步骤 3）【Cowork/CC】
- [x] 2.2 🔁 **转承接** —— 心跳推企微段接线：已被 `zhuopin-lane-watch` tasks 4.2 覆盖（`pause`/`transfer-out`/`check-heartbeat` 均已接入 `发企微.py::send_markdown`，推送失败降级仅落状态）【CC】
- [x] 2.3 🔁 **转承接** —— 波间自动推进与 30 分钟无心跳暂停的看护逻辑：已被 `zhuopin-lane-watch` tasks 5.6 承接并实现（`工具-泳道看护状态机.py::check_heartbeat`/`check-heartbeat` CLI，2026-09-02 `OP-0902-C`）【Cowork】

## 3. 首跑验收（灰度）

- [x] 3.1 首跑限 2 条泳道、Shao Peishen 在场，全链走通（2026-08-29 16:00-16:45：触发→D1 落档→无头 CC 双泳道→心跳全程（对比 0828 批四条全空）→summary；推送降级心跳文件，J 未上线属预期）【他＋CC】
- [x] 3.2 首跑复盘三判据全过（2026-08-29）：误派 0（两泳道零越界，T 还修正了 #434⑵ 一处误列）；漏派全部入「待人裁/待 Cowork 班/LAN 留步」三清单；审计落档齐全（看护件＋批次＋心跳＋summary＋队列回写四步退出码 0＋写后反查）——**上限放开至默认 6**【Cowork】
- [x] 3.3 🔁 **转承接** —— 队列 #312 子项回写＋本包归档：已被 `zhuopin-lane-watch` tasks 5.7 承接（2026-09-02 `OP-0902-C`，队列 `#312`「offlan清池」子项已回写退休说明；本包归档随本次一并执行，见 `proposal.md` 尾注）【Cowork/CC】
