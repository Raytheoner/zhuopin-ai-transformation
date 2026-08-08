## 1. 单测先行（须含验收要求①：全局指针指向别处仍测到本 worktree 代码）

- [x] 1.1 新增回归用例：`5-平台底座/zhuopin_platform/tests/test_worktree_import_bootstrap.py::TestWorktreeIsolationSurvivesPoisonedGlobalPointer::test_local_worktree_wins_over_poisoned_pythonpath`——安全模拟"全局 editable 指针指向另一 worktree"：用 `tmp_path` 构造两份内容不同（含可区分哨兵常量 `WORKTREE_SENTINEL`）的合成 worktree，通过 subprocess 传入伪造 `PYTHONPATH` 环境变量模拟"全局指针污染"（不触碰真实 `site-packages`），断言子进程 `import zhuopin_platform` 解析到本 worktree 的哨兵值而非污染值。**被测代码不是手打副本，是从真实生产 `conftest.py` 用稳定文本锚点原样抽取的引导代码文本**，避免测试与生产代码漂移。另附负向对照：手工验证"若不含本次引导代码，同一污染环境下会解析到错误的 A 而非 B"（真实复现旧故障，证明测试确实有效，非永真断言）。
- [x] 1.2 `test_no_pythonpath_pollution_still_resolves_locally`——从未执行过 `pip install -e`（`sys.path`/`PYTHONPATH` 中不含任何相关条目）时，路径引导后仍可正常 `import`。
- [x] 1.3 `TestMissingRepoRootMarkerFailsLoud::test_raises_when_marker_absent_in_all_ancestors`——仓库根标记缺失时（从一个不含 `5-平台底座/zhuopin_platform` 祖先的临时目录出发）显式抛出 `RuntimeError`，不静默跳过。
- [x] 1.4 核对 QD-A 与 `AI运营指挥中心/serve.py` 确认现状不变、无需新增测试；核实结论已写入 proposal.md/design.md（QD-A 5 份测试文件逐行 grep 零 `zhuopin_platform` 依赖 + `pip show qda-8d-prefill` 确认未被 editable 安装，双重确认不在冲突面内）。

## 2. 实现：路径引导代码落地

- [x] 2.1 在 6 份 `tests/conftest.py`（`zhuopin_platform`／`wecom-aibot-service`／`SC8`／`FI1`／`FI2`／`QD-B`）顶部插入 design.md「决策点 1」给出的引导代码，插入位置早于该文件现有的任何 `zhuopin_platform`/场景包 import。QD-A 经核实不在冲突面内，不改（见 design.md「决策点 3」）。
- [x] 2.2 在 4 个服务入口脚本（`run_baoguan_web.py`／`run_baoguan_dashboard.py`／`run_fi2_web.py`／`run_qd_b_web.py`）顶部插入同一段引导代码。
- [x] 2.3 `run_aibot_service.py`：插入引导代码并将现有 `SERVICE_DIR`/`sys.path.insert(0, str(SERVICE_DIR))` 合并进统一引导（不再保留"给自己包做保护但漏平台底座"两套并存的逻辑）；第 39 行起 `from aibot_service...` 系列 import 确认仍在引导代码之后、正常工作。
- [x] 2.4 逐文件核对：全部 11 个改动文件用 `python -m py_compile` 语法核验通过；引导代码位置逐一目视确认早于该文件全部 `zhuopin_platform`/场景包 import。

## 3. 真实并行验证（验收要求②，本机不在 LAN，经 Shao Peishen 确认可现在做——已完成）

- [x] 3.1 用 `git worktree add --detach` 从 `origin/master`（不含本次修复）真实创建第二 worktree（临时路径，验证后已清理），`pip install -e` 其 `zhuopin_platform` **真实把本机全局 editable 指针指向它**（`pip show` 核实生效）；随后在**本 worktree**（含本次修复）跑 `pytest`（`test_worktree_import_bootstrap.py` 4 项 + SC8 全量 377 项），**全部通过**且全局指针全程保持污染状态未复原（`pip show` 二次核实）——证明本 worktree 的测试结果与全局指针指向谁无关。同时在**第二 worktree 自身**跑 `pytest`（zhuopin_platform 262+1skip），确认它也正确测到自己代码（自我一致，无收尾误伤）。验证完毕后指针复原指向本 worktree、临时 worktree 已 `git worktree remove --force` 清理。
- [x] 3.2 如实记录验证覆盖与边界：**深度覆盖** zhuopin_platform 自身 + SC8（含本次新增的 3 个专项回归用例，subprocess 级别，最强证据）；**其余 5 个场景**（wecom-aibot-service/FI1/FI2/QD-B + 平台底座之外）**依赖同一份引导代码**（同一段文本，非各自独立实现），未逐个重复真实污染验证——判断依据：引导代码是纯路径解析逻辑，不含任何随场景变化的分支，SC8 一例的真实验证已完整覆盖该逻辑的全部执行路径（找到标记/插入路径/优先级生效三步），其余场景是同一份文本的字面复制，重复验证边际价值低，全量回归（见 §5）已确认各自套件本身零漂移。

## 4. 文档同步

- [x] 4.1 核实 `1-转型规划/0-全景路线图/专线opener模板库.md` 全文 grep `pip install -e`/`editable`/`site-packages` **零命中**——该文件本就不含相关表述，无需改写，如实记录（非遗漏）。
- [x] 4.2 更新根 `CLAUDE.md`：§3 仓库结构表（`zhuopin_platform` 行）、§4 平台底座架构开篇段、§5「每个场景固定流程」第 1 步，三处均按 design.md「决策点 4」改写为"`pip install -e` 可选，利于 IDE"表述，并指向本变更包归档路径。
- [x] 4.3 队列 #300 行回填（见本次 commit，含核实结论/决策点定案/测试数/真实验证证据/部署影响结论）。

## 5. 验证

- [x] 5.1 全量回归（本次改动生效状态下逐场景真实数字）：zhuopin_platform 262 passed+1 skip／SC8 377 passed+4 skip／FI1 33 passed／FI2 128 passed+9 skip（较既有基线 128+7，skip 数差异经核实为本地环境缺失的 gitignore 真实/黄金数据文件所致，与本次改动无关，passed 数精确一致零回归）／QD-B 83 passed+25 skip／wecom-aibot-service 344 passed+1 skip——**除 FI2 skip 计数的环境性差异外，其余全部与既有基线精确一致，零回归**；另加本变更新增的 4 个专项测试全绿。

## 6. 收工

- [x] 6.1 `/opsx:archive worktree-import-path-bootstrap -y`（tasks 全部勾选后当场归档）。
- [x] 6.2 队列 §二 登记待 commit 批次，文件清单含队列文件自身（协议〇.7 惯例）。
- [x] 6.3 commit + push；收工重跑一次文档台账。
- [x] 6.4 worktree 为一任务一 worktree 的既定持有 worktree（`followup-dispatch-apply-25679f`），不自删，留待后续任务继续使用或按惯例收尾。
