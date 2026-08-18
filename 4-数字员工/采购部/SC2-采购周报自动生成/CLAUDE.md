# CLAUDE.md — SC2 采购周报自动生成（场景级记忆）

> 场景级上下文（Hermes L2）。开工先读本文件恢复上下文；全项目规则见根 `CLAUDE.md`，需求收敛过程见同目录 `需求grill产出-2026-08-18.md`，技术决策见 `openspec/changes/archive/*sc2-weekly-report-mvp/design.md`。

## 一、定位

**采购周报自动生成**，采购域 L3 场景（AI 生成 → **人工确认发布**）。替代采购经理手动汇总（全景规划 L228-242：3 人天/月、口径不统一），目标 **3 人天/月 → 0.5 人天/月**。

- **读者**：采购部群 + 采购部 AI 专员姚祖怡（**首版不推管理层**，D8）。
- **窗口**：本周 W ＋ 上周 W-1 ＋ 四周前同期周 W-4（D16-R）。
- **档位**：**档 2（真实数据跑通）**。不承诺档 3——周活跃埋点统计全项目未启用。

## 二、关键决策（只列会影响后来人动手的）

| # | 决策 | 一句话理由 |
|---|---|---|
| **D15-R** | **ERP 单源双端点**：订单侧 `ZpViewPurOrder/Query`、收货侧 `GR/Query`。**SRM 不参与** | 🔴 SRM 供应计划看板返回 `300234: 不允许查询当前时间 7 天之前的数据`，「上周」「四周前」两个历史窗口**结构性取不到**。原 D15 判 ERP 给不出收货日期是**读封装没读端点**——`get_gr_lines(doc_no)` 是封装的形状，端点本身支持整表分页且每行带 `BusinessDate` |
| **D16-R** | 「上月环比」＝ W-4 同期周，非上月整月 | 三窗口同为「一个自然周」，量纲可直接比较；整月须除以周数换算，多引入一层要问专员的口径 |
| **D17** | 在途/未清一律按 `LineStatus` 剔除已关闭行（3 自然/4 短缺/5 超额），**不用数量启发式** | 短缺关闭行收货量常年小于订单量，纯数量判据会永久误判为在途（继承 SC8 队列 #173） |
| **D18** | 七层分层 `sources/windows/metrics/report/review/webapp/notify` | 唯一会被判例包反复改的是 `metrics.py`（O-1/O-4 都在它上面）；做成纯函数使「改一次口径 ＝ 改一个函数 + 一组单测」 |
| **D21** | 页面**快照优先**，全量重算走独立的 `POST /api/refresh` | 一次全量真实取数实测 **2 分 19 秒**，挂在 HTTP 请求上用户会以为服务挂了 |

## 三、依赖的平台底座

- `shared_tools/erp_connector`：`get_purchase_orders` / `get_purchase_line_status` / **`get_receipt_lines`（本场景新增）**
- `shared_tools/simple_gate.install_flask_gate`、`shared_tools/access_log.install_flask_access_log`
- `shared_tools/notifiers/wecom`、`audit`（`AuditLogger.jsonl`）、`connector_audit.ConnectorAudit`

**本场景对底座做过的改动（均为纯新增、零行为变更，平台回归 295 passed 零失败为证）**：
1. `models.ReceiptLine`（新 dataclass）
2. `ZpConnector.get_receipt_lines(days)`（`GR/Query` 整表分页 + 客户端按日期过滤 + 4 小时磁盘缓存）
3. `models.PurchaseOrder` 新增 4 个**带缺省值**的可选字段：`make_date` / `unit_price` / `supplier_name` / `buyer`

> ⚠️ 改动 3 有一个**已实测的坑**：`get_purchase_orders` 有 4 小时磁盘缓存，**旧缓存不含新字段**，反序列化后取到缺省值（金额显示 0、采购员显示 0 人）。改字段后须清 `shared_tools/erp_connector/cache/po_cache.json` 再验。这同时也证明了旧缓存向后兼容。

## 四、红线与已知缺口

**红线核对**：mock 先行 ✅（同包内先 mock 后真实）｜ audit 留痕 ✅（周报确认写 `AuditLogger`，连接器访问写 `ConnectorAudit`）｜ **OEM 隔离不适用**（采购 SRM/ERP 供应商数据不走 `data_isolation_layer`，根 CLAUDE.md §4 边界）｜ **L2 门禁不触发**（内部报表、不对客、不自动执行采购动作；L3 由「确认发布」按钮承载）｜ ISO 26262 不适用。

**🔴 三条端点级坑（实测，2026-08-18）**：

1. **`ZpViewPurOrder/Query` 与 `GR/Query` 的服务端过滤一律不可信**。F14 对照测试实证：参数名拼错时**静默返回全表**；`GR/Query` 对 `startDate`/`endDate`/`businessDate`/`beginDate` 四种写法返回的 `Total` 与无过滤基线**完全相同**（27,785），与故意拼错的参数名也相同。⇒ **一律整表取回后在客户端按业务字段过滤**。
2. **`GR/Query` 分页服务端硬顶 500/页**（传 1000/5000 均只返回 500）。
3. **`ZpViewPurOrder` 没有任何交期字段**：`deliveryDate`/`DeliveryDate`/`expectDate`/`planDate`/`demandDate`/`arrivalDate` 六个候选名在 28,274 行中**全部 0 命中** ⇒ 底座的 `expected_date` 与 `supplier_confirmed_date` 实际恒等于制单日。

**已知缺口（首版明确不做，非遗漏）**：

- 🔴 **收货准时率（O-6）**——承接坑 3：没有承诺交期就没有基准。以制单日充当承诺交期算出的准时率恒为「几乎全部逾期」，**那是一个看起来像指标的假数**，按 spec「不可算不呈现」撤下。可能来源＝SRM `get_confirmed_dates`（按单查、仅覆盖已答交的单、是否受 SRM 历史限制影响未验），留待下一轮。**这是首版最大的能力缺口。**
- **工时 / 完工日（O-5，已结）**——三个端点字段全查无工时字段，`CommonEntity/Query` 外网仍 404。
- **质检、物流**——MES/LAN（Q7 排期 2027-05）与 O3（2026-12）。
- **自然语言查询、推送管理层**——二期（D3/D8）。
- **指标口径与异常阈值（O-1/O-4）**——待姚祖怡判例批改。首版**指标从宽全放**、阈值取默认值并全程标「未经确认」；**阈值属判据类，永不因超时自动生效**（IATF 显式签认）。
- **采购部知识资产 backup 未指派**（design 审 ①(a)：只登记缺口、不自行指派）。

## 五、时间线与部署状态

- 2026-08-18 需求 grill（5 轮 14 问，前沿已空）→ 同日 openspec propose ＋ design 审通过 → 同日 apply，档 2 达成。
- **部署：尚未部署 `.51`**（tasks 9.5 未完成）。

### 🔴 过渡期端口豁免（须在此留痕，不得默默占用）

- **豁免内容**：本场景过渡期以自有 Flask 进程对外服务，端口 **8095**，构成对根 `CLAUDE.md` §5「**新场景一律不新起端口对外**」这条硬约束的**显式豁免**。
- **理由**：统一门户路由中间件零代码（决策件写了目标态、地基线未产出），SC2 不等网关（design D9）——不拿场景交付去赌地基工期。
- **批准来源**：Shao Peishen，见 `需求grill产出-2026-08-18.md` D9；端口号 8095 由其 2026-08-18 design 审 ④(a) 定。
- **注销条件**：统一门户网关落地后，SC2 收编进 `/procurement/sc2` 路由，本豁免随之注销。**路由前缀自首版即已是目标态，收编时只改映射、不改场景代码。**
- **部署时须补防火墙入站规则**——只在 `.51` 本机冒烟 200 是假象，外部会超时（根 CLAUDE.md 坑 5）。

## 六、怎么跑

```bash
python run_sc2.py report --mode mock --base 2026-08-19    # mock 出一期周报
python run_sc2.py report --mode real --max-status-materials 0   # 真实全量（约 2m20s）
python run_sc2.py probe                                    # F14 端点参数名对照取证
python run_sc2.py serve --mode real --port 8095            # 起服务
python -m pytest -v                                        # 113 passed
```

- 凭据从最近的 `.env` 自动读入（向上逐级查找，同 SC8 `run_baoguan_web.py`）；**凭据只在 `.env`，不入库、不打印**。
- `--max-status-materials` 是 D17 的已知代价开关：行级状态按料号逐个查，窗口内料号实测 812 个 ⇒ 全量约 2 分钟。**触发截断时会在周报取数说明里显式写出来**（No silent caps）。
- **所有生成物落 `reports/`**（已被 `.gitignore` 的 `**/reports/` 覆盖，`git check-ignore -v` 实测命中）。
