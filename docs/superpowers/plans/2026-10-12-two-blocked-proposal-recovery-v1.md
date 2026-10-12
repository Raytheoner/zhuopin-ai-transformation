# 两项正式接纳阻塞的针对性恢复计划 v1

## 1 事实及目标

本计划只解决FI5、QD-A两项formal admission阻塞；保留SC2/FI14/Q2/Q9四份已正式封存设计。不是六项全部重跑，也不修改Guardian/Workflow、hook、平台或产品代码。

2026-10-12官方Guardian observe两批均needs_manual_wake，无运行任务、delivery_accepted=false；公开`Guardian start --manifest`不带`--run`复核两冻结计划均planned/退出0，未派发模型。四成功树的`git rev-parse HEAD`及`Get-FileHash design.md`与既有回执一致。六源行经官方query锚仍与计划full SHA一致。公开回执及标准指纹在`reports/pc-mvp-1012/v2-review/*-public-plan-final.json`、`public-plan-fingerprints.json`。

- FI5：原四件保留；只修spec的`## ADDED Requirements`标题，父级strict=0；formal仍intent/blocked、无design HEAD/ref。
- QD-A：四件副本未改、父级strict=0；初始可选目录探针退出1，正式驱动判proposal evidence incomplete、无design HEAD/ref。
- 静态接口核验见`reports/pc-mvp-1012/v2-review/two-blocked-recovery-contract.md`：无admission-only修复入口；retire并不要求产品发布，但会保留真正completed任务的row claim。重新claim既有proposal任务无需重新prepare或再次调用proposal模型。

## 2 唯一退役对象及绑定

需新的明确批准才执行下表**当前两v2批次**的正式整体retire，仅释放其未完成claims；全部设计/原树/attempt/日志保留。此前3A只退役旧B1012，不覆盖本表。

| 批次 | plan SHA256 | watch SHA256 | manifest SHA256 |
|---|---|---|---|
| B-1012_v2PC首批提案 | 447dbcb19590eca2d1cb221e1343d9768c45bdd8375f28b56c9a47f8345c312a | 302a3c0c3ec59a7daa98b98ac979f32c750988b8001a1ecee499723024bb9cb4 | 4c08b22c34a166260bd6f1aba9f8069a00871ffda36c65ed6aade84678b5436c |
| B-1012_v2质量独立提案 | c592f48591070c220f59329fd6a5591197b7067c88ea10be018ecffb480e4585 | acadb2e9be50428e1e68d5d4cbdf20ac41656876595bac3f48e0d5df0ec18fdf | 9a8be14bc9070079887b7414e9009c112814721c6e0186230fe79b11a188dcbf |

执行前再现取官方observe/Workflow status、源行及公开计划身份。任一任务running/busy、指纹/队列锚改变、完成判定或归属冲突，即停对应依赖步骤，不能改状态强行解除。

## 3 四项成功任务保全接续

新唯一claim批次`B-1012_v3四设计保全接续`：只复用下表原prepared task、live row、原native linked tree与已封存design。四项不再次prepare，不新派proposal，不改产品与设计；authorizations为空，仅按现态经过正式driver并停在design人工闸。4A业务批准及后续实施计划批准仍按正式外部证据单独绑定，不由本批复用动作代办。

| 行 | task_id | 原隔离树 | 必须保持的design HEAD |
|---|---|---|---|
| 654 | sc2-three-metric-evidence-1012v2 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-sc2/zhuopin-ai | b2933132b733756b30b94e309e2066bbd50d6e43 |
| 678 | fi14-payment-plan-pc-mvp-1012v2 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai | cd1c154800945f6fe6c756bd60474bb8fe082783 |
| 652 | q2-semantic-offline-source-1012v2 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai | 31270c3dc9ff165eec85553f0e26df6ca8b26b5b |
| 653 | q9-apqp-evidence-pilot-1012v2 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai | 1df48365385cf3a2e1c436fbe77466caaae80cd2 |

仍使用原四lane标识，A1–A4新watch绑定原row/action/workspace；max_parallel=3，90秒错峰。新watch/manifest必须通过生成器lint、官方DryRun、live row/state/worktree/claim核验。若retire保留任一completed row，不能重新抢领该行；保全并停其接续供裁决。不改变四原源行full SHA。

## 4 两项失败任务隔离恢复

新唯一批次`B-1012_v3两项接纳恢复`，仅两条独立proposal泳道，max_parallel=2，90秒错峰，所有派生模型显式`gpt-6-luna`。

| 原行 | 新task_id | 新树 | 新lane | 四件唯一写范围 |
|---|---|---|---|---|
| 470 | fi5-wecom-pc-review-alignment-1012v3 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v3-fi5/zhuopin-ai | op1012aa-fi5-admission-v3 | openspec/changes/fi5-wecom-pc-review-alignment-1012v3/ |
| 656 | qda-seven-step-extraction-1012v3 | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v3-qda/zhuopin-ai | op1012ab-qda-admission-v3 | openspec/changes/qda-seven-step-extraction-1012v3/ |

固定源commit`d6851ac082adfa1c0a7e74085bb0f4f7bd1ca206`，通过原生create/attach managed linked worktree创建两个精确新树。若路径已被别任务占用，不覆盖/收养、不改变旧树。prepare前HEAD/common-dir/clean必核；同字节输入只放新树`reports/pc-mvp-input/`，不把副本提前放入openspec造成dirty。

输入复用已确认FI5兼容意图、原场景规则/合同及修正后四件；QD-A复用已核四个源码副本、签认七步映射、原四件及失败回执。旧专业边界原字节保留；新task namespace仅改提案标识，不以此重开需求。FI5明确使用正确OpenSpec ADDED Requirements标题。QD-A不对尚不存在的可选目标目录执行会exit1的探针，需探测时用返回bool的Test-Path；模型实际每个工具失败都保留，不伪装成功。

两原行只在两旧batch正式retire成功后，通过队列锁工具更新到新task/lane输入锚，并登记新批次；四成功行不改。各自prepare→watch生成/lint→官方plan/DryRun→Guardian start --run。只生成proposal/design/spec/tasks四件，outer strict/commit/seal成功才称正式入设计；终态核actual Luna、工具退出、四件、strict及design HEAD/SHA，再独立审查与另行design批准。父级strict副本仍不能代替formal admission。

## 5 新增仓库外范围（待批）

根AGENTS要求仓库外修改先确认，Guardian retire又要求证据在仓库/工作树外。本计划请求明确批准以下**限定范围**：

1. `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1012-two-blocked-v3/`：两个绑定当前plan的retire证据、新batch本地提案/LAN决策与输入身份；不复制凭证。
2. `C:/Dev/Codex/runtimes/zhuopin-ai/state/`与既有Guardian/Workflow runtime日志：仅上述两old/two new batch及六绑定task的retire、claim、prepare/dispatch/stop证据；不改其它任务、不手写formal成功标记。
3. 第4节两个精确新managed trees：Git元数据/原生创建附着、`reports/pc-mvp-input/`只读同字节输入及各自唯一openspec四件；不允许产品实现/测试或新监听服务。
4. 第3节四原树只读复核并由官方driver保全接续状态；设计、产品内容与历史不修改。不执行四成功项新的proposal模型。

主仓内watch/manifest、独立执行记录、R5及两个live row更新按既有锁/登记协议处理；不用此批准改变工具或规则。

## 6 顺序、验收与答复

执行顺序：新授权证据冻结→现场前检→两批正式retire与claim释放核验→四设计新claim保全停闸→两个新树/输入/prepare→两独立proposal执行→真实终态/独审/design供审。局部失败只停对应依赖，保留全部历史；无权限或守卫拒绝不绕过。

验收：四设计HEAD/SHA不变且无需重派proposal；两失败项各获正式strict/HEAD/SHA或留清楚具体停点。并非所有PC MVP完成；新增actual design、实现/测试、真实取数、ff、生产、付款、外发均另审。

本会话第6项：6A（推荐）批准本v1第2–6节的限定退役/证据/状态/四设计保全接续与两个新树两项离线proposal；6B保留现况暂不恢复。无默认，未答不执行仓库外新增范围或退役。
