> ⏸ **状态：条件复启暂缓（财务部意愿，Paul 2026-07-06 线下确认；唐燕萍批改回灌认可）—— 封存不废弃**（详见全景规划 §2.1.4 FI1 段）。
> **工程事实**：内部对账 MVP 已建（mock 30 tests 全绿 + 审计 hash-chain 通 + `fi1/confirm.py` L2 判例采集已落地）；档1 冻结、代码留库，不废弃、不删测试；平台级复用件（`confirm.py` 的 L2 判例采集模式、平台 audit）不受影响，继续供 FI2/FI3 等复用。
> **复启条件（满足其一即可提请复启，Paul 拍）**：① 财务部业务优先级回调、明确要恢复仓库对账自动化；或 ② FI1 依赖数据就绪（SMT 投料/BOM 理论用量的 U9C 直读或 ERP CSV 稳定导出）+ 人力可投；或 ③ FI2/FI3 上线后回看，仓库对账痛点重新升级为优先项。
> **暂缓原因（备查）**：唐燕萍确认主因业务优先级调配（优先推进采购/付款相关的 FI2/FI3，仓库对账后置）。
> **本变更包（openspec `fi1-warehouse-reconcile`，28[x]/12[ ]）不视为"完工未归档"违规**——业务侧主动封存在途工作，非完工拖延；本状态说明由队列 #196（2026-08-04，CC）补写。

## Why

SMT 非精准发料模式导致库存消耗与 BOM 理论用量持续偏差，财务与供应链每月投入多人天逐笔人工核对差异、逐笔翻查定位，耗时且易错。FI1（财务旗舰，全景 §FI1）把这套对账交给数字人做**自动差异分析 + 分类 + 出报告**，财务+供应链经理只复核异常项，把"多人天人工核对"压成"当天自动化完成、差异系统自动标注"。本场景 2026-06-28 经 Paul 拍板由 2026-09 加速到 **2026-08 启动 / 09 试点**，因其 BOM 理论用量读取可直接搭 SC8 已验证的 `ZpConnector + U9C webapi` 便车，数据闸基本打开。

**MVP 范围（Paul 2026-06-28 定）**：只做**内部对账**——SMT 实际投料 vs BOM 理论用量的差异对账。委外加工商库存对账卡 8/15 商务数据条款，**二期**推进、本期留接口位；损耗基线趋势模型亦**二期**，MVP 先把差异算准。

## What Changes

- 新建场景工程 `4-数字员工/财务部/FI1-供应链仓库对账/`，`pip install -e` 平台底座（CLAUDE.md §4/§6）。已 scaffold + imports 全绿。
- **数据接入层**：BOM 理论用量复用平台 `ZpConnector.get_bom_for_products`（SC8 已在 LAN 真实跑通的 U9C BOM/Query，`BomRow` 带 `qty_per_unit` + `loss_rate=m_scrap`）；投料/产出 = 三源统一接口（`data_source` 切 `mock`/`csv`/`u9c`，切源不改对账逻辑）：**最终目标 `u9c` 直读**——MO 实体 `UFIDA.U9.MO.MO.MO`（`FinishedQty` 产出）+ 领料 `MOPickList`，经 `CommonEntity/Query`（**外网当前 404** → fail-loud，仿 SC8 `RealEndpointNotReadyError`，绝不静默回退）；**过渡期 `csv` 应急桥接**取真实数据（ERP 定期导出，已授权，S1 复盘 2026-06-25；字段贴 U9C 语义，端点开放后弃用不改引擎）；`mock` 夹具供开发/回归。
- **纯算法对账引擎**：毛理论口径——理论净用量 = Σ(产出 × `qty_per_unit`，不含损耗)；标准损耗基线 = 理论净用量 × `m_scrap`；总差异 = 实际投料 − 理论净用量 + 差异率。纯函数，每条逻辑一夹具单测（先测后实现），黄金回归。
- **差异分类**：数据驱动规则注册表（仿 QD-B rule registry），按差异方向/是否在标准损耗内/阈值映射为分类档（损耗溢短 / 来料短缺 / 管理差异）。**临时基线口径占位**，财务 AI 对接人 7/31 定稿后替换，规则版本登记（IATF 单一可信源）。
- **对账聚合 + L2 门禁 + 审计**：逐料号库存对账差异报告（理论/标准损耗/实际/总差异/差异率/分类/标记需人工）；**L2 超阈值（金额/比例）标"需人工确认"不自动结案**；每笔判定 + 分类写平台 `audit`（append-only / 3 年；数量为主，财务红色金额脱敏/仅聚合，原始单价不落 AI 侧）；报告标注 **"AI 对账建议，结案在财务+供应链经理"**。
- **OEM 隔离不适用**：FI1 读供应商/ERP 内部数据，按 CLAUDE.md §4 不强加 OEM 路由、不接 `data_isolation_layer`。

## Capabilities

### New Capabilities
- `fi1-feed-source`: 数据接入层——BOM（复用 ZpConnector，真实已验证）+ 投料/产出三源统一加载（`mock` 夹具 / `csv` 应急桥接·过渡真实路径 / `u9c` 直读·最终目标，外网 404 时 fail-loud），Pydantic 边界校验，按源标记审计。（MO/领料 CommonEntity 读收敛设计已预定归 ZpConnector，但 MVP 因 404 + 首消费方**暂留场景本地**，端点开放且真复用时再提升——见 design D4/收口-5。）
- `fi1-reconcile-engine`: 纯算法对账引擎——毛理论用量/标准损耗基线/总差异/差异率计算，纯函数 + 夹具单测 + 黄金回归。（对账引擎 FI1 唯一消费方，rule-of-three 未触发，**场景本地**。）
- `fi1-variance-classify`: 差异分类——数据驱动规则注册表把差异映射为分类档（损耗溢短/来料短缺/管理差异），临时基线口径，对接人 7/31 定稿替换，规则版本登记。
- `fi1-recon-report`: 对账聚合 + L2 门禁 + audit——逐料号差异报告契约、超阈值标"需人工确认"不自动结案、写平台 audit、报告标"AI 预审建议非终局"。

### Modified Capabilities
<!-- 无。底座 audit 为消费方式复用，不改其规格契约；BOM 读复用 ZpConnector 现有方法不改契约；
     投料/产出 MO/领料 CommonEntity 读 MVP 暂留 FI1 场景本地（design D4），未触发底座 platform-data-connectors spec 变更。
     端点开放后提升进 ZpConnector 时，另起变更修订 platform-data-connectors。 -->

## Impact

- **新增文件**：`4-数字员工/财务部/FI1-供应链仓库对账/`（pyproject + feed_source + reconcile_engine + variance_classify + recon_report + tests + mock 夹具 + `data/golden/` 合成样本）。
- **底座依赖（消费，不改）**：`zhuopin_platform.shared_tools.erp_connector.ZpConnector`（BOM 真实读，复用）、`zhuopin_platform.audit`（对账判定 append-only）、`zhuopin_platform.shared_tools.models.BomRow`。
- **不接**：`data_isolation_layer`（OEM 隔离不适用财务，CLAUDE.md §4）。
- **数据源（Paul 2026-06-29 定）**：投料/产出最终走 U9C 直读，**过渡期保留 CSV 应急桥接**取真实数据（已授权），避免 9 月试点完全押在 IT 端点开放上。
- **不修改**：supplychain 仓库；SC/O2/QD 任何场景；平台底座现有 spec 契约。
- **真实数据前置（解锁条件）**：① IT 开放 U9C MO/领料/出入库 webapi 端点（或 LAN/VPN）——真实对账验证前置；② 财务 AI 对接人（2026-06-29 到位）定差异分类规则 + L2 阈值（7/31 定稿）——真实结案验收前置；③ 历史人工对账黄金样本（8/15）——上线回归前置。
- **二期（不在本变更）**：委外加工商库存对账（卡 8/15 商务条款，留接口位）；损耗基线趋势模型；MO/领料 CommonEntity 读提升进 ZpConnector（端点开放后）。

## design 停审点（apply 前必须收口，交 Paul + 财务 AI 对接人）

- **收口-1 差异分类规则 + L2 阈值**：分类档判定边界（损耗溢短/来料短缺/管理差异）+ 差异金额/比例的人工确认阈值，由**财务对接人 7/31 主笔**，非 AI 预设。MVP 先用临时口径跑 mock，真实结案验收待其定稿。
- **收口-2 标准损耗基准归属**：Paul 选用工艺 BOM 的 `m_scrap` 拆分标准损耗 vs 超损；若财务要另立标准损耗表（不用工艺值），需对接人提供损耗基准表。
- **收口-3 产出/完工数量口径**：`MO.FinishedQty` 是否等于对账期产出？批次/在制/跨期如何归属——待对接人 + 生产确认。
- **收口-4 实际投料权威源 entity**：SMT 线体投料过账 vs 工单领料 `MOPickList`，哪个作"实际投料"权威源——待 IT/生产确认 entity 与字段。
- **收口-5 MO/领料 CommonEntity 读提升时机**：端点开放后这些读提升进 ZpConnector（收敛设计已预定归属），届时另起变更修订 `platform-data-connectors`。
