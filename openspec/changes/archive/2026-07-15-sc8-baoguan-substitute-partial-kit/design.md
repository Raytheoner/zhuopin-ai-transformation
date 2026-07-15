## Context

保供看板（`sc8/baoguan.py`）当前把 BOM 里的每个子件当独立物料计缺口，不识别替代料关系；也只输出"齐/不齐"二元判定，无法体现"能先出一部分套数"。姚祖怡口径定稿（`1-转型规划/保供看板v2-口径定稿.md` §2）已明确 C-1（替代料等价合并）与 C-2（部分齐套显示）两条业务规则，字段取数侧（`m_sequence`/`m_componentType`）已由 CC 做过一次生产只读探测验证（15 母件/1324 子件行/56 组替代料，见口径定稿 §2 C-1·①）。

**已知但未验证的部分**：口径定稿的探测只确认了"替代料嵌套在 `m_bOMCompSubstituteDTO4CreateSv` 列表里、且与主件行共享 `m_sequence`"这一结构事实，**没有记录替代料自身的用量（`m_usageQty`）/损耗率（`m_scrap`）/物料主数据（`m_itemMaster`）字段是否与主件行同名同构**——这是本设计遗留的一个开放问题（见 Open Questions），需要在 apply 阶段先做一次针对性字段验证（沿用 C-1 字段验证的既有做法），而不是假设结构一致就直接编码。

## Goals / Non-Goals

**Goals:**
- 替代料关系从 BOM 数据中正确提取，参与齐套判定，消除"替代料现货够、主料仍判缺料"的误判。
- 部分齐套套数正确计算并在看板显示，让姚祖怡看到"卡在哪、还差多少"而不只是红绿二元结果。
- 新增字段/逻辑对现有 O2/SC7/SC8 既有行为零漂移（纯附加，缺省不触发）。

**Non-Goals:**
- 不改变现有四色（🔴/🟠/🟡/🟢）判定规则本身，也不改 `kit_date`/`gap_days`/`risk`/`confirmed_gap_days` 的既有语义。
- 不做"组内现货被多个成品行/产品共享时的双计扣减"这类跨产品净额分配机制——本次在单次 `build_dashboard` 调用内按现状"各成品行独立算"的既有假设处理（与现状 `_covered_by_stock`/净额快照口径一致，不新增跨行状态）。
- 不把替代料合并/部分齐套逻辑做成 O2/SC7 可复用的平台通用能力——两者当前 BOM 数据源（mock CSV）不带这些字段，暂无第二消费方，避免过度设计（YAGNI）。
- 不改 `SC8_NET_INVENTORY` 净额开关行为，也不改多层 BOM 展开（B1）逻辑。

## Decisions

### D1：BomRow 新增字段的设计

**决策：在 `BomRow` 追加两个默认值字段，`sequence: str = ""`、`is_substitute: bool = False`。**

```python
@dataclass
class BomRow:
    product_id: str
    component_id: str
    component_name: str
    level: int
    qty_per_unit: float
    loss_rate: float
    unit: str
    sequence: str = ""          # 新增：BOM 项次（m_sequence），同项次的行互为主料/替代料候选
    is_substitute: bool = False  # 新增：True=替代料（m_componentType==2）；False=主料/常规子件
```

- 备选 A（推荐）：如上，两个通用字段直接挂 `BomRow`，`sequence` 用字符串（与 U9C 原始 `m_sequence` 类型一致，不做整数转换避免非数字项次格式踩坑）。
- 备选 B：不改 `BomRow`，另建 `SubstituteGroup`/`BomComponentGroup` 独立数据结构，`get_bom_for_products` 返回值扩展为 `(rows, failed_ids, substitute_groups)` 三元组。
  - 缺点：改了 `get_bom_for_products` 返回值签名（当前是二元组 `(rows, failed_ids)`），是破坏性变更，O2/SC7/SC8 全部调用方都要跟着改；A 方案纯字段追加不改签名，向后兼容成本更低。
- 备选 C：把替代料整体拍平进 `component_id`（如 `"R01A.0061|R02A.0019"` 复合料号），不新增字段。
  - 缺点：污染 `component_id` 语义（下游库存/SRM 查询按 `component_id` 精确匹配料号，复合料号会查不到任何库存/承诺数据），排除。

**推荐 A**：不破坏现有二元组签名、字段语义清晰、`sequence`+`is_substitute` 组合足以支持"按 (product_id, sequence) 分组、组内 is_substitute 区分主替"的全部下游逻辑。

### D2：连接器如何提取替代料行

**决策：`get_bom_for_products` 遍历 `m_bOMComponents` 时，对每条主件行先构造其自身 `BomRow`（`sequence=m_sequence`, `is_substitute=False`），再遍历其 `m_bOMCompSubstituteDTO4CreateSv` 列表，为每条替代料构造对等的 `BomRow`（`sequence` 与主件行相同，`is_substitute=True`）。**

替代料的 `component_id`/`component_name` 从其自身 `m_itemMaster` 取（假定替代料 DTO 也带 `m_itemMaster` 子对象，与主件行结构一致——这是需要真实验证的假设，见 Open Questions）。`qty_per_unit`/`loss_rate`/`unit`：**推荐直接复用主件行的值**（同一"料位"通常同用量/同损耗率，替代料是"用等量的另一种料顶上"，而非独立配方）；若真实数据验证发现替代料 DTO 自带独立的 `m_usageQty`/`m_scrap`，则改为优先取替代料自身字段、缺失时才回退主件行值。

- 备选：替代料完全不继承主件字段，缺字段就跳过该替代料（不计入分组）。
  - 缺点：如果替代料 DTO 真的没有独立用量字段（大概率，因为它是"替代同一物料需求"而非"新增一条 BOM 行"），这会导致替代料现货永远不参与合计，C-1 直接失效。
- 推荐做法更保守（宁可假设继承主件用量，也不因为缺字段直接放弃整条替代料），但**明确标注为 apply 阶段验证项**。

### D3：等价合并逻辑放在哪一层

**决策：合并/分组逻辑放在 `sc8/baoguan.py`（场景层），不下沉平台 `kit_engine.py`。**

- 备选：做成 `kit_engine.py` 里的通用纯函数（如 `merge_substitute_materials(bom, gross_need) -> dict`），供 O2/SC7 未来复用。
  - 理由不采用：O2/SC7 当前 BOM 数据源（mock CSV）不含 `sequence`/`is_substitute` 字段，没有真实第二消费方；"等价合并、不分主次"是姚祖怡对 SC8 保供场景的业务判断，不代表 O2/SC7 的缺料判定也该采用同一规则（例如 O2 产线齐套可能有"必须用主料、替代料要额外走审批"这类不同约束，未验证不应假设通用）。按项目"三条相似代码好过一个过早抽象"的一贯做法，本次只在 SC8 落地，真正出现第二消费方时再上提。

**实现要点**：在 `_gross_need`（已按 `explode_bom` 展开到叶子件）之后、`_covered_by_stock`/`assess_supply_risk` 判定齐套之前，新增一步"按 (product_id, sequence) 分组"：同组内若存在 `is_substitute=True` 的行，则该组毛需求只计一次（沿用现有叶子件展开结果里主料的毛需求数值，忽略被展开逻辑当作独立叶子件计算出的替代料"毛需求"——替代料本身不产生独立毛需求，它只提供现货），可用现货取组内主料现货+全部替代料现货之和。

### D4：BaoguanRow 新增字段设计（C-1 显示 + C-2 部分齐套）

```python
@dataclass
class BaoguanRow:
    ...既有字段不变...
    # C-1：替代料合并展示（纯附加，无替代料时为空字典，零漂移）
    substitute_groups: dict[str, list[str]] = field(default_factory=dict)
    # {主料料号: [替代料料号, ...]}，供看板标注"含替代料 Rxx"

    # C-2：部分齐套（无 BOM 或未触发净额计算时为 None，零漂移）
    kittable_qty: int | None = None          # 可齐套套数 = min(floor(子件可用现货/单机用量))
    kittable_bottleneck: str | None = None    # 卡住可齐套数的瓶颈子件料号
    kittable_shortfall: int | None = None     # 该瓶颈子件还差多少件（凑到下一整套所需缺口）
```

- `kittable_qty` 的计算**需要子件现货数据**（`inventory` 参数），与净额开关（`SC8_NET_INVENTORY`）当前的"仅当开启时传 `inventory`"逻辑一致——**决策：C-2 复用同一 `inventory` 入参，不额外新增数据源**；即 `SC8_NET_INVENTORY=off` 时 `kittable_qty` 恒为 `None`（无现货数据、无法计算"可先齐几套"），看板对应字段显示"—"或隐藏。
  - 备选：C-2 独立于净额开关，始终尝试取现货计算部分齐套。
  - 不采用理由：净额开关是姚祖怡已走完签字流程的正式开关（跨桌任务队列 #3），C-2 若绕开它直接取现货，等于变相在未签字场景下也把现货数据接入判定路径，混淆两个治理动作的边界；且现状 `SC8_NET_INVENTORY` 已翻 ON（2026-07-14），两者实际不冲突，只是逻辑上明确耦合关系更清晰、更符合"现货相关能力统一挂同一治理开关"的既有惯例。

### D5：看板显示文案位置

`sc8/webapp.py`（`row_to_dict`/`render_html`/`_HTML_JS`）新增：卡片增加"可齐套 {kittable_qty} / {qty}"徽标（`kittable_qty is None` 时不显示该徽标，向后兼容旧数据）；瓶颈行文案追加"，还差 {kittable_shortfall} 件（{kittable_bottleneck}）"；含替代料的子件在瓶颈/覆盖信息里追加"含替代料 Rxx"后缀（据 `substitute_groups` 查主料对应的替代料列表）。四色徽标本身不变。

## Risks / Trade-offs

- **[风险] 替代料 DTO 字段结构假设（D2）未经真实验证** → **缓解**：tasks.md 第一项设为"真实数据字段验证"（复用 C-1 已有验证方法论），验证通过才继续编码；若替代料 DTO 结构与假设不符，回 CC 与 IT 核对后再排期，不无条件按假设硬编码。
- **[风险] 组内现货被多个成品行共享导致双计（Non-Goal 声明的已知限制）** → **缓解**：不在本次解决，但需在验收报告/看板文案里显式说明"部分齐套套数为单成品行独立计算，未扣减同批次其他成品行对同一现货的占用"，避免姚祖怡误读为"绝对可发货数量"。
- **[风险] `kittable_qty`/`substitute_groups` 计算依赖 `inventory` 参数，而调用方（`build_dashboard`）目前只在净额开关 ON 时传入** → **缓解**：D4 已明确耦合关系并写入设计，非本次疏漏；`webapp.py` 显示层需对 `None` 值做好文案兜底（"—"而非报错或误显示为 0）。
- **[Trade-off] 等价合并放场景层而非平台层（D3）** → 若未来 O2/SC7 也需要替代料合并，届时需要一次"从 SC8 提升到平台"的重构；当前判断代价可接受（无第二消费方时过早抽象的维护成本更高）。

## Open Questions

1. ~~替代料 DTO（`m_bOMCompSubstituteDTO4CreateSv` 内的每个元素）是否自带独立的 `m_usageQty`/`m_scrap`/`m_itemMaster` 字段，还是完全继承主件行？~~ **✅ 已验证（见下方 2026-07-15 补充）**。
2. `m_sequence` 是否保证在同一父件下"同序号=同料位"这一映射稳定（有没有理论上序号重复但语义不同的边界情况）？—— 探测样本（1324 子件行）未发现异常，本次按"稳定"假设推进，若验证阶段发现反例需回 Paul/姚祖怡确认口径。**2026-07-15 补充验证**（7 母件/20 组替代料）：未发现反例，`m_sequence` 映射稳定；同时确认 `m_subSeq` 恒为 0（20 组均为单替代料，未见一组多替代场景，与口径定稿 §2 C-1·① 07-08 那次探测结论一致）。
3. C-2 "还差 N 件"（`kittable_shortfall`）的计算口径——是"凑够 `kittable_qty+1` 套还需要的量"，还是"凑够客户下单总量 `qty` 还需要的量"？两者数值不同（后者通常大得多）。**推荐前者**（更贴近"下一步能不能多齐一套"的现场决策），但这是产品/显示层判断，建议 apply 前与姚祖怡确认一句话（可并入姚祖怡后续的显示层抽验，不必单独开会）。**未验证**——仍需姚祖怡确认，见 2026-07-15 补充。

## 2026-07-15 补充：真实数据验证结论（Open Question #1 已解，附代码修正）

**验证方法**：CC 在有 LAN+U9C 凭证访问的环境下，对 7 个真实母件（S02Y.0035/S02Y.0162/S04Y.0112/S07Y.0137/S02Y.0188/F02N.0040/F02N.0226）跑只读 `BOM/Query`，共取得 20 组含替代料的真实料位，逐组核对替代料 DTO 的完整字段内容（`m_itemMaster`/`m_usageQty`/`m_scrap`/`m_sequence`/`m_subSeq`/`m_componentType`/`m_issueUOM`）。只读探测，未写任何 ERP 数据，诊断脚本为一次性使用未入库（同 07-08 那次的做法）。

**结论（关键，纠正了本设计原假设）**：
- 替代料 DTO **确实自带独立的** `m_itemMaster`/`m_usageQty`/`m_scrap`/`m_sequence`/`m_subSeq`/`m_componentType`/`m_issueUOM` 字段（不是"完全继承主件行、没有自己的字段"）。
- 但 **`m_usageQty` 在全部 20 组样本中恒为 `1.0`**，与其所属主件行的真实用量（样本中出现 1/2/3/4/9/10/16 等多种值）**完全无关**——这是 ERP 侧的占位值，不携带真实的替代用量语义（`m_scrap` 同样恒为 0.0，与主件行样本一致，未观察到有区分意义）。
- **因此本设计 D2 的原假设"替代料自带用量则优先用自己的，没有则继承主件行"是错的**——正确做法是**恒继承主件行的 `qty_per_unit`/`loss_rate`，完全忽略替代料自身的 `m_usageQty`/`m_scrap`**，否则会把替代料的展开用量算成"占位 1"，在主件行真实用量 >1 的绝大多数场景下严重低估该料位的真实需求（进而在 C-1 判齐逻辑里得出"现货够"的错误结论）。

**已按此结论修正代码**（`5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py::get_bom_for_products`）：替代料行的 `qty_per_unit`/`loss_rate` 改为无条件取自其所属主件行，不再读取/采信替代料自身的 `m_usageQty`/`m_scrap`。同步更新了 `tests/test_bom_substitute_extraction.py`（原 `test_substitute_with_own_usage_prefers_its_own_value` 改为 `test_substitute_own_usage_ignored_inherits_main_row`，断言方向反转）与 `openspec/specs/platform-data-connectors/spec.md` 的对应 Requirement 描述。全量回归零漂移（平台193+1skip/SC8 188+3skip/O2 20/SC7 41黄金基准精确不漂移/SC1 53）。

**未验证（仍待 Paul/姚祖怡，见跨桌任务队列 `#33`）**：② 姚祖怡真实数据抽验（本次探测拿到的 20 组真实替代料样本可直接作为她抽验素材，不必重新找样本）；③ `kittable_shortfall` 口径一句话确认。
