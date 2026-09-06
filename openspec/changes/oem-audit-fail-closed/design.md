# oem-audit-fail-closed Design

> **合规口径本身已裁决，无需再走 design 审**：D2=(a) 由 Shao Peishen 本人于 2026-09-02 在 `oem-chroma-ownership-rejudge` design 审内定夺（见该包 `design.md` D2 节，`compliance_redline_change`，孙涛不可代）。本文档只记录**实现层面**的技术决策——这些决策未逐条经裁决人拍板，但均不改变 D2 已定的对外语义，故按根 `CLAUDE.md` §5 openspec 门槛③的常规流程处理（技术实现细节，非口径再裁决）。

## 决策 1：默认 `AuditLogger` 的落盘路径

**选项**：
- (a) 沿用既有约定 `reports/audit_log.jsonl`（相对 CWD）——与 README 快速校验示例（L30/L35）、`AuditLogger.jsonl` 文档字符串示例（`logger.py` L16）、其余场景注入 audit 时的既有写法完全同构。
- (b) 新开一个"平台级全局"绝对路径（如锚定 `zhuopin_platform` 包安装位置）。

**✅ 采纳 (a)**。理由：
1. **零新概念**——整个平台目前唯一的审计落盘约定就是"调用方决定 `reports/` 相对路径"，`OEMRouter` 本就是平台代码的一部分，理应遵守同一约定，而不是为它单独发明一套"包级全局路径"的新语义。
2. **规避跨 worktree 路径坑**：`5-平台底座/CLAUDE.md` 已记录本机多 CC worktree 共享同一份 `site-packages` 的路径解析坑（队列 #300）——若默认路径锚定 `__file__`/包安装位置，在 `pip install -e` 场景下可能解析到别的 worktree，与 bootstrap 机制的既有解法（"从调用方 CWD 走"）方向相反。相对 CWD 路径没有这个风险，且与其余连接器/场景的现行做法一致。
3. **已被 `.gitignore` 覆盖**（`reports/audit_log.jsonl` 已在 `zhuopin_platform/.gitignore` L15-16），说明这本就是平台预期的运行期产物落点，不是本次新增的写入位置。

**代价（已知且接受）**：多个场景若都用默认构造的 `OEMRouter()`（不各自注入 audit），会共享同一个相对路径 `reports/audit_log.jsonl`——但这本来就是"调用方各自 CWD 下的 reports/"，不同场景进程的 CWD 天然不同，不会互相覆盖；如某场景需要与自己场景专属的 audit 文件汇合，仍应显式注入自己的 `AuditLogger`（现状即如此，本次不改变这条既有分工）。

## 决策 2：「默认 logger 不可用」在代码里具体指什么

裁决原文只给了后果（"fail-closed"），未定义触发条件本身在实现里长什么样。两处可能失败：

1. **构造失败**：`_default_audit_logger()` 本身抛异常。`AuditLogger.jsonl(path)` 内部只做 `Path(path)` 与共享锁字典查找，实测中几乎不会失败；仍用 `try/except` 兜底，失败时 `self._audit = None`。
2. **写入失败**：`self._audit.record(...)` 抛异常（磁盘满／只读文件系统／权限问题等）——这是更现实的失败模式。

**✅ 两处都覆盖**：`__init__` 里 `try/except` 兜底构造失败；`_record_denied` 里 `try/except` 兜底写入失败。两者最终都收敛成同一行为——`_record_denied` 必以 `CrossOEMAccessError` 结束（原始异常通过 `raise ... from exc` 保留在异常链里，不吞证据、只改判外层类型），不会把"审计通道坏了"误判成"访问被放行"。

## 决策 3：fail-closed 的作用范围——只覆盖拒绝路径，不覆盖允许路径

`platform-oem-isolation` spec 现行 Requirement 标题即「**跨 OEM 访问拒绝前**写审计」——本条从未要求对"允许"路径（本客户专属库／通用知识库）也写审计，D2 裁决文本同样只针对拒绝路径（"违规企图留痕"）。

**因此**：若审计通道故障，但当前这次访问本来就应该被允许（`guard()` 走 L112-114/L116-118 分支），本次改动**不会**额外把它变成拒绝——`_record_denied` 根本不会被调用到。`fail-closed` 的含义是"拒绝路径的审计前置动作失败时，仍必须以拒绝告终"，不是"审计系统故障时全局停摆"。这条边界在本包新增测试 `test_default_audit_logger_unavailable_fails_closed` 里只覆盖拒绝路径，未覆盖允许路径，是刻意为之、非遗漏——扩大到允许路径会把一次"实现修 bug"升级成一次新的合规口径变更（"审计故障时是否连合法访问也一并拒绝"是一个足以另开 design 审的问题），超出 D2 已裁决的范围。

## 决策 4：D5（`GENERAL_COLLECTIONS` 只读闸）不并入本包

`#466` 行内原文：「可一并评估是否同包承接 D5 的只读闸……同包或另包由领取方判，但不得两条都无人承接」。

**✅ 判定：另包，不并入本包。**

理由：
1. **代码现状不对称**——D2 是修一处已存在的行为分支（`_record_denied` 的 `if self._audit is None: return`）；D5 要求的"写入侧校验入口"当前在代码里**完全不存在**（`GENERAL_COLLECTIONS` 目前只在 `guard()` 的读取侧被引用，没有任何写入函数）。D5 是新建一个入口 + 只读闸，不是改一处已有分支，工作量与评审面都是另一个量级。
2. **两者是 spec 里两条独立 Requirement**（「跨 OEM 访问拒绝前写审计」vs「通用知识库 SHALL 由写入侧校验把关」），合规红线的判定单元不同，混在一个 diff 里会让本就属 `compliance_redline_change` 的 review 面变得更难核对——D2 已经是本人裁决过的红线变更，不宜再叠加一个未经单独审视的新入口。
3. **不阻塞**：D5 的"只读闸"是防止新写入越界，当前代码里没有任何写入通用库的函数存在，也就没有"来不及挡住的新写入"风险——D5 延后不产生窗口期风险。

**登记**：本决策与理由已写入本文档与 `proposal.md` Non-Goals，`tasks.md` §5 显式留一条指针，避免"两条都无人承接"。D5 的独立承接（新队列行）需业务总线在本包收口后另行登记——本包只做到"不遗漏、写清楚为什么不做"，不代为登记队列。
