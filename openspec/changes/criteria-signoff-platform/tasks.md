# criteria-signoff-platform Tasks

> 🔴 **A3 段（OP-0903-C3）做 §1 §2 的建造与起草，止于 design 审。**
> ✅ **design 审已于 2026-09-03 由 Shao Peishen 逐条通过**（`G-1`…`G-7`，见看护批 `B-0903_50` §一）⇒ §3 已闭合、§4 解除阻塞。
> 🔴 **收口段（OP-0903-D2）做 §3 的落档与 `G-1` 的代码补强，不做 §4**（改五个场景包 ＝ A4 段，归 D3 泳道）。
> ✅ **§4（A4 段五场景迁移）已于 2026-09-03 由 `OP-0903-D3` 做完**（同批 `B-0903_50` A3 段）⇒ **本包最大的风险已消解**：底座与五份手抄的并存态**已结束**，五个场景现引用底座唯一一份。

> ## 🔴 归档状态：**不归档** ｜ **预期观察窗口：14 天**（供 `工具-落库sweep.py` / `工具-变更包自动归档.py` 读取）
>
> **判定依据**：按「完工即归档纪律」，`tasks` 全 `[x]` 才归档。§1–§4 现已全部完成，**§5（收口）四条全未做** ⇒ **不归档**。
>
> 🔴 **§5 为什么由 `OP-0903-D3` 如实留步、而不是顺手做掉**（2026-09-03）：
> · `5.1` 要同改根 `CLAUDE.md` §4 与 `5-平台底座/CLAUDE.md` —— **两处都不在 D3 泳道 opener 列明的触碰区内**
>   （该 opener 的触碰区 ＝ 五个财务场景包 ／ `openspec/` ／ `master` ／队列 §一 `#470`–`#474`）。看护批 `B-0903_50` 的
>   合入豁免明写「**范围一旦超出各 opener 所列即须停**」⇒ 留步登记，不越界。
> · `5.3` 要财务侧 Champion（唐燕萍线）确认存档 —— **三闸全锁**（硬边界 6），不得起草或发送任何跟进信。
> · `5.2` 台账登记与 `5.4` 归档均在 `5.1`／`5.3` 之后，一并顺延。
>
> 🔴 **为什么用「预期观察窗口」而不是那个永久 defer 文本标记**（`工具-落库sweep.py` 的 `STALE_CHANGE_DEFER_MARKER`，
> 此处**刻意不写出它的字面值** —— 写出来就会被 sweep 当成真声明命中，把本包永久静音）：那一档是**作者对未来的永久声明**，
> 会让 sweep 此后再也不提这个包；
> 而本包缺的 §5 是**马上就要做的一段**（只差一个有权改 `CLAUDE.md` 的泳道 ＋ 一次闸开）。
> 它**应该**被反复提起直到做完 —— 用会到期升级的那一档，等于给这段留了一个会自己响的闹钟。
>
> **窗口为什么仍取 14 天**（原因已换，数字不变，故此处记明以免下次读不懂）：
> 原定 14 天是给 A4 的 `EE-3` 停审留一次往返 —— **那次往返已发生**（`OP-0903-D3` 起草 `fi9-rd-cost-mvp/design.md` 后已 `pause`，待裁）。
> 现在这 14 天改为留给 §5 的两个前提：一次跨触碰区的 `CLAUDE.md` 同改派单 ＋ 一次唐燕萍闸开。
> 若 14 天后仍未归档，说明这两件里至少一件卡住了，该被升级成「疑似遗忘归档」提出来。

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

## 4. A4 段：五场景迁移（✅ **已完成** —— `OP-0903-D3` / 看护批 `B-0903_50` A3 段，2026-09-03）

- [x] 4.1 FI5/FI6/FI8/FI9/FI10 各自 `config.py` 改为 `CriteriaRegistry` 声明，删除 **18** 条裸 `None` 常量（各包另在模块级调 `CRITERIA.assert_rule_version(RULE_VERSION)`，**导入期**即双向校验）
- [x] 4.1a 🔴 **`G-3` 落地：FI10 `SLOW_MOVING_CRITERIA` 必须登记进 FI10 的注册表**（Shao Peishen 2026-09-03 拍板 `G-3 = (a)`）。逐字形态如下，`owner` 与 `question` **不得改写**：

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
- [x] 4.1b 连带改 FI10 用例 `test_l9_slow_moving_source_absent`：断言从「常量是 `None`」改为「注册表里该 key **未签认**且读 `.value` 必抛」（原两条 `L9_SOURCE_ABSENT` 文本断言保留）⇒ 已改名为 `test_l9_slow_moving_registered_but_unsigned`；另立 `L9_OWNERSHIP_RULED` 常量记 `EE-4` 改判（原文保留记成因、新常量记结论，两者并存）
- [x] 4.2 删除 5 份 `test_unsigned_criteria_stay_none` ＋ 5 份 `test_rule_version_marked_unsigned`，改由底座注册表承接 ⇒ 各包改为 `test_criteria_registry_declares_exactly_these` ／ `test_criteria_registry_all_unsigned`（断言**未签认且读取必抛**，比原「常量是 `None`」更硬）／ `test_rule_version_consistent_with_signoff_state`
- [x] 4.3 ✅ **实测通过：18 条进、18 条出**（FI5 4 ／ FI6 4 ／ FI8 3 ／ FI9 3 ／ FI10 4，逐条 `is_signed()` 为假、`raw_value is None`、`signed_keys()` 全空）。🔴 **验收硬条件（防"顺手补数"）**：迁移前后**未签认判据数量必须相等**（**18 条进、18 条出**）。任一条在迁移中被填上值，即视为迁移失败、退回
  🔴 **该数已由 17 改为 18**（Shao Peishen 2026-09-03 拍板 `G-3 = (a)`，`SLOW_MOVING_CRITERIA` 归进注册表所致，见 4.1a）。**不改这个数，A4 会按「迁移失败」被自己的验收条件退回。**
- [x] 4.4 ✅ **实测通过：零残留**（`ast` 扫五个包全部 `.py` 的模块级 `X = None`，命中仅 3 处且全是 `G-2` 三类缺口：FI8 `BANK_BALANCE_ACCESS` ／ FI9 `TIMESHEET_SYSTEM_EXISTS` ／ FI10 `CHIP_PRICE_API`）。🔴 **验收硬条件（防"只增不减"）**：迁移后五个场景包内**不得残留任何本地判据 `None` 常量**——底座与手抄并存比现状更差
- [x] 4.5 ✅ **三条原样未动，且各新增一条「不得并入注册表」用例**（`test_bank_balance_access_is_not_a_criterion` ／ `test_timesheet_existence_is_not_a_criterion` ／ `test_chip_price_api_is_not_a_criterion`）。三类非判据缺口（FI8 `BANK_BALANCE_ACCESS` / FI9 `TIMESHEET_SYSTEM_EXISTS` / FI10 `CHIP_PRICE_API`）⇒ ✅ 已裁 `G-2 = (a)` **不收进底座**：三条**原样留在各自场景包内，一律不动、不得顺手并入注册表**。
  🔴 它们与判据的机械形状虽像，但解除路径各不相同（授权 / 核实 / 等前置 vs 签认）；「合并成一个 `None`」的做法已被明确否决。
  📌 FI9 `TIMESHEET_SYSTEM_EXISTS` 的核实已按 `G-7 = (a)` 独立立行 ⇒ 队列 §一 `#477`（本包不认领）
- [x] 4.6 ✅ 五场景单测全绿 **71 passed**（FI5 10 ／ FI6 12 ／ FI8 16 ／ FI9 17 ／ FI10 16；迁移前基线 53）；底座全量回归 **466 passed / 1 skipped**（**零回归**）；`openspec validate --all --strict` ⇒ **155 passed / 0 failed**（含本批 16 个新建主 spec；🔴 只认「0 failed」，不拿旧计数当预期值）
- [x] 4.7 🔴 **`G-5` 落地：反向依赖（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`，改反向依赖）**
  - **不做什么**：`criteria_signoff` **不得 import `zhuopin_platform.audit`**、不得新增任何写日志的钩子或字段 —— 底座零依赖是它可被任意场景安全引用的前提（design D3）
  - **做什么**：由**五个场景各自的引擎**在调 `AuditLogger.record(AuditEvent(...))` 时，把**当时生效的** `RULE_VERSION` 写进 `AuditEvent.decision`（如 `decision={..., "rule_version": RULE_VERSION}`），成本约一行
  - **依赖方向**：**审计日志指向判据版本**，不是判据模块去写审计日志
  - **为什么够**：`RULE_VERSION` 在全部判据签认完成前自带 `unsigned` 标记（`assert_rule_version()` 双向校验），故每条 AI 决策的日志天然记着「用的哪版口径、当时签完没有」，IATF「AI 辅助决策可追溯」诉求即被满足
  - **验收** ⇒ ✅ **两项均实测通过**：`grep -r "audit" criteria_signoff/` **0 命中**（底座侧净变化为零）；五个场景各落一个 `config.audit_decision(**fields)`（四行，恒带 `RULE_VERSION`）＋ 各一条 `test_audit_decision_carries_rule_version` 拿真的 `AuditEvent` 断言 `decision["rule_version"]`
  - 📌 **为什么刻意五份各留一份、不收进底座**：收进去就等于底座反向知道了场景与 `audit`，而 `G-5 = (a)` 否掉的正是那条依赖。四行的重复是这条依赖方向的代价，划算

## 5. 收口（**待 4 完成**）

- [ ] 5.1 🔴 根 `CLAUDE.md` §4 与 `5-平台底座/CLAUDE.md` 子系统表**同步**补 `criteria_signoff` 行——两者是「原文原样下沉」关系，**必须同改**，改一处即制造漂移（走编辑锁）
- [ ] 5.2 **18** 条业务判据（🔴 含 `G-3` 归入的 `SLOW_MOVING_CRITERIA`）的持有人 ＋ **backup 双人制**登记进《跨场景前置数据与知识库任务总表》§一.2 知识资产台账（A3 段未登记）
- [ ] 5.3 价值指标基线交财务侧 Champion（唐燕萍线）确认存档（现为起草方自评）
- [ ] 5.4 `openspec archive criteria-signoff-platform`
