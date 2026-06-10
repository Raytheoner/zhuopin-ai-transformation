# SC8 · 客户订单交期智能承诺（收割式 MVP）

把"成品交付预期"算出来、经 L2 人工门禁推给客户（比亚迪/上汽/理想）。复用 supplychain
已真实验证的交付日预测引擎（收割进本工程），补门禁文档要求的 **置信度** 与 **启发式补全**，
接平台底座的 **连接器/通知器/L2 门禁/审计**。

> ⚠️ **上线红线**：未过《SC8 上线前置门禁》6 项检查表前，**只出草稿/内部看板，绝不对真实客户自动外发**。
> 本批为 mock 端到端 + 黄金基准框架 + L2 门禁代码生效；真实切换见下文「6/12 切真实」。

---

## 1. 安装与运行

```bash
# 1) 可编辑安装平台底座（一份代码处处复用）
pip install -e ../../../5-平台底座/zhuopin_platform --no-deps
# 2) 可编辑安装本工程
pip install -e . --no-deps
# 3) 跑测试（全 mock，无真实网络调用）
pytest -q
```

预期：**20 passed**。覆盖确定性零偏差、置信度、L2 门禁 fail-closed、幂等、全链审计。

## 2. 工程结构（design D6）

| 模块 | 职责 |
|------|------|
| `config.py` | 可配启发式参数（D2）+ 委外识别（D3） |
| `models.py` | SalesOrder/ForecastOrder（收割）+ DeliveryForecast（扩展置信度/参数版本/瓶颈物料） |
| `loaders.py` | SO/FO 加载（本批只接 mock CSV 夹具） |
| `intake.py` | 订单聚合（同料号合并、交期取最早） |
| `scheduling.py` | SMT 完工（齐料日 + 工时） |
| `forecast.py` | **核心增量**：物料到货估算（关键路径）+ 置信度 + 启发式 |
| `pipeline.py` | `compute_forecasts` 编排 + 预测审计 |
| `gate.py` | L2 门禁判定（低置信/首次承诺/晚于目标日） |
| `notify.py` | forecast→CRM 草稿适配 + 对客口径 + 更正草稿 |
| `pending_queue.py` | 文件型待审批队列（PendingApprovalSink + 幂等） |
| `commitment.py` | 对客承诺闭环编排（门禁→草稿→Notifier→队列→审批→审计） |

## 3. 两个核心增量

### 置信度（二级，design D1，与三色风险**正交**）
- **高** = 有 BOM 且全部直接子件有 SRM 承诺交期 且 非委外；
- **低** = 含任一无反馈物料 / 委外估算 / 无法排产。
- 正交澄清："有反馈但晚于目标日" = **高置信 + 🔴 红风险**（确定性高，但会延期），不折进置信度。

### 启发式（design D2，全部可配于 `config.py`）
| 常量 | 初值 | 含义 |
|------|-----:|------|
| `NO_FEEDBACK_LEAD_DAYS` | 30 | 无 SRM 承诺交期物料：需求日 +N 天（标低置信） |
| `OUTSOURCE_EXTRA_DAYS` | 10 | 委外成品：齐套日 +N 天附加工期 |
| `LOGISTICS_DAYS` | 1 | 物流天数 |
| `DEVIATION_ALERT_DAYS` | 3 | 偏差监控阈值（超此值告警/重算） |
| `PARAM_VERSION` | sc8-params-v0 | 参数版本，写入每条预测审计（可复现可追溯） |

> 改任一常量须 bump `PARAM_VERSION`。黄金基准/真实数据校准后回填初值。

## 4. 委外识别（design D3，Paul 拍板）

- **MVP 过渡口径 = 仅维护清单** `OUTSOURCE_PRODUCT_IDS`（运营维护，最准、不误判）。
  料号前缀 `OUTSOURCE_PREFIXES` **默认关闭**（卓品无可靠前缀约定）。
- **真实权威口径 = U9C 工艺路线 `Operations[].IsSubContract`**（任一工序为 true → 成品委外）。
  接口缝 `is_outsourced_by_routing()` 已留；6/12 接 U9C 后内部切换、调用方不变。

**维护清单怎么填**：编辑 `sc8/config.py` 的 `OUTSOURCE_PRODUCT_IDS`，加入委外成品料号，如：
```python
OUTSOURCE_PRODUCT_IDS = {"X05A.0001", "F03N.0099"}
```

## 5. L2 对客门禁（fail-closed，合规红线）

强制人工确认、不自动外发的情形（任一命中 → 拦入待审批队列）：
- 低置信 / 关键路径物料无反馈 / 预期交付晚于客户目标日 / 首次给某客户做交付承诺。

放行：责任人 `FilePendingQueue.approve(item_id, confirmed_by)` → 外发 + 原子标记 `'sent'`。
**幂等**：重复 approve 只外发一次（绝不重复推客户）。缺 `requires_confirmation` 字段 →
平台 Notifier fail-closed 默认拦截。

## 6. 黄金基准（门禁文档 §2）

- `data/golden/`：mock 样本（覆盖有反馈/无反馈/含委外三类）+ `golden_expected.md` 人工核对基准。
- 确定性逻辑（关键路径、日期加减）对基准**零偏差**；置信度标注正确。
- 6/12 真实订单（5–10 张）到位后，按 `golden_expected.md` 格式回填替换 mock 样本。

## 7. 6/12 切真实（任务 N.1，本批不做）

1. 平台连接器切真实：`ZpConnector`（U9C ERP BOM）+ `XkySrmConnector`（携客云 SRM 承诺交期）。
2. 委外识别切 U9C 工艺路线 `IsSubContract`（实现 `is_outsourced_by_routing` 喂入路径）。
3. 跑黄金基准：确定性偏差 = 0。
4. CRM 先推**内部企微通道**验证，再切真实客户。
5. 过《SC8 上线前置门禁》6 项检查表（黄金基准/回滚SOP/L2代码生效/偏差监控/全链审计/内部通道验证）。
6. 全部勾选 → 才允许对真实客户自动外发。

---
**依赖**：`zhuopin_platform`（平台底座，只消费不改契约）。
**合规**：所有 AI 决策写平台 `audit`（append-only）；推客户 L2 人工确认；先 mock 后真实。
