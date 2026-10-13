# SC2/FI5 冷接续来源绑定纠正计划 v1

> For agentic workers: 批准后按 executing-plans 逐项执行；派生模型只能经正式 Guardian/Workflow 使用显式 gpt-6-luna。以下是执行计划，不生成批准。

**Goal:** 保留全部已有成果，在9A指定的两棵现有工作树中，使用正确来源 HEAD 完成 SC2/FI5 四件同字节正式接纳。

**Architecture:** 保留错误来源封存的v4任务，新增两个独立任务身份，从现有同 HEAD linked checkout调用未修改的正式prepare入口。SC2旧v4批次仅释放未完成claims；不改旧state、封存批准或固定工作树HEAD。接纳后SC2仅机械承接原同字节设计批准，FI5仍停design审。

**Tech Stack:** PowerShell、项目隔离Python、官方队列/锁/Guardian/Workflow、OpenSpec strict、SHA256。

**Spec:** 根AGENTS.md；.claude/rules/队列与落库.md；.agents/skills/zhuopin-lane-watch/SKILL.md；docs/superpowers/plans/2026-10-12-cold-continuation-recovery-v1.md第2–6节及第9项明确批准。现时取证见0-学习与工具/codex-handoff/泳道看护现时核验-2026-10-13.md。

## 1 现时证据与为什么需要新增差量批准

官方Workflow状态显示：两个v4任务均在主仓prepare，source_head封存为f66dca3f7e26d38517be9bd6ff335e025a61b295。SC2新树实际HEAD为b2933132b733756b30b94e309e2066bbd50d6e43，FI5新树为d6851ac082adfa1c0a7e74085bb0f4f7bd1ca206，两树均clean，符合9A原固定来源。SC2 Guardian因此报workspace HEAD drift，模型attempt为0；FI5仅prepared，无模型attempt。

handoff.py::prepare以入口所在ROOT封存HEAD/source_checkout，并以exist_ok=False创建任务目录；官方CLI没有同任务来源重绑定入口。不得重写state或将批准的工作树reset到错误的f66来源。

9A已有业务范围、两个工作树及原设计批准继续保留；本v1新增范围仅是两个v5任务/批次、旧SC2 v4批次退役及新的仓库外批准/执行记录。原9A点名的是v4身份与四个原批次，因此这部分差量须Shao Peishen明确批准。

## 2 精确身份和路径

| 项目 | SC2 | FI5 |
|---|---|---|
| 源行 | §一#654 | §一#470 |
| 新task | sc2-three-metric-cold-1013v5 | fi5-wecom-pc-review-alignment-1013v5 |
| 新batch | B-1013_SC2来源绑定纠正 | B-1013_FI5来源绑定纠正 |
| 实现workspace | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-fi5-admission/zhuopin-ai |
| prepare来源checkout | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-sc2/zhuopin-ai | C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v3-fi5/zhuopin-ai |
| 固定source HEAD | b2933132b733756b30b94e309e2066bbd50d6e43 | d6851ac082adfa1c0a7e74085bb0f4f7bd1ca206 |
| 首阶段唯一写区 | openspec/changes/sc2-three-metric-cold-1013v5/下原四件 | openspec/changes/fi5-wecom-pc-review-alignment-1013v5/下原四件 |
| design原字节SHA256 | 9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e | d74b3870da9298058d0c8e1abc5641fb543016fc6a1f2e857fcb7a1591b76e2f |

新lane/OP在批准后由现有生成器取未占用编号并绑定上述task、batch和workspace；任何身份冲突先停止，不复用旧OP、不自行写替代opener。

### 仓库外差量范围

1. C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1013-cold-source-binding-v1/：保存绑定本计划全文、现时队列/批次指纹的SC2-v4退役、两个v5 intent/LAN批准；SC2同字节设计封存后，仅机械填写其新HEAD/task的标准实施批准。
2. 既有runtime state/logs：仅B-1012_v4SC2冷接续的正式retire回执及两个新task/batch的prepare、claim、proposal、strict、outer commit/seal、后续SC2原12路径CI/review记录。
3. 第2节两个现有实现workspace：首阶段新namespace四件、ignored reports输入/验证证据及outer Git操作；SC2同字节设计接纳后仅原12个已批产品/测试路径。FI5无产品实现。
4. 第2节两个来源checkout仅作只读来源，不写其产品、OpenSpec、临时目录或Git HEAD。

不创建第三棵树；不更改Q2/Q9/FI14/QD-A的任务或批准；不删旧任务、树、失败日志，不reset/rebase旧树，不改ACL、工具、hooks或sealed authorization。

## 3 执行顺序和机器闸

1. fresh Guardian observe与Workflow status核对B-1012_v4SC2冷接续及两个v4任务，均须无活进程/未结算attempt。复核两源行live全文、两实现树clean及固定HEAD/common-dir；只读比对来源checkout的invoke.ps1、handoff.py、guardian_entry.py、workflow_driver.py、workflow_state.py与现时主仓源码。任一源码不同或来源HEAD漂移即停，不复制或修改工具来凑一致。
2. 从正式Guardian公开计划得到SC2 v4 plan/watch/manifest指纹，绑定本次明确答复生成外部retire证据，再用Guardian retire正式退役B-1012_v4SC2冷接续。保留v4任务状态与全部历史。FI5旧prepared任务无batch记录时保留；若发现已有claim，停止报告实际owner，不直接释放。
3. 持共享锁将#654/#470当下执行指针改为第2节v5身份，保留旧段；生成两单项看护件，登记§二批次，release并反查。读取各源行最新全文/定位，按本次答复绑定新的intent/LAN标准JSON，不沿用旧行哈希。
4. 仅调用来源checkout中的正式入口prepare新task。prepare后用Workflow status机器断言source_head/source_checkout等于第2节，source与模型写树为同仓不同linked checkout，queue_full_sha256等于fresh查询值。不符合立即停，该任务保全。
5. 使用9A已核四件identity和输入副本；原四件字节不改。先确保目标新namespace空目录，模型只能把四件复制到新namespace。新manifest首次就固定对应workspace，lan_required=false，LAN证据逐项绑定，使用Guardian start规划、lint与DryRun。源码强制Luna/正常hooks信任/授权均通过后才加--run；并行至多2、错峰至少90秒。
6. outer实际strict、四件逐件SHA、改动白名单、outer commit/design HEAD和正式Workflow seal全部完成才算接纳。SC2 design SHA必须等于第2节原已批字节，FI5同理；不符即停并另审。任何tool_failed、context_stopped、timeout或unknown均保留现场，不记交付完成。
7. SC2同字节设计接纳后，依据本次批准与9A原SC2冷接续v2计划，仅机械绑定新task/新design HEAD，保留原12文件清单；后续合成实现、项目CI、独立Luna review仍走正式Guardian/Workflow。FI5在正式design审查闸停止，不从接纳推导实施批准。

## 4 验收与失败边界

- 两个新task的source_head准确匹配原批准固定工作树；用Workflow status和git rev-parse HEAD验证。
- 原成功设计/部分产品输入及旧v4任务全部保留；SC2/FI5四件逐件SHA匹配，strict/outer commit/seal证据齐全。
- SC2后续仍以原12路径及冷接续v2行为验收、对应项目CI和独立review为准；本计划不把四件接纳当产品完成。
- FI5严格停在design审，未获新的design/实施批准不得继续。
- Q2未结算锁态、Q9/FI14超时及QD-A待实施批准独立留步；不以新批次掩盖它们。
- 不授予ff、生产、真实取数、付款、对外发送或专业签认。任何前置失败只停对应依赖。

## 5 可直接作答

1A（推荐）：批准本v1第2–4节的限定差量，使用原两棵v4树，新增两个v5任务/批次，正式退役SC2 v4未完成claim并纠正prepare来源；保留9A的同字节设计及SC2原12路径范围，FI5接纳后仍待design审。

1B：仅保全现有资产，暂停SC2/FI5接续；不会新增仓库外任务记录。

本项无默认；未答不执行第2–4节。主仓本计划与现时证据登记已在继续看护授权内，不代表新增仓库外差量获批。
