## Context

采购域 v2.3 重排（总线已执行）把 SC3、SC5 从采购目录退役，功能并入存续场景 SC8/SC7（移交单 §六风险1）。这是跨模块（两个场景目录 + 一个新场景目录）的搬移，且涉及 Python 包改名与已安装 editable 包的环境变更，属于"应该有 design.md" 的范畴（跨模块 + 有迁移步骤/回滚考量）。所有业务决策（谁并入谁、要不要保黄金值）已由 Paul 在移交单拍板，design 只记录搬移方式，不引入新决策点。

## Goals / Non-Goals

**Goals:**
- SC3 引擎（29 tests）原样落地为 SC8 内部子模块，测试 100% 通过，行为零变更。
- SC5 引擎（41 tests）原样落地为新场景 SC7，黄金基准 35850/640000/675850 精确保留。
- 旧场景目录不留可运行代码，只留 README 指针，避免"两处代码都能跑"造成的维护歧义。
- Python 环境与磁盘状态一致（卸载旧 editable 包、安装新的）。

**Non-Goals:**
- 不把 SC3 的答交可信度接入 SC8 现有置信度/承诺流水线（`commitment.py`/`forecast.py` 不动）——这是"随 SC8 深化"的独立后续任务。
- 不给 SC7 添加动态安全库存、呆滞处置等 v2.3 新描述的深化功能——那些是 2027-01 SC7② 阶段的范围，本变更只搬 SC5 已有的采购建议/遴选能力。
- 不改变任何风险分级阈值、MOQ/MPQ 公式、L1/L2 门禁规则。

## Decisions

1. **SC3 → SC8：保留"引擎/agent 两文件"结构，落为 `sc8/answer_confidence_engine.py` + `sc8/answer_confidence.py`**（而非拍平合并成一个文件）。
   理由：与 SC8 现有代码风格一致（SC8 本身已是多文件的 `sc8/` 包），且保留 engine/agent 分离便于未来对照原 SC3 变更包做 diff 核实"确实没改逻辑"。
   备选方案（否决）：合并成一个文件——会让 diff 核实变难，否决。

2. **SC5 → SC7：新建独立场景工程 `4-数字员工/采购部/SC7-库存优化建议/`，Python 包命名为 `sc7_inventory`**（而非在 SC8 内部再挂一个子模块）。
   理由：SC7 是移交单/局部定稿中明确保留的采购目录场景（非退役），且会持续吸纳新功能（2027-01 动态安全库存等），需要独立场景工程承载，与 SC1/SC8 同级。包名不沿用 `sc5_purchase`（该名字绑定退役编号，会误导后来者），改用场景域名 `sc7_inventory`（对应"库存优化建议"），内部模块名 `purchase_engine.py` / `business_rules.py` / `agent.py` 保持不变（这些名字描述的是算法职责，不是场景编号，无需改）。
   备选方案（否决）：保留 `sc5_purchase` 包名——会让未来在 SC7 目录里看到"sc5"字样，产生"这是不是没搬完整"的疑问，否决。

3. **审计 scenario 标签跟随新场景改写**（"SC3"→"SC8"，"SC5"→"SC7"），action 名称、decision 字段结构保持原样。
   理由：SC3/SC5 作为独立场景编号已退役，若审计继续写入已退役编号，未来审计追溯会指向一个在全景规划里查无此场景的编号，违反 IATF 可追溯性的"可理解性"要求。而 action/decision 结构是算法输出的形状，与场景编号无关，不必改。
   备选方案（保留旧 scenario 标签 + 加迁移注释）——考虑过，但会让审计 JSONL 里同时出现"SC3"和"SC8"两套历史，未来查"SC8 全部审计"要跨两个 scenario 值检索，增加使用成本，否决。

4. **迁移方式＝物理移动文件 + 改 import 路径，不用 Python 别名/re-export 兼容层**。
   理由：本仓库无其他代码 import `sc3_intransit`/`sc5_purchase`（已 grep 确认），不存在需要兼容的下游消费方，加一层别名反而是无意义的额外维护面。
   备选方案（保留 `sc3_intransit`/`sc5_purchase` 作为 re-export 壳）——否决，无消费方需要兼容。

5. **旧场景目录清空为单个 README.md 指针**，不用 `git mv` 保留 blob 历史于新路径（因为搬到的不是同名文件，是拆分/重组到不同包结构，`git mv` 语义不适用；改用 `git rm` + 新增，历史仍可通过 `git log --follow` 结合 commit message 找回）。

## Risks / Trade-offs

- [风险] 迁移后如果遗漏某个 import 更新，SC8/SC7 的 pytest 会直接失败 → 缓解：迁移每一步后立即跑该场景全量 pytest，绿了才继续下一步。
- [风险] `pip uninstall` 旧包时若终端里还有进程持有句柄（Windows 常见）可能报错 → 缓解：迁移过程不启动任何 SC3/SC5 的运行时进程，卸载前确认无残留 `__pycache__` 锁定。
- [风险] SC8 现有 `sc8-real-data-cutover` 变更包正在进行中（CLAUDE.md 明确"不要碰"）→ 缓解：本变更只新增 `sc8/answer_confidence*.py` 两个全新文件和对应测试，不修改 `sc8/commitment.py`/`forecast.py`/`gate.py` 等 cutover 变更包接触的文件，无冲突面。
- [权衡] SC7 场景当前只有"迁移进来的 SC5 能力"，尚无 SC7 自己的真实数据验证——这是预期的（SC7 从档 1 起步，与 SC5 原状态一致），不是本变更的缺陷。

## Migration Plan

1. 新建 SC7 场景工程骨架（pyproject.toml + 包目录 + tests 目录）。
2. 搬移 SC5 三个源文件到 `sc7_inventory/`，改 import，跑通 41 tests。
3. 搬移 SC3 两个源文件到 SC8 的 `sc8/`，改 import + scenario 标签，跑通对应 tests（原 29 tests，新家文件名下）。
4. 旧目录清空为 README 指针；`pip uninstall` 旧包，`pip install -e` 新 SC7 包。
5. 全仓回归：SC7 独立 pytest + SC8 独立 pytest（含新增子模块）+ 确认平台 `zhuopin_platform` 测试不受影响（本次未改底座）。
6. 更新 SC8/SC7 CLAUDE.md，`openspec sync` 落 `openspec/specs/`，归档本变更。

**回滚**：若中途发现遗漏，本变更所有内容均为新增文件 + 两个旧目录的删除，回滚 = `git revert` 对应 commit（本变更按"完工即归档"纪律走单次或少数几次 commit，回滚粒度可控）。
