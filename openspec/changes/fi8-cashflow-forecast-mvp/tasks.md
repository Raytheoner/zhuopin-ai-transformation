> 🔴 **本包未过 design 审**（🟡 `openspec_design_review`）。§1 已勾选项是本泳道在 🟢 范围内实做的骨架；**§2 起一律不得开工**。
> 📌 **2026-09-03 `OP-0903-D3`（A4 段）**：本包已跑 `/opsx:sync`（delta specs 并入 `openspec/specs/`），并把判据签认迁移到平台底座 `criteria_signoff`——见 §1a。
> 🔴 **`sync` 不是 `apply`**：`sync` 写的是主 specs，`apply` 才是实现 tasks 待办。**design 审仍未过，§2 起照旧不得开工。**

## 1. 工程骨架（🟢，本泳道已完成）

- [x] 1.1 建 `4-数字员工/财务部/FI8-现金流预测与智能预警/` 与 `pyproject.toml`
- [x] 1.2 `tests/conftest.py` 用 `bootstrap.ensure_paths` 唯一样板 ＋ `strict=True`
- [x] 1.3 `models.py` 定形六个契约：`ReceivablePlan` / `PayablePlan` / `PaymentHistory` / `OpeningBalance` / `WeeklyCashflow` / `GapWindow` / `WhatIfScenario`
- [x] 1.4 `PaymentHistory.delay_days` 纯派生量实现 ＋ 用例（日期不可解析返回 `None` 而**非 0**——0 会被下游当成"按期回款"）
- [x] 1.5 `config.py` 三项未签认判据落 `None` ＋ 用例守
- [x] 1.6 🔴 `BANK_BALANCE_ACCESS` **单独**落空 ＋ **独立**用例守（权限缺口，与判据缺口性质不同）
- [x] 1.7 `OpeningBalance.source` 骨架期只允许 `"synthetic"` ＋ 用例守
- [x] 1.8 `WhatIfScenario.is_hypothetical` 恒真 ＋ 用例守
- [x] 1.9 `GapWindow.confirmed_by_cfo` 默认 `False` ＋ 用例守
- [x] 1.10 🔗 `O2_SHORTAGE_SEMANTICS` 引自 `kit_engine.calc_shortage`（含 B6 `missing_snapshot`）＋ 用例守住"引自"
- [x] 1.11 `data/mock/` 四张合成 CSV ＋ README（**不含任何预测结果基准**）
- [x] 1.12 `pytest tests/ -q` 全绿（12 passed）
- [x] 1.13 `git check-ignore -v` 实测四类自动生成物均被忽略

## 1a. 判据签认迁移 ＋ specs sync（A4 段 · `OP-0903-D3` / 看护批 `B-0903_50`，2026-09-03 已完成）

> 本节是 `criteria-signoff-platform` 变更包 §4「A4 段：五场景迁移」在本包这一侧的落点。
> 🔴 **迁移未改变任何行为**：未签认判据的值仍恒为空、读取仍抛、仍无 `default` 旁路；变的只是这条纪律**写在哪**（五份手抄 → 底座一份）。

- [x] 1a.1 `config.py` 的裸 `None` 判据常量改为 `zhuopin_platform.criteria_signoff.CriteriaRegistry` 声明（`CRITERIA`），并在模块级调 `CRITERIA.assert_rule_version(RULE_VERSION)`（**导入期**即双向校验版本号与签认状态）
- [x] 1a.2 删 `test_unsigned_criteria_stay_none` ＋ `test_rule_version_marked_unsigned`（`criteria-signoff-platform` tasks 4.2），改为 `test_criteria_registry_declares_exactly_these` ／ `test_criteria_registry_all_unsigned` ／ `test_rule_version_consistent_with_signoff_state`
  🔴 **§1 里对旧用例名的引用是历史记录，不追改**；现行用例名以本行为准
- [x] 1a.3 🔴 **`G-5` 反向依赖落地**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`）：本包新增 `config.audit_decision(**fields)`，构造写审计的 `decision` 时**恒带当时生效的 `RULE_VERSION`**；用例 `test_audit_decision_carries_rule_version` 拿真的 `AuditEvent` 断言。**依赖方向 ＝ 审计日志指向判据版本，不是判据模块去写日志**；底座侧净变化为零（`grep -r "audit" criteria_signoff/` 可执行代码 **0 命中**，已实测）
- [x] 1a.4 `/opsx:sync` 跑过 —— 本包 delta specs 已并入 `openspec/specs/`（🔴 **`sync` 不是 `apply`**：`apply` ＝ 实现 tasks 待办，本包 §2 起仍不得开工）
- [x] 1a.5 迁移清点：本包 **3** 条判据，迁移前后均**未签认**（`CASH_GAP_THRESHOLD` / `COLLECTION_ESCALATION_CRITERIA` / `PAYMENT_CYCLE_SAMPLING`）
- [x] 1a.6 🔴 **`G-2 = (a)`：`BANK_BALANCE_ACCESS` 原样留在本包、未并入注册表**（**权限缺口**，靠 CFO 办公室审批解除，不靠财务侧签认解除）。新增 `test_bank_balance_access_is_not_a_criterion` 守住这个"没有"
- [x] 1a.7 🔴 **`EE-2` 落档**（Shao Peishen 2026-09-03）：银行余额取数授权**由他本人推**；本包只做**不依赖余额的部分**，**不得绕过**（绕过的形态不止"填个数"，还包括"拿期初余额推算""拿 0 顶上"）。已写进 `BANK_BALANCE_NOT_AUTHORIZED` 与 `fi8-forecast-engine` spec 两处场景

## 2. 🔴 design 收口（未全部关闭不得进 §3）

- [ ] 2.1 收口-1（**最要紧，权限非判据**）：银行账户余额是否可取、以何方式取 —— 财务侧 ＋ **CFO 办公室**明确并落档；走替代方案（期初＋流水推算）者，**替代方案本身也须 CFO 签认**
- [ ] 2.2 收口-2：三项判据财务侧实名签认（缺口门限须 CFO 办公室参与）⚠️ 需唐燕萍确认者 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得单起一封信**
- [ ] 2.3 收口-3（🔗 L8）：收入递延口径与 `O2` 缺口口径精确对应，**`missing_snapshot` 那一支必须显式处理**（`kit_engine` docstring 明写真实切换后必踩）——跨域口径，须 O2 侧一并确认
- [ ] 2.4 收口-4：what-if 与基线在报表/门户上的**呈现侧**区隔规矩（数据侧已由 `is_hypothetical` 锁住）
- [x] 2.5 收口-5：**跨五场景** `criteria_signoff` 是否提升进平台底座（rule-of-three 已触发）⇒ ✅ **已裁并已落地**（Shao Peishen 2026-09-03 拍板 `EE-1 = (a)` 收进底座）：平台底座 `zhuopin_platform.criteria_signoff` 已建成并合入 master（变更包 `criteria-signoff-platform`）；本包已于 A4 段迁移完毕，见 §1a。**本条不再需要收口。**
- [ ] 2.6 判据持有人 ＋ backup 实名指定（🔴 大概率须含 CFO 办公室），登记进前置总表 §一.2（该表**现无 FI8 行**）
- [ ] 2.7 确认本场景是否含 LLM 运行时判断（如自然语言 what-if 解析）；含则须起黄金集

## 3. forecast-engine 滚动预测（design 审后，先测后实现）

- [ ] 3.1 写测试：未授权取银行余额时 fail-loud，**不以 0 或推算值继续**
- [ ] 3.2 写测试：`PAYMENT_CYCLE_SAMPLING` 为空时 fail-loud
- [ ] 3.3 写测试：4/8/12 三视界各自的逐周序列（周分桶边界、跨月、跨年）
- [ ] 3.4 写测试：分客户回款分布落账（含历史样本不足的客户如何处理）
- [ ] 3.5 写测试：🔗 L8 收入递延——`missing_snapshot` 分支不得当作缺口为 0
- [ ] 3.6 实现预测引擎（纯函数为主，口径全从 config 读）
- [ ] 3.7 单测全绿

## 4. gap-alerting 缺口高亮 ＋ 催收 escalation（design 审后，先测后实现）

- [ ] 4.1 写测试：两项门限为空时各自 fail-loud（既不默认触发也不默认不触发）
- [ ] 4.2 写测试：缺口窗口识别（连续负余额、单点触底、窗口合并）
- [ ] 4.3 写测试：AI 不自行发起资金调度
- [ ] 4.4 实现催收推送（复用 `shared_tools.notifiers`，**不自建通道**）
- [ ] 4.5 每次判定写平台 `audit`
- [ ] 4.6 单测全绿

## 5. whatif-engine what-if 影响分析（design 审后，先测后实现）

- [ ] 5.1 写测试：情景叠加后的差异计算与缺口窗口增删
- [ ] 5.2 写测试：`is_hypothetical` 不可关闭；结果可追溯到 `baseline_ref`
- [ ] 5.3 实现 what-if 引擎
- [ ] 5.4 单测全绿

## 6. 收口（不在本包，登记以免遗漏）

- [ ] 6.1 场景 `CLAUDE.md` 六段式（根 `CLAUDE.md` §5 第 6 步）
- [ ] 6.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi8` ＋ 预留网关 auth 接入点
- [ ] 6.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
