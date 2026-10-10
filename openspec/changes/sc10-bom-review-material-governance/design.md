# SC10 技术 design（2026-10-10）

> 状态：已补入原变更包的正式design供审件；D1–D9尚未批准，不是实施计划或实现/测试授权。复用原proposal/tasks/spec和事实骨架。

## 当前阶段与已确认边界

Shao Peishen 最新明确选择 A：确认完整 SC10 intent，并确认首项按小批合成事实对照推进。完整目标仍是 BOM 评审、公司物料治理及优先选用/淘汰建议；首项只交付确定性事实对照：`SC10-MOCK-B01/r1`，2 个成品、3 个物料，核毛需求、共用料来源及缺数。专业判据和真实数据后续处理；SC10 是 L2，由采购经理确认。

这次确认只批 intent 与首项业务范围，**未批准 design、实施计划、源码改动或启动 mock 泳道**。完整intent现已回填status已确认、#468已消费原答；记录见《五项定夺答复消费-2026-10-10.md/.json》。旧10-04准备状态作为历史保留。

## 可复用的已批事实与当前实现

| 主题 | 现有证据 | 对 design 的含义 |
|---|---|---|
| 范围与人工闸 | 最新直接确认；#468（官方 `--row 468 --section 一 --field all`）定义 L2、采购经理确认及 BOM/物料治理目标。 | 当前首项限定为事实层；不输出建议或审批结论。完整建议能力沿用原专业与真实前置。 |
| 现有确定性事实层 | `sc10_bom_review/review.py::collect_facts()` 复用平台 `explode_bom`，逐成品展开以保留产品来源，再合并物料毛需求；`BomUsage.is_shared` 只报告共用事实。 | 复用，不重写 BOM 展开/排序；禁止将共享料直接解释为优先级。 |
| 合成首项基准 | `tests/test_review_facts.py` 已含 F01/F02 与 M-A/M-B/M-C；预期毛需求 M-A=80、M-B=10、M-C=20；M-A 来源为 F01/F02；完备度 `3/1/2/0`（BOM物料数/生命周期未知/无价/主数据缺失）。它是既有合成 fixture 的可复核预期，不是本轮运行结果或真实性结论。 | 使用 `SC10-MOCK-B01/r1` 作为逻辑输入身份，所有数据显著标 mock；不生成“BOM合格”“适用/淘汰”结论。 |
| 缺数语义 | `models.py::MaterialRecord`：生命周期缺省 `UNKNOWN`，单价 `None` 表示无值，负价拒绝；`review.py` 中无主数据物料只进 `not_in_master`，不重复算生命周期未知或缺价。fixture 中 0.0 被视为“有值”，但零价业务有效性仍待 SC10-G-05。 | 明确保留 `UNKNOWN`、`None`、`0.0`、主数据不存在四种不同状态；mock 不把它们合并为零或默认属性。 |
| 当前 API 与 audit | `agent.py::run_review_facts(bom, plans, materials, evaluator, audit)` 要求 evaluator 非空；用现有 `AuditEvent`/`AuditLogger` 写 `automation_level="L2"`、readiness 计数、`review_status="待前置到位"`、三项建议 `blocked_by`，`data_sources` 仅标 `mock:in-memory`；`content_hash` 目前只哈希计数。 | 保留入口、L2、事件字段和既有建议阻断语义；为首项补输入版本/hash链，而非重造通用 audit 或升级为审批事件。 |
| 输入版本缺口 | `BomRow`、`ProductionPlan`、`MaterialRecord`/当前输入没有输入包版本、BOM修订、来源快照 ID 或 as-of；`planned_date` 是计划日期，不是 BOM 版次。审计 hash 仅覆盖 readiness 计数。 | 设计需绑定本次真实输入值与证据身份；同计数不能证明同输入。 |
| OEM/数据边界 | `agent.py` 注释及现存 proposal/spec 指出：普通采购物料数据不适用 OEM 隔离，现测试断言 `oem_context` 留空。 | 采购物料事实保持空 OEM 上下文；不附加 OEM 技术资料。若将来纳入 OEM 技术附件，应另行做数据隔离评审，不能沿用本 mock 边界。 |

历史 18 tests 和原 tasks 的勾选属于既有记录；本轮没有运行测试。SC10场景级CLAUDE已由Root本轮成功读取（已有缓存证据），D1–D7及红线均与本设计对照；根 `4-数字员工/CLAUDE.md` 已核对其 design 审阅后才能进入实施、实施按 TDD 的流程。

## 建议 design 决策（全部待 Shao Peishen 审阅）

| D项 | 建议决定 | 备选及取舍 |
|---|---|---|
| D1 首期交付范围 | 新增/完善一个 **3M 事实层 mock 阶段**，仅跑 `SC10-MOCK-B01/r1`：2成品、3物料、毛需求、共用料来源、四项完备度计数和差异记录。复用 `collect_facts()`。 | 不做公司级体检、不接真实 ERP、不调用三项 `suggest_*`。范围小且可由已确认的合成输入逐格复核。 |
| D2 全量路线与 proposal/tasks 矛盾 | 三项 `suggest_bom_review`、`suggest_selection_level`、`suggest_obsolescence` 不属于本次 3M mock；原 tasks §5.1–5.5 作为完整 SC10 路线图依赖保留，须在正式 tasks 中标明依赖 2.3/2.4/2.5 专业与数据闸、单独 change/design 审。 | proposal 明确“不做建议层”，spec 建议层 fail-loud；tasks §5 却排入本包实现。不能通过只改本报告“解决”正式矛盾，也不能把 §5 勾选/删掉；须正式变更任务映射后才可开3M。 |
| D3 输入清单不可变与版本 | 在 SC10 本地增加只服务于输入封套的 immutable manifest/wrapper，不改平台 `BomRow`、`ProductionPlan` 或 kit_engine。封套记录 `fixture_id=SC10-MOCK-B01`、`revision=r1`、`source_kind=synthetic`、输入清单及显式 schema/facts-contract 版本；持有归一化后的冻结输入快照，计算前后不得读回可变原对象。 | 不用 planned_date 冒充版次/as-of；不为共享平台模型增加 SC10 特有字段。当前 Python fixture 可先哈希规范化对象内容并记录 fixture 定义来源，不宣称已有独立数据文件 hash。 |
| D4 规范化 hash 与 lineage | 对 BOM、生产计划、物料主数据分别生成稳定 SHA-256；再生成 manifest hash（含输入身份/各子 hash/事实规则版本），计算后生成 result hash（manifest hash＋规范化结果事实）。规范化使用明确字段映射、日期/数值规范、稳定排序，保留重复 BOM 行，区分 null/0/UNKNOWN。mock 的 `as_of` 明确标 `not-applicable/synthetic`；真实来源未来必须另有提取时刻与来源快照身份。 | 不用 JSON/Python 对象 `repr`，也不只哈希四个 readiness 数。变更字段而计数相同仍须改变子 hash、manifest/result hash；内容相同而输入顺序不同应得相同 hash。 |
| D5 API/兼容 | 保留现有 `collect_facts()` 计算合同与 `run_review_facts()` 旧调用兼容。新增版本化入口/输入封套为 3M 唯一入口；它验证 manifest 非空，再委托现有事实计算。旧入口可继续被旧测试/调用使用，但无输入 manifest 的运行不得记作3M版本化验收。 | 不强制改共享数据模型或既有调用签名，不以绕过 manifest 的旧调用产出“版本证据完整”的验收记录。 |
| D6 L2 audit 链 | 保留非空 evaluator、`automation_level=L2`、既有 `blocked_by`、`review_status="待前置到位"`；audit 的现有 `decision` 增输入包 ID/revision、三份输入 hash、manifest/result hash、facts-contract 版本及缺数计数。`content_hash` 改为绑定 manifest 与规范化结果，不再只 hash readiness；不记录原始 BOM/物料行。未应用专业规则时记录 `professional_rule_version=not_applied`，不得制造规则版本。 | 复用现有 `AuditEvent` 构造与字段，不增加平台通用审计字段；Root已核平台audit/events.py的decision字典与asdict序列化支持此元数据；实施时仍核实际AuditLogger持久化失败关闭。L2事实留痕不等于采购经理批准 BOM。 |
| D7 缺数与报价 | `UNKNOWN`=生命周期属性未知；`None`=价格无值；`0.0`=技术上存在的零值、业务有效性未签；`not_in_master`=该物料无主数据记录且不重复计其他缺口。 | 不给零价专业有效性、不对生命周期作序排序、不自动把NRND判淘汰；这些仍锁在专业建议前置。 |
| D8 采购经理、责任人与真实阶段 | 事实层由具名 evaluator 运行并写 L2 audit；不增加规则签认步骤，不输出“已批准”。真实姓名的知识持有人/backup 未知只阻挡专业签认和真实业务阶段，不阻挡经 design+具体计划批准后的合成技术 mock。 | 不猜 Owner/API 参数，不把外部源、专业事项或真实数据闸转嫁给 Shao Peishen 回答。 |
| D9 OEM与日志最小化 | 采购物料数据继续不走 OEM 隔离层；记录 mock/普通采购数据来源，不入 OEM 技术附件。Audit只存版本、hash、摘要计数、actor/等级/状态，不存敏感原始输入。 | 未来技术附件若涉及客户/OEM数据，必须隔离评估，不因本结论自动豁免。 |

## 备选整体方案比较

| 方案 | 结果 | 评估 |
|---|---|---|
| A：版本化合成事实mock（建议） | 复用当前 facts 算法，显式输入封套和hash/audit绑定；建议层保持 fail-loud。 | 与最新首项确认一致，能隔离业务结论与技术事实；仍须先过 design、实施计划与正式任务依赖修订。 |
| B：直接实现三项 `suggest_*` | 使用生命周期/价格/共用性给优先级、淘汰或BOM合格判断。 | 拒绝作为本次方案：专业规则/价格/属性前置尚未满足，违反 proposal/spec 和 L2专业签认。完整路线需后续独立 change。 |
| C：本次直接接真实 ERP 物料主数据 | 对公司物料库运行体检。 | 不纳入首项；不是 synthetic mock，需另有数据授权/接口计划/审计和真实数据验证。原 tasks §3 保留为后续真数据阶段。 |
| D：仅沿用计数 hash | 保持当前审计不变，用计数证明试验版本。 | 不足：两个不同 BOM/主数据版本可得相同计数；无法追溯或复现输入，不满足本次显式版本确认。 |

## 验收方向与当前可观测证据

验收使用完全合成的 `SC10-MOCK-B01/r1`，不执行产品测试：

1. 两成品输入 F01(10) 与 F02(20)；M-A 在两 BOM 中用量分别为2和3，M-B仅属F01，用量1，M-C仅属F02，用量1。
2. 规范化结果应为 M-A=80且 `product_ids=(F01,F02)` / shared=true，M-B=10，M-C=20；不能由共用事实导出选用优先级。
3. 合成主数据给 M-A `ACTIVE`/0.1，M-B `UNKNOWN`/`None`，M-C `NRND`/`None`。摘要应为 `materials_in_bom=3, lifecycle_unknown=1, price_missing=2, not_in_master=0`；移除M-C主数据的变体只增 `not_in_master=1`，不把同一缺失重复计缺价/未知。
4. `None`、`0.0`、`UNKNOWN`、主数据记录缺失分开保存；零价只显示存在，不声称可用于采购。任何建议/审批函数仍 fail-loud。
5. audit 要求 evaluator，保留 L2/待前置状态；输入任一值改变而计数不变，input/result hash 也必须改变；仅输入次序改变而内容相同，规范化 hash 应稳定。
6. 产物显著标注 synthetic、fixture revision 和“非真实BOM判断”。不得出现真实客户/OEM资料、生产价或主数据。

既有 tests 文件可做未来任务映射参考；本轮未新增或运行测试，不把旧历史 18 tests 写成此项验收完成。

## 与原 proposal/spec/tasks 的逐项映射

| 原包 | 现文档内容 | 供审处理建议 |
|---|---|---|
| `proposal.md` | 明确排除三项建议，并定义 BOM事实、主数据完备度、审计；文中已有知识资产三问/四档。 | 保持完整目标与首项分期；把3M事实mock写成最新已确认的首交付，不能扩入建议算法。 |
| `specs/sc10-bom-review-facts/spec.md` | 底座展开、共用事实、缺数语义、四计数、建议前置与 L2 audit。 | 复用已有事实要求；补输入版本/hash链及审计覆盖方向须由正式 design 审定；OEM空上下文保持。 |
| `tasks.md` §1 | 9项骨架任务历史标 `[x]`。 | 作为旧交付记录保留，不声称本轮验证或重开。 |
| `tasks.md` §2.1–2.6 | 设计审、前置总表补行、外部源/属性准备、专业工作坊及API合并裁定。 | 不删、不勾、不自解。先获批design，再正式修订依赖图，说明哪些2.x锁住全量/真实建议、哪些前置不适用于3M；若修订未获批，原硬闸继续有效。 |
| `tasks.md` §3–4 | §3是真ERP主数据；§4是外部行情源。 | 保持真实/外部数据路线，非首项 synthetic mock。 |
| `tasks.md` §5.1–5.5 | 当前仍要求实现三个 `suggest_*` 和建议测试，与 proposal/spec 的“前置后另包/不做”冲突。 | 标成完整路线图依赖并转入后续独立 change；不得在本3M阶段勾选/实现。正式迁移前它仍是未解决的 tasks 结构矛盾。 |
| `tasks.md` §6 | 真实档2、归档、部署发布收口。 | 维持后续闸；不用于本次 mock 结束/归档，不把本报告当实现完成。 |

## 阶段闸与下一步

- **已批准**：完整intent/首项范围（按2026-10-10最新直接确认）；事实算法和缺数语义已有源代码/规格；非建议层合成输入范围明确。
- **未批准**：本design的技术决策、3M具体实施计划、3M与原 tasks §2 的正式依赖映射；无任何本次代码/测试授权。
- **专业/真实阶段**：采购经理L2、生命周期/价格/共用料排序、淘汰条件、BOM合格线、零价有效性仍需专业签认。实名知识持有人/backup未知只阻挡这些专业签认和真实业务阶段，不阻挡获批后的技术 mock。
- **建议层**：原厂/第三方API选型、公司价格/物料属性整备及选择/淘汰规则仍是原 tasks 的长期依赖；不进入本轮首项。
- **最窄下一动作**：请 Shao Peishen 审本稿 D1–D9；若通过，再按本design把原tasks矛盾和2.x依赖映射正式改清，并提交独立3M实施计划审阅。只有 design、具体计划、formal依赖修订均获批后，才开 synthetic mock 建造。不得把当前已答范围再grill，也不自行放开 tasks 门禁。

## 证据路径与限制

- 官方队列：§一 #468（`--row 468 --section 一 --field all`）。10-04旧状态保留，10-10已答与本design供审状态按正式回写；产品未实现。此后最新直接批准已由Root同步intent与#468，原答见五项记录。
- 场景资料：`4-数字员工/采购部/SC10-BOM评审与物料库管控/intent.md`、`openspec/changes/sc10-bom-review-material-governance/{proposal.md,tasks.md,specs/sc10-bom-review-facts/spec.md}`。
- 代码与既有mock：`sc10_bom_review/{agent,models,pending,review,sources}.py`、`tests/test_review_facts.py`。
- 适用建造流程：`4-数字员工/CLAUDE.md`。Root已成功读取场景CLAUDE并核底座复用/None/UNKNOWN/枚举不可比较/OEM边界/专业前置；缺失的采购部CLAUDE不作人侧阻塞。
- 此前猜测audit.py不存在，真实定义audit/events.py已按普通路径核清：decision为dict[str,Any]、data_sources为dict[str,str]、to_dict使用asdict。设计复用现有元数据字段，不修改平台。
- 本轮新增正式design供审；proposal/tasks/spec和产品未改，未运行产品测试、真实查询、外发或部署。

## Root 收敛：Risks / Migration / 具体接口边界

- 3M新版本化入口固定为场景内`run_versioned_review_facts`，输入封套/冻结快照固定放`sc10_bom_review/evidence.py`，委托现有`collect_facts`；既有共享模型及未版本化入口不改合同。新入口必须非空evaluator和可写AuditLogger，audit=None或持久化失败不返回验收成功。旧入口结果不能满足3M验收。
- 规范化规则拒绝NaN/Inf；数值以有限十进制字符串规范化，零值保留且不同于null；BOM行保留重复数量，排序只消除输入排列差异，不能去重丢行；日期用既有ISO语义、计划日期不冒充as-of。未应用专业规则显式not_applied。具体字段映射和代码由下一实施计划锁定。
- [相同计数掩盖不同输入] → 冻结输入并分别哈希三源，result同时绑定manifest与事实值；不重读调用方的可变对象。
- [建议任务混入首项] → D2为本次明确依赖裁决建议：原§5保留完整路线指针、未来独立change，3M白名单仅事实+版本+审计；2.x真实/专业闸不关闭。
- [缺值误成有效/合格] → None/0/UNKNOWN/主数据不存在分开；任何建议层保持fail-loud，不以技术完备替业务评审。
- Migration：批准D1–D9后先正式记录3M白名单、§5路线依赖和2.x拆闸，再审具体实施计划；保留9项历史[x]，不勾产品未做项。只在获准隔离mock中实现，不接源/部署；新封套并行旧未版本化接口，旧审计不重算，失败保留原事实骨架。规范增量需对应批准后更新，main spec待正式同步阶段。

本轮正式新增design供审，旧报告末“未改正式文档”描述的是候选准备动作；当前产品、测试、规范/任务依赖仍未改。本审只决定设计与窄片依赖方向，下一步仍需具体实施计划审批。

## 独立审阅消费：明确版本化身份与hash编码

新3M审计仍使用场景SC10/动作bom_review_facts，并必须在decision中含 `evidence_contract="sc10-versioned-facts-v1"`、`run_mode="synthetic_versioned"`、manifest/result hash。验收查询须同时匹配该contract/mode及完整hash链；缺这些键的旧事件为legacy，不能被相同scenario/action自动算入3M。

Canonical JSON固定UTF-8、ensure_ascii=False、sort_keys=True、separators=(",",":"), allow_nan=False；规范化数值为有限Decimal(str(value))的无指数十进制字符串，去除小数部分末尾零（不删整数位零），负零归"0"；null保留JSON null，生命周期取显式enum value，禁止排序枚举。每源行按其完整规范化对象的canonical JSON UTF-8字节排序，重复BOM行保留重复次数；manifest schema/facts-contract版本随上述编码合同一起绑定。输出product_ids稳定排序，未签规则仍not_applied。

审计持久化的具体调用、有效回执与故障注入按既有AuditLogger/sink真实合同在实施计划锁定；不能以创建AuditEvent或调用一个空mock方法作为持久化成功。合成JSONL验收要关联实际event读取，写入异常必须向调用方传播。此项为实施步骤/验证细节，不再向用户询问技术默认。

