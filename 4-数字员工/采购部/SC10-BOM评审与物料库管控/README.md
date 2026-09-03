# SC10 BOM 评审及公司物料库数据管控（骨架期）

> 权威排期 **2027-03**（全景规划 §加速启动总览采购列）。**本骨架期不改排期** ——
> 立行判据「不管规划时间表、能开尽开」只解除开工门槛，不等于排期提前。

## 现在能跑什么

```bash
cd "4-数字员工/采购部/SC10-BOM评审与物料库管控"
python -m pytest -q                 # 18 passed
```

- ✅ **BOM 展开**：复用底座 `zhuopin_platform.agents.kit_engine.explode_bom`（与 O2/SC7/SC8 共用），不重写。
- ✅ **共用料识别**：逐成品展开再合并，保住 `explode_bom` 合计口径丢掉的"需求来自哪个成品"。
- ✅ **数据完备度体检**：BOM 内物料数 / 生命周期未知数 / 无价数 / 主数据缺失数。骨架期最有用的一张表——它回答的是"还差多少数据才谈得上评审"。
- ✅ **审计留痕**：写平台 `audit`，`review_status="待前置到位"`。

## 现在**不能**跑什么，以及为什么

`review.py` 三个 `suggest_*` 全部 fail-loud。

| 卡住的能力 | 前置 | 类型 | 状态（2026-09-03 实读） |
|---|---|---|---|
| BOM 评审建议 | 原厂/第三方贸易网站 API 选型与接入 | 数据型 | ⚪ 新增行；窗口 2027-01～02，**未到、非逾期** |
| 物料库优先选用与淘汰建议 | 我司价格库/物料属性数据整备 | 数据型 | ⚪ 同上 |
| 物料优先选用级别建议 | 选用级别口径与淘汰判据 | 知识型 | 🔴 **前置总表无此行**，本场景据实拆出 |

🔴 **第三项是本次新查出的**：前置总表把它含在「物料属性数据整备」里一并交给姚祖怡 + IT，
但数据整备产出的是**属性值**，不是**排序规则** —— Active/NRND/New Product/Obsolete 到手后，
「NRND 能不能进新 BOM」仍然没有答案。本场景把它单列，避免"属性数据到位"被误读成"SC10 可全量开工"。
补前置总表行属规划文档改动（全景路线图线），**本场景不擅改**，已登记待定夺。

## 目录

```
sc10_bom_review/
  pending.py    前置闸（三项，区分数据型/知识型）
  models.py     LifecycleStatus（刻意不混 str）/MaterialRecord/BomUsage/BomReviewFacts
  sources.py    主数据源 + 外部行情源 Protocol（后者为 Unselected 占位实现）
  review.py     collect_facts（真跑）+ 三个 suggest_*（闸后）
  agent.py      入口 run_review_facts
tests/          18 tests
```
