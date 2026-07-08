---
title: "开场 Prompt · U9C 物料库存实时读取攻关（Fable 5 CC 建造会话用）"
created: 2026-07-03
status: 已执行归档（原地保留——被 CLAUDE.md「库存实时源落地」段"细节见"引用；攻关已完成，Stock/Query 已接入并归档于 stock-api-inventory-source 变更包）
用途: 新开 Claude Code（CC，LAN，建议 Fable 5）会话，攻关"缺料预警 MVP 读不到 U9C 实时库存"这一根阻塞；不全指望原厂 bugfix，找并落地 vendor-independent 取数路。
说明: 已上线引擎（SC8 保供看板 LAN 在跑）的数据源攻关——纪律优先：先摸清 API 现状/复现、给可落地方案、停下报 Paul 定路，再动代码；全回归不漂移。
关联: 5-平台底座/.../erp_connector/connector.py（get_inventory 桩）｜ 缺料预警校准需求 P0 ｜ U9C接入与连接器收敛-待办追踪（#3/#4/#6/#7）｜ 7-外部文档/U9C库存查询API测试报告 ｜ session接力-采购域场景落地
---

# 开场 Prompt —— U9C 物料库存实时读取攻关（CC 交接）

> **⚡ 侦察已完成（2026-07-05，本轮只读联调）——攻关有解，见 `7-外部文档/U9C库存取数-侦察结果与推荐-2026-07-05.md`。**
> 结论：**DB 只读直连当场取到真实现货**（`dbo.InvTrans_WhQoh`，实测 R01A.0012 现存量 2,827,195 等真数），vendor-independent、不等原厂、**当前唯一可用路**、推荐首选。SOAP `IBatchQueryItemQtySVR` 鉴权虽破（免 OAuth、ThreadContext 数字 OrgID）但**喂确有货料号仍回 0（已证伪，短期不作备选）**。
> **待 Paul 拍板**：定 DB 直连为路 + 可用量口径；**待 IT**：建只读账号（勿再用 sa）。🔴 两条安全隐患（sa+明文口令 / SOAP 免鉴权越权）见结果文档 §五，须升级整改。
> 下一会话若接手：读结果文档 → 若 Paul 已定路 + IT 建好只读账号，则走 openspec 把 DB 只读取数封装进 `ZpConnector.get_inventory` + 接 kit_engine/SC8。下方原任务书保留作背景。

> 用法：新开 CC 会话（建议 **Fable 5**），**让 CC 读本文件**（不必整段粘贴）。短开场词：
> 「读 `1-转型规划/开场prompt-U9C库存实时读取攻关-CC交接.md` + CLAUDE.md 当前进度，按文件里的攻关任务执行；先摸清 API 现状/复现，给 vendor-independent 取数方案，动代码前停下报我。」
> CC = LAN 建造车间（连真实库、改代码、跑回归）。下方代码块是给 CC 读的任务全文。

```
【CC 攻关任务·U9C 物料库存实时读取 —— LAN 执行, Fable 5】

== 一句话 ==
缺料预警 MVP 的根卡在"读不到卓品现货数量"。用友 webapi 的库存端点有原厂 bug
（已提交原厂修，ETA 不可控）。本任务 = 不等原厂，找到并落地一条 vendor-independent 的
**实时**库存取数路，接进 ZpConnector.get_inventory，喂给缺料/保供引擎，消除误判。

== 先读上下文恢复（按序）==
① CLAUDE.md 当前进度（§4 底座/连接器、§7 红线）
② 7-外部文档/用友OpenAPI完整文档/ —— **原厂完整 OpenAPI 包（金矿，必读）**：
   · 相关openAPIJSON串示例（仅U9C）/相关JSON串示例/查询可用量.txt（**测通·扁平体，无 IsProdCancel**）
     vs 查询可用量（没测通）.txt（**嵌套体·含 IsProdCancel = IT/我们踩坑的那个**）→ 证明是版本/DTO 绑定错配
   · API调用事例/查询料品可用数接口事例.cs（**另一库存服务** UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR）
   · 相关openAPIJSON串示例（仅U9C）/U9C*.postman_collection.json（全 webapi 端点目录 + JSON 体）
   · U9C公共查询接口.postman_collection.json + 公共查询接口示例/（CommonEntity 正确用法）
   · 1、U9API接口清单.xls / 2、常用-API接口字段说明(必传字段版).xls（字段规格）
   · JAVA调用U9轻量级接口示例/HttpClient.java（SOAP/.svc 服务的轻量级 HTTP 调用范式）
③ 7-外部文档/U9C库存查询API测试报告.md —— IT 原厂 bug 实测（webapi 两个库存端点全废）
④ 7-外部文档/Claude用友middleware接口.txt —— 曾评估的"中间件"思路（已判绕不过，见下）
⑤ 5-平台底座/连接器收敛设计-ZpConnector与U9CConnector.md（附录 A 实体/端点映射）
⑥ 1-转型规划/U9C接入与连接器收敛-待办追踪.md
   —— #3 CommonEntity / #4 DB直连 airead / #6 FO 卓品视图先例(关键) / #7 收货历史
⑦ 1-转型规划/缺料预警校准需求.md（P0 业务口径 + Paul §6/§9 决策）
⑧ 1-转型规划/开场prompt-缺料预警修复-CC交接.md（P0 原始交接）
⑨ 代码：erp_connector/connector.py（get_inventory 桩≈L404；AuthLogin/_zp_post/_u9c_bom_post）
       | agents/kit_engine.py（calc_shortage L47-86）
       | SC8 sc8/forecast.py（estimate_material_arrivals L38，**无库存入参**）+ sc8/baoguan.py
⑩ 探测工具：5-平台底座/zhuopin_platform/scripts/probe_u9c.py（测试库只读探测器 + 生产硬拦）

== 问题现状（这是根）==
两个引擎都拿不到"卓品现货数量"：
  · SC8 保供看板 estimate_material_arrivals **架构上没有库存入参**（现场误判主体，
    且它自成四色、**不走 kit_engine**）；无 SRM 承诺的子件——哪怕满仓——一律进"待催/催货"。
  · kit_engine.calc_shortage 有 InventoryRow，但真实 get_inventory 恒返回 current_stock=0
    （zp webapi 无库存余量端点，只有 ZpViewItemMaster 物料主档、无数量）。

用友 webapi 库存端点实测（IT + 本 session 独立在生产 erp:4443 复现）：
  · /U9C/webapi/Invtrans/QueryQohAndAvailable → 原厂 bug：QueryQohAndAvailableSv.cs:137
    把 IsProdCancel(bool) 拼进 SQL → "列名 'True' 无效"。客户端任何输入都躲不开
    （null/字符串/整数/不传，均被服务端还原成 bool）。**已提交原厂修，ETA 不可控。**
  · /U9C/webapi/Invtrans/EasyQueryQoh → 404 未部署。
  · /U9C/webapi/CommonEntity/Query → 404（连生产 webapi 面也没有，非仅外网限流）。
  · OAuth2/AuthLogin + BOM/Query → ✅ 可用（现有 real BOM 就靠它）。

**原厂完整文档（②）新增关键情报**：
  · webapi 全端点目录已提取（U9C*.postman_collection.json）：REST 面**唯一**现存量查询就是
    Invtrans/QueryQohAndAvailable（另有 InventorySheet/Checking=盘点、CommonEntity/Query）。
    → REST 面没有别的可用库存端点藏着，别再瞎试 REST。
  · **bug = 版本/DTO 绑定错配，非死症**：原厂自带示例 查询可用量.txt 用**扁平体**
    {Org,ItemCode,ItemName,OwnOrg,Wh,StorageType}（无 IsProdCancel）标注**测通**；
    嵌套体（QueryDTORDataList.QohInfo.IsProdCancel）标**没测通**——正是 IT/我们踩的那个。
    卓品的 build 绑定了坏的嵌套 DTO controller。→ 给原厂的 ticket 改成：**"按你们文档的扁平
    DTO 版本重部署/对齐 Invtrans controller"**（比"修 Sv.cs:137"更硬的凭据）。
  · **发现第二个库存服务**：UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR（批量查询料品可用数），
    在 **SOAP/WCF 面**（/U9/Services/UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR.svc），
    **不经过坏的 QueryQohAndAvailable REST 包装**。轻量级 HTTP 调法见 JAVA HttpClient.java。
    → 若卓品 U9C 暴露了 /U9/Services 面（或其轻量级 wrapper），这是真·vendor-independent 旁路。

"中间件"思路（middleware.txt）判定**绕不过原 REST 端点**：bug 在服务端 Sv 层，任何 HTTP
客户端发同一 QueryQohAndAvailable 请求都炸；再起 U9CClient = 重复一个更弱、脱离平台审计的
ZpConnector。**不建**。但换**另一个服务/另一个面**（ItemQty SOAP、zp 视图、DB）是另一回事。

== 已做的努力与成果（本 session）==
- 定位根因（数据侧：现货数量数据源缺失）；mock 复现"库存一到误判即消失"（变体3）。
- 生产只读探测独立复现原厂 bug；判定 SC8 保供看板是现场误判主体、不走 kit_engine。
- 建测试环境隔离 profile（Paul 定，联调不碰生产）：
  · .env.test（gitignore，IT 测试库 192.168.100.49:6666 值 + 待填 secret）
  · .gitignore 加固（.env.* 全忽略 + !.env.example 放行；实测 .env.test 已忽略）
  · scripts/probe_u9c.py（只加载 .env.test、生产主机硬拦白名单、只读、不打印密钥）
- 探测器已验证：正确锁测试库、生产硬拦在位；测试库 ai 客户端 clientsecret 与生产不同
  （生产密钥试连=参数错误；空=参数错误；不传=404）→ **待 IT 给测试库 secret**。
  swagger/api-docs 被登录态挡住（拿到 secret 后可枚举全接口面）。

== 攻关目标 ==
不依赖原厂修 bug，落地一条**实时**读卓品现货（现货量/可用量，最好含安全库存/仓别/批次）
的路 → 实现进 ZpConnector.get_inventory（real 模式）→ 库存维度接进 kit_engine + SC8
保供看板 → P0 误判结构性消失。

== 候选路径（排序；先摸清可行性，别急落地）==
A. 卓品自建 /zp 库存视图（首选·vendor-independent·有一天落地先例）★★★
   - 先例(待办#6)：FO 同样"webapi 无查询接口"，IT 一天内建了卓品视图
     GET /zp/api/ForecastOrder/Query（apiKey 走 URL query，Swagger /zp/swagger/ui/index）。
   - 打法：请 IT 照此建 GET /zp/api/Inventory/Query（或 ZpViewQoh），从 U9C DB 现存量出数，
     走已在用的 /zp 面。**不碰用友原厂代码、IT 自控、复用工作信道 + 平台审计。**
   - 起步：先扫 /zp/swagger/ui/index 看有无现成库存视图（此面用 apiKey/query，不需 U9C OAuth
     secret）；没有则起草视图字段规格交 IT，照 FO 改造范式接 loaders/get_inventory。

B. ItemQty SOAP/轻量级服务（新发现·可能是最快的原生旁路）★★★
   - 原厂文档②：UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR（批量查询料品可用数），
     在 /U9/Services/…svc 面，**不经过坏的 QueryQohAndAvailable**。
   - 起步（便宜先试）：探 /U9/Services/UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR.svc 是否可达；
     参照 JAVA调用U9轻量级接口示例/HttpClient.java 的轻量级 HTTP 调法 + ThreadContext(OrgID/UserID
     /EnterpriseID) 鉴权，用 Python 复刻一次只读调用（测试库）。通了就是 vendor-independent。
   - 风险：SOAP 面鉴权异于 webapi OAuth2；卓品是否对外/对 LAN 暴露 /U9/Services 未知——先探活。

C. DB 只读直连（Door ③·已有 airead 账号）★★
   - 待办#4：正式库 DB 192.168.6.2:5555 有只读账号 airead（弱口令，需轮换）。
   - 打法：找 DBA 要现存量**视图**名 + 轮换 airead 口令 → pyodbc/pymssql 只读 SELECT →
     实现 get_inventory。绕开整个 webapi 层，实时。
   - 红线：耦合 DB schema（打在 DBA 认可的视图上、别碰原始表）；只读；写 audit；轮换弱口令。

D. 原厂/半原厂并行（不作主线，但凭据变硬）：
   - 拿②的"扁平体测通/嵌套体没测通"证据，要求原厂**按文档扁平 DTO 版本对齐 Invtrans controller**
     （比"修 Sv.cs:137"更硬）；或部署 EasyQueryQoh（另一服务、无此 bug）。继续跟，不指望其及时。
   - 注：卓品 build 绑定坏的嵌套 DTO，客户端换扁平体也会 NullReference（IT 已试）→ 无客户端解，
     必须服务端对齐版本。

== 起步动作（先摸清，动代码前停下报 Paul）==
1. **探 ItemQty SOAP 面**（路径 B）：/U9/Services/…IBatchQueryItemQtySVR.svc 可达性 + 轻量级鉴权
   （测试库，只读）——这条最有可能是"零 IT 改动即可取数"的旁路，优先试。
2. 扫 /zp 面 swagger（/zp/swagger/ui/index）——确认有无现成库存视图；不需 U9C OAuth secret。
3. 拿到测试库 secret 后跑 probe_u9c.py（顺带拉 U9C swagger 全集，核对②的端点目录）。
4. 评估 A/B/C 可行性 → 给 Paul 一页纸：推荐路径 + IT/DBA 需求清单（视图字段/账号/口令/SOAP 暴露）
   + 工作量。★停下报 Paul 定路，再动代码。

== 修复+验证（定路后·test-first·全回归不漂移）==
- get_inventory real 实现（选定路径）→ 返回真实 current_stock（+available/safety 若可得）。
- kit_engine：按缺料校准需求 §4-A，快照缺失/数据不可判 → "待核实"+fail-loud，不进 shortages
  （阈值策略与采购专员 §3/§9 口径对齐后再定）。
- SC8 保供看板：给 assess_supply_risk/build_dashboard 加 inventory 入参，默认 None=零漂移；
  有库存+开关 → 现货净额≥毛需求的子件退出待催/催货。
- 全回归：平台/O2/SC5/SC8 全绿；SC5 黄金值 35850/640000/675850、SC8 real_frozen 不漂移；
  若误判清零**预期改变**保供四色/缺料清单，与专员重核黄金基准、登记原因，不静默改。
- 走 openspec change（propose→Paul 审 design→apply）。

== 红线与边界 ==
- 已上线引擎（SC8 保供 LAN 在跑）——回归安全第一；改 calc_shortage 影响 O2/SC5/SC8 三消费方。
- 联调**一律走测试库**（probe_u9c.py 生产硬拦）；主线真实数据用生产 .env。先 mock/脱敏再切真实。
- 只读、绝不写 ERP；每次判定写平台 audit；L2 门禁不动；对客闸 CUSTOMER_OUTBOUND_ENABLED 全程关。
- OEM 隔离不适用采购/库存数据（CLAUDE.md §4）。
- 凭据只进 .env/.env.test（gitignore，不入库、不打印）；airead 弱口令若启用先轮换。
- 不改规划文档（全景/实施计划/前置总表）——Cowork 的活；本攻关进展滚动进
  session接力-采购域场景落地.md。业务"真缺料"口径来自采购专员（§3/§9），你负责取数/接入/回归。

== 关键坐标 ==
- 生产 ERP：erp.equalitytec.com:4443（外网）/ 192.168.6.2:5555（内网）；
  DB 只读 airead@192.168.6.2:5555（弱口令待轮换，待办#4）。
- 测试库（联调用）：192.168.100.49:6666（.env.test；待 IT 给 ai clientsecret）；
  外网测试网关 testerp.equalitytec.com:4445。
- 认证：U9C webapi = OAuth2 AuthLogin→JWT→header token（BOM 在用）；/zp 面 FO = apiKey 走 URL query。
- base 约定：host-only（连接器内部自拼 /U9C 与 /zp；带 /U9C 会双拼 404）。
- get_inventory 桩：erp_connector/connector.py ≈L404（现 current_stock=0）；
  探测器 scripts/probe_u9c.py；原厂 bug 报告 7-外部文档/U9C库存查询API测试报告.md。
- 原厂完整文档：7-外部文档/用友OpenAPI完整文档/（金矿；扁平体测通示例/ItemQty 服务/全端点目录/字段规格）。
- ItemQty SOAP 端点：/U9/Services/UFIDA.U9.ISV.ItemQty.IBatchQueryItemQtySVR.svc
  （DTO=ItemQtyQueryDTOData→ItemQty4ISVDTOData[]；轻量级 HTTP 调法见 JAVA HttpClient.java）。
```
