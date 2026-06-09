# Design — 平台底座收割：迁入 supplychain 真连接器

> 审阅对象：Paul（VP）。本文 6 个技术决策（D1–D6）请逐条拍板；标 ⭐ 的是架构级、影响后续所有场景。
> 篇幅按"15–30 分钟可审完"控制，实现细节留给 tasks。

## Context

- 目标位置 `zhuopin_platform/shared_tools/` 当前为空占位；`audit`（AuditLogger/JSONL）与 `data_isolation_layer`（OEMRouter）是**已写好的真骨架**，本次只对接、不重建。
- supplychain 真连接器**不是孤立文件**，存在内部依赖链，收割必须连带处理：
  - `connector.py`（抽象）、`zp_connector.py`、`u9c_connector.py`、`csv_connector.py` 全部 `from src.data_loader import BomRow/InventoryRow/...` —— **强依赖 `data_loader.py`**（438 行，定义 9 个 dataclass + CSV 加载函数）。
  - `xky_srm_connector.py`（516 行）**自带一套 SQLite 审计**（`data/srm_audit.db`，存 req/resp 全文，保留 90 天）。
  - `crm_notifier.py` **依赖 `delay_case.py`** 的 `DelayCase`/`CaseEvent`（479 行，含 `CaseStore` SQLite + `CaseStatus` 枚举），并调用 Claude API（降级模板）。
  - `wecom.py`（74 行）零业务依赖，纯 Webhook，最干净。
- 约束：先 mock、不连真实库；统一审计接平台 audit（IATF 3 年）；采购连接器不加 OEM 路由；凭据从 env 注入不入库。

## Goals / Non-Goals

**Goals:**
- 把上述连接器/通知器填入 `shared_tools/`，对接平台 `audit`，保留 `data_isolation_layer` 接入点（不强用）。
- 迁入对应测试夹具，全程 mock 跑绿，作为后续 SC1/SC8 的 import 基座。
- 理顺依赖：把连接器强依赖的数据模型层一并收割，业务模型层（SC8 专属）排除在外。

**Non-Goals:**
- 不收割业务智能体（delivery_forecast/kit_analysis/supplier_tracking 等）。
- 不接真实 SRM/ERP/U9C/企微端点；不接 ClickHouse；不接 Chroma/RAG。
- 不改造 SC1 场景的 import（后续独立变更）；不执行 supplychain 打 tag 存档。

## Decisions

### ⭐ D1. 数据模型层 `data_loader.py` 一并收割，拆为平台 `models.py` + `csv_loaders.py`
连接器强依赖 `data_loader` 的 dataclass，不搬则无法运行。
- **选 A（推荐）**：收割 `data_loader.py` 进 `shared_tools/`，拆成 `models.py`（9 个 dataclass，纯类型）+ `csv_loaders.py`（load_* 函数 + CSV 回退）。连接器 import 改为 `from zhuopin_platform.shared_tools.models import ...`。
- 选 B：整体照搬 `data_loader.py` 单文件不拆。省事，但把 SC8 专属的 `ForecastOrder`/`load_forecast_orders_from_excel` 等也带进平台底座，污染通用层。
- **理由**：A 让平台层只留通用数据契约；SC8 专属加载（Excel/ERP 导出）随 SC8 收割时再落位。代价是拆分时要分清哪些 dataclass 通用、哪些属 SC8（见 Open Q1）。

### ⭐ D2. SRM 的 SQLite 自审计 → 统一为平台 `AuditLogger`（JSONL）
`xky_srm_connector` 现把每次调用写 `srm_audit.db`（req/resp 全文，90 天）；任务要求统一平台 audit（JSONL，3 年）。
- **选 A（推荐）**：剥离 SQLite 审计，连接器每次数据访问改调 `AuditLogger.record(AuditEvent(...))`；req/resp 全文不进合规审计（含供应商敏感字段），仅保留可选本地 debug 日志（默认关）。合规审计记结构化决策：场景/动作/数据来源/PO 号/时间。
- 选 B：双写（SQLite 调试 + JSONL 合规）。信息全但两套留痕、违背"单一可信源"。
- **理由**：A 符合 IATF 单一可信审计源 + 3 年留存；req/resp 全文留在合规审计反而有数据外泄面。**注意**：90 天 SQLite 历史是否需迁移？倾向不迁（属 supplychain 存档），见 Open Q2。

### ⭐ D3. `crm_notifier` 与 `DelayCase` 解耦——平台层接通用输入，`delay_case.py` 不收割
`delay_case.py` 是 SC8 的业务案例模型（含 CaseStore 持久化），不属平台底座。
- **选 A（推荐）**：平台 `crm_notifier` 改为接受一个轻量输入契约（`Protocol` 或 dataclass：客户/订单号/原交期/新交期/原因列表），不再 import `DelayCase`。SC8 落位时由 `DelayCase` 适配到该契约。`delay_case.py` 留 supplychain，随 SC8 收割。
- 选 B：把 `delay_case.py` 一起搬进平台。但 CaseStore 是 SC8 状态机 + SQLite，搬进底座等于把业务逻辑塞进通用层。
- **理由**：A 保持底座"通用通知能力"纯净，符合分层；草稿生成器本就只需少数字段。代价：定义一个小输入契约 + 改 `build_prompt`/`_template_draft` 签名。

### D4. 目录布局：按职责分子包（贴合收割策略表）
```
shared_tools/
├── models.py                # D1：通用数据 dataclass
├── csv_loaders.py           # D1：CSV 加载 + 回退
├── connector.py             # DataConnector 抽象基类
├── srm_connector/           # 携客云 SRM（只读，承诺交期）
├── erp_connector/           # zp REST（真实 ERP：PO/物料）
├── u9c_connector/           # U9C 骨架（CSV 回退，待 7/1 MCP）
├── crm_notifier/            # CRM 延期通报草稿（D3 解耦后）
└── notifiers/               # wecom 企微推送（通用通道）
```
- 备选：全平铺成模块。否决——子包便于后续每个连接器带自己的 README/夹具/真实切换开关。

### D5. 审计接入点：连接器构造时注入 `AuditLogger`（依赖注入，不内部硬建）
- 连接器 `__init__(..., audit: AuditLogger | None = None)`；为 None 时用 `AuditLogger.jsonl(默认路径)`。便于测试注入内存/临时 sink，避免测试污染真实日志。
- 否决"连接器内部 new 一个 logger"：不可测、路径写死。

### D6. Claude API 模型与降级：保持 `claude-sonnet-4-6`，本次走模板降级
- `crm_notifier` 草稿生成默认模型 `claude-sonnet-4-6`（与全局技术栈一致），无 `ANTHROPIC_API_KEY` 时自动降级 `_template_draft()`。
- 本次 mock 验证全程走模板分支，不发真实 API 调用；模型 id 设为可配置常量。

## Risks / Trade-offs

- **[D1 拆分误判] 把 SC8 专属 dataclass 当通用搬进底座** → 缓解：Open Q1 先确认通用集合；只搬连接器 import 链实际用到的 5–6 个（BomRow/InventoryRow/PurchaseOrder/ProductionPlan/Supplier + SRM 交期相关）。
- **[D2 审计语义变化] req/resp 全文从审计中移除，排查问题时信息变少** → 缓解：保留可选本地 debug 开关（默认关、不留存合规），生产排障时临时开启。
- **[D3 契约设计] 输入契约定义不当导致 SC8 适配别扭** → 缓解：契约字段对齐 `build_prompt` 当前实际读取的字段，最小集；SC8 收割时再校验。
- **[import 重写面大] 11 个测试文件 + 连接器全部 `src.*` → `zhuopin_platform.*`** → 缓解：tasks 里按"模型层→抽象→各连接器→通知器→测试"顺序逐层迁移，每层迁完即跑该层测试（SuperPowers 先测试后实现）。
- **[凭据泄漏] 真实 zp/SRM/企微凭据** → 缓解：全部 env/.env 注入，`.env` 不入库；测试用假凭据 + mock 端点。

## Migration Plan

1. 收割数据模型层（D1）→ 跑 models/csv_loaders 单测。
2. 收割 `connector.py` 抽象 + `csv_connector` → 跑接口契约测试。
3. 逐个收割 srm/erp(zp)/u9c 连接器，接入 AuditLogger（D2/D5）→ 各自夹具测试 mock 跑绿。
4. 收割 `wecom`（最简）→ crm_notifier 解耦改造（D3）→ 通知层测试。
5. 平台 `tests/` 汇总跑全绿（`pytest`，无真实端点）。
6. 回滚策略：本变更纯新增 `shared_tools/` 内文件，不动 audit/router/现有场景；如需回滚直接删除新增子包即可，无副作用。

## Open Questions

1. **(D1) 通用 dataclass 边界**：`SalesOrder`/`ForecastOrder`/`SrmDemandOrder`/`SrmDeliveryOrder` 这几个——哪些算平台通用、哪些归 SC8？我倾向只搬连接器当前 import 链用到的，其余留 SC8。你认可这条边界吗？
2. **(D2) 90 天 SRM SQLite 审计历史**：是否需要迁进平台 audit？我倾向不迁（属 supplychain 存档，且为调试级 req/resp 全文）。同意？
3. **(D3) 通知输入契约形态**：用 `Protocol`（鸭子类型、SC8 的 DelayCase 直接满足）还是显式轻量 `dataclass`（更直观、需适配）？我略偏 `Protocol`，减少 SC8 适配成本。你的偏好？
