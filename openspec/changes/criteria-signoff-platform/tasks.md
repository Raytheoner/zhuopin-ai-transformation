# criteria-signoff-platform Tasks

> 🔴 **A3 段（OP-0903-C3）做 §1 §2 的建造与起草，止于 design 审。**
> ✅ **design 审已于 2026-09-03 由 Shao Peishen 逐条通过**（`G-1`…`G-7`，见看护批 `B-0903_50` §一）⇒ §3 已闭合、§4 解除阻塞。
> 🔴 **收口段（OP-0903-D2）做 §3 的落档与 `G-1` 的代码补强，不做 §4**（改五个场景包 ＝ A4 段，归 D3 泳道）。

## 1. 底座模块建造（A3，✅ 已完成）

- [x] 1.1 建 `5-平台底座/zhuopin_platform/zhuopin_platform/criteria_signoff/`
- [x] 1.2 `errors.py` —— 异常族三类（`CriterionNotSignedOffError` / `CriterionContractError` / `UnknownCriterionError`），全部 fail-loud、无一可吞
- [x] 1.3 `models.py` —— `Signoff`（四项必填、拒占位词）＋ `Criterion`（frozen；`raw_value`/`value` 分离；两条构造期不变式）
- [x] 1.4 `registry.py` —— `CriteriaRegistry`（整体查缺、状态查询、`assert_rule_version` 双向校验）；**无 default 旁路、无宽松别名、无 `__getattr__` 回退**
- [x] 1.5 `__init__.py` —— 导出面 ＋ 收/不收边界说明

## 2. 单测与回归（A3，✅ 已完成）

- [x] 2.1 `tests/test_criteria_signoff.py` —— **45 passed**
- [x] 2.2 反例用例：读未签认判据必抛（判据侧 ＋ 注册表侧 ＋ 异常信息含 owner/question）
- [x] 2.3 API 形状守卫：`value_of` 签名恰为 `(self, key)`、`value` 是 property、无宽松别名、无 `__getattr__` 回退
- [x] 2.4 不变式守卫：有值无签认 / 有签认无值 / 占位词签认人 / frozen / 重复 key / 空注册表
- [x] 2.5 **「关掉守卫即失败」实测坐实**：删掉 `Criterion.value` 的 fail-loud 守卫后重跑 ⇒ **4 条转红**（`DID NOT RAISE`），还原后 45 passed；另有两条常驻元测试（`test_guard_is_load_bearing` / `test_guard_off_also_breaks_the_registry_path`）把该证明留在套件里
- [x] 2.6 底座全量回归 **452 passed / 1 skipped**（新增前 407 passed，零回归）
- [x] 2.7 `git check-ignore -v` 实测五个新文件均**不被忽略**（会正常入库）
- [x] 2.8 **`G-1` 日期校验的正反例（OP-0903-D2 补）**：反例 8 条（`2026-13-45` / `2026-02-30` / `2026/09/03` / `20260903` / `2026-9-3` / `03-09-2026` / `2026-09-03T00:00:00` / `2026年9月3日`）＋ 正例 4 条（含闰日 `2024-02-29`）；另一条 `test_date_check_is_additional_not_a_replacement_for_the_blacklist` 守「日期校验不得顶替占位词黑名单」
- [x] 2.9 **`G-1` 的「关掉即转红」照 2.5 做法坐实**：拆掉 `Signoff.__post_init__` 里那行校验后重跑 ⇒ **8 条转红**（全部 `DID NOT RAISE`），还原后 **59 passed**；常驻元测试 `test_date_check_is_load_bearing` 把证明留在套件里。本文件用例数 **45 → 59**

## 3. design 审（✅ **已通过** —— Shao Peishen 2026-09-03 逐条拍板）

- [x] 3.1 Shao Peishen 审 `design.md` §定夺项 **五条** ⇒ **全部裁完**（编号沿用看护批 `B-0903_50` §一）：
  - `G-1` ① 占位词黑名单 ＝ **(a) 留**，另补 `YYYY-MM-DD` 格式校验
  - `G-2` ② 三类「1 次」缺口 ＝ **(a) 不收进底座**
  - `G-3` ②′ FI10 `SLOW_MOVING_CRITERIA` ＝ **(a) 归进注册表**，owner ＝ 财务侧
  - `G-4` ③ L2 模型层纪律 ＝ **(b) 另立队列行、不排期** ⇒ 队列 §一 `#476`（🛑 排队中）
  - `G-5` ④ `AuditLogger` ＝ **(a) 不接**，改反向依赖（见 4.7）
  - `G-6` ⑤ A4 段 ＝ **(a) 同批批准**
- [x] 3.2 🔴 **①-④ 属判据/口径类，起草方未默认生效任何一条**（全部停等到裁决）；⑤ 已批 ⇒ 本包不撤回
- [x] 3.3 **裁决落档（OP-0903-D2）**：`design.md` §定夺项改写为已裁决形态（逐条记裁决原文＋拍板人＋日期），D1.2／风险段的过期表述同步校正（17 → 18、「审未过」措辞）
- [x] 3.4 🔴 **本包不再重开任何一条**；任一条若需改动，须重新走一次 design 审，不得就地改判

## 4. A4 段：五场景迁移（✅ **已获批开工**（`G-6`），🔴 **本泳道 OP-0903-D2 不做**，归 D3 泳道）

- [ ] 4.1 FI5/FI6/FI8/FI9/FI10 各自 `config.py` 改为 `CriteriaRegistry` 声明，删除 **18** 条裸 `None` 常量
- [ ] 4.1a 🔴 **`G-3` 落地：FI10 `SLOW_MOVING_CRITERIA` 必须登记进 FI10 的注册表**（Shao Peishen 2026-09-03 拍板 `G-3 = (a)`）。逐字形态如下，`owner` 与 `question` **不得改写**：

      Criterion(
          key="SLOW_MOVING_CRITERIA",
          question=(
              "呆滞物料的认定口径（库龄门限／周转率门限／例外物料）—— "
              "本口径 FI10 先出、SC7 后对齐（EE-4 拍板 2026-09-03），"
              "签认前须知会 SC7 口径确认人"
          ),
          owner="财务侧",
          note=(
              "口径用于存货跌价计提（进财务报表），故 owner 归财务侧而非 SC7 业务口径确认人；"
              "#474 要求与 SC7 呆滞口径同口径，但 SC7 那份属②期深化（2027-01）尚未落地，"
              "经 EE-4 裁为「FI10 先定、SC7 后对齐」——故它已不再是「无源可取」，而是一条标准待签认判据"
          ),
      )

  🔴 **它仍是未签认判据，`raw_value` 恒 `None`** —— 本条是「登记进注册表」，**不是给它填值**。任何人在此填值即触发 4.3 的迁移失败。
  🔴 连带删除 FI10 侧的裸常量 `SLOW_MOVING_CRITERIA = None`；`L9_SOURCE_ABSENT` 那段说明文字**保留**（它记的是 `#474`／EE-4 的来龙去脉，注册表的 `note` 不替代它）。
- [ ] 4.1b 连带改 FI10 用例 `test_l9_slow_moving_source_absent`：断言从「常量是 `None`」改为「注册表里该 key **未签认**且读 `.value` 必抛」（原两条 `L9_SOURCE_ABSENT` 文本断言保留）
- [ ] 4.2 删除 5 份 `test_unsigned_criteria_stay_none` ＋ 5 份 `test_rule_version_marked_unsigned`，改由底座注册表承接
- [ ] 4.3 🔴 **验收硬条件（防"顺手补数"）**：迁移前后**未签认判据数量必须相等**（**18 条进、18 条出**）。任一条在迁移中被填上值，即视为迁移失败、退回
  🔴 **该数已由 17 改为 18**（Shao Peishen 2026-09-03 拍板 `G-3 = (a)`，`SLOW_MOVING_CRITERIA` 归进注册表所致，见 4.1a）。**不改这个数，A4 会按「迁移失败」被自己的验收条件退回。**
- [ ] 4.4 🔴 **验收硬条件（防"只增不减"）**：迁移后五个场景包内**不得残留任何本地判据 `None` 常量**——底座与手抄并存比现状更差
- [ ] 4.5 三类非判据缺口（FI8 `BANK_BALANCE_ACCESS` / FI9 `TIMESHEET_SYSTEM_EXISTS` / FI10 `CHIP_PRICE_API`）⇒ ✅ 已裁 `G-2 = (a)` **不收进底座**：三条**原样留在各自场景包内，一律不动、不得顺手并入注册表**。
  🔴 它们与判据的机械形状虽像，但解除路径各不相同（授权 / 核实 / 等前置 vs 签认）；「合并成一个 `None`」的做法已被明确否决。
  📌 FI9 `TIMESHEET_SYSTEM_EXISTS` 的核实已按 `G-7 = (a)` 独立立行 ⇒ 队列 §一 `#477`（本包不认领）
- [ ] 4.6 五场景单测全绿（迁移前基线 53 passed），底座全量回归零回归（收口后基线 **466 passed / 1 skipped**），`openspec validate --all --strict` 全绿
- [ ] 4.7 🔴 **`G-5` 落地：反向依赖（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`，改反向依赖）**
  - **不做什么**：`criteria_signoff` **不得 import `zhuopin_platform.audit`**、不得新增任何写日志的钩子或字段 —— 底座零依赖是它可被任意场景安全引用的前提（design D3）
  - **做什么**：由**五个场景各自的引擎**在调 `AuditLogger.record(AuditEvent(...))` 时，把**当时生效的** `RULE_VERSION` 写进 `AuditEvent.decision`（如 `decision={..., "rule_version": RULE_VERSION}`），成本约一行
  - **依赖方向**：**审计日志指向判据版本**，不是判据模块去写审计日志
  - **为什么够**：`RULE_VERSION` 在全部判据签认完成前自带 `unsigned` 标记（`assert_rule_version()` 双向校验），故每条 AI 决策的日志天然记着「用的哪版口径、当时签完没有」，IATF「AI 辅助决策可追溯」诉求即被满足
  - **验收**：底座侧净变化为零（`grep -r "audit" criteria_signoff/` 在可执行代码里 0 命中）；引擎侧至少一条用例断言 `decision` 内含 `rule_version`

## 5. 收口（**待 4 完成**）

- [ ] 5.1 🔴 根 `CLAUDE.md` §4 与 `5-平台底座/CLAUDE.md` 子系统表**同步**补 `criteria_signoff` 行——两者是「原文原样下沉」关系，**必须同改**，改一处即制造漂移（走编辑锁）
- [ ] 5.2 **18** 条业务判据（🔴 含 `G-3` 归入的 `SLOW_MOVING_CRITERIA`）的持有人 ＋ **backup 双人制**登记进《跨场景前置数据与知识库任务总表》§一.2 知识资产台账（A3 段未登记）
- [ ] 5.3 价值指标基线交财务侧 Champion（唐燕萍线）确认存档（现为起草方自评）
- [ ] 5.4 `openspec archive criteria-signoff-platform`
