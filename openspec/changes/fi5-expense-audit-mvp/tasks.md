> 🔴 **本包未过 design 审**（`openspec_design_review` ＝ 🟡，须 Shao Peishen 拍板）。下方 §1 已勾选项是本泳道在 🟢 范围内实际做完的骨架；**§2 起一律不得开工**——按根 `CLAUDE.md` §5 第 3-4 步，design 审通过后才走 `/opsx:apply`。
> 📌 **2026-09-03 `OP-0903-D3`（A4 段）**：本包已跑 `/opsx:sync`（delta specs 并入 `openspec/specs/`），并把判据签认迁移到平台底座 `criteria_signoff`——见 §1a。
> 🔴 **`sync` 不是 `apply`**：`sync` 写的是主 specs，`apply` 才是实现 tasks 待办。**design 审仍未过，§2 起照旧不得开工。**

## 1. 工程骨架（🟢 `worktree_local_build`＋`unit_regression_tests`，本泳道已完成）

- [x] 1.1 建 `4-数字员工/财务部/FI5-费用报销智能审核/` 目录与 `pyproject.toml`（包名 `fi5-expense-audit`，deps ＝ `zhuopin_platform` ＋ `pydantic>=2.0`）
- [x] 1.2 `tests/conftest.py` 用 `bootstrap.ensure_paths` **唯一被允许的样板** ＋ `strict=True`（未内联任何自研引导，`工具-引导样板lint.py` 判据）
- [x] 1.3 `fi5_expense_audit/models.py` 定形四个契约：`ExpenseClaim` / `ExpenseLine` / `BudgetBalance` / `AuditFinding`
- [x] 1.4 `AuditFinding.needs_manual_review` 默认 `True`（L2 默认侧＝需人工，放行须被判据显式证成）＋ 用例守住
- [x] 1.5 `fi5_expense_audit/config.py` 四项未签认判据落成 `None`，**不给默认数**
- [x] 1.6 `tests/test_scaffold.py::test_unsigned_criteria_stay_none` —— 谁填了数 CI 立刻红
- [x] 1.7 `data/mock/` 三张合成 CSV ＋ README（🔴 无任何真实报销/发票数据；`invoice_no` 刻意写成 14 位带前导零，提示 join 键须实测）
- [x] 1.8 `pytest tests/ -q` 全绿（8 passed）
- [x] 1.9 `git check-ignore -v` 实测四类自动生成物均已被忽略（见 proposal §伴生文件）

## 1a. 判据签认迁移 ＋ specs sync（A4 段 · `OP-0903-D3` / 看护批 `B-0903_50`，2026-09-03 已完成）

> 本节是 `criteria-signoff-platform` 变更包 §4「A4 段：五场景迁移」在本包这一侧的落点。
> 🔴 **迁移未改变任何行为**：未签认判据的值仍恒为空、读取仍抛、仍无 `default` 旁路；变的只是这条纪律**写在哪**（五份手抄 → 底座一份）。

- [x] 1a.1 `config.py` 的裸 `None` 判据常量改为 `zhuopin_platform.criteria_signoff.CriteriaRegistry` 声明（`CRITERIA`），并在模块级调 `CRITERIA.assert_rule_version(RULE_VERSION)`（**导入期**即双向校验版本号与签认状态）
- [x] 1a.2 删 `test_unsigned_criteria_stay_none` ＋ `test_rule_version_marked_unsigned`（`criteria-signoff-platform` tasks 4.2），改为 `test_criteria_registry_declares_exactly_these` ／ `test_criteria_registry_all_unsigned` ／ `test_rule_version_consistent_with_signoff_state`
  🔴 **§1 里对旧用例名的引用是历史记录，不追改**；现行用例名以本行为准
- [x] 1a.3 🔴 **`G-5` 反向依赖落地**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`）：本包新增 `config.audit_decision(**fields)`，构造写审计的 `decision` 时**恒带当时生效的 `RULE_VERSION`**；用例 `test_audit_decision_carries_rule_version` 拿真的 `AuditEvent` 断言。**依赖方向 ＝ 审计日志指向判据版本，不是判据模块去写日志**；底座侧净变化为零（`grep -r "audit" criteria_signoff/` 可执行代码 **0 命中**，已实测）
- [x] 1a.4 `/opsx:sync` 跑过 —— 本包 delta specs 已并入 `openspec/specs/`（🔴 **`sync` 不是 `apply`**：`apply` ＝ 实现 tasks 待办，本包 §2 起仍不得开工）
- [x] 1a.5 迁移清点：本包 **4** 条判据，迁移前后均**未签认**（`TRAVEL_STANDARD_TABLE` / `ENTERTAINMENT_LIMIT_TABLE` / `L2_BUDGET_BLOCK_PCT` / `RISK_GRADE_BOUNDARIES`）；`config.py` 内**零**裸 `None` 判据常量残留（`criteria-signoff-platform` tasks 4.3／4.4）

## 2. 🔴 design 收口（apply 前必须全部关闭；未关闭即不得进 §3）

- [ ] 2.1 收口-1：财务侧交付并**实名签认**四项判据（差旅标准／招待限额／超预算阈值／风险分级边界）⚠️ 若需唐燕萍确认 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得为此单起一封信**
- [ ] 2.2 收口-2：四项判据的持有人 ＋ backup 实名指定，登记进《跨场景前置数据与知识库任务总表》§一.2
- [ ] 2.3 收口-3：IT 核实 U9C 报销模块端点是否在既有 10 个财务侧端点内（**不得假设存在**）
- [ ] 2.4 收口-4：发票号字面一致性实测（位数／前导零／空格／全半角／代码前缀）→ 定 join 键。**不得沿用 FI2 后 8 位方案**
- [ ] 2.5 收口-5：报销发票 OCR 精度实测（不沿用 FI2 65.8%，也不沿用「与本次无关」直接判可用）
- [x] 2.6 收口-6：**跨五场景**——是否在平台底座新增 `criteria_signoff` 模块（rule-of-three 已触发，5 个财务场景同需）。⇒ ✅ **已裁并已落地**（Shao Peishen 2026-09-03 拍板 `EE-1 = (a)` 收进底座）：平台底座 `zhuopin_platform.criteria_signoff` 已建成并合入 master（变更包 `criteria-signoff-platform`）；本包已于 A4 段迁移完毕，见 §1a。**本条不再需要收口。**
- [ ] 2.7 前置总表缺 `FI5` 行一事已交全景路线图线（本包只登记、不代补）

## 3. policy-rules 报销政策规则引擎（design 审后，先测后实现）

- [ ] 3.1 写测试：判据为 `None` 时引擎 **fail-loud**，不得回退任何内置数
- [ ] 3.2 设计规则注册表结构 `{规则ID, 条件, 结论, 严重度, 是否触发 L2}` ＋ 版本号（仿 FI1 `variance_classify` 与 QD-B rule registry，**不另立一套**）
- [ ] 3.3 写测试：差旅标准判定（职级 × 住宿上限 × 夜数；边界值、缺职级、跨档）
- [ ] 3.4 写测试：招待限额判定（人均 ＝ 金额/人数；人数为 0、人数缺失、场合类型未登记）
- [ ] 3.5 实现规则引擎 ＋ `RULE_VERSION` 登记（判据不写死在代码里）
- [ ] 3.6 引擎单测全绿

## 4. budget-guard 预算余额与超预算拦截（design 审后，先测后实现）

- [ ] 4.1 写测试：余额计算（`budget − used`）、期间/科目/部门三键缺任一时的行为
- [ ] 4.2 写测试：阈值为 `None` 时 fail-loud
- [ ] 4.3 写测试：拦截发生在**提交时**而非月末（这是本场景的价值点，须有用例锁住）
- [ ] 4.4 实现拦截判定 ＋ 通知上级（复用 `zhuopin_platform.shared_tools.notifiers`，**不自建通道**）
- [ ] 4.5 单测全绿

## 5. risk-grading 异常报销风险分级（design 审后，先测后实现）

- [ ] 5.1 写测试：三类异常各自的判定（超标／频繁／关联交易）＋ 边界未签认时 fail-loud
- [ ] 5.2 🔴 「关联交易识别」若落在 LLM 侧 ⇒ 须同步起黄金集（冻结输入 ＋ 专家认可输出），**无黄金集不晋档 3**
- [ ] 5.3 实现分级引擎（边界从 `config` 读，不写死）
- [ ] 5.4 单测全绿

## 6. expense-report 部门费用分析 ＋ L2 门禁 ＋ audit（design 审后，先测后实现）

- [ ] 6.1 写测试：部门 × 科目 × 期间聚合口径
- [ ] 6.2 写测试：`needs_manual_review=True` 的行**一律不自动结案**
- [ ] 6.3 每笔判定写平台 `audit`（append-only，3 年留存）
- [ ] 6.4 报告标注「AI 初审建议，结案在财务经理」
- [ ] 6.5 单测全绿

## 7. 收口（不在本包，登记以免遗漏）

- [ ] 7.1 场景 `CLAUDE.md` 六段式（定位/决策/底座/红线/时间线/依赖）—— 根 `CLAUDE.md` §5 第 6 步
- [ ] 7.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi5` 并预留网关 auth 接入点（Shao Peishen 2026-07-29 硬约束，增量必须当天止住）
- [ ] 7.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
