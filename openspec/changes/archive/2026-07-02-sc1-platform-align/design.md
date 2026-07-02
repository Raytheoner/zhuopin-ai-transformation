# Design: SC1 平台对齐收尾

## Context

SC1 MVP 已完成、openspec 归档，但仍有两处跨工程/重复：
1. `src/audit_log.py`：自造 AuditLogger，不带 hash-chain，不可 verify_chain
2. `src/data_providers.py`：SRMProvider 通过 `sys.path` hack 引用 supplychain

§1 平台加固（P2）已合入 master：audit hash-chain、Pydantic 边界校验、SRM 令牌桶限流。本次做最后一步对齐，不改业务逻辑。

## Goals / Non-Goals

**Goals**
- 删除本地 AuditLogger 主体，改接平台（白嫖 hash-chain）
- 删除 sys.path 黑魔法，SRMProvider 改 import 底座 connector
- 行为等价：评分/报告/审计逻辑不变，原有测试不退化
- task 9.1（真实 SRM 接入）明确 BLOCKED，不在本 PR

**Non-Goals**
- 重构评分引擎或报告逻辑
- 连接真实 SRM/ERP
- 优化 main.py 交互流

---

## ⚡ 架构决策 D1（需 Paul 拍板）：SRM 接入方式

| | 选项 | 说明 |
|---|------|------|
| **A（推荐）** | `SRMProvider._get_connector()` 内部换 import 路径，保留 DataProvider/ManualProvider/get_delivery_data 接口全部不变 | 外科手术式：只动一个方法，main.py 和上层代码零修改 |
| B | 删除 `SRMProvider`，直接用底座 `XkySrmConnector`，DataProvider 抽象层也删掉 | 更干净，但要同时改 main.py 的调用侧；ManualProvider 回退逻辑也要重写 |

**我推荐 A**：

1. SC1 的 `DataProvider(ABC)` 是有意为之的扩展点——`ERPProvider` 未来也会实现这个接口，删掉会破坏这个设计
2. `ManualProvider` 和 `get_delivery_data()` 离线回退逻辑，是 mock 跑通的核心；保留比删除安全
3. A 的改动量：`_get_connector()` 内部 3 行 → `from zhuopin_platform...import XkySrmConnector`；B 至少改 main.py + 重写回退逻辑
4. 外科手术式红线：只动必要处

**→ 请 Paul 确认 A，或选 B 并说明是否同意删掉 DataProvider 抽象层。**

---

## Decisions（其余，确认后生效）

**D2：审计适配层 SC1AuditAdapter（薄包装，不是完全删除）**

```python
# src/audit_log.py — 保留文件，内容替换
from zhuopin_platform.audit import AuditLogger, AuditEvent
from zhuopin_platform.audit.sinks import JsonlSink, ChainVerifyResult

class SC1AuditAdapter:
    def __init__(self, log_path: Path):
        self._platform = AuditLogger(JsonlSink(log_path))

    def append_record(self, evaluator, supplier_name, supplier_code,
                      result, delivery_source, ai_text_hash,
                      report_path="", error="") -> None:
        self._platform.record(AuditEvent(
            scenario="SC1",
            action="supplier_risk_eval",
            evaluator=evaluator,
            automation_level="L2",
            decision={
                "supplier_name": supplier_name,
                "supplier_code": supplier_code,
                "risk_level": result.risk_level,
                "composite_score": result.composite_score,
                "scores": {k: v.value for k, v in ...},
                "weights": result.weights,
                "data_sources": {...},
                "report_path": report_path or "FAILED",
            },
            content_hash=ai_text_hash,
            error=error,
        ))

    def verify_chain(self) -> ChainVerifyResult:
        return self._platform.verify_chain()

    def query_by_supplier(self, supplier_name: str) -> list[dict]:
        records = self._platform.query_by(supplier_name=supplier_name)
        # 映射回旧格式摘要（向后兼容）
        return [{"timestamp": r["timestamp"], "risk_level": r["decision"]["risk_level"], ...} for r in records]

    def verify_integrity(self) -> dict:
        return self._platform.verify_integrity()
```

`main.py` 的 `AuditLogger` import 改为 `SC1AuditAdapter`，调用侧代码不变。

**D3：测试更新策略**

- `test_scoring.py`：**不改**（无审计/SRM 依赖，天然等价）
- `test_audit_log.py`：**更新断言**适配平台 JSON 格式（`record["decision"]["supplier_name"]` 等）；保留红数据保护测试；新增 `verify_chain()` 通过测试
- 新增 `tests/test_srm_platform.py`：mock SRMProvider 接口等价、跨工程 import 无残留

**D4：pyproject.toml + 保留 requirements.txt**

新建 `pyproject.toml`（`zhuopin_platform` 依赖 + pip install -e），`requirements.txt` 保留 openai/requests/python-dotenv（第三方）。

## Risks / Trade-offs

- [SC1AuditAdapter 旧 JSON 格式与新格式不同] → 主动更新 test_audit_log.py 断言；main.py 不变
- [verify_integrity() 旧实现有 invalid_lines 统计，平台实现无此字段] → SC1AuditAdapter.verify_integrity() 代理平台 + 补齐必要字段（保持兼容）
- [task 9.1 真实 SRM] → BLOCKED，mock 跑通即可，env 变量不配置时 SRMProvider 抛 RuntimeError，由 get_delivery_data 回退

## Migration Plan

1. `git checkout -b feat/sc1-platform-align`
2. 先写/更新测试（test_audit_log 更新 + test_srm_platform 新建）
3. 实现 SC1AuditAdapter（audit_log.py 重写）
4. 实现 SRMProvider 改 import（data_providers.py 手术）
5. 更新 main.py import（AuditLogger → SC1AuditAdapter）
6. 全绿 → openspec archive → git commit + push

## Open Questions

1. **D1 架构决策**（等 Paul 确认 A 或 B）
