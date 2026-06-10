## Why

SC1 MVP 已完成并归档，但仍处于"独立态"：本地 `src/audit_log.py` 自造了 AuditLogger、`src/data_providers.py` 的 SRMProvider 通过 `sys.path` 黑魔法直接引用 supplychain 跨工程连接器。§1 加固（hash-chain / Pydantic / 限流）已合入 master，SC1 切到底座后即可白嫖这些能力，同时满足 IATF 单一可信源要求。

## What Changes

- **审计切底座**：删除本地 `AuditLogger` 主体逻辑，改用 `zhuopin_platform.audit.AuditLogger + AuditEvent`；在 SC1 层保留薄 `SC1AuditAdapter`（`append_record()` 接口不变，供 main.py 调用）。审计记录升级为 P2 hash-chain 格式，可 `verify_chain()`。
- **SRM 连接器切底座**：删除 `SRMProvider._get_connector()` 里的 `sys.path` 黑魔法，改为 `from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector`。`DataProvider` ABC、`ManualProvider`、`get_delivery_data()` 接口不变。
- **包化**：添加 `pyproject.toml`（替代 `requirements.txt` 中的底座部分），声明 `zhuopin_platform` 依赖。
- **mock 验证**：新增/更新测试：审计等价对照（新旧格式关键字段映射）、`verify_chain()` 通过、SRM 切换后 `get_delivery_rate()` 行为不变。
- task 9.1（真实 SRM 数据接入）明确标记为 BLOCKED，留作 6/12 单独变更。

## Capabilities

### New Capabilities

- `sc1-audit-platform-bridge`：SC1 审计适配层——将 SC1 特定字段（supplier_name / scores / ai_text_hash）映射到 `AuditEvent.decision`，底层走平台 hash-chain JSONL sink
- `sc1-srm-platform-connector`：SRMProvider 内部改用底座 `XkySrmConnector`，消除跨工程 sys.path 引用，获得 Pydantic 校验 + 令牌桶限流

### Modified Capabilities

（无 spec-level 需求变更，仅实现层换底，行为等价）

## Impact

- `src/audit_log.py`：重写为 SC1AuditAdapter 薄包装（调用平台 AuditLogger），原始 JSONL 写法删除
- `src/data_providers.py`：SRMProvider._get_connector() 改 import 路径，其余不变
- `tests/test_audit_log.py`：更新断言适配新 JSON 结构（platform AuditEvent 格式）
- `pyproject.toml`：新建（替代 requirements.txt 中的底座依赖声明）
- `requirements.txt`：保留第三方依赖，移除底座相关
