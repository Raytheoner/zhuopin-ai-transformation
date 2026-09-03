# 任务 · SC10 BOM 评审及公司物料库数据管控（队列 §一 #468）

> 🔴 **1.0 是硬闸**：本包 `design.md` 尚未撰写、design 审未过（🟡 档）。
> 第 2 组之后各项在 design 审通过前不得开工。
> 🔴 **另有一处须 design 审先裁决**：proposal「本包查出的一处判据源缺口」——
> 「物料优先选用级别口径」是否补进前置总表、补成什么形态。**本泳道不擅改规划文档。**

## 1. 骨架期（不依赖前置，`OP-0903-B2` 已完成）

- [x] 1.1 前置逐项实读并落进代码：`pending.py` 三项（区分数据型/知识型——两者按 6 周/8 周倒排，混记会算错启动日）
- [x] 1.2 结构模型：`LifecycleStatus`（四属性逐字取自规划；**刻意不混入 `str`**）／`MaterialRecord`／`BomUsage`／`BomReviewFacts`
- [x] 1.3 BOM 展开走底座 `kit_engine.explode_bom`，逐成品单独展开再合并以保住「需求来自哪个成品」
- [x] 1.4 数据完备度体检 `data_readiness`：BOM 内物料数／生命周期未知数／无价数／主数据缺失数
- [x] 1.5 取数层：`MaterialMasterSource` Protocol ＋ `InMemoryMasterSource`；`ExternalCatalogSource` Protocol ＋ `UnselectedCatalogSource` 占位
- [x] 1.6 前置闸：三个 `suggest_*` 调用即抛，错误带 Owner／类型／判据源／实读状态
- [x] 1.7 入口与留痕：`run_review_facts()`，`evaluator` 非空强校验，audit 标 `review_status="待前置到位"` ＋ 三项 `blocked_by`
- [x] 1.8 测试：18 tests 全绿，含①「三项建议必须抛」②「生命周期枚举不可比较大小」（拦"靠枚举顺序偷偷造判据"）③「窗口未到 ≠ 已逾期」④「`oem_context` 刻意留空」
- [x] 1.9 场景 `CLAUDE.md` 六段式 ＋ `README.md`

## 2. 前置到位闸（🔴 未满足即不开工第 4 组之后）

- [ ] 2.1 本包 `design.md` 撰写并过 design 审（🟡 档，须 Shao Peishen 拍板）
- [ ] 2.2 「物料优先选用级别口径」是否补进前置总表 —— 待裁决（属规划文档改动，须走移交单交全景路线图线）
- [ ] 2.3 原厂/第三方贸易网站 API 选型完成并签约（姚祖怡 + IT，窗口 2027-01～02）
- [ ] 2.4 我司价格库/物料属性数据整备完成（同上）
- [ ] 2.5 物料优先选用级别口径工作坊完成、采购经理签认、backup 实名点名（知识型，按 8 周倒排须与 2.3/2.4 **并行**安排）
- [ ] 2.6 与 `#475`（芯片市场价格 API）核对：两处外部 API 是否可合并采购一套 —— 🔴 本包不代判

## 3. 真实主数据接入（可先于 2027-01 窗口做，不依赖外部 API）

- [ ] 3.1 `ErpMasterSource` 实现 `MaterialMasterSource`，只读接 U9C 物料主数据
- [ ] 3.2 单测：主数据缺字段时如实落 `UNKNOWN`/`None`，**不得回填猜测值**
- [ ] 3.3 用真实主数据跑一次 `data_readiness` 体检，产出「2027-01 数据整备该整备什么」的清单交姚祖怡

## 4. 外部行情源接入（依赖 2.3）

- [ ] 4.1 按选型结果实现 `ExternalCatalogSource`，替换 `UnselectedCatalogSource`
- [ ] 4.2 价格/参数/封装字段映射与缓存策略（配额敏感，须在 design 里定清）
- [ ] 4.3 单测：外部源不可达时 fail-soft 降级到我司价格库，且降级事实须进 audit（不得静默）

## 5. 建议层（TDD：先测后码；口径来自 2.4/2.5，不得自拟）

- [ ] 5.1 `suggest_selection_level()`：按签认口径实现，移除 `pending.require`
- [ ] 5.2 `suggest_obsolescence()`：同上
- [ ] 5.3 `suggest_bom_review()`：同上
- [ ] 5.4 🔴 单测须断言：口径配置缺失/版本不匹配时 fail-loud，**不得回退到任何内置默认**
- [ ] 5.5 🔴 单测须断言：`LifecycleStatus` 仍不可比较大小（防实现期顺手加回 `str` 混入）

## 6. 收口

- [ ] 6.1 真实数据验证（档2）→ `/opsx:archive` → commit + push
- [ ] 6.2 场景 `CLAUDE.md` 更新（含部署状态段）
- [ ] 6.3 发布收口：统一门户路由 `/procurement/sc10`（🔴 不新起端口）＋ 部署段基本测试 ＋ 回滚 SOP ＋ 灰度反馈入口
