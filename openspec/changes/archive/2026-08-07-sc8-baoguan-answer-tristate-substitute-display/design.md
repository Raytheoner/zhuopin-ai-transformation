# sc8-baoguan-answer-tristate-substitute-display Design

## 开工前三问自答（opener §七，均按默认执行，0 问直接干）

- **Q1 同车/串行** → 按默认 (a) 同车一个变更包：#296/#297 均触碰
  `_component_supply_status`，"整体复核一遍"与黄金基准重跑本就只需跑一次，拆开
  反而要重复跑两遍且第二个必然 rebase 第一个。
- **Q2 365 天止步点** → 按默认 (a) 先实测：见 D3，已测得真实成本，判定可接受，
  不预设阈值、不升级 §四。
- **Q3 复核落点** → 按默认 (a)：`docs/queue_296_material_commitment_tristate_audit.md`
  ＋ `docs/queue_297_substitute_display_audit.md`，均入库，不落 `reports/`
  （#267 教训：gitignored 目录在 worktree 清理时真实丢过一次）。

## D1：三态判据的真实字段映射（2026-08-07，生产凭据只读实测）

姚祖怡给出的 SRM 单据状态三态——「差异已确认」「无差异」「待答交」——**在
`get_receive_board()` 原始响应里没有对应的独立字段**。真实穷举 763 条 record／
1302 条 `itemList` 条目的全部字段（`rec_keys`/`item_keys`/`poline_keys` 三层
逐一 union），确认字段集合为：

```
record: innerVendorCode/innerVendorName/itemList/prodFeature/productCode/
        productFeature/profitCenterCode/profitCenterName/receiveAddressCode/
        receiveAddressName/receiveType
item:   answerQty/boardDate/cancelFlag/deliveriedQty/deliveryList/detailList/
        planQty/poLineList/receiveList/receivedQty/scheduleBatch/
        scheduleCreateName/scheduleCreateTime/schedulePlanType/
        schedulePublishName/schedulePublishTime
```

没有 `diffStatus`/`confirmStatus`/`documentStatus` 一类字段。三态只能由
`answerQty`（供应商回复数量）与 `planQty`（我方计划数量）两个数字字段的关系
派生——这与她原话完全吻合，不是我方臆造：

| 她的判据 | 字段条件 | 展示要求 |
|---|---|---|
| 待答交 | `answerQty is None` | 答交数量/日期显示"无" |
| 差异已确认 | `answerQty is not None` 且 `answerQty != planQty`（含 `0`） | 显示实际数字 |
| 无差异 | `answerQty is not None` 且 `answerQty == planQty` | 显示实际数字 |

对我方⑦⑧展示逻辑而言，「差异已确认」与「无差异」**没有区别**——两者都要显示
`answerQty` 实际值——真正的分野只在 `answerQty is None` 这一条件上。

**真实数据交叉验证**（当前 365 天窗口内实测）：`answerQty is None` 的 item 共
223 个（真·待答交）；`answerQty == 0` 的 item 共 669 个（已答交、答复为 0——此前
被误判为"无"的那一类，样例 `R01A.1022`：`planQty=5000.0, answerQty=0.0`，即
"计划要 5000，供应商确认答不了"，属于"差异已确认"，必须显示 `0`，不能显示"无"）。

## D2：两处代码修正（范围精确限定，不动既有判定红线）

### D2a：`sources._extract_board_commitments`——None/0 混淆根治

```python
# 现状（bug）：
answer_qty = int(item.get("answerQty") or 0)
if answer_qty <= 0:
    continue

# 改为：
raw_aq = item.get("answerQty")
if raw_aq is None:
    continue          # 待答交：无记录，上游如实显示"无"
answer_qty = float(raw_aq)  # 含 0——0 是合法的"已答交"值，不再跳过
```

范围仍**仅限本函数**（驱动 `load_material_commitments`→⑦⑧答交展示与 B2 周期
匹配），不影响 `_extract_board_po_map`/`load_srm_deliveries` 驱动的既有
kit_date/gap_days/四色风险判定口径（红线不动，同 #211 v2、#262 先例）。

### D2b：`baoguan._component_supply_status`——状态列改挂同一数据源

现状：`confirmed = m not in nf_set`（`nf_set` 来自 `mat.no_feedback_materials`，
即旧 `/purchase/answer`+看板最早日期 60 天窗口口径），与驱动⑦⑧的
`material_commitments`（`receiveType==2`口径）是两条独立管线——这正是
`R02A.0019`"答交数量/日期显示无、状态却显示已答交"的根因：两条管线各自算得
"正确"，但互相不一致。

改为：

```python
if material_commitments is not None:
    confirmed = bool(material_commitments.get(m))
else:
    confirmed = m not in nf_set   # material_commitments 整体加载失败时的降级
```

**保留旧口径作为降级兜底**——`baoguan_service.py` 现有 `try/except` 在
`load_material_commitments` 失败时把整个 `material_commitments` 置为 `None`
（fail-soft）；此时若强行用新口径会让状态列全部退化成"未答交"，比失败前更差。
`material_commitments is not None`（哪怕是空字典 `{}`，即"加载成功但这个料号
确实没有记录"）才切换到新口径；仅当**整体加载失败**（`None`）才退回旧信号。
`nf_set`/`mat.no_feedback_materials` 因此保留，不删除。

## D3：365 天窗口真实成本（实测，非估算）

```python
>>> _chunk_date_windows(today, today+180)
3 段
>>> _chunk_date_windows(today, today+365)
6 段   # opener 估算"约7段"，实测 6 段
```

`/receiveBoard/queryList.json` 的进程级令牌桶（`XkySrmConnector._buckets`，按
endpoint 路径隔离、跨该 connector 全部实例共享，`1 token/30s`）同时被
`load_srm_deliveries`（每次快照重算固定发 1 次）与本函数（3→6 次）共用。
365 天窗口比 180 天窗口**多 3 次顺序调用**，最坏情形（桶初始为空）每次多等
~30s，合计约 **多等 90 秒**。

**判定：可接受，不升级 §四。** 依据：① 180 天口径落地时（#262）已用同一论证
"约 60 秒排队等待、与 BOM 多层递归等步骤同数量级"通过；365 天的增量（90s）与
之同一数量级，`compute_snapshot` 全量重算本身跨越 BOM 多层递归+多个真实 API
串行调用，已是分钟级别；② 分段窗口数不重叠、不重复计数的正确性已由既有
`_chunk_date_windows` 单测覆盖，扩到 6 段不引入新的正确性风险，只是线性增加
等待时间。若 apply 阶段实测出比这里估算显著更差的真实耗时（如叠加限流重试
远超 90 秒），按队列 #296 行原话"转 §四 报 Shao Peishen，不得自行改小她给的
数字"处理，不擅自把 365 改回 180。

## D4：BOM 缺口物料清单替代料并列展示（#297，纯展示追加）

### 数据模型

`ComponentSupplyStatus` 新增字段：

```python
role: str = ""   # ""=无替代关系的普通行；"primary"=有替代料的主料行；
                  # "substitute"=替代料展示行
```

### 计算位置：`_component_supply_status` 内联追加

对每条**已通过既有 `gap_qty<=0` 过滤、真正出现在缺口清单里**的主料行，查
`_substitute_groups(bom, so.item_code).get(component_id, [])`；命中时：

1. 主料行本身 `role="primary"`（无命中则 `role=""`，不动既有行为）。
2. 紧随其后为每个替代料 id 追加一条**独立计算**的展示行（`role="substitute"`），
   复用与主料完全相同的取值规则：
   - `qty_needed` = **沿用主料行已算出的 `need`**（她的模板两行 qty 相同：
     主料 800／替代料 800——不是分别按各自 BOM 用量算，因替代关系语义就是
     "同一份需求，两种满足路径"）；
   - `status`/`transit_qty`/`confirmed_date`/`confirmed_batches`：对替代料
     id 独立跑一遍 D2b 的状态判定 + D2a 修复后的答交数据（`purchase_orders`/
     `material_commitments` 两个字典本就按 `components` 全集加载、已含替代料
     id，见 `baoguan_service.py:90` 的 `components` 集合构造，无需新增数据
     加载）；
   - `available_qty`/`gap_qty`：`inventory.get(sub_id, 0)` 独立计算，**不与
     主料共享抵扣池**——她的模板证实这是独立展示（主料 avail=0/gap=800，
     替代料 avail=254/gap=546，546≠800−254 的"合并后剩余"逻辑，是各自独立
     的"需求−自身现货"）。**已有的跨料号聚合判定**（`_covered_by_stock`/
     `_kittable_qty`，#263 落地）**不受影响**——那条链路决定"这个主料行还
     算不算缺口"（已含替代料合并现货的正确聚合），本次只是把聚合背后的两个
     分量单独摊开给她看，聚合结论本身不变。

### 前端渲染

`componentStatusHtml`：`role==="primary"` 时料号后追加"（主料）"，
`role==="substitute"` 时追加"（替代料）"；`role===""` 不追加任何文案（不给
无替代关系的普通行增加视觉噪音）。8 列渲染逻辑（`answerQtyText`/
`answerDateText`/`CST_LABEL` 等）对 `role="substitute"` 行原样复用，无需
分支。

### 红线确认

本设计全程未修改 `_covered_by_stock`/`_kittable_qty`/`_gross_need`/
`_classify`/`gap_days` 任一判定函数；`ComponentSupplyStatus` 新字段带默认值
（向后兼容）；替代料展示行是**追加**到 `_component_supply_status` 返回列表
里的**额外**元素，不替换、不删除任何既有主料行。交付须含黄金基准重跑
`counts` 逐字不变的显式证明（同 #263 先例格式）。

## D5：与既有字段的关系澄清（避免实现时混淆）

- `confirmed_date`（旧 `/purchase/answer` 单一日期字段）**不受本次改动影响**，
  继续序列化供内部参考，前端不再作为展示来源（沿用 #152 既有约定）。
- `mat.no_feedback_materials`/`nf_set` **不删除**，仅退居 D2b 的降级兜底路径。
- `_extract_board_po_map`/`load_srm_deliveries`（驱动 kit_date/gap_days/四色
  判定）**本次完全不动**——第三次重申红线不因"三态判据"这个新概念而扩大
  修改范围。
