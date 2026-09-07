# oem-audit-fail-closed Tasks

> 合规口径（D2=(a)）已由 Shao Peishen 本人于 2026-09-02 裁决，本包只实现，不再走 design 审拍板；`design.md` 记录的是实现层技术决策。

## 1. 出件
- [x] 1.1 proposal ＋ design ＋ tasks ＋ spec delta 出件【CC】
- [x] 1.2 openspec 门槛自评写入 proposal（三条全中）【CC】

## 2. 全部调用点核查（穷举 `OEMRouter(` 实例化，不抽样）
- [x] 2.1 `router.py` 类文档字符串示例（L53-55）——非可执行代码，行为描述随实现同步更新，无需改字【CC】
- [x] 2.2 `tests/test_smoke.py::test_isolation_allows_own_and_general`——只走允许路径，不触发 `_record_denied`，无需改动【CC】
- [x] 2.3 `tests/test_smoke.py::test_isolation_blocks_cross_oem`——走拒绝路径，默认构造现会落盘 `reports/audit_log.jsonl`；已加 `monkeypatch.chdir(tmp_path)` 避免污染仓库工作目录【CC】
- [x] 2.4 `tests/test_oem_isolation_audit.py` 四个用例——`test_no_audit_still_raises` 因行为改变已重写为 `test_no_audit_uses_default_logger_and_still_raises`（断言默认 logger 确有落笔）；其余三个已显式注入 audit，无需改动【CC】
- [x] 2.5 `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_oem_isolation.py` 八处 `OEMRouter(`——七处 `OEMRouter()` 全部只触达允许路径或提前 `return None`（`oem_customer is None` 时 `resolve_project_source` 在调 `router.resolve()` 之前就返回），一处 `OEMRouter(audit=audit)` 已显式注入；**全部核查完毕，无一处受本次默认值变更影响**【CC】
- [x] 2.6 `fi9_rd_cost/oem_isolation.py` 生产代码——`resolve_project_source`/`partition_by_ownership` 只接收调用方传入的 `router: OEMRouter` 实例，自身不构造 `OEMRouter()`，不受本次默认值变更影响（构造责任在调用方，FI9 当前无生产级调用方，见 2.5）【CC】
- [x] 2.7 `4-数字员工/财务部/FI10-存货跌价智能分析`——grep 命中的三处均为文档字符串/注释提及 `OEMRouter`，无实际实例化，不受影响【CC】
- [x] 2.8 QD-B 场景——OEM 路由红线现仍未接线（无 `OEMRouter(` 调用），本次改动不产生新影响面【CC】

## 3. 实现
- [x] 3.1 `router.py` 新增 `DEFAULT_AUDIT_LOG_PATH` 常量 ＋ `_default_audit_logger()` 辅助函数【CC】
- [x] 3.2 `OEMRouter.__init__`：`audit=None` 时改为内建默认 logger（构造失败兜底为 `None`）【CC】
- [x] 3.3 `OEMRouter._record_denied`：`self._audit is None` 分支由 `return` 改为 `raise CrossOEMAccessError`（fail-closed）；写入失败改用 `try/except` 包裹并 `raise ... from exc`【CC】

## 4. 测试
- [x] 4.1 既有单测回归：`5-平台底座/zhuopin_platform/tests/` 全量 467 passed / 1 skipped（`pytest tests/ -q`）【CC】
- [x] 4.2 `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_oem_isolation.py` 21 passed（消费方回归）【CC】
- [x] 4.3 新增 `test_default_audit_logger_unavailable_fails_closed`，对应 spec Scenario「审计通道完全不可用」【CC】
- [x] 4.4 更新 `test_no_audit_still_raises` → `test_no_audit_uses_default_logger_and_still_raises`，对应 spec Scenario「未注入 audit 时使用默认 logger」【CC】

## 5. D5（只读闸）处置——判定：另包，不并入本包
- [x] 5.1 判定理由已写入 `design.md` 决策 4：D5 要求新建写入侧校验入口，当前代码零基础（`GENERAL_COLLECTIONS` 只在读取侧被引用），与 D2"改一处既有分支"不对称，且属独立 spec Requirement，不宜与 `compliance_redline_change` 的本包合并评审【CC】
- [x] 5.2 已在 `proposal.md` Non-Goals 与本节显式登记，避免"两条都无人承接"——D5 的独立队列登记留给业务总线在本包收口后另行处理，本包不代为登记队列行【CC】

## 6. 收口
- [x] 6.1 `openspec validate oem-audit-fail-closed --strict` 须绿——已验证通过【CC】
- [x] 6.2 push 分支，登记队列 §二，等待业务总线过目（🔴 本包自身不做合入动作）——已完成；**合入由另一泳道执行**：`OP-0906-E` 2026-09-06 14:1x 把 `claude/op0906c-oem-audit-fail-closed-aa7199`（原 commit `7211db3`）rebase 后 ff 入 master，新 commit **`4b9c2a0`**，`git merge-base --is-ancestor 4b9c2a0 master` ⇒ 已并入（业务总线 `OP-0906-B` 独立实证）。上句「不合入 master」自此过时，Shao Peishen 2026-09-06 答 (a) 放行【CC】

## 7. 独立复验与收口余项（`OP-0907-T` 2026-09-07 14:05 CST，队列 §一 `#466` 派生）

- [x] 7.1 **实现在 master 已生效**：`git show --stat 4b9c2a0` 命中 `router.py`／`test_oem_isolation_audit.py`／`test_smoke.py` ＋ 本包四件；master 树上 `router.py` 现文为 `DEFAULT_AUDIT_LOG_PATH` ＋ `_default_audit_logger()` ＋ `_record_denied` fail-closed 版【CC】
- [x] 7.2 **单测回归复跑（亲验，非转抄）**：`5-平台底座/zhuopin_platform` 全量 `pytest tests/ -q` ⇒ **528 passed / 1 skipped**（较 `OP-0906-C` 自陈的 467 增长 61，系其后其它泳道新增用例，非本包影响）；`tests/test_oem_isolation_audit.py` ＋ `tests/test_smoke.py` ⇒ **9 passed**；FI9 消费方 `tests/test_oem_isolation.py` ⇒ **21 passed**【CC】
- [x] 7.3 **`openspec validate oem-audit-fail-closed --strict` 复跑绿**（输出 `Change 'oem-audit-fail-closed' is valid`）【CC】
- [x] 7.4 **调用点清单复核（重跑穷举 grep，非抽样）**：`grep -rn "OEMRouter(" --include="*.py"` 全仓 **16 处**，与 §2 逐条对齐、无新增生产调用点 —— 1 处类文档字符串示例（`router.py:53`）＋ 15 处测试（FI9 8 处、平台 `test_oem_isolation_audit.py` 5 处、`test_smoke.py` 2 处）；`import` 面另有 FI10 `tests/test_scaffold.py:28` 仅导入不实例化（§2.7 原表述「三处均为文档字符串/注释提及」对该行不精确，**结论不变**：FI10 无实例化）。**全仓无任何生产代码构造 `OEMRouter`**，QD-B OEM 路由红线仍未接线【CC】
- [x] 7.5 **运行期产物不污染仓库**：`test_smoke.py::test_isolation_blocks_cross_oem` 已 `monkeypatch.chdir(tmp_path)`；`**/reports/`（根 `.gitignore:41`）＋ `reports/audit_log.jsonl`（平台 `.gitignore:16`）双重忽略；全仓 `find -name audit_log.jsonl` 零命中，`git status` 无 `reports` 相关条目【CC】
- [ ] 7.6 🟡 **主 spec 未同步（本次新发现，须先定归属再动手）**：`openspec/specs/platform-oem-isolation/spec.md` L9／L15-17 仍是**旧文** ——「无 audit 注入时仅抛错（**向后兼容**）」＋ Scenario「无 audit 注入时仅抛错」。该 Scenario 现已与实现**直接相反**（默认构造现会经默认 logger 留痕，默认 logger 不可用时 fail-closed 拒绝）。⚠️ 队列 `#466` 状态格「文本侧冲突已于 2026-09-02 收口」只在**变更包 delta 内**成立，主 spec 尚未落。🔴 **注意 archive 次序**：`oem-chroma-ownership-rejudge` 与本包**各持同一 Requirement 的 MODIFIED**，本包版本是其超集（多一段 fail-closed 义务范围限定）⇒ 必须 **先 archive `oem-chroma-ownership-rejudge`、后 archive 本包**，反序会把已收紧的文本回退。归属与执行时机待业务总线派发【CC】
- [ ] 7.7 🟡 **`3-治理与合规/OEM数据隔离规范.md` §5 映射表 §3.2 行现状改判**（`#466` 剩余项②，队列已注明「归业务总线另批」）：现文 `⚠️ **部分实现**`，按本次复验应改判 `✅ 已实现`。改动属「改口径判据」⇒ 停等 Shao Peishen 一个字母，**本会话不动该文件**；拟改文本已随 `OP-0907-T` 复命件交出【CC】
