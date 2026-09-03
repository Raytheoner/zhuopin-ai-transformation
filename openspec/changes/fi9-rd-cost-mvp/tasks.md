> 🔴 **本包未过 design 审**（🟡 `openspec_design_review`）。§1 已勾选项是本泳道在 🟢 范围内实做的骨架；**§2 起一律不得开工**。
> 📌 **2026-09-03 `OP-0903-D3`（A4 段）**：本包已跑 `/opsx:sync`，并把判据签认迁移到平台底座 `criteria_signoff`——见 §1a。
> 🔴 **`sync` 不是 `apply`**：`sync` 写的是主 specs，`apply` 才是实现 tasks 待办。**design 审仍未过，§2 起照旧不得开工。**
> ⏳ **本包另有一份 `design.md`，是只覆盖 `2.4`（`EE-3` OEM 项目标识接法）的局部件，待 Shao Peishen 裁**——它**不代表整包 design 审已通过**，§2 另有六条收口项尚未起草。

## 1. 工程骨架（🟢，本泳道已完成）

- [x] 1.1 建 `4-数字员工/财务部/FI9-研发费用归集与高新认定/` 与 `pyproject.toml`
- [x] 1.2 `tests/conftest.py` 用 `bootstrap.ensure_paths` 唯一样板 ＋ `strict=True`
- [x] 1.3 `models.py` 定形五个契约：`RdProject` / `CostEntry` / `LaborRecord` / `CapitalizationVerdict` / `AuxLedgerRow`
- [x] 1.4 🔴 `CapitalizationVerdict.is_external_ready` 恒假（无置真路径）＋ 用例守
- [x] 1.5 🔴 `AuxLedgerRow.disclaimer` **无默认值**（必填）＋ 用例守
- [x] 1.6 `RdProject.is_high_tech_scope` 默认 `None`（未判）而非 `False`（判了不纳入）＋ 用例守
- [x] 1.7 `config.py` 三项未签认判据落 `None` ＋ 用例守；`LaborRecord.rate` 同
- [x] 1.8 🔴 `TIMESHEET_SYSTEM_EXISTS` 单独落空 ＋ 独立用例守（**存在性**未核实，非"还没接"）
- [x] 1.9 `EXTERNAL_FILING_GATE` 对外材料红线落成常量 ＋ 用例守
- [x] 1.10 发票号 join 纪律写进 `models.py` docstring ＋ 用例守
- [x] 1.11 `data/mock/` 三张合成 CSV ＋ README（🔴 **不打标准答案判定**，`is_high_tech_scope` 全空亦刻意）
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
- [x] 1a.5 迁移清点：本包 **3** 条判据，迁移前后均**未签认**（`CAPITALIZATION_CRITERIA` / `HIGH_TECH_POLICY_LIBRARY` / `RD_RATIO_DEFINITION`）
- [x] 1a.6 🔴 **`G-2 = (a)`：`TIMESHEET_SYSTEM_EXISTS` 原样留在本包、未并入注册表**（**存在性未核实**，靠去核实一次解除，已独立立行队列 §一 `#477`）。新增 `test_timesheet_existence_is_not_a_criterion` 守住这个"没有"
- [x] 1a.7 ⏳ **`EE-3` 起草完毕、`pause` 待裁**（Shao Peishen 2026-09-03 已裁「**会**带出 OEM 项目标识，按接 `data_isolation_layer` 设计」，但**接法**命中 openspec 门槛②「涉鉴权与数据可见性」⇒ 须单独走 design 审）：
  - 已起草 `design.md`（**局部件**，只覆盖 `2.4`，不代表整包 design 审通过），含 **5 条定夺项**，🔴 **一条都未默认生效**
  - 已在 `config.py` 落 `OEM_PROJECT_SCOPE_PENDING_DESIGN` ＋ 用例守——防后来者按其余财务场景「财务数据不隔离」的结论把本场景顺手归并进去
  - 🔴 **本泳道未实现任何隔离层接线、未新增任何带 OEM 归属的字段**

## 2. 🔴 design 收口（未全部关闭不得进 §3）

- [ ] 2.1 收口-1（**最先做**）：核实工时系统是否存在／由谁维护／能否取数。不存在则由财务/研发侧明确人工费用替代归集方式**并签认**（**不得由实现方自选分摊法**）
- [ ] 2.2 收口-2：四项判据财务 ＋ **研发侧**主笔实名签认（资本化判据／高新政策库／研发费用占比口径／工时单价）。🔴 **占比口径特别留意：准则口径与高新口径分子分母不一致，混用即出错** ⚠️ 需唐燕萍确认者 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得单起一封信**
- [ ] 2.3 收口-3：对外门禁的**流程侧**规矩（谁审、审什么、留什么痕）——数据侧已锁
- [ ] 2.4 收口-4（🔴 易漏）：研发项目是否会带出 **OEM 项目标识**？
  - ✅ **「会不会」已裁**：Shao Peishen 2026-09-03 答 `EE-3` ＝ (a) —— **会，按接 `data_isolation_layer` 设计**。原话理由：研发费用归集按项目走，OEM 项目几乎必然出现；**这一条错了是合规问题，宁可多接**。
  - ⏳ **「怎么接」待裁**：接法命中根 `CLAUDE.md` openspec 门槛②（涉鉴权与数据可见性）⇒ 须走 design 审。`design.md`（**局部件**，只覆盖本条）已由 `OP-0903-D3` 于 2026-09-03 起草，含 5 条定夺项，🔴 **一条都未默认生效**，泳道已 `pause --action-key openspec_design_review`。
  - 🔴 **其中 §定夺项 ② 是本包排期的真卡点**：高新认定辅助账天然跨全部 OEM（政府申报要全公司口径），与隔离规范 §3.1 的 fail-closed 正面相撞。**② 裁定前 MUST NOT 实现任何跨项目汇总** ⇒ §4.5 与 §5 全部卡在这一条上。
  - 🔴 连带：无论 §定夺项 ① 裁成哪条，都须回写《OEM 数据隔离规范》§2 三分法表（现对"研发费用金额"这类数据是**空的**）——规范修订须经 Shao Peishen 批准。
- [ ] 2.5 收口-5：加计扣除备查资料包的载体与版本策略（入库＝申报材料进 git 历史；不入库＝无版本可追溯、与 IATF 冲突），并据结论核实 `.gitignore` 覆盖
- [x] 2.6 收口-6：**跨五场景** `criteria_signoff` 是否提升进平台底座（rule-of-three 已触发）⇒ ✅ **已裁并已落地**（Shao Peishen 2026-09-03 拍板 `EE-1 = (a)` 收进底座）：平台底座 `zhuopin_platform.criteria_signoff` 已建成并合入 master（变更包 `criteria-signoff-platform`）；本包已于 A4 段迁移完毕，见 §1a。**本条不再需要收口。**
- [ ] 2.7 判据持有人 ＋ backup 实名指定（🔴 须含研发侧），登记进前置总表 §一.2（该表**现无 FI9 行**）
- [ ] 2.8 LLM 黄金集计划：资本化判定若落 LLM 侧，**历年已通过申报的判定可直接作为冻结输入 ＋ 专家认可输出**；本场景产出对外 ⇒ 此项**不可省**

## 3. cost-collection 成本采集（design 审后，先测后实现）

- [ ] 3.1 写测试：工时系统存在性未核实时，人工费用归集 **fail-loud，不以分摊估算代替**
- [ ] 3.2 写测试：材料/制造费用按（项目 × 期间 × 类型）归集，来源单据可回溯
- [ ] 3.3 写测试：真实源通道未核实时 fail-loud，不回退 mock
- [ ] 3.4 若涉发票对碰：先做字面一致性实测，据实测结论定 join 键（**不沿用 FI2 后 8 位**）
- [ ] 3.5 实现采集层
- [ ] 3.6 单测全绿

## 4. capitalization-rules 资本化规则引擎（design 审后，先测后实现）

- [ ] 4.1 写测试：判据为空时 fail-loud，不回退准则通用解读或行业惯例
- [ ] 4.2 设计规则注册表 `{规则ID, 条件, 结论, 依据条款, 版本}`（仿 FI1 `variance_classify`，**不另立一套**）
- [ ] 4.3 写测试：判定可追溯到具体准则条款/企业政策条目
- [ ] 4.4 写测试：不落在任何已签认规则覆盖内 → 判"待定" ＋ 需人工，**不得归入默认档**
- [ ] 4.5 写测试：准则口径与高新口径**分别**计算占比，不得共用一套
- [ ] 4.6 实现规则引擎 ＋ `RULE_VERSION` 登记
- [ ] 4.7 单测全绿

## 5. aux-ledger-and-filing 辅助账 ＋ 备查资料包 ＋ 对外门禁（design 审后，先测后实现）

- [ ] 5.1 写测试：政策库未签认时辅助账生成 fail-loud（**格式本身由政策库定**，不得用模板猜）
- [ ] 5.2 写测试：`reviewed_by` 为空的行不得进入任何对外产物
- [ ] 5.3 写测试：不存在把 `is_external_ready` 置真的路径
- [ ] 5.4 实现辅助账 ＋ 核心指标 ＋ 备查资料包
- [ ] 5.5 每笔归集/判定/人工改判写平台 `audit`（🔴 对外申报 ⇒ 审计轨迹**不可简化**）
- [ ] 5.6 投入产出分析 ＋ 「AI 分析建议，须人工确认」标注
- [ ] 5.7 单测全绿

## 6. 收口（不在本包，登记以免遗漏）

- [ ] 6.1 场景 `CLAUDE.md` 六段式（根 `CLAUDE.md` §5 第 6 步）
- [ ] 6.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi9` ＋ 预留网关 auth 接入点
- [ ] 6.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
