> 🔴 **本包未过 design 审**（`openspec_design_review` ＝ 🟡，须 Shao Peishen 拍板）。下方 §1 已勾选项是本泳道在 🟢 范围内实际做完的骨架；**§2 起一律不得开工**——按根 `CLAUDE.md` §5 第 3-4 步，design 审通过后才走 `/opsx:apply`。

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

## 2. 🔴 design 收口（apply 前必须全部关闭；未关闭即不得进 §3）

- [ ] 2.1 收口-1：财务侧交付并**实名签认**四项判据（差旅标准／招待限额／超预算阈值／风险分级边界）⚠️ 若需唐燕萍确认 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得为此单起一封信**
- [ ] 2.2 收口-2：四项判据的持有人 ＋ backup 实名指定，登记进《跨场景前置数据与知识库任务总表》§一.2
- [ ] 2.3 收口-3：IT 核实 U9C 报销模块端点是否在既有 10 个财务侧端点内（**不得假设存在**）
- [ ] 2.4 收口-4：发票号字面一致性实测（位数／前导零／空格／全半角／代码前缀）→ 定 join 键。**不得沿用 FI2 后 8 位方案**
- [ ] 2.5 收口-5：报销发票 OCR 精度实测（不沿用 FI2 65.8%，也不沿用「与本次无关」直接判可用）
- [ ] 2.6 收口-6：**跨五场景**——是否在平台底座新增 `criteria_signoff` 模块（rule-of-three 已触发，5 个财务场景同需）。拍板前五场景各留一份本地实现
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
