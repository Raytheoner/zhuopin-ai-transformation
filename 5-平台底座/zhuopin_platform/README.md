# zhuopin_platform — 卓品智能 AI 转型平台底座

跨部门数字员工的共享底座。一份代码、处处复用，单一可信源（满足 IATF 审计与 OEM 隔离合规）。

## 安装（开发模式）

各数字员工场景在自己目录执行：

```bash
pip install -e ../../5-平台底座/zhuopin_platform   # 路径按相对位置调整
```

> 要求 Python ≥ 3.11（与 SC1 一致）。

## 四个子系统

| 子系统 | 作用 | Phase 1 状态 |
|--------|------|-------------|
| `audit` | IATF 可追溯审计，JSONL 先行 / ClickHouse 9月汇聚（同接口可切换） | ✅ 可用 |
| `data_isolation_layer` | OEM 数据隔离，per-OEM 向量库路由，拒绝跨库 | ✅ 路由可用，RAG 待接 Chroma |
| `shared_tools` | doc_parser / srm / u9c / external_apis | 🔧 骨架，按解依赖进度实现 |
| `agents` | 跨部门智能体逻辑 | 🔧 骨架 |

## 快速校验

```python
from zhuopin_platform.audit import AuditLogger, AuditEvent
from zhuopin_platform.data_isolation_layer import OEMRouter, CrossOEMAccessError

audit = AuditLogger.jsonl("reports/audit_log.jsonl")
audit.record(AuditEvent(scenario="SC1", action="supplier_risk_eval",
    evaluator="张采购", automation_level="L2",
    decision={"risk_level": 4}, content_hash="..."))

OEMRouter().guard(oem="比亚迪", collection="oem_saic")  # 抛 CrossOEMAccessError
```

测试：`pytest tests/`（冒烟测试覆盖审计写读、红色数据保护、OEM 隔离红线）。

## 后续

- SC1 改造：把 `src/srm_connector` 与 `src/audit_log.py` 切换为 import 本包（消除跨工程引用）。
- 9月：`audit` 启用 ClickHouseSink，灰度双写校验后切换。
- `data_isolation_layer/rag` 接 Chroma，承载 Q1/Q6/R1 知识库。
