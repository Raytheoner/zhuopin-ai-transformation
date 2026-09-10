---
title: "分支分类清单 · 未并入 master 的 claude/* 分支 patch-id 三分类（§一 #553 ⑴）"
created: 2026-09-10
status: 生效（只读清单，不含任何处置）
用途: 队列 §一 #553 期望产出 ⑴——按 #534 patch-id 口径把未并入 master 的 claude/* 分支分为「内容已在 master／真未落地／该删」；本件只产出「知道」，不产出「处置」
配套: §一 #553（承接行）／§一 #534（patch-id 判据正本，同夜 534-patchid 泳道在建工具，可用本件 §四 #341 两条作验收靶）／看护件-泳道看护批B-0910_夜批六泳道-2026-09-10.md
执行: CC 泳道 553-branch-triage（OP-0910-W，批 B-0910_夜批六泳道，无头档）
---

# 分支分类清单 · 未并入 master 的 `claude/*` 分支（§一 `#553` ⑴）

> 🔴 **本件是「知道」，不是「处置」**：一个分支都没合、没删、没改；所有判定均可用 §六 的脚本在任何 checkout 上重跑复核。
> 🔴 **合不合、删不删是后续决策**（`#553` 行内原话「本行不催合并」）；本件 §二～§四 的「建议」列只给方向，不设默认项、不生效。

## 〇、口径与现取

| 项 | 值（2026-09-10 23:07 本地，本机 `Get-Date`） |
|---|---|
| 基准 `master` | `9cca4711`（＝`origin/master`，起棒时 `git fetch --prune` 后现取） |
| 候选范围 | `git branch -a --no-merged master` 命中 `claude/` **140** 条（本地 66 ＋ 远端 74；`#553` 立行时 21:0x 现取为 134，其后本夜批四泳道 push 等使其增长） |
| 去重后 | 分支名 **81** 个；(分支名, 尖端) 组合 **86** 个（本地＝远端同尖端者只算一次；本地≠远端者两侧各算一次） |
| 判据正本 | §一 `#534`（「SHA 谱系≠内容已合入」）；`#455`／`#341`／`#482`／`#504` 四条实证 |

**三层判据，按序短路，前一层命中即定 A，不再看后层**（为什么这样排：`#455` 证明三点 diff 会把已合入内容误报成「未合入」；等价提交的文件后来在 master 被继续改写是常态，不能拿文件不同当「未落地」）：

1. **patch-id 等价**：`git cherry master <tip>`（内部即逐提交 `git patch-id` 与 `<tip>..master` 比对）。全部独有提交标 `-` ⇒ **A**。
2. **尖端逐字节**：仅对 `+`（无等价）提交触碰的文件，`git diff <tip> master -- <files>` 为空 ⇒ **A**（squash／改写后合入的形态）。
3. **行级包含**（`#482` 口径）：仅对 `+` 提交自身 `git show --unified=0` 的新增非空行，逐行在 master 同路径文件中查存在；缺失 0 行 ⇒ **A**。
4. 以上都不中 ⇒ 看是否 **C 该删**：⒜ 是别的未并入 `claude/*` 分支的祖先（`git for-each-ref --contains <tip>` 现取）——内容全在后继分支上；⒝ 缺失行**只**落在过程状态文件（队列真身两份／归档件／接力卡／CHANGELOG／`队列行日志/`／`队列回写待补/`／`reports/`／根 `CLAUDE.md`）——这些格在 master 上早被后续会话重写，合回只会倒灌陈旧状态。
5. 其余 ⇒ **B 真未落地**，附缺失行数与落点文件。

## 一、总览


| 分类 | (分支名, 尖端) 数 | 占比 |
|---|---|---|
| A 内容已在 master | **64** | 74% |
| B 真未落地 | **18** | 20% |
| C 该删 | **4** | 4% |
| 合计 | 86 | 100% |

**B 细分**（只标注，不改分类）：B1 在跑／本夜批 ＝ 5；B2 今日交付·待 ff ＝ 3；B3 起草件／design 审前 ＝ 5；B4 陈旧未落地（≥4 天） ＝ 5。

🔑 **一句话结论**：`#553` 行内那句「主仓 ff 由 sweep 收尾段串行做」所指向的积压，**真实规模不是 134，而是 B4 那 5 条陈旧件 ＋ B2/B3 那 8 条待人审件**；其余 64 条内容早已在 master、4 条只剩陈旧过程态或已被后继分支包含。**分支图上的 134 条「未并入」里 74% 是假阴性**——与 `#455`／`#341` 的教训同形，这次是全量坐实。

## 二、B · 真未落地（18 条）——内容确不在 master

| # | 分支@尖端 | 侧 | 末提交 | 细分 | 承接行 | 独有提交 | 缺失行/新增行 | 缺失落点（前 3） | worktree 占用 | 现状核对（现取） |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `claude/op0910s-550-sentinel-enforce`@`a851ee91` | remote | 2026-09-10 21:48 | B1 在跑／本夜批 | #550 | +1 | 243/269 | `0-学习与工具/test_工具-opener批处理执行v2.py` 171<br>`0-学习与工具/工具-opener批处理执行v2.ps1` 67<br>`0-学习与工具/工具-opener生成.py` 2 | ☑ | **在跑**（`OP-0910-S`，与本批并行）；本地 `85ce3334` 领先远端 `a851ee91` 一步（22:57 又提交一次，未 push）。 |
| 2 | `claude/op0910t-quality-intake-13`@`a9c95bc9` | local+remote | 2026-09-10 22:24 | B1 在跑／本夜批 | #542–#548 | +1 | 93/93 | `1-转型规划/0-全景路线图/拆件-质量部13回件五行与10份8D验收样本-2026-09-10.md` 93 | ☐ | **本夜批泳道**，22:24 已 push，待看护者串行 ff。 |
| 3 | `claude/op0910v-552-k2-tool`@`dde1baca` | local+remote | 2026-09-10 22:30 | B1 在跑／本夜批 | #552 | +1 | 740/740 | `0-学习与工具/工具-队列行K2外置.py` 441<br>`0-学习与工具/test_工具-队列行K2外置.py` 299 | ☐ | **本夜批泳道**，22:30 已 push，§一 `#552` 已回写「已交付·待 ff」。 |
| 4 | `claude/op0910u-538-sc2-detail`@`05f60e66` | local+remote | 2026-09-10 22:32 | B1 在跑／本夜批 | #538 | +1 | 781/789 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py` 298<br>`4-数字员工/采购部/SC2-采购周报自动生成/tests/test_detail.py` 298<br>`4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py` 79 | ☐ | **本夜批泳道**，22:32 已 push。 |
| 5 | `claude/op0910s-550-sentinel-enforce`@`85ce3334` | local | 2026-09-10 22:57 | B1 在跑／本夜批 | #550 | +1 | 243/269 | `0-学习与工具/test_工具-opener批处理执行v2.py` 171<br>`0-学习与工具/工具-opener批处理执行v2.ps1` 67<br>`0-学习与工具/工具-opener生成.py` 2 | ☑ | **在跑**（`OP-0910-S`，与本批并行）；本地 `85ce3334` 领先远端 `a851ee91` 一步（22:57 又提交一次，未 push）。 |
| 6 | `claude/op0910m-544-heartbeat-batch`@`904a83e7` | local+remote | 2026-09-10 14:13 | B2 今日交付·待 ff | #544 | +1 | 104/136 | `0-学习与工具/test_工具-泳道看护状态机.py` 64<br>`0-学习与工具/工具-泳道看护状态机.py` 37<br>`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md` 3 | ☐ | 今日 14:13 交付，§一 `#544` 行态 partial；待 ff。 |
| 7 | `claude/op0910n-529-timeout-semantics`@`26aa8b8b` | local+remote | 2026-09-10 14:26 | B2 今日交付·待 ff | #529 | +2 | 447/530 | `0-学习与工具/工具-泳道看护状态机.py` 210<br>`0-学习与工具/test_工具-泳道看护状态机.py` 185<br>`0-学习与工具/skills源码/zhuopin-lane-watch/CHANGELOG.md` 24 | ☐ | 今日 14:26 交付；§一 `#529` 状态列首段仍是「🛑 排队中·暂非可动」（首段未随交付回填）；待 ff。 |
| 8 | `claude/op0910l-507-sweep-apply`@`c3dac6d8` | local+remote | 2026-09-10 14:31 | B2 今日交付·待 ff | #507 | +2 | 659/827 | `0-学习与工具/工具-落库sweep.py` 315<br>`0-学习与工具/test_工具-落库sweep.py` 249<br>`openspec/specs/sweep-manifest-coverage-guard/spec.md` 54 | ☑ | 今日 14:31 交付（apply 棒）；§一 `#507` 行态 partial、行内写「剩余＝apply 棒」；待 ff。 |
| 9 | `claude/op0822c-sweep-alerts-b9424a`@`dcc8396d` | local+remote | 2026-08-27 12:07 | B3 起草件／design 审前 | #87 | +1 | 191/191 | `openspec/changes/sweep-resident-hint-deploy-manifest/proposal.md` 89<br>`openspec/changes/sweep-resident-hint-deploy-manifest/design.md` 56<br>`openspec/changes/sweep-resident-hint-deploy-manifest/tasks.md` 27 | ☐ | 整包 `openspec/changes/sweep-resident-hint-deploy-manifest/` 在 master 不存在（含 archive）。 |
| 10 | `claude/op0906i-dont-guard-487`@`3c369a16` | local+remote | 2026-09-06 14:52 | B3 起草件／design 审前 | #487 | +1 | 705/705 | `1-转型规划/0-全景路线图/起草件-队列487子项-dont静默丢弃/方案甲-骨架补不做什么段.patch` 296<br>`1-转型规划/0-全景路线图/起草件-队列487子项-dont静默丢弃/方案乙-生成器fail-loud.patch` 211<br>`1-转型规划/0-全景路线图/起草件-队列487子项-dont静默丢弃/两版方案与自检结论-2026-09-06.md` 196 | ☐ | 起草件目录 `起草件-队列487子项-dont静默丢弃/` 在 master 不存在；但 §一 `#487` 行内明写「`--dont` 静默丢弃子项**已裁并已落地合入 master**」⇒ 这 705 行是**已被裁决取代的候选方案**，不是待落地产出。归 B 只因内容确不在 master；处置上更接近 C，交总线定。 |
| 11 | `claude/op0907ae-reserve-draft-487`@`5952640a` | local+remote | 2026-09-07 16:39 | B3 起草件／design 审前 | #487 | +1 | 358/358 | `openspec/changes/queue-reserve-unfilled-release/design.md` 113<br>`openspec/changes/queue-reserve-unfilled-release/proposal.md` 110<br>`openspec/changes/queue-reserve-unfilled-release/specs/editlock-queue-number-reservation/spec.md` 68 | ☐ | 整包 `openspec/changes/queue-reserve-unfilled-release/` 在 master 不存在。 |
| 12 | `claude/op0908i-358-audit-retention-b52b16`@`56f6aad7` | local+remote | 2026-09-08 10:25 | B3 起草件／design 审前 | #358 | +4 | 467/467 | `openspec/changes/audit-retention-archive/proposal.md` 150<br>`openspec/changes/audit-retention-archive/design.md` 128<br>`openspec/changes/audit-retention-archive/tasks.md` 72 | ☐ | 整包 `openspec/changes/audit-retention-archive/` 在 master 不存在；它是 `op0907x-audit-retention-358` 的后继（后者归 C）。 |
| 13 | `claude/op0909i-eval-suite-review-1a4f02`@`1f484130` | local+remote | 2026-09-09 11:10 | B3 起草件／design 审前 | #440 | +2 | 191/191 | `1-转型规划/0-全景路线图/design审读件-discipline-eval-suite-2026-09-09.md` 190<br>`.claude/rules/两桌同步与取证.md` 1 | ☑ | `design审读件-discipline-eval-suite-2026-09-09.md` 在 master 不存在；另 `.claude/rules/两桌同步与取证.md` 有 1 行（「退出码只认被执行进程自己那一层」，行内写 Shao Peishen 2026-09-09 答 `2a`）不在 master——**一条已获批的纪律条文没进权威载体**，值得总线优先看。 |
| 14 | `claude/unified-portal-design-8a2ce3`@`648a0e5b` | local+remote | 2026-08-04 17:10 | B4 陈旧未落地（≥4 天） | #162 | +2 | 1950/1950 | `5-平台底座/unified-portal-gateway/portal_gateway/webapp.py` 200<br>`5-平台底座/unified-portal-gateway/tests/test_webapp.py` 182<br>`5-平台底座/unified-portal-gateway/portal_gateway/sso.py` 137 | ☐ | 整个 `5-平台底座/unified-portal-gateway/` 目录在 master **不存在**（`git cat-file -e` 现取）；1950 行全在分支上。2026-08-04 起搁置 37 天。**#162 §一 行在两份真身与三份归档件均查不到**（`工具-队列查询.py --row 162 --section 一` 五处 ✗），只在归档 202608 §二 有同号批次行 ⇒ 承接行下落不明，属该行自身的问题、非本清单能定。 |
| 15 | `claude/a22-closure-form-apply`@`93245b2a` | local+remote | 2026-08-25 08:58 | B4 陈旧未落地（≥4 天） | #353 | +1 | 794/931 | `5-平台底座/wecom-aibot-service/tests/test_delivery.py` 124<br>`openspec/changes/followup-closure-form-survives-backfill/tasks.md` 121<br>`5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/followup_gate.py` 102 | ☐ | `followup_gate.py` 在 master 存在，但分支的 102 行（闭环形态四常量／解析器）不在其中；与 §一 `#353` 行内自陈「🔴 未合 master，tasks 34/36」**一致**。 |
| 16 | `claude/a30-inbound-whitelist-apply`@`32feda54` | local+remote | 2026-08-25 14:43 | B4 陈旧未落地（≥4 天） | #380 | +1 | 8/469 | `openspec/changes/aibot-inbound-whitelist-li-jiaolong/tasks.md` 8 | ☐ | 469 行新增中仅 8 行不在 master，全部落在 `openspec/changes/aibot-inbound-whitelist-li-jiaolong/tasks.md`（勾选状态）；代码侧全部已在 master。§一 `#380` 行态 blocked（5.2／5.3 归档待做）。**差集极小，接近 A**。 |
| 17 | `claude/queue-315-apply-9f2c1a`@`b2ef1811` | local+remote | 2026-08-27 11:57 | B4 陈旧未落地（≥4 天） | #315 | +1 | 55/1007 | `openspec/changes/queue-dual-file-split/tasks.md` 27<br>`0-学习与工具/工具-共享文档编辑锁.py` 12<br>`0-学习与工具/test_工具-落库sweep.py` 5 | ☑ | 「抢救 2026-08-11 遗留 1130 行未提交改动」的 wip 件；1007 行中 55 行不在 master，其中 27 行属 `openspec/changes/queue-dual-file-split/tasks.md`——**该变更包 master 已于 2026-08-17 归档**（`openspec/changes/archive/2026-08-17-queue-dual-file-split`），余 28 行散在编辑锁／sweep／队列查询三工具。**#315 §一 行在两份真身与三份归档件均查不到**。 |
| 18 | `claude/happy-thompson-017679`@`72479645` | local+remote | 2026-09-06 21:28 | B4 陈旧未落地（≥4 天） | #398⑹ | +2 | 390/415 | `0-学习与工具/test_工具-落库sweep.py` 92<br>`openspec/changes/sweep-commit-message-extraction/design.md` 66<br>`openspec/changes/sweep-commit-message-extraction/proposal.md` 62 | ☐ | `openspec/specs/sweep-commit-message-extraction/spec.md` 与其变更包在 master 均不存在；sweep 主体 44 行＋单测 92 行不在 master ⇒ `#398⑹`「提交信息提取改为整格即信息」**修法真未落地**。分支名为随机名（非 OP 编号），2026-09-06。 |

**读法**：B1 与 B2 是「正常在途」，不是积压——它们正是 P4 那句话许诺要有人 ff 的对象；**B3 五条是人审关口**（design 审／择一／定级），机器不能替；**B4 五条才是真正的沉没件**（最老 37 天），每条都有具名承接行，但其中两条（`#162`／`#315`）**承接行本身已查不到**。

## 三、C · 该删（4）——不携带任何独有内容

| # | 分支@尖端 | 侧 | 末提交 | 承接行 | 该删依据 | 缺失行落点 | 现状核对 |
|---|---|---|---|---|---|---|---|
| 1 | `claude/op0828h-fi216-letter-r5`@`bea10122` | local | 2026-08-28 08:02 | #423/#424/#426 | 未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports），主体产出已在 master；这些过程态在 master 上早被后续会话重写，合回只会倒灌陈旧状态 | `1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md` 1<br>`1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md` 1 | 本地尖端 `bea10122` 比远端 `7a3060a3` 多 1 个提交，该提交只改队列真身 2 行（`#426` 立行），且 `#426` 在 master 已由 `7c8e850` 定案 ⇒ 差集＝陈旧过程态。远端 `7a3060a3` 本身归 A。 |
| 2 | `claude/op0828h-rebased-on-1826529`@`bea10122` | remote | 2026-08-28 08:02 | #423/#424/#426 | 未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports），主体产出已在 master；这些过程态在 master 上早被后续会话重写，合回只会倒灌陈旧状态 | `1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md` 1<br>`1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md` 1 | 与上一行**同一尖端** `bea10122` 的另一个远端名（仅远端存在），同判。 |
| 3 | `claude/op0829i-fi2-queue-verify`@`403541a9` | local+remote | 2026-08-29 13:07 | #390/#423/#424 | 未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports），主体产出已在 master；这些过程态在 master 上早被后续会话重写，合回只会倒灌陈旧状态 | `1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md` 4 | 唯一提交只改 `跨桌任务队列-业务场景.md` 4 行（OP-0829-I 本地验证回写），该格在 master 早被后续会话重写。 |
| 4 | `claude/op0907x-audit-retention-358`@`736ddd69` | local+remote | 2026-09-07 15:25 | #358 | 是后继分支的祖先（claude/op0908i-358-audit-retention-b52b16@56f6aad），内容全在后继分支上，本分支不携带任何独有内容 | `openspec/changes/audit-retention-archive/proposal.md` 150<br>`openspec/changes/audit-retention-archive/design.md` 91<br>`openspec/changes/audit-retention-archive/tasks.md` 72 | 是 `op0908i-358-audit-retention-b52b16@56f6aad` 的祖先（`for-each-ref --contains` 现取），后者含其全部提交 ⇒ 本分支不携带任何独有内容。 |

⚠️ **「该删」是分类，不是动作**。真要删须先核 worktree 占用（§五）并走总线；本件不删。

## 四、A · 内容已在 master（64）——分支图上「未并入」，内容却一行不少

| # | 分支@尖端 | 侧 | 末提交 | 独有提交 | 证据层 | worktree 占用 |
|---|---|---|---|---|---|---|
| 1 | `claude/op0823d-reply-match-latest-7cc457`@`82ffe483` | remote | 2026-08-23 19:38 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 2 | `claude/a27-opener-archive-precheck`@`fa3f6cea` | local+remote | 2026-08-25 09:25 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 3 | `claude/queue-398-mech-signal`@`fb0d1858` | local+remote | 2026-08-25 11:29 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 4 | `claude/a23-env-anchor-collapse`@`c13a9594` | local+remote | 2026-08-25 12:11 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 5 | `claude/op0826s-a3-outbox-relay`@`367b8837` | local | 2026-08-26 22:57 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 6 | `claude/lan-cleanup-scanner-fix-6a5653`@`2dddb147` | remote | 2026-08-27 12:22 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 7 | `claude/op0828h-fi216-letter-r5`@`7a3060a3` | remote | 2026-08-28 07:33 | 3 | patch-id 全等价（cherry −3） | ☑ |
| 8 | `claude/op0828g-local-master-divergence-alert`@`6ebdc144` | remote | 2026-08-28 08:04 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 9 | `claude/op0828o-423-kpi-mode-a`@`b2a760c1` | local+remote | 2026-08-28 13:29 | 1 | patch-id 全等价（cherry −1） | ☑ |
| 10 | `claude/lane-watch-mode-impl-84bfc6`@`87f9d884` | local+remote | 2026-09-02 10:44 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 11 | `claude/lint-queue-restate-pkg-0902`@`dc24cb39` | local | 2026-09-02 15:38 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 12 | `claude/editable-import-guard-0902`@`58db0ad2` | local | 2026-09-02 15:50 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 13 | `claude/followup-meta-0902`@`0c3ef14a` | local | 2026-09-02 16:11 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 14 | `claude/op0902a2-leadtime-median`@`a74e7d9b` | remote | 2026-09-02 22:21 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 15 | `claude/op0902a5-atp-propose`@`16d20b25` | local+remote | 2026-09-02 23:07 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 16 | `claude/op0902b3-atp-literal`@`3e8e768d` | local+remote | 2026-09-02 23:56 | 3 | patch-id 全等价（cherry −3） | ☐ |
| 17 | `claude/op0903a1-atp-review`@`1bf6b514` | local+remote | 2026-09-03 07:53 | 4 | patch-id 全等价（cherry −4） | ☐ |
| 18 | `claude/op0903b1-atp-apply`@`35674a6d` | local+remote | 2026-09-03 08:29 | 6 | patch-id 全等价（cherry −6） | ☐ |
| 19 | `claude/op0903b2-proc-scenarios`@`04611c3a` | local+remote | 2026-09-03 08:40 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 20 | `claude/op0903b3-fin-scenarios`@`cd38aff0` | local+remote | 2026-09-03 08:57 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 21 | `claude/op0903c2-spec-note`@`bab88c76` | remote | 2026-09-03 09:49 | 7 | patch-id 全等价（cherry −7） | ☐ |
| 22 | `claude/op0903c1-proc-apply`@`9ba60c30` | remote | 2026-09-03 10:04 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 23 | `claude/op0903c3-criteria-signoff`@`c7006960` | local+remote | 2026-09-03 10:04 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 24 | `claude/op0903f1-fi2-batch-4cc6ad`@`0c420962` | local | 2026-09-03 18:57 | 1 | 未等价提交 1 个，新增 159 行全部已在 master 同文件（#482 行级） | ☑ |
| 25 | `claude/op0905i-pth-impl-459`@`b30e4ef3` | local+remote | 2026-09-05 16:38 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 26 | `claude/op0905o-domain-route-341`@`4b8a98a1` | local | 2026-09-05 18:52 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 27 | `claude/op0905n-editrow-guard-455`@`7bd70b51` | local+remote | 2026-09-05 19:52 | 3 | patch-id 全等价（cherry −3） | ☑ |
| 28 | `claude/op0905o-domain-route-341`@`5931085d` | remote | 2026-09-05 20:18 | 4 | patch-id 全等价（cherry −4） | ☐ |
| 29 | `claude/op0906c-oem-audit-fail-closed-aa7199`@`7211db3f` | remote | 2026-09-06 09:34 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 30 | `claude/op0906f-lane-notify-ops-1eb2d6`@`a5d419b1` | remote | 2026-09-06 13:19 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 31 | `claude/op0906k-status-triage-454`@`34be71ce` | local | 2026-09-06 15:29 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 32 | `claude/op0906l-credential-guard-480`@`a778c197` | local | 2026-09-06 15:46 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 33 | `claude/op0906q-r1-precheck-439`@`f54838e6` | remote | 2026-09-06 19:35 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 34 | `claude/op0906t-usage-sampler`@`63fef1fe` | remote | 2026-09-06 19:50 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 35 | `claude/op0906s-intent-gate`@`1c4de050` | remote | 2026-09-06 19:56 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 36 | `claude/op0907g-lanewatch-deploy-478`@`2ab960bf` | local+remote | 2026-09-07 06:43 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 37 | `claude/op0907f-openspec-483`@`2de7dd69` | local | 2026-09-07 06:49 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 38 | `claude/op0907h-docx-reader-481`@`8579e800` | local | 2026-09-07 06:52 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 39 | `claude/op0907i-sweep-manifest-479`@`8b25ab55` | local+remote | 2026-09-07 06:56 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 40 | `claude/op0907k-serial-gate-482`@`867a2918` | local+remote | 2026-09-07 07:17 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 41 | `claude/op0907j-plan-scanner-462`@`7c204763` | local+remote | 2026-09-07 07:31 | 3 | patch-id 全等价（cherry −3） | ☐ |
| 42 | `claude/op0907f-openspec-483`@`9ce23da3` | remote | 2026-09-07 16:52 | 3 | patch-id 全等价（cherry −3） | ☐ |
| 43 | `claude/op0907h-docx-reader-481`@`bdf761f8` | remote | 2026-09-07 17:09 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 44 | `claude/op0907ad-followup-metadata-447`@`43dc7397` | local+remote | 2026-09-07 17:12 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 45 | `claude/op0907af-lanewatch-deploy-478-apply`@`bcfdd6a5` | local+remote | 2026-09-07 17:32 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 46 | `claude/op0907aj-serial-gate-482-apply`@`261f747a` | local+remote | 2026-09-07 18:53 | 2 | 未等价提交 1 个，新增 1258 行全部已在 master 同文件（#482 行级） | ☐ |
| 47 | `claude/op0907ah-plan-scanner-462`@`b8510ce0` | local+remote | 2026-09-07 19:01 | 6 | patch-id 全等价（cherry −6） | ☐ |
| 48 | `claude/op0907ai-sweep-manifest-479-apply`@`ade5ed30` | local+remote | 2026-09-07 19:52 | 2 | 未等价提交 1 个，新增 618 行全部已在 master 同文件（#482 行级） | ☐ |
| 49 | `claude/op0908d-eval-suite`@`e57544c1` | local+remote | 2026-09-08 09:57 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 50 | `claude/op0908e-general-readonly`@`e8023a77` | local+remote | 2026-09-08 09:58 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 51 | `claude/op0908f-readme-rawcell`@`b3cc59f8` | local+remote | 2026-09-08 10:07 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 52 | `claude/op0908h-ledger-p1`@`5fb32ec5` | local+remote | 2026-09-08 10:47 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 53 | `claude/op0908r-heartbeat-vis`@`b784019f` | local+remote | 2026-09-08 17:12 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 54 | `claude/op0908p-opener-single`@`a5ad0ce8` | local+remote | 2026-09-08 17:14 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 55 | `claude/op0908s-l2-discipline`@`76f2ac46` | local+remote | 2026-09-08 17:15 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 56 | `claude/op0908q-exc-guard`@`122a696a` | local+remote | 2026-09-08 17:27 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 57 | `claude/op0908u-506-base-date-freeze-d7894e`@`f716db23` | local+remote | 2026-09-08 17:51 | 1 | patch-id 全等价（cherry −1） | ☐ |
| 58 | `claude/op0908n-sweep-carrier`@`e1608e98` | local+remote | 2026-09-08 18:04 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 59 | `claude/op0908o-pth-blind`@`a3704c96` | local+remote | 2026-09-08 18:04 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 60 | `claude/op0908k-505-hwm-835a34`@`5aa75589` | local+remote | 2026-09-08 21:30 | 2 | patch-id 全等价（cherry −2） | ☐ |
| 61 | `claude/op0909aa-533-editlock-deadlock`@`05d6dab8` | remote | 2026-09-09 23:51 | 1 | patch-id 全等价（cherry −1） | ☑ |
| 62 | `claude/op0909ac-532-bot-domain`@`affb7a92` | remote | 2026-09-09 23:55 | 1 | patch-id 全等价（cherry −1） | ☑ |
| 63 | `claude/op0909ab-530-evidence-guard`@`ea7596d9` | remote | 2026-09-10 00:00 | 1 | patch-id 全等价（cherry −1） | ☑ |
| 64 | `claude/op0910j-sdk-request-timeout-545`@`49189500` | local+remote | 2026-09-10 13:10 | 1 | patch-id 全等价（cherry −1） | ☐ |

**证据层分布**：patch-id 全等价 ＝ 61；未等价提交 1 个 ＝ 3。

🎯 **`#534` 实证靶已在本清单内验过**：`claude/op0905o-domain-route-341` 两个尖端（本地 `4b8a98a1`／远端 `5931085d`）**均判 A**（cherry 全 `-`；2026-09-10 曾被三点 diff 误判「+1452 行未合入」的正是它）。同夜 `534-patchid` 泳道建的工具须在同一输入上给出同一结论，可直接拿本节做回归夹具。

⚠️ **A 类里有一种形态值得注意**：patch-id 等价、但行级缺失数很大（如 `op0906l-credential-guard-480` 245/245、`op0907f-openspec-483` 本地尖端 491/491）——这不是矛盾：同一提交已进 master（`git log master -- <path>` 可见同名提交），随后 openspec 包被 **archive 搬走**，文件路径变了。**这正是「不能拿文件差异判未落地」的第三条实证**（前两条＝`#455`／`#341`）。


## 五、本地／远端分叉的分支（18 个分支名）

| 分支 | 本地尖端 → 判 | 远端尖端 → 判 | 说明 |
|---|---|---|---|
| `claude/lan-cleanup-scanner-fix-6a5653` | `99f0c536` → 已并入 master | `2dddb147` → A | 一侧已是 master 祖先 |
| `claude/op0823d-reply-match-latest-7cc457` | `48626e25` → 已并入 master | `82ffe483` → A | 一侧已是 master 祖先 |
| `claude/op0828h-fi216-letter-r5` | `bea10122` → C | `7a3060a3` → A | 两侧都未并入，且判定不同 |
| `claude/op0902a2-leadtime-median` | `da2cb38c` → 已并入 master | `a74e7d9b` → A | 一侧已是 master 祖先 |
| `claude/op0903c1-proc-apply` | `54f56cbb` → 已并入 master | `9ba60c30` → A | 一侧已是 master 祖先 |
| `claude/op0903c2-spec-note` | `209fde4b` → 已并入 master | `bab88c76` → A | 一侧已是 master 祖先 |
| `claude/op0905o-domain-route-341` | `4b8a98a1` → A | `5931085d` → A | 两侧判定一致 |
| `claude/op0906c-oem-audit-fail-closed-aa7199` | `4b9c2a09` → 已并入 master | `7211db3f` → A | 一侧已是 master 祖先 |
| `claude/op0906f-lane-notify-ops-1eb2d6` | `c64003a9` → 已并入 master | `a5d419b1` → A | 一侧已是 master 祖先 |
| `claude/op0906q-r1-precheck-439` | `44d73f8a` → 已并入 master | `f54838e6` → A | 一侧已是 master 祖先 |
| `claude/op0906s-intent-gate` | `3a68bf01` → 已并入 master | `1c4de050` → A | 一侧已是 master 祖先 |
| `claude/op0906t-usage-sampler` | `1994b531` → 已并入 master | `63fef1fe` → A | 一侧已是 master 祖先 |
| `claude/op0907f-openspec-483` | `2de7dd69` → A | `9ce23da3` → A | 两侧判定一致 |
| `claude/op0907h-docx-reader-481` | `8579e800` → A | `bdf761f8` → A | 两侧判定一致 |
| `claude/op0909aa-533-editlock-deadlock` | `831d5f7a` → 已并入 master | `05d6dab8` → A | 一侧已是 master 祖先 |
| `claude/op0909ab-530-evidence-guard` | `a4a441c4` → 已并入 master | `ea7596d9` → A | 一侧已是 master 祖先 |
| `claude/op0909ac-532-bot-domain` | `70c9992a` → 已并入 master | `affb7a92` → A | 一侧已是 master 祖先 |
| `claude/op0910s-550-sentinel-enforce` | `85ce3334` → B | `a851ee91` → B | 两侧判定一致 |

读法：「已并入 master」一侧＝该尖端是 master 祖先（`--merged`），本就不在 134 之列；另一侧才是候选。**判定不同**的只有 `op0828h-fi216-letter-r5`（本地多 1 个只改队列 2 行的提交 ⇒ C；远端 A）。

## 六、方法与可复现

- 只读命令：`git fetch --prune` → `git for-each-ref` → `git merge-base --is-ancestor` → `git cherry`（patch-id）→ `git diff-tree --name-only` → `git diff <tip> master -- <files>` → `git show --unified=0` ＋ `git show master:<path>` 逐行查存在 → `git for-each-ref --contains`。**无任何写操作**（`git status` 前后均只有本件一处新增）。
- worktree 占用列＝`git worktree list --porcelain` 的 `branch refs/heads/claude/*` 行（39 条被占用）；删分支前必须先 `git worktree remove`，否则 `branch -D` 会被拒——这是 §三「该删」落地时的前置，本件只报不做。
- 运行环境：CC 无头会话，worktree `.claude/worktrees/op0910w-553-branch-triage`（起自 master `9cca4711`）；全量一轮 ≈3 分钟（86 组合）。
- 🔴 **两处已知局限**（读清单时要带着）：⑴ 行级包含用「整行 strip 后在 master 同路径文件任意位置存在」判，对被 master **重排到别的文件**的内容会误报缺失（只会让 A 漏判成 B，不会反向）；⑵ 过程状态文件白名单是手写正则（见脚本 `STATE_PATTERNS`），未覆盖的过程态文件会让 C 漏判成 B。两者方向都是**偏向多报 B**，即本清单的 B 是上界。

<details><summary>脚本全文（`triage.py`，本次实跑版本，供 534-patchid 泳道与后续复核直接取用）</summary>

```python
# -*- coding: utf-8 -*-
"""OP-0910-W / §一 #553 ⑴：按 #534 patch-id 口径对未并入 master 的 claude/* 分支做只读三分类。
只读 git：for-each-ref / merge-base / cherry(patch-id) / diff / show。一个分支都不合、不删。
"""
import json, os, subprocess, sys, collections, re

REPO = os.getcwd()
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "op0910w", "triage.json")

def git(*args, check=True, text=True):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} rc={r.returncode}: {r.stderr[:300]!r}")
    return r.stdout.decode("utf-8", "replace") if text else r.stdout

MASTER = git("rev-parse", "master").strip()

# ── 1. 候选：claude/* 且未并入 master（本地 heads ＋ origin 远端）
refs = {}
for line in git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/claude", "refs/remotes/origin/claude").splitlines():
    ref, sha = line.split()
    name = ref.replace("refs/heads/", "").replace("refs/remotes/origin/", "")
    side = "local" if ref.startswith("refs/heads/") else "remote"
    refs.setdefault(name, {})[side] = sha

def is_ancestor(a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=REPO, capture_output=True).returncode == 0

# 「过程状态文件」——泳道收工回写产生的、后续在 master 上必然被再次重写的文件（判「该删·仅剩陈旧过程态」用）
STATE_PATTERNS = [
    r"^1-转型规划/0-全景路线图/跨桌任务队列(-业务场景|-机制环境)?\.md$",
    r"^1-转型规划/0-全景路线图/跨桌任务队列-归档-\d+\.md$",
    r"^1-转型规划/0-全景路线图/session接力-.*\.md$",
    r"^1-转型规划/0-全景路线图/进度编年-CHANGELOG\.md$",
    r"^1-转型规划/0-全景路线图/队列回写待补/",
    r"^1-转型规划/0-全景路线图/队列行日志/",
    r"^reports/",
    r"^CLAUDE\.md$",
]
STATE_RE = [re.compile(p) for p in STATE_PATTERNS]
def is_state_file(p):
    return any(r.search(p) for r in STATE_RE)

master_blob_cache = {}
def master_lines(path):
    if path not in master_blob_cache:
        r = subprocess.run(["git", "show", f"{MASTER}:{path}"], cwd=REPO, capture_output=True)
        if r.returncode != 0:
            master_blob_cache[path] = None
        else:
            master_blob_cache[path] = set(l.strip() for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip())
    return master_blob_cache[path]

def analyze(name, tip):
    mb = git("merge-base", "master", tip).strip()
    # 独有提交（非 merge）与 patch-id 等价判定：git cherry 内部即 patch-id 比对，'-'＝master 里已有等价补丁
    cherry = [l for l in git("cherry", "master", tip).splitlines() if l.strip()]
    plus = [l[2:] for l in cherry if l.startswith("+")]
    minus = [l[2:] for l in cherry if l.startswith("-")]
    n_commits = len(git("rev-list", f"{mb}..{tip}").split())
    # 分支相对基点的净改动文件（全量，仅供规模参考）
    files = [f for f in git("diff", "--name-only", mb, tip).splitlines() if f]
    # 🔴 文件级／行级比对只看「无 patch-id 等价」的 '+' 提交自己的 diff——等价提交的文件后来在 master 被继续改写属正常，不算未落地
    plus_files = []
    for c in plus:
        plus_files += [f for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).splitlines() if f]
    plus_files = sorted(set(plus_files))
    differ = [f for f in git("diff", "--name-only", tip, MASTER, "--", *plus_files).splitlines() if f] if plus_files else []
    missing = collections.OrderedDict()
    added_total = 0
    for c in plus:
        diff = git("show", "--unified=0", "--format=", c)
        cur = None
        for l in diff.splitlines():
            if l.startswith("+++ "):
                cur = l[4:]
                cur = None if cur == "/dev/null" else (cur[2:] if cur.startswith("b/") else cur)
                continue
            if l.startswith("---") or l.startswith("@@") or l.startswith("diff ") or l.startswith("index ") or l.startswith("new file") or l.startswith("deleted file") or l.startswith("similarity") or l.startswith("rename") or l.startswith("Binary"):
                continue
            if l.startswith("+") and cur:
                s = l[1:].strip()
                if not s:
                    continue
                added_total += 1
                ml = master_lines(cur)
                if ml is None or s not in ml:
                    missing[cur] = missing.get(cur, 0) + 1
    missing_total = sum(missing.values())
    last_date = git("log", "-1", "--format=%ci", tip).strip()[:16]
    subject = git("log", "-1", "--format=%s", tip).strip()
    return dict(
        name=name, tip=tip[:8], merge_base=mb[:8], commits_ahead=n_commits,
        cherry_plus=len(plus), cherry_minus=len(minus),
        files_changed=len(files), files_differ_from_master=len(differ),
        added_lines_in_differing_files=added_total, missing_lines=missing_total,
        missing_by_file={k: v for k, v in missing.items()},
        missing_files_state_only=(missing_total > 0 and all(is_state_file(f) for f in missing)),
        last_commit=last_date, subject=subject,
    )

cands = []
for name, sides in sorted(refs.items()):
    tips = set(sides.values())
    for tip in tips:
        if is_ancestor(tip, MASTER):
            continue  # 已并入（--merged），不在 134 之列
        side = "+".join(s for s, v in sides.items() if v == tip)
        cands.append((name, tip, side, sides))

results = []
for i, (name, tip, side, sides) in enumerate(cands, 1):
    r = analyze(name, tip)
    r["side"] = side
    r["local_tip"] = sides.get("local", "")[:8]
    r["remote_tip"] = sides.get("remote", "")[:8]
    r["local_remote_diverged"] = bool(sides.get("local") and sides.get("remote") and sides["local"] != sides["remote"])
    results.append(r)
    print(f"[{i}/{len(cands)}] {name} +{r['cherry_plus']}/-{r['cherry_minus']} differ={r['files_differ_from_master']} missing={r['missing_lines']}", file=sys.stderr)

# ── 2. 被别的 claude/* 分支包含（祖先关系）⇒ 该删·被后继分支取代（一次 for-each-ref --contains，不逐对）
for r in results:
    me = full_tip = None
    for s2, v2 in refs[r["name"]].items():
        if v2[:8] == r["tip"]:
            me = v2
    sup = []
    for line in git("for-each-ref", "--format=%(refname:short) %(objectname:short)", "--contains", me,
                    "refs/heads/claude", "refs/remotes/origin/claude").splitlines():
        n2, t2 = line.split()
        n2 = n2.replace("origin/", "", 1) if n2.startswith("origin/") else n2
        if n2 == r["name"] or t2[:7] == r["tip"][:7]:
            continue
        if is_ancestor(t2, MASTER):
            continue
        sup.append(f"{n2}@{t2}")
    r["superseded_by"] = sorted(set(sup))

# ── 3. 三分类
def classify(r):
    if r["cherry_plus"] == 0:
        return "A 内容已在 master", "全部独有提交 patch-id 在 master 有等价（git cherry 全 '-'）"
    if r["files_differ_from_master"] == 0:
        return "A 内容已在 master", "patch-id 未逐对命中，但未等价提交触碰的全部文件在 master 尖端逐字节相同（squash／改写后合入）"
    if r["missing_lines"] == 0:
        return "A 内容已在 master", "文件后来在 master 被继续改，但分支新增的每一非空行都已在 master 同文件中（#482 行级口径）"
    if r["superseded_by"]:
        return "C 该删", f"是后继分支的祖先（{', '.join(r['superseded_by'][:2])}），内容全在后继分支上，本分支不携带任何独有内容"
    if r["missing_files_state_only"]:
        return "C 该删", "未落地的行只剩过程状态文件（队列真身／接力卡／CHANGELOG／队列行日志／reports），主体产出已在 master；这些过程态在 master 上早被后续会话重写，合回只会倒灌陈旧状态"
    return "B 真未落地", f"{r['cherry_plus']} 个独有提交无 patch-id 等价；{r['files_differ_from_master']} 个文件与 master 不同；{r['missing_lines']} 行新增内容 master 中不存在"

for r in results:
    r["category"], r["reason"] = classify(r)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(dict(master=MASTER[:8], total=len(results), results=results), f, ensure_ascii=False, indent=1)
print(f"master={MASTER[:8]} candidates={len(results)} -> {OUT}")
print(collections.Counter(r["category"] for r in results))
```
</details>

## 七、给 `#553` ⑵⑶ 的输入（本泳道不做 ⑵⑶——⑵ 触碰 `opener骨架.md`，与在跑 `OP-0910-S` 重叠）

- ⑵ **P4 措辞**：现状是「主仓 ff 由 sweep 收尾段或看护者收工时串行做」，而 sweep 从不合泳道分支、看护者收工也无此步骤（`#553` 行内 grep 三零命中）。本清单给出的事实：**真需要有人 ff 的只有 B1/B2 这类「交付后 24 小时内」的件**——若措辞改成「留人工」，须同时写清由哪条线在多长窗口内做，否则它们会像 B4 五条一样沉 30 天以上。
- ⑶ **告警阈值**：若挂 sweep 常驻告警，建议**只数 B（按本件三层判据现算），不数分支图**——直接数 `--no-merged` 会把 64 条假阴性算进去，告警从第一天起就是噪声。B 的当前值 18（含在跑 5）；剔除 B1 后为 13。阈值数字属口径判据类，🟡 由 Shao Peishen 定，本件不设。
- 两条**承接行查不到**的沉没件（`#162` unified-portal 1950 行／`#315` 编辑锁抢救 55 行）：不是分支问题，是队列可追溯性问题——建议总线先补承接行，再定合／删。

## 八、本泳道边界自陈

- 做了：⑴ 全量三分类 ＋ 逐条证据 ＋ 可复现脚本。
- 没做（按看护件 §二bis 本格）：⑴ 未合、未删任何分支；⑵ 未改 `opener骨架.md`；⑶ 未加 sweep 告警类；⑷ 未改任何队列行的状态判定，§二「现状核对」列只是现取引用。
- 🔴 **不得表述为「已清理 134 条分支」**：清理数＝0。
