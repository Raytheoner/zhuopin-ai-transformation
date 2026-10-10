# SC11 技术 design

> 状态：已补入 `openspec/changes/sc11-inventory-transfer/design.md` 的正式供审件，A2/B2尚未批准；不批准源码、测试、Guardian、真实数据、ERP 写入、邮件外发或发布。
>
> 按主会话转达，Shao Peishen 已回答 A，确认完整 intent / 首期范围。本件据此准备技术设计候选；该答复不等于 design 审批、具体实施计划批准或专业规则签认。此前被拒的capability路径经Get-Item证实不存在；实际 `specs/sc11-transfer-planning/spec.md` 已由Root普通路径完整读取。六项现行requirements已对照，PMC原确认人唯一判据需按下文明确改为版本/hash绑定，而非声称现行规格已支持。

## 1. 供审目标与边界

将首期 synthetic/mock 拟稿做成两项可复核的技术能力：

1. 跨 demand 使用同一模拟库存账本，确保方案拟占量不超过该次库存快照；显式 mock 顺序只用于演示，不代定业务优先级。
2. 将 PMC 确认绑定到不可变拟稿版本及其完整内容 hash；确认之后若业务内容或所依赖输入变化，必须形成新版本，旧确认不得授权新版本。

保留原 proposal 的场景模型：确定性调拨候选与拟稿；四条原则完整、显式排序；缺数据不冒充零或最优；PMC 确认门禁；ERP 和邮件通道未接仍 fail-loud。首期不建立新审批服务、不连接真实数据、不实施业务分配阈值。

## 2. 已核事实与输入边界

- 原 proposal 将四条原则正文的可度量表达与冲突顺序区分：前者可供专家批改，后者不得由技术默认；距离/“尽量少”的度量、部分调拨、替代料和月中临时任务仍是业务知识问题。
- 原 tasks 将 `design.md` 审批列为第 2 组硬闸，并写明第 2 组之后不得在 design 审通过前开工。生产计划通路、三委外仓实时库存、专业签认/backup、物流矩阵及口径分别列为依赖；真实来源未齐时不能晋档真实业务。
- M2 静态读码事实：现候选按 demand 分别枚举完整单仓，再依调用时传入的显式原则顺序排序取首项；当前不在多 demand 之间扣减共享库存、不拆分。原则分数均缺失时，稳定输入顺序可能残留；这不是已签的业务排序规则。`TransferPlanDraft` 可变，确认字段写在 draft 上；现 hash 仅覆盖 summary，未绑定完整内容与输入；审计参数可缺省。确认后 ERP/邮件执行入口仍因未接通而 `NotWiredYet`。
- 首期 mock 不读取真实生产计划、ERP/委外仓库存或物流数据。每个合成输入及输出均须带 `MOCK-*` 身份和明确的 scenario assumptions。

## 3. 设计决定候选 A：共享库存守恒

### 3.1 方案比较

| 方案 | 技术行为 | 评价 |
|---|---|---|
| A1：只报聚合超用 | 独立生成各 demand 候选，另按库存快照、源仓和物料聚合拟占量，报告不足，不选择分配赢家。 | 改动最少且不暗示优先级；无法演示有序试算如何影响同一份库存。 |
| **A2：mock 顺序保守试算（推荐）** | 每份 synthetic scenario 显式列演示 demand 顺序和原则假设；在单次模拟内共享扣减账本。仅完整单仓在扣除本轮已预留后仍能满足整个 demand 时，记录 provisional reservation；否则尝试其余完整单仓候选；均不可满足则记 unmet。 | 可验证守恒与冲突呈现；演示顺序可反转以显露影响。该顺序明确是 fixture 输入，不是业务政策或真实推荐。 |
| A3：全局优化/拼单 | 联合求解多个 demand、源仓、跨仓拆分/替代及多目标。 | 依赖尚未签认的业务规则与真实矩阵/库存，不属于首期。不得由本设计顺带引入。 |

### 3.2 推荐 A2 的行为合同

- **库存账本键**至少包含本轮 `inventory_snapshot_id/version`、源仓和物料；新模拟每次从同一份输入快照初始化独立余额，不写回输入库存或外部系统。
- demand 的 fixture 顺序作为 `scenario_order` / `scenario_assumption` 显式记录。它只让人观察“若按此展示顺序试算会怎样”，不得映射成正式优先级、PMC批准或默认排序。
- 每个 demand 候选仍要求完整的显式 `priority_assumption`。可按这组假设排序完整单仓候选；全缺评分时必须呈现 `unranked / needs_manual_review`，不得借稳定输入顺序挑一个仓或先让某个 demand 占货。mock scenario 若要展示顺序效果，必须在 fixture 中明确给出合成原则评分/排序假设，并标注其未获业务签认。
- 仅允许整条 demand 由一个源仓满足。不够的候选不做部分占货；不得跨仓拼单，不引入替代料逻辑。候选仓剩余量不足时可检查其它完整单仓候选；无可行候选则记录完整 unmet 数量与可复核原因。
- 输出应区分 `provisionally_reserved`、`unmet`、`unranked`，同时留每条 demand 的需求量、候选检查、模拟前后余额、scenario 顺序和缺口原因。`provisional` 只说明该 mock 假设内通过守恒，不说明生产可执行或业务优先。
- 每次模拟必须满足：任一 `(快照, 源仓, 物料)` 下所有 provisional 数量之和不超过快照可用量；`unmet` 不得减少余额；同一输入、相同规则版本和假设产生同一拟稿内容。

### 3.3 守恒验收方向（未来实现计划；本轮不跑测试）

1. 复用原 mock 对照 SC11-C06：一个源仓库存 6，两个 demand 各需 4。任一演示顺序最多 provisional 占 6；一个provisional 4，另一个整单unmet 4，余额2；总量短缺2是核对事实，不允许由此部分下发2；翻转 `scenario_order` 可翻转演示赢家，但两种输出均显式标为 scenario assumption。
2. 多物料、多仓时，reservation 按共享仓库/物料余额独立守恒，不能把一个 demand 的扣减从同料不同仓或不同料错误串用。
3. 若所有候选评分均缺失，输出 unranked；不因 demand 输入顺序创建业务分配。测试夹具须证明无负余额、无部分占货和无真实源调用。

## 4. 设计决定候选 B：不可变版本、确认绑定与审计

### 4.1 方案比较

| 方案 | 技术行为 | 评价 |
|---|---|---|
| B1：可变 draft 增 approved hash | 确认时保存 hash，执行时重算比对。 | 若只 hash summary 或漏掉输入、假设/行内容，无法识别实质变化；可变对象易漏掉变更入口。 |
| **B2：不可变 DraftRevision + 独立 ApprovalRecord（推荐）** | 每版保存完整规范化内容、revision 和 hash；确认另追加记录并指向精确 `draft_id/revision/content_hash`。修改产生新 revision，旧确认保留审计但失去对新版本的效力。 | 精确回答人确认的是哪一版；不替业务定优先级或拆分规则，适合首期 mock 技术准备。 |
| B3：独立事件溯源/审批服务 | 建持久事件流、完整撤回/并发工作流和独立审批服务。 | 需要额外基础设施/Owner，超出此包和首期 mock，不预先决定。 |

### 4.2 推荐 B2 的内容与授权合同

- `DraftRevision` 是不可变快照，最少包含 `draft_id`、单调 `revision`、`content_hash`、schema/算法版本、规范化内容和来源引用。业务相关 hash 输入包括：计划/BOM/库存/矩阵来源标识、版本/hash 与 as-of；需求及演示顺序；原则/评分定义版本及 `priority_assumption`；候选、provisional lines、unmet、数量/物料/源仓/目标仓/needed-by；分配与 mock 假设；scope/算法/schema 版本。
- 使用固定编码与 canonical JSON 规则（字段排序、Decimal/日期规范化、稳定空值表示）后 SHA-256。显示格式、创建时钟、签认人和 audit event id 不属于业务内容 hash，分别进入事件记录。任何可能改变调拨含义的内容或依赖输入变化都必须改变 hash。
- `ApprovalRecord` 独立追加 signer 身份/角色、UTC 时间、被确认的 `draft_id/revision/content_hash` 及结果。签认记录不可被 draft 编辑覆盖。审批时对将确认版本重算/校验 hash；内容不一致则 fail-loud，不产有效确认。
- 内容编辑或输入版本改变不得原位修改已签 revision：复制并生成新 revision/hash，状态回到待确认；旧 `ApprovalRecord` 和旧版本继续留存，但只对旧 hash 有效。旧确认不得沿用到新 revision，也不得因为 `approved_by` 仍有值就通过。
- 如需兼容现有 `TransferPlanDraft` 及 UI/序列化消费者，可保留 `lines`、`unmet`、`priority_assumption`、`summary` 和旧 `approved_by/approved_at` 作为只读投影；真值以 revision 与精确引用的 `ApprovalRecord` 为准。保留执行端原先只能接收 draft 的窄接口，不加绕过审批的参数。

### 4.3 L2 gate、通道与审计事件

- 新拟稿/新修订事件写入 append-only audit，记录输入版本引用、scenario assumption、输出 hash、算法/schema 版本及 `review_status`；没有 audit sink 或写入失败时，业务路径 fail-loud，不能生成可确认/可执行状态。仅明确隔离的 synthetic preview 可采用测试专用 sink；输出仍标记 `not_approved/not_for_execution`。
- PMC 确认是针对一个精确 hash 的 L2 人工事件，必须实名留痕；它只是内容确认，不等于执行授权。批准或拒绝/撤回如纳入实现，事件必须同样追加，不能改写旧事件。
- 后续 `commit_to_erp` gate 只能匹配当前 revision/hash 的有效 PMC `ApprovalRecord`，再经过独立获批的 ERP 通道/操作授权；当前通道未接，保留 `NotWiredYet`，不得产出“已落库”审计事件。
- 邮件 `notify_outsourced_warehouse` 仍为独立门禁：即使有 PMC 内容确认，也必须另有针对该次发送的外发授权和审计；当前通道未接，继续 `NotWiredYet`。本 design 不实现或申请真实发送。
- 每个 audit event 至少绑定事件类型、主体、时间、`draft_id/revision/content_hash`、来源/授权上下文及结果；审计故障不得静默降级为无审计运行。Audit 的长期保存与现平台既有 append-only 及 L2 留存要求兼容，不造新底座。

### 4.4 版本与授权验收方向（未来实现计划；本轮不跑测试）

1. 相同规范化业务输入/内容 hash 稳定；改变任一来源快照/hash/as-of、需求顺序、原则假设、reservation/unmet 内容、算法/schema 版本时 hash 改变；纯显示顺序、签认时钟/人名变化不改变业务 hash。
2. 审批记录绑定具体 revision/hash；确认后编辑任何调拨行、数量、unmet、来源引用或假设都生成新 revision，新版未确认。旧批准留存但不能解锁新 hash。
3. 未批准、旧版本批准、hash 不匹配分别 fail-loud；即便批准完全匹配，未接 ERP/邮件仍报 `NotWiredYet`，发信还要求另一项外发授权。
4. Audit sink 缺失、不可写或事件不能绑定准确 revision/hash 时，业务生成/确认流程 fail-loud；不得产生看似成功的执行记录。

## 5. 兼容性与拟改动边界

预计仅在原 SC11 包内扩展，不建新平台服务：

- `models.py`：增加不可变 revision、ApprovalRecord、分配状态/账本证据的类型；旧 `TransferPlanDraft` 面向兼容端保留为视图/交付对象。
- `routing.py`：在现候选枚举结果后加 mock-only shared-reservation 试算器；不改 BOM 展开、真实数据源或业务公式；不得实现拆分/替代。
- `agent.py`：创建完整内容快照/hash 与版本；将 mock path 与未来业务 path 的 audit 要求显式分开，业务路径不可由 `audit=None` 降级。
- `gate.py`：确认变为独立记录并校验精确 hash；保留未确认拒绝、无旁路、已确认但未接通仍 `NotWiredYet` 的既有合同。执行通道不接线。
- `pending.py` / 原四原则和候选代码：只有必要时表达版本化配置引用；在签认前不设默认顺序、不装载真实矩阵。
- 不改平台底座、门户/UI、生产计划/库存 connector、ERP/mail adapter、全景规划和前置总表；任何进一步扩面须新供审。

## 6. 原 tasks 闸与 mock 窄片拆分建议

以下是供审的任务拆分建议，不修改/勾选原tasks，也不解除现有硬闸：

1. `2.1`（design 获批）继续作为任何产品实现的前置；之后仍须另有逐文件白名单、验收和执行环境的具体实施计划批准。当前仅准备本 design，不代表 `2.1` 完成。
2. 原 `2.2` 前置总表补行及打标/Owner闭合是规划移交事项，原文记为未落地；本 design 不代写、不关闭。真实路径仍保留 `2.3` 生产计划通路、`2.4` 三委外仓实时库存、`2.5` 专业原则签认/backup、`2.6` 物流矩阵/口径等门槛。
3. 建议在正式 review 明确接受 A2/B2 后，另提一个**独立、窄、合成数据专用的 mock 任务组**（例如 `3M`）：`3M.1` 固定 MOCK fixture 与场景顺序；`3M.2` shared-stock 守恒/unranked 行为；`3M.3` immutable revision 与 canonical hash；`3M.4` 精确 hash 的 ApprovalRecord；`3M.5` audit 失败关闭与既有 L2 gate/NotWiredYet/邮件授权边界；`3M.6` 仅合成测试与独立 review。
4. 此 `3M` 是否可在真实专业前置 `2.5/2.6` 前开工，必须由 design 审和后续具体实施计划**明确修订任务依赖**后才成立；若批准件未显式拆闸，则严格按现 tasks 执行，第 3 组及之后继续不开工。未获 Guardian、隔离工作树/实施授权前也不动源码或跑测。
5. 原 3.1–3.4 的签认规则版本化、距离矩阵及真实业务候选路线，以及原 4.x 真实源、替代料和部分调拨、原 5.x ERP/mail 通道，仍由各自真实数据/专业/通道前置控制；3M 的合成成功不得勾销这些任务或晋真实档。

## 7. 专业与数据缺口按阶段分离

| 缺口 | 约束能力/阶段 | 不应扩展成 |
|---|---|---|
| G-01：四原则冲突/先后、共享料谁先获得 | 真实业务排序、真实 shared-stock 分配；须经有权专业人员对案例签认。 | A2 fixture 的显式 demo 顺序不是该签认。 |
| G-02：“调拨尽量少”的可度量定义 | 业务级评分与候选择优；不影响 mock 以显式 assumption 说明仅为情景。 | 技术团队自行把段数/单据数/里程设成生产口径。 |
| G-03：“就近”的度量及矩阵来源/版本 | 真实路由评价和真实路径建议；需指定矩阵持有人、签认距离/时长口径。 | A2 的无真实路线 demo，或通用默认矩阵。 |
| G-04：部分调拨、多仓拼单、替代料 | 超出首期整单单仓 mock；需签认后另列范围和验收。 | 隐含拆分、替代或按最大可用量部分占货。 |
| G-05：月中临时任务和原计划冲突 | 月中动态插单/实时决策能力单独暂停，需业务优先策略；若未来引入 LLM 再单独登记黄金集。 | 首期固定 mock 周计划。 |
| G-06：缺距离/日期/全缺评分或候选时业务处理 | 真实工作流如何继续/升级由专业口径确认；技术建议 fail-closed、明确 unranked/unmet。 | 将技术标记视作业务批准的处置流程。 |
| 业务知识持有人与 PMC 确认人实名、backup | 专业签认、确认责任和真实业务准入；原 tasks 指定批改会/backup 要求须按项目实名规则落实。 | 用技术作者、IT回件人或岗位泛称替代实名授权；不挡纯 synthetic mock 设计候选。 |
| 生产计划、三委外仓库存、物流矩阵及权限 | 真实数据/真实路由阶段；各源均须版本、as-of、授权与审计证据。 | mock 调试或设计供审阶段。 |
| ERP 写入、邮件外发通道及专项授权 | 真实执行/外发阶段；分别接通、单独审、保留 PMC L2 与发信授权两道门。 | 确认拟稿即视为执行或发送批准。 |

## 8. 阶段闸总结与供审请求

| 阶段 | 可做事项 | 仍然禁止/阻断 |
|---|---|---|
| 当前 design 供审 | 评审 A2/B2、兼容设计、audit/gate 语义及是否接受窄 mock 任务依赖拆分。 | 已补正式design供审；不改tasks/源码，不跑产品测试、不用真实数据、不启 Guardian/隔离建造、不连接通道。 |
| design 与具体实施计划获批后 | 仅可按批准的路径白名单和拆分任务，在获准隔离环境进行 synthetic/mock 实现与验证。 | 若正式批准未明确放行独立 mock 片，则原 tasks 第 3 组硬闸保持原状；不得自行视为已解除。 |
| 专业与真实数据准入后 | 按 signed criteria、指定矩阵/源版本及真实数据授权，另行评审真实验证。 | Owner/backup、专业签认、计划/库存/矩阵来源任一缺失都不能宣称真实业务已就绪。 |
| 执行/对外阶段 | ERP 接通后仍按精确 hash PMC 确认与独立执行授权；邮件另走逐次发送授权。 | 当前两通道未接，继续 fail-loud；design 和 mock 均不授予部署/发送权限。 |

请在正式 design 审中确认：是否采用 A2 + B2；canonical hash 字段合同与 ApprovalRecord 是否满足现有审计体系；是否接受把 mock-only 任务从原真实前置任务中显式分拆、且仅在具体计划获批后执行。G-01 至 G-06 的专业口径和所有真实数据/执行授权仍按原独立流程，不在本次 design 中代签。

## 9. 来源与核验限制

- `openspec/changes/sc11-inventory-transfer/proposal.md`：Why/What Changes、两条 design 边界、知识资产三问、四档晋级、L2 与 audit 边界。
- `openspec/changes/sc11-inventory-transfer/tasks.md`：第 1 组既有骨架、第 2 组硬闸 `2.1–2.6`、第 3 组以后依赖及真实接入/执行边界。
- `4-数字员工/采购部/SC11-库存智能调拨/CLAUDE.md`：场景定位、显式原则/矩阵、PMC实名确认与外发授权、`NotWiredYet` 和 mock 先行。
- `0-学习与工具/codex-handoff/SC10与SC11补grill-M2事实与需求树-2026-10-04.md`：SC11 既有代码静态事实、六项专业问题、真实前置及设计缺件。
- `reports/procurement-intents-1010/SC11技术设计选项准备-2026-10-10.md`：A2/B2 备选细节、SC11-C06 守恒样例、hash/audit 验收方向、源代码行定位。
- 实际原spec：`openspec/changes/sc11-inventory-transfer/specs/sc11-transfer-planning/spec.md`；Root已正常读取，不把猜错缺路径作为人侧阻塞。
- 上轮 SC2 窄补核：`openspec/changes/sc2-biztype316-receipts/design.md` 前五行已读回；首句现为“正式 OpenSpec design 供审稿，D1–D10待批准”，同时说明四件成包、严格结构核验 1 passed/0 failed、design 与实施计划仍须分别批准。旧“未迁入正式 change”已消除。

**本稿状态**：已由Root串行收敛为正式design供审；原tasks/spec和产品未改，未解除任何实现闸。

## 10. Root 对现行规范的对照与明确修订方向

### 10.1 PMC requirement 必须正式修订（本轮未改规范）

原spec“PMC确认门禁”写明确认状态唯一判据是拟稿所记录确认人。B2将其收紧为：**系统MUST要求可归责PMC实名确认，并校验确认记录精确指向当前draft_id/revision/content_hash；仅approved_by非空不构成有效确认；系统MUST NOT提供跳过确认的参数或开关。** signer在只读拟稿视图上可展示，真值为指向不可变内容的独立记录。新增“确认后修改”“旧版本确认”“hash不匹配”“无审计确认”失败场景；保留无确认/空人名拒绝、单拟稿入参无旁路、已确认而通道未接、邮件另授权六个旧场景。

上述是供审的规范修订内容；design批准后须按明确范围正式修订delta和依赖，才可写实施计划，不直接覆盖main spec。旧approved_by/at及历史记录原样保留，只标为unversioned history，不自动生成新的有效ApprovalRecord。

### 10.2 库存和假设合同补足

A2仅synthetic/mock路径。若候选完整评分tuple并列，且fixture没有显式合成tie选择，输出unranked而非按list顺序挑仓；fixture可显式提供scenario_candidate_order，仅破完整评分tuple的同分，不得改变非同分排序；demand的scenario_order只确定需求试算顺序。两种顺序各自命名并进入content hash和audit。全部评分缺数同样unranked。此技术输出不代签G-01/G-06真实业务处理。整单unmet数量与总量shortage是两字段，不能把余额当已批准的部分调拨。

### 10.3 审计与数据接口

Root已核平台audit/events.py：decision可存结构化版本/事件元数据，data_sources必须为字符串引用，timestamp为UTC，to_dict保留这些键。新拟稿、确认/拒绝及修订的正式orchestration均必须可写sink；无sink、写失败或hash校验失败不得产有效确认状态。低层纯函数演示若不落审计，只能返回不可确认/不可执行的preview，不能称作完整run_draft/L2交付。

### 10.4 Risks / Trade-offs 与 Migration Plan

- [旧确认人字段被继续当充分证据] → gate只接受当前版本/hash有效记录，旧字段只读展示，历史不自动迁移授权。
- [相同sum/summary掩盖不同调拨] → canonical hash覆盖完整输入、假设、行/unmet、版本；显示/时间/签认人另入事件。
- [守恒被误成业务优先] → mock-only账本与显式情景顺序，真实排序仍等签认。
- [audit失败后仍返回确认] → 先成功追加绑定事件再提供有效状态；失败保持未确认。

本轮仅design。批准A2/B2及3M依赖拆分后先正式更新PMC requirement/守恒规范与任务依赖，再审具体逐文件计划；只有计划也批准才进入隔离mock实现。保留全部13项历史[x]及真实/专业/ERP/邮件任务未闭状态；不升级真实档、不归档、不部署。规范和hash设计迁移不重写旧审计、旧拟稿或旧确认，回退保留旧骨架但不能用旧签名授权新版本。

