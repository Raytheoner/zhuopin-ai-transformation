# oem-audit-fail-closed Proposal

> **来源**：队列 §一 `#466`（2026-09-02 立，OP-0902-B1）；由 `#374` 变更包 `oem-chroma-ownership-rejudge` 的 design 审 **D2=(a) 收紧**裁决直接派生（裁决人 **Shao Peishen 本人**，2026-09-02，`compliance_redline_change`——孙涛不可代，代理条已满足）。
> **依据件**：`openspec/changes/oem-chroma-ownership-rejudge/design.md` D2 ／ 同包 `specs/platform-oem-isolation/spec.md` 的「跨 OEM 访问拒绝前写审计」MODIFIED 条（裁决文本已定稿，本包据此实现）／ `3-治理与合规/OEM数据隔离规范.md` §3.2（V1.1 已补明「未注入 audit 时怎么办」）。
> **openspec 门槛核对（根 `CLAUDE.md` §5 三条）**：①改变全项目口径 ✅（"审计不再可选"是一条新的强制口径）／②涉鉴权与数据可见性 ✅（OEM 隔离拒绝路径）／③改变既有模块对外语义 ✅（`OEMRouter` 构造签名默认值与 `_record_denied` 行为均变）——**三条全中**，且属合规红线，本走独立变更包（`#374` 明写"不改任何隔离层实现代码"，实现另立行＝本包）。

## Why（一段）

`router.py` 现状：`OEMRouter()` 默认构造 `audit=None`，`_record_denied` 遇 `self._audit is None` 直接 `return`（静默不写）——跨 OEM 访问被拒绝时若调用方忘记注入 `audit`，这次违规拦截**不产生任何证据**。这与 `3-治理与合规/OEM数据隔离规范.md` §3.2「**每次** `CrossOEMAccessError` 触发**必须**写平台 audit……违规**企图**本身就是审计事件」直接冲突——旧版 `openspec/specs/platform-oem-isolation/spec.md` 的「无 audit 注入时仅抛错（向后兼容）」把它写成了可选项，而隔离规范写的是必须。在 IATF 16949 可追溯性审核面前，「拦截到了却没有证据」与「没拦截」是同一个结论。

Shao Peishen 本人已于 2026-09-02 就此冲突裁决 **D2=(a) 收紧**：不注入 `audit` 时 `OEMRouter` 内建默认 `AuditLogger`；连默认都不可用时 `guard()`/`resolve()` 直接拒绝（fail-closed）。该裁决与配套 spec 文本已在 `oem-chroma-ownership-rejudge` 包内定稿，但该包明写「本包不改任何隔离层实现代码」——实现命中 openspec 门槛③，须独立变更包承接，即本包。

## What Changes

1. **`OEMRouter.__init__`**：`audit=None` 时不再保留为 `None`，改为内建默认 `AuditLogger.jsonl("reports/audit_log.jsonl")`（路径与 README 快速校验示例、其余场景注入 audit 时的既有约定同构）；默认构造本身失败（极罕见）时 `_audit` 置 `None`，留给 `_record_denied` 兜底。
2. **`OEMRouter._record_denied`**：`self._audit is None` 时不再 `return`（静默放行原调用），改为直接 `raise CrossOEMAccessError`（fail-closed，说明审计通道不可用）；审计写入本身抛异常（如落盘失败）时同样捕获并改判为 `CrossOEMAccessError`（`from exc` 保留原始异常链，不吞证据）。`resolve()`/`guard()` 的既有拒绝路径不变，只是审计前置动作从"尽力而为"变为"失败即拒绝"。
3. **spec delta**（`platform-oem-isolation`）：`跨 OEM 访问拒绝前写审计` 一条改 MODIFIED，删去「无 audit 注入时仅抛错（向后兼容）」，落入 `oem-chroma-ownership-rejudge` 已定稿的收紧文本 ＋ 两条新增 Scenario（默认 logger／审计通道不可用）。
4. **单测**：`test_smoke.py::test_isolation_blocks_cross_oem` 与 `test_oem_isolation_audit.py::test_no_audit_still_raises` 因行为改变需同步更新（后者改名为 `test_no_audit_uses_default_logger_and_still_raises`，断言默认 logger 确有落笔）；新增 `test_default_audit_logger_unavailable_fails_closed` 对应「审计通道完全不可用」Scenario。

## Non-Goals

- 🔴 **不实现 D5**（`GENERAL_COLLECTIONS` 写入侧校验入口 / 只读闸）。理由见 `design.md` §D5 处置；`#466` 行内允许「同包或另包由领取方判，但不得两条都无人承接」——本包判定**另包**，已在本文档与 `tasks.md` 显式登记，不视为遗漏。
- 不新建 `rag.retrieve()` 唯一入口（L2，排期 2027-05，`#374` 已裁）。
- 不部署 `.51`、不触碰生产服务。
- 不改 `3-治理与合规/OEM数据隔离规范.md` §5 映射表（该文件正在队列 §二 `B-0906_A` 批次内由 sweep 落库，本轮碰它会撞车；改判由业务总线在本包合入后另批做——见 opener「不做什么」）。

## Impact

- **spec**：`platform-oem-isolation`（MODIFIED 1 条 Requirement，2 条新增 Scenario）。
- **代码**：`5-平台底座/zhuopin_platform/zhuopin_platform/data_isolation_layer/router.py`；`tests/test_smoke.py`；`tests/test_oem_isolation_audit.py`。
- **调用点核查**（全库穷举 `OEMRouter(` 实例化，逐一见 `tasks.md` §2）：仅测试文件与一处类文档字符串示例，无生产代码路径受影响（QD-B 红线尚未接线；FI9 现有调用全部停在允许路径或已显式注入 audit）。
- **不改**任何权威文档口径（隔离规范/全景规划），只落代码与 spec delta。

## 知识资产三问（根 `CLAUDE.md` 全景规划 §1.4 第 2 条要求）

**⑴ 本流程哪些判断是人脑默会经验？**
- 「审计写入失败时应改判拒绝而非放行」——本次显式写成代码分支（`try/except` 包 `_audit.record` 并改抛 `CrossOEMAccessError`），此前无人写下过"万一落盘失败怎么办"。
- 「默认审计路径取哪里」——沿用既有约定（`reports/audit_log.jsonl` 相对 CWD，与 README/各场景注入方式一致），未另立新约定，避免"两套默认路径"的隐性分叉。

**⑵ 由谁显性化？（持有人 + backup）**
- 持有人：**Shao Peishen**（D2 裁决人，本包实现的合规口径来源）
- backup：**孙涛**（可代 design 审查；本条已属"实现落地"而非"合规红线再裁决"，孙涛可代审本包 tasks，但不可代**改判** D2 本身）
