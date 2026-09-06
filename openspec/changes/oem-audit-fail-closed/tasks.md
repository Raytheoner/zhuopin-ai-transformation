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
- [ ] 6.2 push 分支，登记队列 §二，等待业务总线过目（🔴 不合入 master，本包不做该动作）
