# criteria-signoff-platform Tasks

> 🔴 **A3 段（本泳道 OP-0903-C3）只做 §1 与 §2 的建造与起草，止于 design 审。§3 起全部待审过。**

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

## 3. design 审（A3 收尾，⏸ **停在此处**）

- [ ] 3.1 Shao Peishen 审 `design.md` §定夺项 **五条**：① 占位词黑名单去留 ② 三类「1 次」缺口收不收（②′ FI10 `SLOW_MOVING_CRITERIA` 归不归） ③ L2 模型层纪律是否另立一件 ④ 是否接 `AuditLogger` 留痕 ⑤ **A4 段是否同批批准**
- [ ] 3.2 🔴 **①-④ 属判据/口径类，起草方不得默认生效**；⑤ 不批则本包整体撤回

## 4. A4 段：五场景迁移（**待 3.1 审过，本泳道不做**）

- [ ] 4.1 FI5/FI6/FI8/FI9/FI10 各自 `config.py` 改为 `CriteriaRegistry` 声明，删除 17 条裸 `None` 常量
- [ ] 4.2 删除 5 份 `test_unsigned_criteria_stay_none` ＋ 5 份 `test_rule_version_marked_unsigned`，改由底座注册表承接
- [ ] 4.3 🔴 **验收硬条件（防"顺手补数"）**：迁移前后**未签认判据数量必须相等**（17 条进、17 条出）。任一条在迁移中被填上值，即视为迁移失败、退回
- [ ] 4.4 🔴 **验收硬条件（防"只增不减"）**：迁移后五个场景包内**不得残留任何本地判据 `None` 常量**——底座与手抄并存比现状更差
- [ ] 4.5 三类非判据缺口（FI8 `BANK_BALANCE_ACCESS` / FI9 `TIMESHEET_SYSTEM_EXISTS` / FI10 `CHIP_PRICE_API`）按 3.1 定夺项 ② 的裁定处置；未裁定前**原样留在场景包内，不动**
- [ ] 4.6 五场景单测全绿（迁移前基线 53 passed），底座全量回归零回归，`openspec validate --all --strict` 全绿

## 5. 收口（**待 4 完成**）

- [ ] 5.1 🔴 根 `CLAUDE.md` §4 与 `5-平台底座/CLAUDE.md` 子系统表**同步**补 `criteria_signoff` 行——两者是「原文原样下沉」关系，**必须同改**，改一处即制造漂移（走编辑锁）
- [ ] 5.2 17 条业务判据的持有人 ＋ **backup 双人制**登记进《跨场景前置数据与知识库任务总表》§一.2 知识资产台账（A3 段未登记）
- [ ] 5.3 价值指标基线交财务侧 Champion（唐燕萍线）确认存档（现为起草方自评）
- [ ] 5.4 `openspec archive criteria-signoff-platform`
