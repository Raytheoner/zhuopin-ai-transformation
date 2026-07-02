## Why

supplychain 的 `kit_analysis.py` 已在真实 BOM/库存/在途数据上验证过齐套算法，精度达标，但仍孤立在单体试验田里。运营部 O2（物料齐套预警）需要这份能力作为数字员工的核心引擎——收割并挂载到全景，消除跨工程引用，统一走平台底座的 models / audit 契约。

## What Changes

- **新建场景目录** `4-数字员工/运营部/O2-物料齐套预警/`，含独立 Python 包 `o2_kit_shortage`
- **收割齐套引擎**：`explode_bom` + `calc_shortage` 原样迁移，仅将 `from src.data_loader import ...` 改为 `from zhuopin_platform.shared_tools.models import ...`（底座已有完全匹配的四个 dataclass，IATF 单一可信源）
- **审计接入**：齐套决策（触发产品/缺口物料/缺口量/运行时间）写 `zhuopin_platform.audit`（append-only JSONL，与 P2 hash-chain 配套）
- **mock 数据验证**：两个成品 × 三层 BOM 的脱敏夹具，结果与手工对照偏差 < 1%
- 不连真实库（BOM/库存/在途真实接入是后续任务）

## Capabilities

### New Capabilities

- `kit-shortage-engine`：BOM 递归展开引擎（`explode_bom`）+ 缺口计算（`calc_shortage`），直接复用底座 models，审计可追溯
- `o2-kit-shortage-alert`：数字员工入口——加载 mock 数据、调用引擎、写审计、返回结构化缺料预警报告

### Modified Capabilities

（无，本次新增场景，不改已有 spec 的需求）

## Impact

- `4-数字员工/运营部/O2-物料齐套预警/`（新建，含 pyproject.toml / o2_kit_shortage/ / tests/）
- `zhuopin_platform`：只读依赖（models / audit），不修改平台代码
- `supplychain/src/agents/kit_analysis.py`：只读收割源，不改动
