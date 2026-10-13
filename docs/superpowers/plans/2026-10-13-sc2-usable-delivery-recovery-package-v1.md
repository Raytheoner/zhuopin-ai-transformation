# SC2可用交付与有限恢复执行包 v1

> 执行：正式Guardian/Workflow，所有派生明确gpt-6-luna；本件待明确批准。复用既有业务设计，不启动泛化需求讨论。

**Goal:** 先交付可打开的SC2三指标MOCK页面、计算/来源明细/可核验期次，再承接已批独立任务；分别记录合成、真实可用、生产、业务验收。

**Architecture:** 只增加已失败产物的正式接纳、可信终止结算和原任务有限冷接续；新机制经CI/独审后从候选的正式入口作用于列明任务，不改主仓运行机制或生产。SC2接纳后沿原12文件补齐报告和页面。

**Tech Stack:** 现有PowerShell/隔离Python/Guardian/Workflow/OpenSpec/pytest/Flask；不安装依赖，不换全局editable指针。

**Spec:** docs/superpowers/specs/2026-10-13-pc-mvp-finite-recovery-design-v1.md。本次批准须同时绑定该设计及本计划实际SHA；原7A/8A/9A/1A/10A仍有效，未扩大其业务范围。

## 1 一次批准的新增范围

唯一新增机制task `pc-mvp-finite-recovery-1013`、batch `B-1013_PC交付有限恢复`、branch `codex/pc-mvp-finite-recovery-1013`。唯一新增**机制**树 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-finite-recovery-1013/zhuopin-ai`，从批准消费时现取的主仓HEAD创建并封存；来源checkout/HEAD/common-dir/入口字节必须匹配，不重演来源错绑。SC2继续原v4树，无新增业务task/树。

仓库外仅 `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1013-pc-mvp-finite-recovery-v1/` 标准intent/LAN/design/recovery/local-demo证据，以及既有runtime中本机制task和下列四业务task的正常claim/attempt/checkpoint/审计/结算/CI/review记录。不得编辑别的任务、sealed旧批准或全局调度。

机制产品/测试白名单（仓库相对路径）：

1. `0-学习与工具/codex-handoff/handoff.py`：显式CLI模式和回执参数。
2. `0-学习与工具/codex-handoff/workflow_driver.py`：外层验证接纳与冷接续，不绕过gate。
3. `0-学习与工具/codex-handoff/workflow_recovery.py`（新）：无副作用的身份/原文/路径/终止/完整性核验及错误分类。
4. `0-学习与工具/codex-handoff/workflow_state.py`：排他锁内可信结算/追加恢复审计；caller直接完成仍拒绝。
5. `0-学习与工具/codex-handoff/guardian_adapter.py`：指定任务恢复回执对账、有限续段。
6. `0-学习与工具/codex-handoff/guardian_entry.py`：工作树外逐项恢复批准绑定。
7. `0-学习与工具/codex-handoff/tests/test_workflow_recovery.py`（新）。
8. `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`。
9. `0-学习与工具/codex-handoff/tests/test_workflow_state.py`。
10. `0-学习与工具/codex-handoff/tests/test_guardian_adapter.py`。
11. `0-学习与工具/codex-handoff/tests/test_guardian_entry.py`。

另仅本机制namespace `openspec/changes/pc-mvp-finite-recovery-1013/` 的proposal/design/tasks/spec四件、ignored reports证据，以及主仓本执行包/设计/四项状态报告/锁登记。新机制四件设计须与本设计同字节，outer strict/封存后可机械绑定本次设计批准；任何实质变化另审。候选源码不得在CI/独审前作用于真实旧task。

## 2 保留原批准的业务范围

| task | 原树 | 产品/测试及原计划 |
|---|---|---|
| sc2-three-metric-cold-1013v5 | pc-mvp-1012-v4-sc2-continuation | 原12路径；2026-10-12-sc2-three-metric-cold-implementation-v2.md SHA32e7ef06172407f7b3745b65da10d5eb2d029426450b594087ac838810adf99d |
| q2-semantic-offline-source-1012v2 | pc-mvp-1012-v2-q2 | 原8路径；质量实施集合v1第2节；不含上传/UI或真实校准 |
| q9-apqp-evidence-pilot-1012v2 | pc-mvp-1012-v2-q9 | 原24路径；质量实施集合v1第3节；不含正式阶段裁决 |
| fi14-payment-plan-pc-mvp-1012v2 | pc-mvp-1012-v2-fi14 | 原17路径；原计划SHA7cb1fe70ac82ecb7dd247410a6447e78b9762b13c8eb0becc808ef19eb00a383；不含真实取数/付款 |

上述树均位于C:/Users/Paul Shao/.codex/worktrees/<树名>/zhuopin-ai。原业务白名单从原sealed approval读取并逐项核对，不能把报告中的简称当额外路径许可。范围内实现、定向测试、必要回归、独立审查、P0/P1缺陷修复、成果保全及有限恢复合并覆盖。原SC2三指标设计SHA9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e不改。

## 3 顺序及可运行小段

1. **一次前检**：已批准原件/哈希、必要输入可读、PowerShell/Python/OpenSpec可用；可选件Test-Path后才读；工作树绑定/输出位置/服务端口占用/claim/活进程分别核。由外层提供必要规则和当前段精简输入，禁止native盲目重扫全景或尝试sed。原失败证据先保存，工具失败不认作功能RED。
2. **机制TDD**：先对本次SC2 dirty四件和Q2 unresolved锁作隔离RED；实现严格入口，GREEN后跑受影响handoff子项目完整CI。负例覆盖额外dirty/staged、错误HEAD/task/thread、四件hash漂移、symlink/hardlink/越界、批准漂移、活进程/PID重用、父退出子树未知、缺seal、仅D3摘要、caller伪造JSON、重复/并发结算；每个拒绝都断言旧资产/state/lock不变。
3. **独立Luna审查机制**：绑定候选HEAD及CI原文，复核全部拒绝路径、默认行为未放宽和无成功伪造；缺陷仅在第1节11路径修，按影响回归，直至审查通过。使用候选正式入口的权限在本包，ff不在本包。
4. **SC2四件接纳**：在原v5 task/原树，依设计§2严格条件，新只读review+outer strict/commit/seal。失败旧attempt不改。确认同设计SHA后机械绑定原12路径和本包恢复回执；FI5已通过，不重做。
5. **SC2第一可运行段**：消费原12部分资产与SIGNED-DEFINITIONS；先关闭metrics两个无条件pending及单物料窗口外分子缺陷，再补report/webapp。先完成“同快照计算→API→页面→来源行/公式/期次→audit”闭环，保留pending/unknown。阶段checkpoint留原HEAD/部分文件hash/所做验证/缺口，尚非完整交付。每段只供必要输入；新上下文从可信checkpoint继续，不能默认续超过150k旧thread。
6. **SC2交付验证**：对应SC2项目根定向与旧report/UI/detail/golden回归，outer CI精确`python -m pytest -q --tb=short --junit-xml=pytest-result.xml`；同snapshot/hash贯通页面、API、来源明细和audit；default-off/有效零/缺数/未签/日历/hash冲突/audit失败/旧输出不漂移逐项验证。独立Luna审查，缺陷在原12路径内修后重核。不得以测试数替代此可打开成果。
7. **其他已批任务**：Q2可信结算可在SC2推进时独立处理；结算不等于Q2上传故障修复。SC2页面闭环后再扩大并行，Q9/FI14按原批准和新受控checkpoint继续。未知保护保留；每task连续两个恢复尝试未通过即停止该依赖，汇报精确证据，不换同类task/tree重跑。

## 4 本地演示及发布准备（不批准生产）

本地候选名 `SC2-PC-three-metric-mock-v1`，实际版本采用最后通过CI/review的implementation HEAD及snapshot_id；当前没有该HEAD，不编造。允许本机127.0.0.1:8096上的**临时MOCK演示**，复用原SC2路由，不新造场景端口；占用则不接管既有进程，采用静态页面/API/CSV回放。只操作本包持有且匹配启动记录的演示进程。使用原临时门禁的进程级MOCK口令，不改凭据/权限或production配置。

页面 `/procurement/sc2/three-metric-evidence/<snapshot_id>`；API `/procurement/sc2/api/three-metric-evidence/<snapshot_id>`。使用人：Shao Peishen演示、采购专员复核；使用人不等于已指定验收签署人。数据仅原MOCK/公司日历固定摘录；开关默认off，仅本地进程opt-in。备份为原树/旧快照/失败证据与新checkpoint；回退关闭本地开关并停止自有演示进程，旧路径保留，证据不删除。

验收：三张卡均可打开；完整且适用已签定义产生数值并展示分子/分母/来源/统计日/筛选边界，缺数unknown、未签pending；快照ID/hash/审计一致；至少一个有效零、一组确定算术、未决分母与缺历史对照。新期次缺依据可打开并显示待核，不冒充当期完整率。

预计演示：**工程目标为本补件获批并完成机制CI/独审后一个连续执行工作日内交付首个三指标MOCK闭环**，不是承诺上线时间；机制安全证据不能满足时即时报告，不给虚构钟点。第一条三指标页面实跑成功后更新实际演示时间与入口，不等全场景或全部专业材料齐。

未来生产目标仍为原SC2服务/门户，候选版本、试点使用人、真实源权限、实际备份与回滚、冒烟和反馈入口必须在具体发布请求中提前齐备；ff/.51/真实取数/外发各自另审，本包不代批。

## 5 集中决策

1A（推荐）：批准本v1第1–4节及绑定设计v1，限定一个机制task/树/11机制路径，四原业务task/树/原白名单的保全接纳、可信结算、有限冷接续、实现测试独审修复及本地MOCK演示。工程负责人本会话承担，SC2先行。

1B：只继续现有授权内只读/合成回放与来源绑定；SC2正式接纳和Q2安全结算仍留闸。

本项无默认。不是再批准三指标业务目标，也不是重复批准1A来源纠正/7A/8A/9A。未获本差量批准，不改机制或新增外部任务/树。
