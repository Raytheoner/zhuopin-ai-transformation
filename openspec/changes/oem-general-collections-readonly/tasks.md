# oem-general-collections-readonly Tasks

> 合规口径（D5=(a)）已由 **Shao Peishen 本人** 2026-09-02 裁决，本包只实现，不再走口径审；`design.md` 记录的是实现层技术决策，其第 6 节两项定夺留给 design 审。
> 执行泳道：`OP-0908-E`／批 `B-0908_B`／队列 §一 `#491`；分支 `claude/op0908e-general-readonly`。

## 1. 前置条件核实（硬序）

- [x] 1.1 **`#466` 已合入 master 的实证（现取，非转抄）**：worktree 树上 `router.py` 已是 fail-closed 版——`DEFAULT_AUDIT_LOG_PATH` ＋ `_default_audit_logger()` 均在，`_record_denied` 的 `self._audit is None` 分支为 `raise CrossOEMAccessError` 而非 `return`。⇒ `#491` 的硬序前置（等 `#466` 合入后再碰 `router.py`）已满足【CC】
- [x] 1.2 出件：proposal ＋ design ＋ tasks ＋ spec delta；openspec 门槛自评写入 proposal（三条全中）【CC】

## 2. 全部相关代码点核查（穷举，不抽样）

- [x] 2.1 **`GENERAL_COLLECTIONS` 全仓引用穷举**（`grep -rn "GENERAL_COLLECTIONS" --include="*.py"`）：本次改动前**仅 2 处**——`router.py` 的集合定义（L49）与 `guard()` 读取侧判定；**零写入侧引用**。⇒ D5 判「零写入路径」的前提事实在 2026-09-08 仍成立【CC】
- [x] 2.2 **三个通用 collection 名全仓穷举**（`grep -rn "kb_supplier\|kb_quality_cases\|kb_finance_rules" --include="*.py"`）：本次改动前仅 4 处，全部在 `router.py` 定义行与两份平台单测的**读取**断言里（`test_oem_isolation_audit.py:80`、`test_smoke.py:35`）。**无任何生产代码提及通用库**【CC】
- [x] 2.3 **`OEMRouter(` 实例化穷举**：全仓 **30 处**（`grep -rn "OEMRouter(" --include="*.py" | wc -l`），分布于 7 个文件。⚠️ **与 `#466` tasks §7.4「全仓无任何生产代码构造 OEMRouter」相比已变化**：`4-数字员工/财务部/FI10-存货跌价智能分析/fi10_inventory_writedown/intake.py` 现有生产实例化（`build_router()` 内两处）——该结论自 2026-09-07 起过时，**本包据现取重述，不沿用旧结论**【CC】
- [x] 2.4 **FI10 生产调用点逐行核**：`intake.py` 只调 `resolve()`（归属校验）与 `guard()`（视图属主 vs 数据属主，读取侧），目标 collection 全部来自 `router.resolve()` 的返回值（即 OEM 专属库），**从不触碰通用 collection、无任何写入动作** ⇒ 不受本包影响【CC】
- [x] 2.5 **本包为纯新增 API**：`guard()`／`resolve()`／`_record_denied` 的既有调用行为逐字不变（`_record_denied` 新增的 `action`／`error_cls` 两参均带默认值＝原行为）。⇒ 30 处既有实例化点**无一需要改动**【CC】

## 3. 实现

- [x] 3.1 `router.py` 新增 `GeneralCollectionReadOnlyError(PermissionError)`——刻意不继承 `CrossOEMAccessError`（design 决策 2），类 docstring 写明理由【CC】
- [x] 3.2 `router.py` 新增 `ACTION_GENERAL_WRITE_DENIED = "general_collection_write_denied"`【CC】
- [x] 3.3 `GENERAL_COLLECTIONS` 上方补写只读闸注释：D5 出处、"已有内容不受影响"、唯一解闸条件、以及**为何不给运行期开关**（design 决策 5）【CC】
- [x] 3.4 `_record_denied` 泛化：新增 `action` / `error_cls` 两个带默认值的参数，使只读闸复用同一条 fail-closed 通道而非复制第二份（design 决策 4.1）【CC】
- [x] 3.5 新增 `OEMRouter.guard_write(oem, collection)`：通用库分支先留痕后抛 `GeneralCollectionReadOnlyError`（只读闸先于 OEM 上下文判定，任何上下文一律拒）；非通用 collection 委派给既有 `guard()`【CC】
- [x] 3.6 类 docstring 用法示例补两行（通用库读放行 / 写抛错），使"读可写不可"在最显眼处可见【CC】
- [x] 3.7 `data_isolation_layer/__init__.py` 导出 `GeneralCollectionReadOnlyError` 并补模块 docstring 的读写分工说明【CC】

## 4. 测试

- [x] 4.1 新增 `5-平台底座/zhuopin_platform/tests/test_general_collections_readonly.py`，**13 passed**（`python -m pytest tests/test_general_collections_readonly.py -q`，退出码 0）。逐条对应 spec 的 6 条 Scenario，另加 3 条实现约束护栏【CC】
  - 三个通用库**逐个**参数化覆盖（不抽样）：拒绝 ＋ 留痕 ＋ reason/oem_context 断言
  - 五种 OEM 上下文（三家已注册 ＋ 未注册 ＋ 空串）一律被拒 ⇒ "不因上下文豁免"
  - 异常类分离断言：`GeneralCollectionReadOnlyError` **不是** `CrossOEMAccessError` 子类、双向都不是、同为 `PermissionError` 子类
  - 本客户专属库写入放行且**不写**违规审计（fail-closed 只覆盖拒绝路径）
  - 跨客户专属库写入仍抛 `CrossOEMAccessError` ＋ 写 `cross_oem_access_denied`
  - 未注册上下文写专属库在 `resolve()` 处被拒并留痕
  - 未注入 audit 时经平台默认 logger 留痕后仍拒绝
  - 审计写入失败 ／ 默认 logger 构造失败（`_audit is None`）两种通道故障均 fail-closed
  - **回归护栏**：读取侧未被改动（三个通用库读取仍无条件放行、不留痕）
  - **架构约束机器守**：模块内不存在 `*WRITABLE*`／`*ALLOW_WRITE*`／`*WRITE_ENABLED*` 名字，`OEMRouter` 无 `write_validator` 属性（design 决策 5）
- [x] 4.2 平台全量回归：`5-平台底座/zhuopin_platform` 下 `python -m pytest tests/ -q` ⇒ **589 passed / 1 skipped**，退出码 0【CC】
- [x] 4.3 消费方回归 ①：`4-数字员工/财务部/FI9-研发费用归集与高新认定` `pytest tests/test_oem_isolation.py -q` ⇒ **21 passed**，退出码 0【CC】
- [x] 4.4 消费方回归 ②（**本轮新出现的生产调用方**）：`4-数字员工/财务部/FI10-存货跌价智能分析` `pytest tests/ -q` ⇒ **47 passed**，退出码 0【CC】
- [x] 4.5 运行期产物不污染仓库：三处会走默认构造的用例均 `monkeypatch.chdir(tmp_path)`；`git check-ignore -v reports/audit_log.jsonl` ⇒ 命中 `.gitignore:50:**/reports/`（退出码 0）【CC】

## 5. 🟡 隔离规范 §5 映射表 §2.3 行改判——**文本已备好，本泳道不落字**

🔴 **为什么停在这里**：`3-治理与合规/OEM数据隔离规范.md` 是 `status: 生效` 的 IATF 正式规范，其 L10 自定「维护：边界变更须经 Paul 批准并在本文修订记录登记」；且同一张表 §3.2 行的**同类改判**（V1.2，2026-09-07）确是在 Shao Peishen 答 `2(a)` 之后才落字的（见该文件 §6 修订记录末行）。落字必然要在 §6 新增一行 V1.3 并填"批准"栏——本泳道**不代签批准人**。改判本身亦命中 🟡 `change_criteria`。

- [x] 5.1 **拟改文本已逐字备好**（下方），交业务总线转呈 Shao Peishen 拍板后由承接泳道落字【CC】
- [ ] 5.2 🟡 待 Shao Peishen 一个字母后落字：§5 映射表 §2.3 行 ＋ §6 修订记录新增 V1.3 行【待派发】

**§5 映射表 §2.3 行 —— 现文（2026-09-08 现取）**：

```
| §2.3 通用库写入校验 | L1 | 通用库写入侧"无 OEM 信息"校验 | ❌ **待设计**；且读取侧对 `GENERAL_COLLECTIONS` **无条件放行、不校验 OEM 上下文**（`guard()` L78-80）⇒ 含 OEM 信息的内容一旦写进通用库，任何客户上下文都能检索到，全程不报错不留痕。🔴 **D5=(a)（Shao Peishen 2026-09-02）：校验入口建成前通用库置为只读**，已有内容不受影响、禁止新写入 | 变更包 tasks 4.2（可由 §一 **#466** 同包承接） |
```

**拟改为**：

```
| §2.3 通用库写入校验 | L1 | 通用库写入侧"无 OEM 信息"校验 ／ 只读闸 `OEMRouter.guard_write()` | ⚠️ **部分实现**：**⑴ D5 只读闸 ✅ 已实现**（`guard_write()` 对三个通用 collection 一律拒绝并写 `general_collection_write_denied` audit，审计通道故障时 fail-closed；异常类 `GeneralCollectionReadOnlyError` 与跨 OEM 拒绝分离；**不留运行期开关/可注入 validator**，解闸须改写实现并经变更包评审）。**⑵ §2.3 三项校验入口本身仍 ❌ 待设计** —— 无 OEM 信息校验／脱敏＋质量 Champion 签字／写入写 audit 三项均未建，只读闸正是"入口未建成期间"的替代控制，**不是**该入口的实现。**⑶ 读取侧语义未变**：对 `GENERAL_COLLECTIONS` 仍无条件放行、不校验 OEM 上下文（`guard()` `router.py` L142-144）——但只读闸生效后通用库不再有新内容进入，且全仓从未存在过写入通用库的代码（2026-09-08 穷举实证），故存量风险面为空；是否一并收紧读取侧属新口径变更，**未答**。 | 只读闸＝变更包 `oem-general-collections-readonly`（队列 §一 **#491**）；校验入口本身待另立行 |
```

**§6 修订记录拟新增行**（批准栏须由 Shao Peishen 填，本泳道留空不代签）：

```
| 2026-09-08 | V1.3 | **一处**：**§5 映射表 §2.3 行**由 `❌ 待设计` 改判为 `⚠️ 部分实现` —— D5=(a) 只读闸已落代码（变更包 `oem-general-collections-readonly`，队列 §一 **#491**，`OEMRouter.guard_write()` ＋ 新异常类 ＋ 独立审计动作 `general_collection_write_denied`），单测 13 passed、平台全量 589 passed/1 skipped、FI9 21 passed、FI10 47 passed。🔴 **同行内显式挂账两项，未随本次改判消失**：⑴ §2.3 三项校验入口本身仍未建，只读闸只是入口未建成期间的替代控制；⑵ 读取侧无条件放行未动，是否收紧属新口径变更、未答。 🛑 **未动**：§2.3 正文、§3.2 行、§7 运维面（仍缺）、其余各行现状 | **待 Shao Peishen 批准**（本行不得在批准前落字） |
```

## 6. 收口

- [x] 6.1 `openspec validate oem-general-collections-readonly --strict` 须绿【CC】
- [x] 6.2 push 泳道分支 `claude/op0908e-general-readonly`【CC】
- [ ] 6.3 🟡 **合入 master 不由本泳道执行**（`merge_to_master`），交看护者/sweep 串行收尾【待派发】
- [ ] 6.4 🟡 **design 审两项定夺**（`design.md` §6：读取侧那句怎么处置 ／ 本包 archive 次序是否真解耦）【待派发】
- [ ] 6.5 🔴 **本包不做任何 archive 动作**。已知硬约束：`oem-chroma-ownership-rejudge` 须早于 `oem-audit-fail-closed`（反序会用过渡版盖掉定稿版）；本包 ADDED 的 Requirement 与二者不同名，按 design 决策 3 判定**不进该次序链**——该判定本身列为 6.4 的定夺项②，请审查方复核后再 archive【待派发】

## 7. 已知失真（同域、非本包的活，不顺手改）

- [ ] 7.1 ⚠️ 主 spec `openspec/specs/platform-oem-isolation/spec.md` L9／L15-17 仍写「无 audit 注入时仅抛错（**向后兼容**）」＋ Scenario「无 audit 注入时仅抛错」，与已合入 master 的实现**直接相反**。该失真由 `#466` 持续盯住、同步动作归 `#374` 收尾（见 `oem-audit-fail-closed` tasks 7.6）。**本包未触碰该文件**，且本包 delta 为 ADDED 新 Requirement、与该条不同名 ⇒ **与该失真无冲突**【CC · 仅记录】
