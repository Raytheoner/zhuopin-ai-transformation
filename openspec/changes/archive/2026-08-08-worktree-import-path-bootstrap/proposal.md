# worktree-import-path-bootstrap Proposal

## Why

`pip install -e` 把"哪一份源码是权威"写进了全机唯一的 `site-packages`（本机系统 Python、无 venv），而 `git worktree` 模型的前提是"同时存在 N 份平等的源码副本"——两个模型直接矛盾。本机 `site-packages` 当前注册了 **10 个 editable 包**（`zhuopin_platform` 及 9 个场景包），任一 CC session 在自己的 worktree 里跑一次 `pip install -e`，就会把全机指针**静默**改指向自己，其余 worktree 的 pytest/服务入口毫无察觉——它们仍能正常 `import`，仍能跑测试，仍然全绿，只是测的是别人 worktree 的代码。**这是"返回值正常、结论是反的"故障族**（CLAUDE.md §5「工具静默回退」同族），与已实证的 #98／#208 editable 目标静默漂移是同一件事的完整版。

本次开工核实进一步坐实了严重性：当前全局 `zhuopin_platform` 的 editable 指针指向 `fi2-tax-export-excel-d3938b` worktree（既非本 worktree，也非主工作区），且 `5-平台底座/wecom-aibot-service/scripts/run_aibot_service.py` 第 31-33 行在模块顶层 `from zhuopin_platform... import ...`、**完全没有任何路径保护**——同文件第 38 行却已经对 `aibot_service` 自身包手工 `sys.path.insert(0, str(SERVICE_DIR))`。即：本项目里"给自己的包做路径保护、但漏了平台底座"这个具体缺口已经在生产脚本里真实存在，不是假设的风险。另一个既有精确对照——`4-数字员工/质量部/QD-A-8D不良分析/scripts/run_prefill.py` 第 19 行已经用 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` 解决了"无需 pip install 即可 import 场景自身包"的同一类问题（QD-A 的 `qda_prefill` 包本身**从未被 `pip install -e` 过**，`pip show qda-8d-prefill` 实测确认无此记录，其测试与脚本一直依赖"从场景根目录调用+手工 sys.path 插入"这条与全局 editable 指针完全无关的路径，故 QD-A 全场景不在本次冲突面内——见下）——本变更把这一既有范式扩展到「平台底座 + 场景自身」两条路径，覆盖全部经逐文件核实**真正存在 `zhuopin_platform` import** 的 6 份 `tests/conftest.py` 与 5 个服务入口脚本。

## What Changes

- 在 6 份现存 `tests/conftest.py`（zhuopin_platform / wecom-aibot-service / SC8 / FI1 / FI2 / QD-B）**顶部、任何 `zhuopin_platform`/场景包 import 之前**，插入一段自包含的路径引导代码：从 `__file__` 向上walk 找到本 worktree 的 `5-平台底座/zhuopin_platform` 目录，把它与本场景自身根目录一并插到 `sys.path` 最前。
- 在 5 个会 `import zhuopin_platform` 或场景包的服务入口脚本（`run_baoguan_web.py`／`run_baoguan_dashboard.py`／`run_fi2_web.py`／`run_qd_b_web.py`／`run_aibot_service.py`）顶部插入同一段引导代码；`run_aibot_service.py` 额外把既有的 `sys.path.insert(0, str(SERVICE_DIR))` 一行并入统一引导（不再是"给自己包做保护但漏平台底座"的半截实现）。
- **明确不改**：QD-A 全场景（`tests/conftest.py`／`run_prefill.py`／`run_calibration.py`）——实测其测试文件（`test_calibrate.py` 等 5 份）逐一核对，仅 import `qda_prefill`，从未 import `zhuopin_platform`，且 `qda_prefill` 自身未被 `pip install -e`，不存在可被"静默顶替"的全局指针，本就不在冲突面内（见 design.md「决策点 3」）；`1-转型规划/AI运营指挥中心/serve.py`（实测零 `zhuopin_platform`/场景包依赖，纯标准库 HTTP server，不在本次冲突面内）。
- 更新 `1-转型规划/0-全景路线图/专线opener模板库.md` 与根 `CLAUDE.md` §5「每个场景固定流程」第 1 步：`pip install -e` 从"必需步骤"改为"可选，仅用于 IDE 自动补全/类型检查，不再是 import 能否成功的前提"。
- **BREAKING**：无对外可见行为变化——`import zhuopin_platform`/场景包在任何 worktree 下解析到的都应是"该 worktree 自身的代码"，这本就是所有人一直以来的隐含预期，只是此前不可靠。唯一可观察差异：`pip install -e` 是否被执行、执行了几次、指向哪个 worktree，不再影响任何测试或服务的结果。

## Capabilities

### New Capabilities

- `worktree-import-bootstrap`：定义"pytest 测试收集"与"服务入口脚本启动"这两个时刻，`zhuopin_platform` 与场景自身包必须解析到调用方所在 worktree 自身代码、且不依赖任何全局 editable 安装状态的行为契约。

### Modified Capabilities

（无——本变更不改变任何既有业务判定逻辑，只改变 import 路径解析的可靠性，不涉及 `sweep-*`／`editlock-*`／各场景业务规则等既有 capability 的 REQUIREMENTS。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 两处：① "多个 CC session 并行开工前该不该互相协调 `pip install -e`"——此前完全靠人记住"两个 session 都不要跑 `pip install -e`，若必须跑只允许一方"这条纸面约定（见队列 #300 行内"⏱ 立即可用的止血"段），本变更把它从人脑约定变成与谁跑过、跑了几次都无关的结构性保证；② "改动面该收多窄"——即哪些入口脚本真的存在冲突面、哪些不需要动（如 QD-A 两脚本、`AI运营指挥中心/serve.py`），此前无人系统核实过，是本次 propose 阶段逐文件 grep 实测得出，不是预先假设。
2. **由谁显性化？** CC 建造车间（本变更包设计与实现，独立 worktree `followup-dispatch-apply-25679f`）；持有人 = 本次执行 session；backup/仲裁 = Shao Peishen（design.md 须经其审核批准方可 `/opsx:apply`，per CLAUDE.md §5 固定流程第 3 步，且命中 §5「机制/工具类模块的 openspec 触发门槛」第①条"改变全项目口径"）。
3. **用什么方法提取？** 历史案例反推 + 当场实测坐实（非 AI 起草·专家批改类，无业务语义判断）：队列 #98／#208 是既有的两次 editable 目标静默漂移实证；本次 propose 阶段的实测（`pip show zhuopin_platform` 证实全局指针当前指向第三方 worktree、`run_aibot_service.py`/`run_prefill.py` 两份真实源码的逐行核对）补上了"冲突面到底有多大、哪些文件真正需要改"这一此前只停留在推断层面的问题。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：本变更为**跨项目治理机制**（多 worktree 并行开发的环境隔离基建，非独立业务场景），不适用四档"对客交付"口径；套用最接近的档位描述 = **档1 mock 验证**（design 审通过、代码与单测完成，含"全局指针指向别处、本 worktree 测试仍测到自己代码"的自动化回归用例，但尚未经过真实双 worktree 并行 pytest 的端到端验证）。
- **晋下一档的条件**：晋**档2 真实数据跑通** —— ① 单测覆盖"全局 editable 指针指向另一 worktree 时，本 worktree 测试仍正确解析到自身代码"这一核心回归场景（安全的沙箱化模拟，不触碰真实 `site-packages`）；② 一次真实并行验证：两个 worktree 同时跑 `pytest`，各自测到各自代码（真实 `git worktree`，非模拟）；③ 全量回归零漂移（7 个场景 + 平台底座既有测试套件全绿）；④ opener 模板与根 CLAUDE.md §5 场景固定流程第 1 步同步改写，不留"规则与机制打架"的中间态。
- **价值指标**（风险型）：消除"并行 CC 建造互相静默顶替 editable 指针，测试全绿但测的是别人的代码"这一故障——基线 = 队列 #98／#208 两次既有实证 + 本次开工时的第三次实测坐实（`zhuopin_platform` 指针当前指向 `fi2-tax-export-excel-d3938b`），目标 = 无论谁跑没跑过 `pip install -e`、跑了几次，任一 worktree 的测试与服务入口结果都只由该 worktree 自身磁盘内容决定。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断，纯 Python 导入路径解析）。

## Impact

- 受影响代码：6 份 `tests/conftest.py`（`zhuopin_platform`／`wecom-aibot-service`／`SC8`／`FI1`／`FI2`／`QD-B`）+ 5 个服务入口脚本（`run_baoguan_web.py`／`run_baoguan_dashboard.py`／`run_fi2_web.py`／`run_qd_b_web.py`／`run_aibot_service.py`）。
- 受影响文档：`1-转型规划/0-全景路线图/专线opener模板库.md`、根 `CLAUDE.md` §5 场景固定流程第 1 步。
- **部署影响（design.md 单独分析，回应队列 #300 行内"design 里正好论证零影响 or 须逐个部署"）**：`tests/conftest.py` 改动零部署影响（测试专属，不随任何服务部署）；三个 `.51` 服务入口脚本（SC8/FI2/QD-B）改动本身零风险且不要求立即重新部署——`.51` 上三服务各自有独立 venv（如 `C:\fi2\.venv`），本就不共享本机这套"无 venv 全局 site-packages"环境，不受本变更修复的具体故障影响，下次自然部署即可带上本次改动；企微机器人常驻服务（`ops/wecom-service-home` worktree，与本机其它 CC session 共享同一套全局 site-packages）是唯一真实受益方，建议本次改动合入后随下一次常规重启带上，不需要紧急重启。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——不适用（纯 import 路径解析，不涉及新增 audit 事件）；OEM 隔离——不适用；L2 人工确认门禁——不适用；ISO 26262——不适用（非车规安全相关代码）。
