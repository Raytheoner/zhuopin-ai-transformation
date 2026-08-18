# CLAUDE.md — FI1 供应链自动仓库对账（场景级进度笔记）

> 本文件是 FI1 场景的本地记忆/进度笔记，与采购(SC*)/质量(QD*)场景分开。
> 项目级上下文见仓库根 `CLAUDE.md`；FI1 规划权威见全景规划 §FI1、实施计划 §一财务表、
> 跨场景前置数据总表 FI1 行、`1-转型规划/财务部场景开工就绪清单.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）；排期若变只在此记并提示 Paul 通知 Cowork。

## 定位（Paul 2026-06-28 拍板）
- FI1 = 财务/供应链交叉场景，**2026-08 启动 / 09 试点**（09→08 加速，搭 SC8 已验证连接器便车）。
- 自动化等级 **L2**：AI 自动对账 + 差异分类 + 出报告，财务+供应链经理审核异常项、结案；超阈值不自动结案。
- **MVP 范围·内部对账先行**：SMT 实际投料 vs BOM 理论用量的差异分析与对账。
- **明确不做·二期**：① 委外加工商库存对账（卡 8/15 商务数据条款，留接口位）；② 损耗基线趋势模型。
- OEM 隔离【不适用】：FI1 读供应商/ERP 内部数据，按根 CLAUDE.md §4 不强加 OEM 路由。

## 开工澄清结论（Paul 2026-06-28 答）
1. **投料/产出数据源**：**最终目标 = U9C ERP 直读（webapi）**；**过渡期 = CSV 应急桥接**（Paul 2026-06-29 细化）。
   ⚠️ 现实约束：U9C 投料/出入库/完工(MO) 走 `CommonEntity/Query`，**外网当前 404**（仅 BOM/Query + FO/Query 开放）。
   落地 = feed-source 三源统一接口：`mock`（夹具）/ `csv`（ERP 导出，过渡期真实路径，已授权 S1 复盘 2026-06-25）/
   `u9c`（最终目标，端点不可达 fail-loud 仿 SC8 `RealEndpointNotReadyError`）；切源不改对账逻辑。
   CSV 字段贴 U9C 语义，端点开放后切 `u9c` 零改引擎。
2. **损耗口径 = 毛理论 + 差异显性拆分**。理论净用量 = qty_per_unit × 产出（不含损耗）；
   实际 − 毛理论 = 总差异，再用 U9C BOM 的 `m_scrap`（loss_rate）拆「标准损耗内」vs「超损/管理差异」。
3. **黄金基准 = 暂用合成样本**。8/15 历史人工对账到位后替换为真实 golden。

## 复用底座资产（搭 SC8 便车）
- **BOM 理论用量**：`zhuopin_platform.shared_tools.erp_connector.connector.ZpConnector`
  `.get_bom_for_products(ids, max_depth)` → `list[BomRow]`（带 `qty_per_unit` + `loss_rate=m_scrap`）。
  SC8 已在 LAN 真实跑通这条 OAuth2 路径；`from_env(audit=...)` 从 `.env` 注入凭据。
- **投料/产出（待 IT 开放）**：U9C 实体 `UFIDA.U9.MO.MO.MO`（`FinishedQty` 产出）+ `MOPickList`（领料/投料），
  via `CommonEntity/Query`。收敛设计已预定：这些 CommonEntity 方法「新增到 ZpConnector 内，不另起类」
  （`5-平台底座/连接器收敛设计-ZpConnector与U9CConnector.md` 附录 A）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（scenario="FI1"，append-only hash-chain，IATF 3 年）。

## 红线（建造时守住）
- 先 mock/脱敏跑通逻辑，再切真实库。
- 每笔对账判定 + 差异分类写平台 `audit`（数量为主；财务红色金额脱敏/仅聚合，原始单价不落 AI 侧）。
- L2 人工门禁：差异超阈值（金额/比例）标"需人工确认"，不自动结案。
- AI 结论 = "对账建议"，结案在财务+供应链经理。

## 状态
- 2026-06-28：场景工程 scaffold。
- 2026-06-29：OpenSpec propose 完成 + design 审核通过（Paul 拍板毛理论口径、合成 golden、**CSV 应急桥接·最终仍 U9C 直读**）。
- 2026-06-29：`/opsx:apply` 完成 **MVP 核心（mock 先行，先测后实现）**——四模块 `feed_source`/`reconcile_engine`/`variance_classify`/`recon_report` + `run.py` 一键跑通；**30 tests 全绿** + `python -m fi1.run` 端到端通 + 审计 hash-chain 校验通过。临时口径已落 `config.py`（L2 阈值）+ 规则注册表（`fi1-temp-2026-06-29`）。
  - 已完成 tasks 组 2-6 + 8.1；**未做**：组 1 收口（待对接人/IT）、组 7 真实数据验证（待 CSV 导出/对接人规则）、8.2 archive+push（待 Paul 定提交时机）。
  - **下一步**：① 对接人交付收口-1 分类规则+L2阈值（替换临时口径）；② ERP 导出投料/产出 CSV 走 `csv` 应急桥接做真实小样本；③ 真实跑通 + 历史 golden 后 `/opsx:archive`。
  - 运行：`python -m fi1.run`（mock）/ `python -m fi1.run --data-source csv --csv-dir <ERP导出目录>`（过渡真实）。
- 2026-06-29 **⏸ 暂停**：财务专员反馈**需求有变**，等其正式回复再继续。当前 MVP 已落 master（`e5ead24`，已 push）。
  - 恢复时先比对新需求与现有口径差异：多数变更应落在 `config.py`（L2 阈值）+ `variance_classify` 规则注册表（分类档/口径），引擎/接入层一般不动；若涉及范围/数据源/口径结构变化（如改净理论、改投料源、加金额维度），需回头修 design + specs 再 apply。
  - **下一会话**：读本 CLAUDE.md + 接力文件 → 拿到专员新需求 → 评估改动落点（优先 config/规则表）→ 必要时 propose 增量变更。

## 关键依赖/前置（解锁条件）
- 🔴 财务 AI 对接人（2026-06-29 到位）定**差异分类规则 + L2 阈值**（7/31 定稿）+ 收口-2/3/4 口径——真实结案验收前置；未定前 CC 只用临时口径跑 mock。
- 🟡 IT 开放 U9C MO/领料/出入库 webapi 端点（或 LAN/VPN）——**最终 U9C 直读**前置；过渡期 CSV 应急桥接兜底，故**非试点阻断项**。
- 🟡 ERP 定期导出投料/产出 CSV（过渡期真实数据路径）——9 月试点真实验证用。
- 🟡 历史人工对账黄金样本（8/15）——上线回归前置。

## 路径引导（队列 #345，2026-08-18）—— 扁平部署布局下不再硬失败

- **改了什么**：本组件下列入口顶部的 #300 worktree 隔离引导，**找不到 `5-平台底座/zhuopin_platform` 标记时不再无条件 `raise`**：`fi1/run.py`、`fi1/confirm.py`
- **为什么**：`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋ `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 `pip install -e` 进该服务 venv，全机唯一一份），**本就没有 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于把入口在生产布局上钉死。2026-08-18 SC8（8091）与 QD-B（8093）当天各自被它打挂过一次。
- **改法**（同 QD-B `dcc4162` / SC8 `a858769` 已验证范式）：找到标记 → 按 #300 原样前插（开发机 N 个平等 worktree 需确定性）；找不到 → 只插自身包路径、平台底座交环境解析（生产机唯一一份、无歧义）；**只有当环境里也没有 `zhuopin_platform` 时才 raise** —— 不引入静默失败。
- 🔑 **为什么这类雷本地测不出来**：**本地永远能找到仓库根标记**，全量测试全绿与它毫无关系。凡"引导/路径解析"类改动，**本地绿 ≠ 生产可启动**。
- ⚠️ **`tests/conftest.py` 刻意不改**：在 monorepo 内 fail-loud 是**有价值的**——测试就该跑在仓库里，找不到标记说明环境真错了，此时静默回退才是隐患。
- **收拢为平台底座共享函数** 见 `openspec/changes/platform-bootstrap-ensure-paths/`（已 propose，待 Shao Peishen 审 design，本次未 apply）。
