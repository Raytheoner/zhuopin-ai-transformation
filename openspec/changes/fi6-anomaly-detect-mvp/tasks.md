> 🔴 **本包未过 design 审**（🟡 `openspec_design_review`，须 Shao Peishen 拍板）。§1 已勾选项是本泳道在 🟢 范围内实做的骨架；**§2 起一律不得开工**。
> 📌 **2026-09-03 `OP-0903-D3`（A4 段）**：本包已跑 `/opsx:sync`（delta specs 并入 `openspec/specs/`），并把判据签认迁移到平台底座 `criteria_signoff`——见 §1a。
> 🔴 **`sync` 不是 `apply`**：`sync` 写的是主 specs，`apply` 才是实现 tasks 待办。**design 审仍未过，§2 起照旧不得开工。**

## 1. 工程骨架（🟢，本泳道已完成）

- [x] 1.1 建 `4-数字员工/财务部/FI6-异常交易实时检测/` 与 `pyproject.toml`（包名 `fi6-anomaly-detect`）
- [x] 1.2 `tests/conftest.py` 用 `bootstrap.ensure_paths` 唯一样板 ＋ `strict=True`
- [x] 1.3 `models.py` 定形五个契约：`Transaction` / `PartyProfile` / `HistoryBaseline` / `AnomalyFinding` / `CaseRecord`
- [x] 1.4 `AnomalyFinding.needs_manual_review` 默认 `True`、`escalated` 默认 `False` ＋ 用例守
- [x] 1.5 🔴 `PartyProfile` **不含**任何"是否关联方"字段 ＋ 用例守住这个"没有"
- [x] 1.6 `CaseRecord.confirmed_by` 无默认值（必填实名）＋ 用例守
- [x] 1.7 `config.py` 四项未签认判据落 `None`，不给默认数 ＋ 用例守
- [x] 1.8 两处「本项目内不存在」落成常量并由用例守：`CASE_LIBRARY_ABSENT`、`FI3_NO_ENTITY`
- [x] 1.9 `data/mock/` 三张合成 CSV ＋ README（🔴 **刻意不给异常标签**，理由见 README）
- [x] 1.10 `pytest tests/ -q` 全绿（10 passed）
- [x] 1.11 `git check-ignore -v` 实测四类自动生成物均被忽略

## 1a. 判据签认迁移 ＋ specs sync（A4 段 · `OP-0903-D3` / 看护批 `B-0903_50`，2026-09-03 已完成）

> 本节是 `criteria-signoff-platform` 变更包 §4「A4 段：五场景迁移」在本包这一侧的落点。
> 🔴 **迁移未改变任何行为**：未签认判据的值仍恒为空、读取仍抛、仍无 `default` 旁路；变的只是这条纪律**写在哪**（五份手抄 → 底座一份）。

- [x] 1a.1 `config.py` 的裸 `None` 判据常量改为 `zhuopin_platform.criteria_signoff.CriteriaRegistry` 声明（`CRITERIA`），并在模块级调 `CRITERIA.assert_rule_version(RULE_VERSION)`（**导入期**即双向校验版本号与签认状态）
- [x] 1a.2 删 `test_unsigned_criteria_stay_none` ＋ `test_rule_version_marked_unsigned`（`criteria-signoff-platform` tasks 4.2），改为 `test_criteria_registry_declares_exactly_these` ／ `test_criteria_registry_all_unsigned` ／ `test_rule_version_consistent_with_signoff_state`
  🔴 **§1 里对旧用例名的引用是历史记录，不追改**；现行用例名以本行为准
- [x] 1a.3 🔴 **`G-5` 反向依赖落地**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`）：本包新增 `config.audit_decision(**fields)`，构造写审计的 `decision` 时**恒带当时生效的 `RULE_VERSION`**；用例 `test_audit_decision_carries_rule_version` 拿真的 `AuditEvent` 断言。**依赖方向 ＝ 审计日志指向判据版本，不是判据模块去写日志**；底座侧净变化为零（`grep -r "audit" criteria_signoff/` 可执行代码 **0 命中**，已实测）
- [x] 1a.4 `/opsx:sync` 跑过 —— 本包 delta specs 已并入 `openspec/specs/`（🔴 **`sync` 不是 `apply`**：`apply` ＝ 实现 tasks 待办，本包 §2 起仍不得开工）
- [x] 1a.5 迁移清点：本包 **4** 条判据，迁移前后均**未签认**（`AMOUNT_SURGE_CRITERIA` / `FREQUENCY_ANOMALY_CRITERIA` / `RELATED_PARTY_CRITERIA` / `L2_ESCALATION_CRITERIA`）；`config.py` 内**零**裸 `None` 判据常量残留（`criteria-signoff-platform` tasks 4.3／4.4）

## 2. 🔴 design 收口（未全部关闭不得进 §3）

- [ ] 2.1 收口-1：财务侧交付并实名签认四项判据（金额突增／频率异常／关联方／升级门限）⚠️ 需唐燕萍确认者 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得单起一封信**
- [ ] 2.2 收口-2：**关联方定义单独走一次专家工作坊**（定义题，非经验题）
- [ ] 2.3 收口-3：与 IT 定"实时"的实时程度（逐笔触发／分钟级轮询），并核实 U9C 应付/应收流水取数能力（**批量导出不等于满足"实时"**）
- [ ] 2.4 收口-4：与 `FI3` 的接口形状——现在定契约位还是等其落地？（🔴 FI3 目前无工程实体，本泳道 2026-09-03 实测）
- [ ] 2.5 收口-5：案例库载体（存哪／谁维护／如何进回归）
- [x] 2.6 收口-6：**跨五场景** `criteria_signoff` 是否提升进平台底座（rule-of-three 已触发）⇒ ✅ **已裁并已落地**（Shao Peishen 2026-09-03 拍板 `EE-1 = (a)` 收进底座）：平台底座 `zhuopin_platform.criteria_signoff` 已建成并合入 master（变更包 `criteria-signoff-platform`）；本包已于 A4 段迁移完毕，见 §1a。**本条不再需要收口。**
- [ ] 2.7 判据持有人 ＋ backup 实名指定，登记进前置总表 §一.2（该表**现无 FI6 行**，缺行已交全景路线图线）

## 3. pattern-detectors 三类模式检测器（design 审后，先测后实现）

- [ ] 3.1 写测试：判据为空时三个检测器各自 fail-loud，不回退任何统计经验值
- [ ] 3.2 写测试：金额突增（命中／未命中／历史样本不足）
- [ ] 3.3 写测试：频率异常（窗口边界、月结集中开票这类正常波峰不得误报）
- [ ] 3.4 写测试：关联方（命中依据字段可追溯；主数据缺字段时标需人工而非放行）
- [ ] 3.5 写测试：🔴 历史基线缺失/案例库为空时 **MUST NOT 以「无历史即正常」放行**
- [ ] 3.6 实现三检测器（口径全部从 config 读，不写死）
- [ ] 3.7 单测全绿

## 4. case-library 可疑交易案例库（design 审后，先测后实现）

- [ ] 4.1 写测试：判例必填实名；匿名判例不得进回归基准
- [ ] 4.2 写测试：判例记录 `RULE_VERSION`，规则升版后可回溯旧口径结论
- [ ] 4.3 实现判例采集（**复用 FI1 `fi1/confirm.py` 已落地的 L2 判例采集模式，不另立一套**）
- [ ] 4.4 实现误报率回看
- [ ] 4.5 单测全绿

## 5. escalation-and-report 升级推送 ＋ 月度分析（design 审后，先测后实现）

- [ ] 5.1 写测试：门限为空时 fail-loud（既不默认推、也不默认不推）
- [ ] 5.2 写测试：AI 不自行处置任何交易
- [ ] 5.3 实现推送（复用 `shared_tools.notifiers`，**不自建通道**）
- [ ] 5.4 每笔判定写平台 `audit`（append-only，3 年）
- [ ] 5.5 实现月度报告：🔴 须**聚合出系统性漏洞**，不是罗列个案（这是本场景更值钱的一半）
- [ ] 5.6 报告标注「AI 分析建议，处置在财务主管」
- [ ] 5.7 单测全绿

## 6. 收口（不在本包，登记以免遗漏）

- [ ] 6.1 场景 `CLAUDE.md` 六段式（根 `CLAUDE.md` §5 第 6 步）
- [ ] 6.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi6` ＋ 预留网关 auth 接入点
- [ ] 6.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
