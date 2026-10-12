# SC2 三项指标证据合同与周报切片：设计修订草案

> 状态：供内部 design review；这是独立修订草案，不是对正式 OpenSpec design 的修改，也不构成实施、真实取数、合入、部署或外发授权。
> 对照基线：隔离提案 `sc2-three-metric-evidence-1012`，design HEAD `23d9e97e462c8cbc5feb5c73c0eff510a6e0c4d7`，design SHA-256 `2d09c3a0ef4b2ad060bf32da7abeb4278cf1495f3fbaeddb26d61a49955576e2`。

## 1. 目的与来源边界

本草案仅把隔离 design 的三项必需修订写清：已签公式能支持什么数值、不可变证据快照与旧版并存/回退方式、现有工作日日历和固定合成样本的使用方法。SC2 的报告范围仍是采购部 #23/#24 已签认的三项替换：下单按时完成率、排程按时答交率、按时到货率。不得将 #538 的历史残差/187 行比较或 BizType=316 四指标材料混入本变更，也不得重建首版周报、改既有发布/复核/通知行为或新增业务规则。

业务来源锚点：`4-数字员工/采购部/SC2-采购周报自动生成/intent.md` §二 D01–D06、§三 G01–G04；`1-转型规划/0-全景路线图/拆件-采购部24-SC2三项指标范围与字段签认-2026-10-03.md` §二、§三；采购部 #23 原定义段 61–103（下单）、106–141（排程）、144–182（到货）。#24 回件答明三项替换旧周报内容、排程期限“五个工作日”、到货字段和日期边界。字段截图仅证明 UI 位置，不证明接口可用。

## 2. 公式与证据计算边界

### 2.1 三项通用前置

每个计算都绑定一项**已签公式来源引用**（来源文件/回件、段落或字段、规则版本）；只有来源引用逐项覆盖统计对象、分子、分母、窗口/事件时点和适用日历时才允许输出数值。实现不得用旧三窗口、旧 order/receipt schema、字段名相似或 mock 中的排列代填空缺。公式引用缺失或签认范围不能覆盖当期时，结果为 `PENDING`，reason code `SIGNED_FORMULA_NOT_BOUND`；接口事实缺失则记录 `unknown` 原因，两者不得合并成零。

采购部 #23/#24 证明以下有限事实：三项替换范围；下单期限六个工作日；排程答交期限五个工作日；周末及法定假日不计、调休上班日计入；到货闭区间与逐物料算术平均。凡未在上述回件/intent 明确的具体分子、分母、起点/端点、期次归属，不由工程推导。实施前须将原签认的精确字段/分子/分母和引用位置绑定至规则记录；绑定不到的项按本节状态返回，不以实现阶段“补公式”。

### 2.2 分指标

| 指标 | 允许直接复用的签认 | 计算限制 |
|---|---|---|
| 下单按时完成率 | 采购部 #23/#24 三项替换及 6 个工作日期限；周末/法定假日扣除、调休工作日计入 | 不将“2026-09-07 截止”推广为滚动窗口。G01（新期次窗口/历史状态时点）未签时，涉及期次或历史状态的结果保持 `PENDING`；可展示已核实的来源行/事件，不宣称完整率值。仅在 #23 的已签定义能逐项绑定该计算时才生成数值。 |
| 排程按时答交率 | 五个工作日期限（#24 澄清原“五个昨日”为笔误）；工作日历口径同上 | 不用当前答交状态回填历史状态，不把当前未答交数倒推为期限内答交事实。G01 未签或答交历史时点缺失时分别保留 `PENDING` / `unknown`；公式分子/分母必须引用 #23 原文精确条款，未绑定不产率值。 |
| 按时到货率 | 入库日期闭区间：`计划发布日期 ≤ 入库日期 ≤ 同物料“正确认数量为正”的答交日期`；按时入库数量按 #24 指定字段求和；物料率＝按时入库数量 ÷ 计划应到数量；部门率＝各物料率算术平均（不数量加权）；每颗物料作为一个种类 | **分母**严格绑定 #23 段 147 的“排程日期下第二行正数量”（#24 拆件 §二亦注明），不以订单量、ERP 制单量或可用量替代。G02 多计划/重复入库归属未签、G03 零/缺分母未签、G04 退货/作废/撤销/关闭处理未签时，对受影响物料率及部门汇总保留 `PENDING`，不得任配、去重、扣减或剔除。 |

### 2.3 G01–G04 与零值

四项保留为待签专业案例，不是本变更内的设计决定：G01 期次窗口/历史状态；G02 多计划、多个答交版本及重复入库的匹配归属；G03 零分母/缺值与部门平均纳入；G04 退货、作废、撤销/关闭及生效时点。涉及未签规则的指标必须是 `PENDING`，reason code 指向对应 `G01`…`G04`；不得造数据让案例看似已解。

只有在签认公式和证据齐全、分母为正时，`value=0` 才代表计算所得确为零。已取到的真实零分母是 `PENDING/G03_ZERO_DENOMINATOR`，不能套用旧模型的 `no_data` 替代签认；字段/历史/页集缺失是 `unknown`。部门平均只在其业务分母成员资格及每项归属均已确定时计算；若有任何未解决成员可能改变平均的分子、分母或成员集，不发布看似完整的部门率。

## 3. 版本化快照、兼容、回退与审计

### 3.1 对象与版本

保留现有 `sc2/report.py::report_to_dict/snapshot_to_report/save_snapshot/load_snapshot` 和 `sc2/detail.py::dataset_to_dict/dataset_from_dict/save_dataset/load_dataset` 旧格式、旧目录和读写语义不变。旧 report 快照不含显式 schema version：仅在具备旧 `period/base_date/metrics` 必需键且不含新 `schema_version` 时，由独立 legacy reader 识别为 `legacy_report_v0`；不满足键合同则 fail-closed。旧 dataset 仍按 `detail.py` 当前 `DATASET_SCHEMA` 严格识别；不得把旧 FrozenDataset 解释成新三指标 evidence。

新增 schema 固定为 `sc2_three_metric_evidence/v1`，至少包含：

- `snapshot_id`：新生成的 UUID；同一期多次生成仍各自唯一，不以 period 覆盖旧对象。
- `schema_version`、`period`、`created_at_utc`、`mode=synthetic`、`canonical_sha256`。
- `source_capabilities`：fixture/source 标识与版本、查询区间、分页完整性、历史可用性、缺失字段；所有来源均明示 `MOCK-`，不记录虚构 API 或 raw payload。
- `workday_calendar_ref`、`rule_refs`：规则来源锚点、已签口径版本及日历 ID/版本/hash。
- 原始合成事实与行级 evidence refs；每项 metric 的 status、value、numerator、denominator、聚合说明、适用 rule refs、证据引用及 reason codes。

canonical hash 使用 UTF-8、稳定键顺序/日期与数值表示的规范 JSON，排除 `canonical_sha256` 自身后计算 SHA-256；序列化规则版本随 schema 记录。任何重算/修订生成新 `snapshot_id`，禁止原位改写。

### 3.2 落盘与发布次序

新对象仅落 `sc2/config.py::reports_dir()` 下隔离目录 `sc2_three_metric_evidence/<period>/<snapshot_id>.json`；不写旧 `sc2_weekly_{period}.json` 或旧 dataset 路径。通过 `config.py` 增加该子目录路径函数，不增加端口、服务或共享存储。

写入顺序：在目标目录同卷写唯一临时文件 → flush/close 并回读解析、复算 canonical hash → 用**不覆盖**的原子 rename 发布到唯一 `snapshot_id` 目标；目标已存在即拒绝。随后向现有 `config.audit_path()` 指向的 `sc2_audit.jsonl` 追加一次平台审计事件，包含 action、period、snapshot_id、schema_version、canonical hash、source 摘要、规则与日历版本、各指标状态及 evidence refs。JSONL 链写后回读并验链。审计失败时不得在新 PC 视图/接口中呈现为已完成周报；已落盘快照保留为未发布对象供审计，不自动删除、不复用 ID。连接器访问审计 `sc2_connector_trace.jsonl` 与业务计算审计不同；本变更全程 mock，不触发连接器。

报告及明细读新数据必须通过明确 `snapshot_id` 查找，不设可变“最新一期”指针。通过现有 `/procurement/sc2` 增加显式 opt-in PC 路径和其只读 API；默认旧页面/旧 reader 不变。实施阶段若需发布指针或默认切换，属于额外范围须另审。

### 3.3 状态接口与 HTML

API 对每项返回稳定字段：`status` (`value|unknown|pending`)、`value`、`numerator`、`denominator`、`reason_codes[]`、`evidence_refs[]`、`snapshot_id`、`schema_version`、`rule_refs[]`、`workday_calendar_ref`。`status=value` 时才可给 value 与分子/分母；0 为数值且 status=value。`unknown`/`pending` 的 value、numerator、denominator 均为 null，不可被客户端转成 0。reason codes 使用固定机器值：`SOURCE_FIELD_MISSING`、`HISTORY_UNAVAILABLE`、`PAGE_SET_INCOMPLETE`、`RELATION_UNPROVEN`、`CALENDAR_UNAVAILABLE`、`CALENDAR_OUT_OF_RANGE`、`SIGNED_FORMULA_NOT_BOUND`、`G01`、`G02`、`G03`、`G04`。可以并列多个原因，不以单个优先级丢失事实。

HTML 将 0 显示为 `0%`，unknown 显示“资料未知”并列原因，pending 显示“业务判例待签”并列 G 编号；若 unknown 与 pending 同时存在，两者同时展示。未决行级证据可列在明细，但不汇总成默认分母。API/HTML 仅只读，不出现发送、刷新真实源或采购执行动作。

### 3.4 回退

旧格式快照与旧 report/dataset path 不改写。新 PC 路径由显式 opt-in 配置默认关闭；任一新快照、审计验链或 reader 失败，返回当次失败状态，不自动转用真实源、旧计算结果或模拟补位。回退仅关闭 opt-in 并继续使用旧 reader/renderer；新 schema 快照、临时失败证据和审计事件全部保留，不清理、不覆盖。测试用合成 legacy report、legacy dataset 与 v1 快照证明双读、无旧金样漂移、失败关闭及切回旧路径。

## 4. 工作日日历与固定合成样本

采用现有公司权威表，不另建/推算日历：`4-数字员工/财务部/FI3-付款申请自动校验/data/holidays/holiday_calendar.csv`。其权威源是 `7-外部文档/财务部/财务部-tangyanping-回复-2026-08-22-2026年及2027年节假日日历-7ce72f2c7b3e279f72e50821b9589f2c.xlsx`；已消费核验记录 `1-转型规划/0-全景路线图/FI3前置就绪包-节假日日历落档与design落字指令-2026-09-02.md` §七，记录源 MD5 `8e5295e84d310477722b5bfc353e88be`、745日覆盖 2026-01-01 至 2028-01-15，且 2026/2027 版中“是否工作日”与“日期类型”自洽。遵循采购部#22/#499：直接读“是否工作日”，不自行合成周末/节假日/调休日历优先级。

测试禁止运行时依赖 FI3 文件或读取其目录：新增固定测试 fixture `tests/fixtures/three_metric_evidence/workday_calendar.json`，由实现阶段从上述经核验来源抽取有限的公开日历日期，记录源 MD5、原日历版本/覆盖、逐日 `is_workday` 和 fixture SHA；业务订单、物料、人员、数量均为 `MOCK-` 合成值，不把真实业务行带入 fixture。fixture 的日期必须覆盖普通工作日、周末非工作日、法定假日非工作日及调休上班日，不能用随机生成或机器当前日期。此 fixture 只用于复现已签日历行为，不改变公司日历正本。

待计算日期超出 pinned 日历覆盖、日历引用缺失或版本不匹配时，相关事实 `unknown`，reason=`CALENDAR_OUT_OF_RANGE` / `CALENDAR_UNAVAILABLE`，不延伸、外推或套现代系统日历。六/五工作日的精确起点/边界仍须从 #23/#24 对应定义绑定；不能由日历数据替代业务事件边界。

## 5. 合成纵向切片与验收

只使用 `MOCK-` 标识；合成周计划、需求、答交、入库行引用均能追到固定 fixture。至少覆盖：(a)已签公式与证据完整时可算的到货率样例，含计划日期下第二行正数量分母、闭区间端点及每物料算术平均；(b)一个需 G02/G03/G04 判例的到货边界，输出 PENDING；(c)下单/排程因 G01 期次/历史状态或公式引用未闭而 PENDING；(d)源历史/字段/页集缺失导致 unknown；(e)工作日与调休/节假日固定日历解析、缺版本/越界 unknown；(f)合法 `0%` 与两种不可计算状态的 API/HTML 对照。

若 #23/#24 原文不能提供可绑定公式的完整样例，则不得为了达成完整数值路径新造判据；仍可完成显示 PENDING/unknown 的 PC 证据切片。验收包括从输入、快照、计算到页面/明细的同一 `snapshot_id` 与 hash 可追溯，审计事件包含对应 ID/hash，旧 reader 输出与旧快照原字节无变化，audit 失败/重复 ID/坏 hash 均不显示成功结果。

## 6. 触碰区与验证边界

### 实施白名单（后续单独批准后才可触碰）

**8 个现有 SC2 代码文件**：

- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/windows.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py`（实现版本化证据 codec/读写，不另增 `evidence.py`）
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py`

**4 个新增全合成测试/fixture 文件**：

- `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/legacy_snapshot.json`
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/new_snapshot.json`
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/workday_calendar.json`

不改写既有测试/金样，实施验证仅额外运行既有 `tests/test_caseback_golden.py` 和 `tests/test_delivery.py`；其余项目 CI 和design原列回归按最终批准实施计划执行。最具体 CI 根固定为 `4-数字员工/采购部/SC2-采购周报自动生成`；精确 job 命令/cwd/隔离环境须在实施前从受信 workflow 核实并记录，本草案不猜命令。

不触碰 `sc2/notify.py`、`sc2/outbox.py`、`sc2/review.py`、共享平台、旧快照/生产数据、真实 ERP/SRM、供应商/OEM 数据、#538/#539 任务或316四指标资料。真实接口和数据可行性仍是IT/工程内部任务，不转嫁业务专员。

## 7. 审查/授权状态

本文件是供复核的修订方案，不能代表正式 workflow 中 `design.md` 已修改、已验证或已获批。根会话应另行核对本文件对照的 commit/hash、提出正式 amend 方案并取得所需审批；在正式 design 修订、审批及后续实施授权分别完成前，不开始产品实现或测试。
