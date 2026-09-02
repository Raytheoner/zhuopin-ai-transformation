---
status: 🔴 已退休（2026-09-02，`OP-0902-C`，随 `lane-watch-mode` 架构收敛被 `zhuopin-lane-watch` 吸收；design 曾于 2026-08-29 由 Shao Peishen 审通过，原话「审核通过」，历史记录不追改）
name: zhuopin-lane-clearpool
description: 🔴 已退休，指向 zhuopin-lane-watch——「offlan清池」现为该 skill 的别名触发词，效果等价（先跑 LAN 探针自动判 on/off-LAN 定候选范围，替代本 skill 原来「人不在／零确认」的单一前提）。本文件保留作历史参照与 zhuopin-lane-watch 步骤 1-2 的判据引用来源，不再独立触发。原描述（历史存档，按「历史记录不追改」保留）：卓品智能AI转型项目·off-LAN 一句话清池。当 Shao Peishen 说"offlan清池""off-LAN 清池""周末清池"时使用：扫两份队列真身出 off-LAN 候选，按白名单选件、按触碰区排波次，落档看护件后经批处理工具起无头 CC 泳道，心跳+企微四类事件推送，收工汇总推他。全程零确认（连"开启泳道"口令也不需要），业务建造与一切对外发送永不自动入批。
---

> 🔴 **本 skill 已于 2026-09-02 退休，被 `zhuopin-lane-watch` 吸收**——成因：清池「人不在」的设计前提写错了（清池是 Shao Peishen 手动触发的，触发那一刻他必然在场），前提一改，清池与看护的差别只剩网络范围，而那是机器跑一次探针就知道的，不需要两个触发词。**现在该说「开启泳道看护」（或沿用旧口令「offlan清池」，二者同指同一个 skill）**。下文正文按「历史记录不追改」原样保留，作为 `zhuopin-lane-watch` 执行步骤 1-2（扫池／排波）的判据引用来源；`lane-clearpool-skill` openspec 变更包的 4 项未完成任务已转承接，见 `openspec/changes/lane-watch-mode/tasks.md` §5bis。完整成因见 `zhuopin-lane-watch/CHANGELOG.md` 2026-09-02 节。

# 卓品 · off-LAN 一句话清池（规则正本 v1.0，历史存档）

> **权威判据正本＝`openspec/changes/lane-clearpool-skill/`（归档后＝对应 specs）**：D1 白名单、D2 链条、D3 护栏在彼，不在此复述细节——本文件是执行编排，与 design 冲突时以 design/spec 为准。

## 触发与前置

- 触发：Shao Peishen 在 Cowork 说「offlan清池」（可带参：`上限N`）。
- 前置自检三条，任一不过即停下来报：⑴ `git fsck` 健康＋`fetch` 后与 origin 对齐；⑵ 编辑锁无他人长占；⑶ 上一清池批（若有）汇总已出。

## 执行步骤

1. **扫池**：读两份队列真身＋当月归档件（防已完成误派，衔接 #397）；按 design D1 四条选件，落选者按原因分入「待人裁」「待 Cowork 班」「LAN 留步」三清单。
2. **排波**：触碰区两两比对，重叠即分波；锁工具族恒最后一波（独占收工窗口）；单批上限默认 6。🔴 **首跑灰度（tasks 3.1）：本 skill 第一次真实触发时上限强制 2、且须 Shao Peishen 在场；三判据（误派 0／漏派入待人裁节／审计落档齐全）全过后方放开默认上限。**
3. **落档**：生成 `看护件-<当日Get-Date>-offLAN批.md`（格式沿 0829 样板：〇口径／一硬边界继承／二矩阵／三泳道 opener 正文），走锁登记 §二 批次；🔴 落档失败即全停。
4. **起泳道**：经 `工具-opener批处理执行v2.ps1` 起无头 CC（isolation: worktree），opener 正文原样传；心跳落 `reports/lane-heartbeat/`。
5. **看护**：四类事件（开工/等人/完成/失败）推企微私信（OP-0829-J 通道；未上线则降级仅心跳并在看护件标注）；波间自动推进；任一泳道 STOPPED 或 30 分钟无心跳→暂停后续波＋告警＋等人。
6. **收工**：汇总（每泳道一行＋心跳全文＋未闭合产出扫描器三形态数字＋三清单节）推企微＋落档；队列回写走锁。

## 🔴 红线（与 spec 同义，此处只留提醒行）

业务建造与一切对外发送永不自动入批；不自造 🛑 豁免；`.51`/真实库/规划文档/他线在办不碰；0828 看护件 §一 十条硬边界整体继承；「已部署 .51」类报告必假、当场停。

## 版本

- v1.0（2026-08-29 出件，随 openspec 变更包 `lane-clearpool-skill` 待审）。沿革此后写同目录 CHANGELOG.md。
