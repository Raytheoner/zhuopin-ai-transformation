# Tasks — 平台底座收割：迁入 supplychain 真连接器

> 执行原则（SuperPowers）：每组**先写/迁测试再实现**，每组迁完即跑该组测试 mock 跑绿，再进下一组。
> 全程不连真实 SRM/ERP/U9C/企微端点；import 由 `src.*` 改写为 `zhuopin_platform.shared_tools.*`。

## 1. 准备与脚手架

- [x] 1.1 在 `shared_tools/` 下建子包目录：`srm_connector/ erp_connector/ u9c_connector/ crm_notifier/ notifiers/`，各含 `__init__.py`
- [x] 1.2 确认 `pyproject.toml` 依赖（requests/python-dotenv 已在）；`pip install -e` 平台包可导入
- [x] 1.3 在平台仓库 `.gitignore` 增补：连接器可选 debug 日志路径、`.env`、本地缓存（po_cache 等）
- [x] 1.4 建 `tests/fixtures/`，迁入 supplychain `data/mock/*.csv`（bom/inventory/purchase_orders/production_plan/suppliers）作脱敏夹具

## 2. 数据模型层（D1：models.py + csv_loaders.py）

- [x] 2.1 迁测试：从 supplychain 迁 `test_csv_connector.py` 相关用例，改写 import，标记待实现
- [x] 2.2 收割 `data_loader.py` 的**连接器返回 shape** dataclass → `shared_tools/models.py`（BomRow/InventoryRow/PurchaseOrder/ProductionPlan/Supplier + SRM 返回类型 SrmDemandOrder/SrmDeliveryOrder）
- [x] 2.3 业务聚合类型（SalesOrder/ForecastOrder）**不迁**，留 SC8；确认 models.py 不含其引用
- [x] 2.4 收割 `load_*` 函数 + CSV 回退 → `shared_tools/csv_loaders.py`，import 指向 models.py
- [x] 2.5 跑 2.1 测试：models/csv_loaders mock 跑绿（8 passed）

## 3. 数据抽象与 CSV 连接器（DataConnector + CSVConnector）

- [x] 3.1 迁测试：`test_connector_interface.py` → 平台 tests，改写 import
- [x] 3.2 收割 `connector.py`（DataConnector 抽象）→ `shared_tools/connector.py`，import 指向 models.py
- [x] 3.3 收割 `csv_connector.py`（CSVConnector，主源不可用时回退）→ `shared_tools/`，import 指向 csv_loaders
- [x] 3.4 跑契约测试：不同数据源遵循同一抽象接口、回退 CSV 跑绿（4 passed）

## 4. 审计接入层（D2/D5）

- [x] 4.1 设计连接器轻量访问痕迹 helper（`ConnectorAudit`）：构造时注入 sink；只记数据源/动作/目标标识/时间（D2 粒度：不刷合规决策，合规留场景层）
- [x] 4.2 实现可选 debug 日志开关（`DebugLog`）：默认关、独立 `*.debug.log`、gitignore；req/resp 全文仅显式开启时写，绝不进合规 audit
- [x] 4.3 写测试：验证（a）默认无 req/resp 全文文件；（b）连接器只产轻量痕迹、不写场景级合规决策字段；（c）sink 可注入临时对象（6 passed）

## 5. SRM 连接器（携客云，只读）

- [x] 5.1 迁测试：SRM 连接器看板解析 + 承诺交期，改写 import、mock 端点
- [x] 5.2 收割 `xky_srm_connector.py` → `srm_connector/`，保留 MD5 签名/只读逻辑；凭据改 env 注入
- [x] 5.3 **剥离自带 SQLite 审计**（srm_audit.db）→ 改用 4.x 注入式 ConnectorAudit 轻量痕迹；req/resp 全文移入可选 DebugLog
- [x] 5.4 SRM 审计测试改造为验证"轻量痕迹 + 默认无全文 + 无 SQLite 残留"
- [x] 5.5 跑 SRM 测试 mock 跑绿（6 passed）；全程无真实网络调用

## 6. zp ERP 连接器（真实 ERP shape，mock 验证）

- [x] 6.1 迁测试：`test_zp_connector.py`，改写 import、mock REST 响应
- [x] 6.2 收割 `zp_connector.py` → `erp_connector/`；JWT 认证/PO/物料/BOM 逻辑保留，凭据 env 注入
- [x] 6.3 接入 4.x 审计 helper（source=zp_ERP）；PO 缓存改包内 gitignore cache/，测试用临时目录
- [x] 6.4 跑 zp 测试 mock 跑绿（6 passed，不触 testerp 真实端点）

## 7. U9C 骨架连接器

- [x] 7.1 迁测试：`test_u9c_connector.py`，改写 import
- [x] 7.2 收割 `u9c_connector.py` → `u9c_connector/`，保留 CSV 回退；保留 7/1 MCP 真实接入点 TODO
- [x] 7.3 接入 4.x 审计 helper；跑测试验证"接口未就绪时 CSV 回退、不阻塞"（4 passed）

## 8. 通知通道（D3 解耦 + wecom）

- [x] 8.1 定义通知输入 `Protocol`（`NotificationMessage`：收件人/标题/正文/严重度 + `DelayNoticeInput`：客户/订单/原交期/新交期/原因）于 `crm_notifier/`
- [x] 8.2 收割 `wecom.py` → `notifiers/`（零业务依赖）；webhook env 注入；mock 推送测试
- [x] 8.3 迁测试：通知层测试改写为基于 Protocol 的输入，去除 DelayCase 依赖（含 AST 校验无 import）
- [x] 8.4 收割 `crm_notifier.py` → `crm_notifier/draft.py`：`build_prompt`/`template_draft` 改读 Protocol 字段，**不 import delay_case**
- [x] 8.5 保持 `claude-sonnet-4-6` 为可配置常量（DEFAULT_MODEL）；无 ANTHROPIC_API_KEY 降级模板；测试全走模板分支
- [x] 8.6 实现外发前置 L2 门禁（`Notifier`）：高风险/推客户未确认只产草稿、不自动外发；测试验证
- [x] 8.7 通知动作经注入 AuditLogger 留痕（动作/渠道/人工确认状态）；通知层测试（13 passed）

## 9. 汇总验证与收尾

- [x] 9.1 平台 `pytest` 全量跑绿（51 passed）；conftest 网络守卫拦截真实连接，确认零真实端点调用
- [x] 9.2 更新 `shared_tools/__init__.py` 导出 + 平台 README「四个子系统」表：shared_tools 由🔧改✅
- [x] 9.3 自检：采购连接器（zp/SRM）无 OEM 路由参数、`data_isolation_layer` 接入点预留可用（OEMRouter 冒烟通过）
- [x] 9.4 `openspec status` 确认 applyRequires 完成；准备 `/opsx:archive` + git commit（未切真实库、未打 supplychain tag）
