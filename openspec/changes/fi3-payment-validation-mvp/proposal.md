# fi3-payment-validation-mvp Proposal

> 🔴 **状态：档 1 mock 已全绿，design 审 🟡 待 Shao Peishen。** 由无头泳道 `B-0917_波1建造 / op0917j-fi3-new`（件号 `OP-0917-J`，队列 §一 `#605`）起草并建造。**本包类别 ＝ 业务场景变更包**（非机制/环境类）⇒ `openspec/config.yaml`「本次退休哪一个既有守卫」按其括注不适用。
> 🔴 **`intent.md` 现为 `status: 待确认`**（转写版，非 grill；`#605` 明令不跑 grill）⇒ CI `scene-intent-gate-lint` 对本包报违规属**如实状态**，转 `已确认` 由 Shao Peishen 定。

## Why（为什么做）

付款环节是资金安全高风险区：三单未配齐反复退回、打错收款账户、重复/超额付款靠记忆与 Excel、超合同/暂估价累计无人实时掌握、预付款无单据先打款、付款日期靠人按账期算。FI3 让数字员工在付款申请**审批前**跑完六项校验，输出《通过/拦截清单》给审批人（L3 旁路清单，乙方案），并把每笔判定写平台 `audit`。**错拦一笔烦人，漏拦一笔亏钱**——所以判据一条不猜、主数据缺失不当通过、日历越界不外推。

**立项依据**：全景规划 §2.1.4 FI3 块（v10 2026-09-17 前拉至 2026-09，七子场景同批开工）；队列 §一 `#605`／`#603`／`#602`；Shao Peishen 2026-09-17 答 `1a 2a` 与 `a`。

## What Changes（改什么）

- 新建 `4-数字员工/财务部/FI3-付款申请自动校验/`：`fi3_payment_validation/{config,models,holiday_calendar,checks,validation_engine,feed_source,dashboard,run}.py` ＋ `tests/`（25 passed）＋ `data/mock/` 六表 ＋ `data/holidays/holiday_calendar.csv`（745 行，由 `scripts/build_holiday_calendar.py` 从唐燕萍 2026-08-22 xlsx 搬运，md5 `8e5295e84d310477722b5bfc353e88be`）。
- **R1–R8 逐条以 `Signoff(唐燕萍, 2026-07-10/07-14, 凭据路径)` 登记进底座 `criteria_signoff`**，`RULE_VERSION = fi3-v1-tangyanping-2026-07-10`；引擎无一处写死数字。
- **两项未签认落 `PENDING` 注册表（读即抛）**：账龄预警天数、L4 会签。`AUTOMATION_LEVEL` 恒 `L3` 并由用例守。
- 七子场景：FI3-1 配票前置（消费 FI2 结果）／FI3-2 账户比对／FI3-3 重复付款／FI3-4 超合同与暂估价／FI3-5 预付款分级＋账龄度量／FI3-6 付款日期（账期解析＋节假日顺延）／FI3-7 仪表盘（汇总结构＋Markdown 清单）。

### New Capabilities
- `fi3-validation-engine`：六项校验器 ＋ 四态归类 ＋ R7 特批通道 ＋ audit 留痕。
- `fi3-payment-calendar`：节假日日历数据件与工作日顺延（fail-loud 边界）。
- `fi3-validation-dashboard`：综合校验清单／仪表盘（档 1 Markdown；档 2 门户页 `/finance/fi3`）。

### Modified Capabilities
无。平台 `audit`／`criteria_signoff`／`bootstrap`／`connector_errors` 为消费复用，不改其契约。FI2 只读其结果，不改 FI2。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

**1. 本流程哪些判断是人脑默会经验？** 已全部显性化为 R1–R8（分级／账户变更／查重参数／超合同与暂估价线／预付款档位／账期四类／紧急通道／L4 门槛），见 `config.CRITERIA`。仍在人脑里的两项：预付款账龄预警天数（`FI3-G-01`）、L4 会签流程（`FI3-G-02`）。

**2. 由谁显性化？** 持有人 ＝ **唐燕萍**（财务总监，实名签认人）。🔴 backup 与前置总表 FI3 行的持有人登记**未指派，本包不代指派**（`FI3-G-03`，卡 EE-5 待定项）。

**3. 用什么方法提取？** 已用 **AI 起草·专家批改**（2026-07 三步法，strawman → 唐燕萍圈改 → 回件确认）；上线后以 **L2 改判判例累积**校 R8 的误拦率／漏拦（复用 FI1 `confirm.py` 模式，档 2 接）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位 ＝ 档 1（mock 验证）**：十二张合成申请覆盖四态与六子场景全部分支，`pytest -q --tb=short --maxfail=5` **25 passed**；CLI 出清单＋审计 JSONL。
- **晋档 2（真实数据跑通）条件**：① design 审通过（🟡）；② `feed_source` 接 U9C 五端点（`Supplier/Query`／`Pay/Trace`／`AP/Query`／合同／预付款）＋ FI2 `.51:8094` 结果读取，仍 fail-loud；③ 付款申请单乙方案导出形态与财务侧对齐；④ 真实小样本（脱敏）逐单与人工判定对账。
- **晋档 3（内部服务）**：门户页 `/finance/fi3`（不新起端口）、`.51` 部署＋冒烟＋回滚 SOP、跟进信（串行闸三分支）。
- **晋 L4（自动拦截）**：R8 门槛达标 ＋ **Shao Peishen ＋ CFO 会签**（`PENDING.L4_PROMOTION_COSIGN`）＋ 甲方案 IT 可行性。🔴 本包不代联络。
- **价值指标（风险型为主）**：付款退回率↓80%+；打错账户系统拦截趋零；重复/超额检出 >99%；长账龄预付款↓50%+；审批效率↑60%+（基线由唐燕萍确认）。
- **LLM 判据黄金集**：本场景**不含 LLM 运行时判断**（账期解析为正则四类），黄金集不适用；将来若引入须先补黄金集。

## Impact（影响面）

- **新增**：上述场景目录；`openspec/changes/fi3-payment-validation-mvp/`。
- **底座依赖（消费，不改）**：`criteria_signoff`、`audit`、`bootstrap.ensure_paths`、`shared_tools.connector_errors.RealEndpointNotReadyError`。
- **不接** `data_isolation_layer`：付款/供应商数据属公司自有财务数据，不适用 OEM 隔离。
- **不修改**：FI2 任何文件；队列 `#339`（`[S:timed=2026-10-01]`，其输入件明写「勿提前深读」，本包**刻意未消费**——P2P 四项对照与 L4 会签底稿模板留给该行浮出时做）；任何规划文档。

### 红线核对
| 红线 | 本包状态 |
|---|---|
| mock 先行 | ✅ 只有合成夹具；`u9c` 抛 `RealEndpointNotReadyError`，无回退 |
| audit 留痕 | ✅ 每张申请一条 `AuditEvent`，`decision` 恒带 `rule_version`＋`automation_level`；payload 账号只留尾 4 位 |
| OEM 隔离 | ➖ 不适用 |
| L2/L3 门禁 | ✅ `needs_manual_review` 恒 `True`、`AUTOMATION_LEVEL="L3"` 用例守；AI 不碰钱 |
| ISO 26262 | ➖ 不适用 |

### 伴生文件的 .gitignore 覆盖（强制项，队列 #328 子项②）
本变更新增两种自动生成物：`reports/fi3_checklist.md`／`reports/fi3_audit.jsonl`（CLI 产出）。`git check-ignore -v` 实测：`4-数字员工/财务部/FI3-付款申请自动校验/.gitignore:2:reports/` 命中 `reports/x.md`；`:5:__pycache__/` 命中 `.pyc`。`data/holidays/`、`data/mock/` 为可入库件（公开日历／合成数据），刻意不忽略。

## design 停审点（🟡 Shao Peishen）

见 `design.md` D1–D8。**本包停在档 1**：design 审通过前不接真实库、不部署、不发信。
