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
- 🔴 **O-7 周中生成时本周窗口不完整**（2026-08-18 部署当天发现）——首版已显式声明、未根治，详见下方「部署当天新增的两条口径修正」。
- **采购部知识资产 backup 未指派**（design 审 ①(a)：只登记缺口、不自行指派）。

## 五、时间线与部署状态

- 2026-08-18 需求 grill（5 轮 14 问，前沿已空）→ 同日 openspec propose ＋ design 审通过 → 同日 apply，档 2 达成。
- **2026-08-18 同日部署 `.51` 并冒烟通过**（tasks 9.5 完成；Shao Peishen 同日答 (a) 解除此前的 3b 推迟）。

### 部署状态（2026-08-18 首次部署）

| 项 | 值 |
|---|---|
| 地址 | `http://192.168.100.51:8096/procurement/sc2/` |
| 健康检查 | `http://192.168.100.51:8096/procurement/sc2/api/ping`（门禁豁免） |
| 全量重算 | `POST .../api/refresh`，真实模式实测 **102 秒** |
| 服务器布局 | **扁平** `C:\sc2\{app, zhuopin_platform, .venv}`（非 monorepo） |
| 计划任务 | `Sc2WebServer`（SYSTEM + AtStartup + 失败重启 3 次），State=Running |
| 防火墙 | 入站规则 `Sc2-WebServer-8096` |
| 推送/部署脚本 | `sync-to-server.ps1`（笔记本跑）／`deploy-server.ps1`（`.51` 跑）／`smoke-server.ps1`（`.51` 跑，冒烟七项） |
| 回滚 | `schtasks /End /TN Sc2WebServer ; schtasks /Delete /TN Sc2WebServer /F`（防火墙规则可留） |

**冒烟结果（七项全过）**：ping 200／匿名访问被门禁 302／登录后关键页 200／`/api/refresh` 真实全量重算 200（102 秒）／重算后页面走快照 0 秒／重算全程进程未重启／**从笔记本外部实测 ping 200**（不是只在 `.51` 本机，根 CLAUDE.md 坑 5）。**进程 CreationDate 逐次核对真实刷新**（4584 → 4464 → 6256），非只信脚本打印「已重启」。

> ⚠️ **L3 确认发布刻意未在生产上实跑**：那会往 `audit` 写一条「某人已确认发布」的真实记录，而实际没有人确认过——**IATF 审计轨迹里不能有编造的签认**。该路径由两个单测覆盖（表单可确认／未填确认人被拒），留给姚祖怡本人首次真实确认。

### 🔴 过渡期端口豁免（须在此留痕，不得默默占用）

- **豁免内容**：本场景过渡期以自有 Flask（waitress）进程对外服务，端口 **8096**，构成对根 `CLAUDE.md` §5「**新场景一律不新起端口对外**」这条硬约束的**显式豁免**。**这是 `.51` 上第 7 个对外端口**（既有 8080／8090／8091／8092／8093／8094／8095）。
- **理由**：统一门户路由中间件零代码，SC2 不等网关（design D9）——不拿场景交付去赌地基工期。
- **批准来源**：Shao Peishen，见 `需求grill产出-2026-08-18.md` D9；端口号 **8096 由其 2026-08-18 部署当日改判**。
- 🔴 **为什么不是 design 审 ④(a) 原定的 8095**：那次定 8095 的依据是「顺延现网 8091-8094」，**而该前提是错的**——部署前实测 `.51` 上 **8090 跑着 `UnifiedPortalGateway`、8095 跑着 `ZhuopinRecruitAgent`**（uvicorn/FastAPI，`C:\apps\zhuopin-recruit-agent`，计划任务已注册且 Running），**两个都在原普查的视野外**。**教训与 D15-R 同型：结论建立在一次没做实的核查上，直到真去碰它才塌。**
- **注销条件**：统一门户网关落地后，SC2 收编进 `/procurement/sc2` 路由，本豁免随之注销。**路由前缀自首版即已是目标态，收编时只改映射、不改场景代码。**
  - 📌 **网关其实已存在但还接不了**：`.51:8090` 已有 `UnifiedPortalGateway` 在跑，但①其源码只在未合入 master 的分支 `claude/unified-portal-design-8a2ce3`（队列 #162/#335 已挂账）②路由表仍是试点单条（`/` → 8092）。**收编 SC2 须等它先合入 master 并具备多路由能力**，不是本场景能自行完成的动作。

### 部署当天发现并修掉的三件（都只在真部署时才暴露）

1. **#300 引导在扁平布局下 fail-loud**（队列 #345 同族）——`run_sc2.py` 原实现找不到 `5-平台底座/` 标记就无条件 `raise`，而 `.51` 正是扁平布局 ⇒ 服务进程秒退而计划任务仍报成功。已照 QD-B/SC8 已验证改法改为「找不到标记 → 交由环境解析，环境里也没有才报错」，**两个方向都实测过**（扁平布局能跑出真实周报／平台真缺失时仍明确报错，非静默通过）。
2. **门禁把健康检查挡在外面**——`install_flask_gate` 缺省豁免是裸 `/api/ping`，而本场景路由全在 `/procurement/sc2` 之下 ⇒ **没有任何路径命中豁免**，部署脚本的健康检查与此后一切存活探测都会 302 到登录页、误判服务不健康。已显式传带前缀的豁免路径并加单测。
3. **页面「确认发布」按钮在过渡期是坏的**——按钮提交的是**表单**，而 `api_confirm` 原来只认 JSON body 与网关身份，过渡期无网关下发身份 ⇒ 必然 400。**而这正是本场景 L3 的唯一人工动作、也是部署的全部意义所在**。已让确认人来源变为「JSON body → 表单 → 网关身份」三级，页面加确认人姓名输入框；**未填确认人仍拒绝**（无主语的确认在 IATF 审核时等于没有确认）。

### 部署当天新增的两条口径修正

- **服务端缺省不截断行级状态取数**（`--max-status-materials` 缺省 0）——首次部署实测窗口内料号 **830 个**，而 `RealFeed` 缺省上限 200 ⇒ **630 个料号拿不到行级状态、按「状态未知」计入在途**，在途类指标偏高。截断确实会写进取数说明（No silent caps），但那只是「诚实地报告一个次优数」，而页面上那些数正是要请姚祖怡判例批改的对象。慢的代价由 D21 承担（页面读快照、重算走独立 refresh）。
- 🔴 **O-7（新，首版即声明）：周中生成时本周窗口不完整** —— 三窗口同为一个自然周才使量纲可比（D16-R），**但基准日落在周中时本周只过了 N/7 天，上周与上月同期都是完整 7 天** ⇒ 所有「量」类指标的环比/同比系统性巨幅偏低。部署当天（周二，2/7 天）**21 个指标里 16 个被打 🔴，那不是业务波动**。**任何阈值调整都修不掉它，因为它不是阈值问题。** 已按「不可算不呈现」的同一精神在周报顶部**显式声明**（完整周运行时该行不出现，不构成日常噪音）；**根治口径（是否改为默认出上一个完整周）属 D16-R 的修改，须走追认，留判例包与 Shao Peishen 定。**

## 六、怎么跑

```bash
python run_sc2.py report --mode mock --base 2026-08-19    # mock 出一期周报
python run_sc2.py report --mode real --max-status-materials 0   # 真实全量（约 2m20s）
python run_sc2.py probe                                    # F14 端点参数名对照取证
python run_sc2.py serve --mode real --port 8096            # 起服务（缺省即 8096，行级状态不截断）
python -m pytest -v                                        # 120 passed
```

- 凭据从最近的 `.env` 自动读入（向上逐级查找，同 SC8 `run_baoguan_web.py`）；**凭据只在 `.env`，不入库、不打印**。
- `--max-status-materials` 是 D17 的已知代价开关：行级状态按料号逐个查，窗口内料号实测 812 个 ⇒ 全量约 2 分钟。**触发截断时会在周报取数说明里显式写出来**（No silent caps）。
- **所有生成物落 `reports/`**（已被 `.gitignore` 的 `**/reports/` 覆盖，`git check-ignore -v` 实测命中）。
