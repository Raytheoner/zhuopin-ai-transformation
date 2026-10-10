# Design: SC2 收货报表 BizType316 子集

> 状态：正式 OpenSpec design 供审稿，D1–D10待批准。四件已在本目录成包，2026-10-10严格结构核验1 passed/0 failed；这不代表技术实现、产品测试或design审批。本包按架构路径准备，实施须再审具体计划；#277已答口径不重问。

## Context

SC2当前从 ERP `GR/Query` 取得收货行。既有 `get_receipt_lines()` 以整表分页为主，在连接器与文件层有四小时缓存，映射未带BizType；`sources._fetch_receipts()` 再按BusinessDate窗口过滤并构造无类型/状态的 `ReceiptRecord`。四项目标指标及CSV明细已存在，但当前聚合与明细共享未过滤的 `dataset.receipts`。

§四 #277 已指定仅对新收货报表四指标及其明细采用BizType316；该选择不改变API省略参数时仍不筛选、旧冻结/缓存不重算的约束。连接器的业务类型过滤能力、逐行BizType、组织请求/默认、状态字段均未有独立现网证据。本设计不假设服务端能力已落地。

## Goals

1. 只让 #277 指定的四指标及对应明细使用一个可证明的BizType316子集。
2. 类型/过滤不确定时准确报告对应指标缺口，不静默使用全类型数据、零值或编码前缀猜测。
3. 旧快照和旧缓存保留原值，其他共享收货指标不因本增量发生隐式口径变化。
4. 让来源能力、过滤方式、范围和取得时刻可以审计与复现。

## Non-goals

- 重新设计当前SC2指标UI、修改三项指标替换包、纠正历史数量差异。
- 发明退货/作废/冲销过滤，或将组织猜测写成业务默认。
- 全量复制一份普通收货数据集、建设通用快照服务、建设全新明细路由框架。
- 真实接口查询或部署。本稿不包含生产授权。

## Proposed flow

1. **Connector**：保留现有无类型请求给共享收货数据；若接口确有逐行类型字段且语义、分页完整性可验证，优先由同一全量响应在本地派生316子集。若不能逐行派生，才考虑另发 `bizType=316` 请求，且必须先独立验证服务端过滤能力。API省略参数一律不筛选。
2. **Source adapter**：将原始请求范围、实际生效方式和响应能力转成显式元数据；不要从“IT说可以”或“请求发出成功”推导过滤成功。若逐行类型不可用且服务端过滤又未能独立验证，拒绝生成316口径数值。
3. **FrozenDataset**：共享 `dataset.receipts` 始终保留现有全量/旧语义。仅当逐行类型字段可证时，从该完整集合派生 `receipts_316`；若需独立服务端316请求，则它只供四个目标指标及对应明细使用，不替换共享集合。缺类型的行不能静默进入或排除后仍宣称总量完整。
4. **Metrics/detail**：复用四个既有指标key/标签/算法；同一窗口由同一316范围提供聚合及CSV。共享 `receipts` 上的收货单据数、料号数、可溯源率保持原行为。
5. **Snapshot/cache**：新类型/能力证据使用新schema与包含过滤身份的缓存key；旧格式仍由旧路径读取，不能为新口径回填默认316，也不能覆盖已经冻结的旧期数据。新文件拟采用 `sc2_weekly_{period}__biztype316-v1.json`、`sc2_dataset_{period}__biztype316-v1.json` 与 `gr_lines_{days}d__biztype316-v1.json`。缺省 `config.reports_dir()` 为 `SCENE_ROOT/reports`，可被 `SC2_REPORTS_DIR` 覆盖；connector `_po_cache_file.parent` 缺省为包内 `cache/`，可被构造参数覆盖。假路径 `git check-ignore -v` 实测：默认周报/数据集命中根 `.gitignore:59 **/reports/`，默认connector缓存命中平台 `.gitignore:12 **/cache/`；原忽略准备包中的 proposal 命中 reports 规则。正式路径 `openspec/changes/sc2-biztype316-receipts/proposal.md` 未命中ignore规则。没有读取环境覆盖值，也未核验覆盖目录或实际文件。
6. **Evidence/audit**：真实访问按平台既有ConnectorAudit要求记录请求身份、结果范围、端点/能力证据、分页与取得时间。只在未来获准的取证阶段验证；mock不能替代现网证据。

## Decisions

以下 D 项均是建议，不是 #277 之外的新批准。

| ID | 建议决定 | 理由/边界 |
|---|---|---|
| D1 — 目标集隔离 | 仅让既有 `receipt_line_count`、`receipt_qty`、`receipt_amount`、`receipt_supplier_count` 四项及其对应收货明细读取316子集；其它基于共享 `dataset.receipts` 的指标继续使用原集合。 | #277只点名四项和对应明细；禁止把服务端316响应替换全量共享收货集。页面沿用既有UI，范围标识说明这四项按316计。 |
| D2 — 两种来源架构与默认推荐 | **方案A（默认推荐）**：若每行有完整、语义经证的BizType，则取现有完整收货集并派生316子集，共享 `dataset.receipts` 不变。**方案B（A不可用时）**：保留现有全类型请求/集合供共享与旧指标，同时另发 `bizType=316` 请求，独立验证过滤生效后只将该响应供四指标与对应明细。服务端过滤能力未证时，B不可启用。 | A避免重复请求且保持原始全量集合；B仅在无逐行类型时作为替代。#277规定省略参数不筛选，任何服务端过滤都须有能力证据。 |
| D3 — 类型未知语义 | 只有在既无已验证的服务端完整316筛选结果、又无完整逐行类型成员证据时，四指标和对应明细才报告“BizType316范围未证/资料不足”，不产生完整值。省略 `bizType` 本身不构成缺口，若逐行类型完整可证仍可采用方案A。 | 直接执行 #277；不能把 unknown 当 316，也不推断前缀。 |
| D4 — 缺字段粒度 | 分开报告受影响值：缺类型/过滤/BusinessDate或分页完整性未知 → 四项及明细范围完整性未知；缺数量 → 数量、金额不完整（行数/供应商数可在其必需字段完整时单独计算）；缺单价 → 金额不完整；缺供应商名 → 供应商数不完整。不得把部分和伪装为全量和。 | 不让单字段缺失扩大为不相关指标的业务否决，也不把可算的其它指标一并归零。详情需标注字段缺口；若行级缺失使明细无法核对目标聚合，则相应detail完整性标为不足。 |
| D5 — 组织范围 | 记录实际选定组织及其来源；不在SC2中硬编码 `Org=Z`，也不将“没有新增组织验证”本身升级为统一业务否决。若发现跨组织混合，或不能证明本次结果属于现有业务上下文要求的组织，则只阻止“目标组织全量值”声明，并给出组织范围缺口。 | IT的 `Org=Z` 是未独立验证的陈述；现connector未显式传组织。后续可先核合同/参数元数据，真实查询另过授权。#14保持closed。 |
| D6 — 状态/退货 | 延续SC2当前收到的GR/Query行与BusinessDate边界，不增加状态、作废、退货、冲销过滤。状态未知不作为新的全局否决默认。若IT后续证实返回行中含需业务排除的类别，再单独提交那项规则供专业签认。 | #277只签BizType边界；现ReceiptRecord没有这些字段/过滤。避免把新问题偷偷加为阻断，同时不声称状态规则已验证。 |
| D7 — 公式继承 | 沿用当前四公式：行数、数量求和、数量×当前unit_price、非空supplier_name去重；不改价格基准或供应商主键。 | 当前UI/算法已存在。若实施发现新源的字段含义不同，先记录事实并只为发生变化的定义申请专业确认。 |
| D8 — 旧快照 | 新数据集增BizType/能力元数据使用新schema与 `__biztype316-v1` 身份；旧period/缓存不得刷新覆盖。新316结果遇到同period旧冻结时单独保存或保持新值不可用，绝不原位重算旧件。 | 严格遵守#277；现 `DATASET_SCHEMA=1` 已拒绝不匹配schema。 |
| D9 — 缓存 | 316专用缓存身份至少区分 `days`、业务类型和能力版本；仅有 `days` 且不含BizType的旧内存/磁盘缓存不可命中为316。旧缓存不清理、不改写。拟名为 `gr_lines_{days}d__biztype316-v1.json`。 | 缺省cache目录由 `_DEFAULT_PO_CACHE_FILE.parent` 得出为连接器包内 `cache/`，构造器允许 `po_cache_file` 注入覆盖。默认假文件命中平台 `.gitignore:12 **/cache/`；覆盖目录未读取/核验。 |
| D10 — 路径与数据边界 | 只使用合成fixture。缺省SC2 `reports/` 假文件命中根 `.gitignore:59 **/reports/`；连接器包内 `cache/` 假文件命中平台 `.gitignore:12 **/cache/`。 | 规则已对缺省目录核验；运行时覆盖值可能改变目录，部署配置如启用覆盖须另行核验。原reports供审目录被忽略；本正式包已在可跟踪的 `openspec/changes/sc2-biztype316-receipts/`。知识持有人/Owner与Backup均unknown，阻挡专业签认和真实业务阶段，不阻挡Native mock；技术实施仍需批准design与具体计划。 |

## Gaps and metric impact

| 未知项 | 影响范围 | 处理方式 |
|---|---|---|
| 无逐行BizType，且显式过滤未验证 | 四指标与对应明细 | 按#277报“范围未证/资料不足”；不是业务阈值问题。 |
| BusinessDate缺失或分页完整性无法证明 | 所有窗口内四指标及明细完整性 | 报窗口/行集缺口；不把缺行算为0。 |
| 数量字段缺失 | 数量、金额；详情中相应行字段 | 两指标不显示全量值；若行数及供应商字段完整，仍可各自算其可证值。 |
| 单价字段缺失 | 金额 | 仅金额为资料不足；数量和行数不受该字段单独影响。 |
| 供应商名缺失 | 到货供应商数 | 该项不可宣称完整；不把空字符串当一个供应商。 |
| 组织范围未记清 | 目标组织全量声明 | 不把Org=Z当默认；先取组织来源事实。如果已有运行上下文能证明单组织则记录该事实，不能证明时只标目标组织范围未知。 |
| 状态/退货语义未知 | 不新增排除判断 | 保持当前返回行行为，并标明“按当前GR/Query返回行统计”；只有发现既定业务要求与来源类别冲突，才阻止受影响指标并请求专业签认。 |

## Data and compatibility

- 默认方案A：若全量源逐行类型完整可证，单份typed冻结数据仍承载原始收货行和source metadata，通过视图/函数派生316子集。备选方案B：若A不可用但服务端过滤可验证，独立保存316来源结果，仅四指标与对应明细读取；完整共享集继续原样用于其它指标。不得用B的响应覆盖全量 `dataset.receipts`。
- 新316范围通过scope元数据或独立typed row wrapper显式保存 `biz_type`（或已验证的服务端过滤凭据）、filter requested/applied/verified、source/endpoint capability version、组织来源、period window、pagination completeness、captured_at 和可判定字段的缺失清单。不得更改旧共享 `ReceiptRecord` 数值类型/默认行为；缺数量/单价只让新316子集相应指标不完整。
- 旧 `sc2_dataset_{period}.json` / `sc2_weekly_{period}.json` 保持不变。新schema不得把旧文件读成316；有同period旧冻结时不覆盖。scope/version作为新结果身份的一部分；只保存原有周报+数据集配对，不加第二份全量副本。
- Connector的旧 `gr_{days}` 内存与 `gr_lines_{days}d.json`缓存不带类型；新scope拟使用 `gr_{days}__biztype316-v1` 与 `gr_lines_{days}d__biztype316-v1.json` 这类含业务类型及版本的身份，不读取旧文件作为新口径证据。默认cache路径规则已核验；若注入覆盖路径则实施时复核该路径。
- 针对新schema的合成fixture使用 `MOCK-*` ID。生产回件与实际原始行不进入测试仓库或版本控制。

## Security and compliance

- mock先行、真实请求遵守授权与ConnectorAudit；不复制密钥/连接串。
- OEM隔离规则继续有效；此变更是采购数据，不跨客户域共享。
- 本范围没有L2决策自动执行、客户交付、生产发布或ASIL工作。
- Git只接纳代码、文档与合成fixture；真实源快照/接口响应留在受控运行期位置并保持ignore。

## Components and likely files

- Platform connector: `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py`。
- SC2 domain/data path: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`, `sources.py`, `metrics.py`, `detail.py`。
- Snapshot/display path only if needed: `report.py`, `config.py`, `webapp.py`。
- Planned tests only: SC2 `tests/test_sources.py`, `test_metrics.py`, `test_detail.py`, `test_report.py`; platform connector test path to be identified in formal implementation preparation.

## Risks / Trade-offs

- 来源当前不带类型 → A只对完整、可证逐行类型启用；mock实现成员证据与失败关闭，真实源取得前继续报缺口。
- B需重复请求且可能静默忽略参数 → B默认禁启，独立合同/全页范围证据到位后再过真实阶段授权；不允许仅凭请求成功宣称过滤生效。
- 数值默认0可能掩盖原始缺项 → 在新scope/typed wrapper保留字段缺失证据，不修改旧共享行模型默认值。
- schema/身份新增可能让UI错读旧期 → 旧文件按旧语义打开；新scope按独立身份打开，同period不覆盖，四指标与详情同一个冻结成员集。
- 部署覆盖目录可能不被ignore → 默认路径已有实际核验；任何配置覆盖在启用前逐项核验，不读取敏感环境来推定当前部署就绪。

## Migration Plan

1. 设计批准后形成具体实施计划和路径白名单；先在获准隔离工作树完成Native/Guardian对应的合成实现与验收，不查询生产。
2. 对新316身份提供显式选择/范围标签；历史入口继续读原冻结，不能自动把既有期次迁为316。
3. 真实来源合同/过滤证据、专业签认、Owner/backup及授权到位后，另审真实验证与发布；不因mock通过启用B或重算历史。
4. 回滚只停用新增316入口/配置并保留新证据文件；旧路径原件未改，不用覆盖、删除或重算来回滚。ff、部署与对外发送仍各按具体项审批。

## Open Questions

这些未知可留给真实阶段，不改变本次mock的A派生+B默认禁启架构：

1. IT/接口负责人提供哪种受控合同与全页对照证据证明服务端过滤真正生效；证据未到时B不可启用。
2. 真实知识持有人/Owner及Backup实名、价值度量定义与Champion基线；未实名前不进入专业签认或真实业务。
3. 实际部署是否启用目录覆盖；启用前复核其ignore与受控数据位置，不假定默认目录就是生产目录。

## Approval request

请审D1–D10及上述风险/迁移边界。批准本书面design后才进入具体实施计划；本件不申请真实查询、服务器修改、ff或生产发布。
