> 🔴 **本包 design 审 🟡 待 Shao Peishen**。§1／§2 为档 1 范围（`#605` 期望产出＝骨架＋包＋档 1 mock 全绿），本泳道已完成；**§3 起（真实数据／部署／L4）design 审通过前一条都不得动手**。
> 🔴 停在档 1：L3→L4 晋级须 Shao Peishen ＋ CFO 会签，本包不代联络 CFO 办公室。

## 1. 工程骨架（🟢，本泳道已完成，commit `6df5926`）

- [x] 1.1 建 `4-数字员工/财务部/FI3-付款申请自动校验/` 与 `pyproject.toml`（包名 `fi3-payment-validation`）
- [x] 1.2 `tests/conftest.py`／`run.py` 用 `bootstrap.ensure_paths` 唯一样板（conftest `strict=True`）；`工具-引导样板lint.py` 对本目录零命中
- [x] 1.3 `config.py`：R1–R8 逐条 `Criterion.signed(值, Signoff(唐燕萍, 2026-07-10／R1 07-14, 凭据))` 入 `criteria_signoff`；`RULE_VERSION=fi3-v1-tangyanping-2026-07-10` 导入期校验
- [x] 1.4 `config.PENDING`：`PREPAY_AGEING_WARN_DAYS`／`L4_PROMOTION_COSIGN` 未签认读即抛；`AUTOMATION_LEVEL="L3"` 用例守
- [x] 1.5 `models.py` 定形七个契约 ＋ `mask_account` 尾 4 位脱敏
- [x] 1.6 节假日日历落档：`scripts/build_holiday_calendar.py` 从唐燕萍 2026-08-22 xlsx 搬运 → `data/holidays/holiday_calendar.csv` 745 行（源 md5 `8e5295e84d310477722b5bfc353e88be`；分布 495/172/61/17、是 512/否 233 与就绪包 §一 逐项相符）
- [x] 1.7 `data/mock/` 六表合成夹具 ＋ README（基准日 2026-09-17）
- [x] 1.8 `.gitignore`（`reports/`／`__pycache__/`，`git check-ignore -v` 实测命中）

## 2. 档 1 mock 引擎（🟢，先测后实现，本泳道已完成）

- [x] 2.1 `holiday_calendar.py`：直查 `是否工作日`；`roll_to_workday`／`add_workdays`；越界 `CalendarOutOfRangeError`（用例 4 条）
- [x] 2.2 FI3-1 `check_three_way_match`：消费 FI2 结果，未配齐＝拦截（D1）
- [x] 2.3 FI3-2 `check_account`：三字段比对／30 天并行窗口／新账户首用提醒／无主数据＝拦截（D2）
- [x] 2.4 FI3-3 `check_duplicate`：发票级累计超额拦截／±3 天同额疑似提醒／未扣回预付款提醒
- [x] 2.5 FI3-4 `check_contract_cap`：含税累计 vs 上限／框架汇总（D5）／暂估价 30% 预警 50% 拦截／合同缺记录＝拦截
- [x] 2.6 FI3-5 `check_prepayment`：R5 四档单据支撑与审批人；`prepay_ageing` 只出度量
- [x] 2.7 FI3-6 `compute_due_date`：R6 四类正则解析（D6）＋ 节假日顺延；解析不出＝提醒
- [x] 2.8 `validation_engine.validate`：四态归类；R7 特批只豁免 FI3-1（D3），补齐期限按工作日；《未匹配付款跟踪清单》
- [x] 2.9 审计：每张申请一条 `AuditEvent`，`decision` 恒带 `rule_version`＋`automation_level`，payload 无原始账号（D8）
- [x] 2.10 FI3-7 `dashboard.summarize`／`render_markdown` ＋ `run.py` CLI
- [x] 2.11 `feed_source`：mock 装载；`u9c` 抛 `RealEndpointNotReadyError` 不回退
- [x] 2.12 `pytest -q --tb=short --maxfail=5` **25 passed**（十二张申请四态与子场景命中逐张断言）
- [x] 2.13 `intent.md`（转写版，`status: 待确认`）＋ 场景 `CLAUDE.md` 六段式

## 2bis. design 审

- [x] 2b.1 🟡 **design 审 ＝ ✅ 已通过**（Shao Peishen 2026-09-17 答 `1a`，D1–D8 整表通过、无驳回）⇒ §3 收口闸解除
- [x] 2b.2 `intent.md` `status` 转 `已确认`（答 `2a`，认可转写版、不补跑 grill）⇒ CI `scene-intent-gate-lint --enforce` 对本包转绿

## 3. 🔴 design 审收口（未全部关闭不得进 §4）

- [ ] 3.1 Shao Peishen 审 D1–D8（🟡）
- [ ] 3.2 `intent.md` `status` 转 `已确认`（Shao Peishen）⇒ CI `scene-intent-gate-lint` 对本包转绿
- [ ] 3.3 `FI3-G-01` 账龄预警天数 → 并进下一封财务信（唐燕萍串行闸，现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，不单起一封）
- [ ] 3.4 `FI3-G-03` 判据持有人／backup 登记前置总表 FI3 行（人事，不代指派）
- [ ] 3.5 付款申请单乙方案导出字段形态与财务侧对表

## 4. 档 2 真实数据跑通（design 审后；🔴 LAN 依赖，本机 off-LAN 留步）

- [ ] 4.1 `feed_source` 接 U9C 五端点（`Supplier/Query`／`Pay/Trace`／`AP/Query`／合同／预付款）＋ FI2 `.51:8094` 结果，仍 fail-loud
- [ ] 4.2 脱敏真实小样本逐单与人工判定对账，差异归因
- [ ] 4.3 `#339` 浮出（`[S:timed=2026-10-01]`）后：P2P 四项对照写进 design ＋ 汉化 L4 会签证据底稿模板（🔴 本包刻意未提前消费）

## 5. 档 3 内部服务（design 审后）

- [ ] 5.1 门户页 `/finance/fi3`（不新起端口，预留网关 auth 接入点）
- [ ] 5.2 `.51` 部署＋冒烟＋回滚 SOP；场景 CLAUDE.md 补「部署状态」段
- [ ] 5.3 第 8 步跟进信（串行闸三分支＋发送三条硬前置）

## 6. L4 晋级（R8 门槛达标后）

- [ ] 6.1 L3 跑 ≥2 个月、误拦 <2%、漏拦 0 重大（判例采集复用 FI1 `confirm.py` 模式）
- [ ] 6.2 甲方案（U9C 审批流内嵌）IT 可行性
- [ ] 6.3 🔴 **Shao Peishen ＋ CFO 会签落档** → `PENDING.L4_PROMOTION_COSIGN.signed(...)` → `AUTOMATION_LEVEL` 升 L4
