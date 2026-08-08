## Context

见 proposal.md「Why」——根因（`pip install -e` 写全机唯一 `site-packages` vs `git worktree` 的"N 份平等副本"前提矛盾）、既有实证（#98／#208）、本次开工实测（全局指针当前指向 `fi2-tax-export-excel-d3938b`；`run_aibot_service.py` 已有"给自己包做保护但漏平台底座"的真实半截实现；`run_prefill.py` 已有可扩展的既有范式）均在那里，本节不重复。

队列 #300 行内「目标达成度判定」（2026-08-07 补，Shao Peishen 已确认）已把验收标准与两条 Non-Goal 写死：

- **验收标准 = 消除静默类冲突，不是消除所有冲突**。判据：撞了会不会知道——只有静默冲突会让人无法信任测试结果，响亮冲突（如 `git push` 非快进被拒）当场可见可修，不构成本次改动理由。
- **Non-Goal ⑴**：不为 `git push` 并发造机制（响亮失败，opener 加一句 fetch+rebase 重试即可）。
- **Non-Goal ⑵**：不顺手上 venv（候选甲，已在下方「决策点 1」否掉；本次选定候选丙，不是"丙＋甲"）。

现有 7 份 `tests/conftest.py` 逐一核实过，当前**只含 fixture，无任何路径引导代码**（本次开工时逐份 Read 确认）；其中 QD-A 一份经进一步核实（其 5 份测试文件逐行 grep import 语句 + `pip show qda-8d-prefill` 确认未被 editable 安装）**不在冲突面内、不需要改动**（见「决策点 3」），故实际改动 6 份。5 个服务入口脚本现状：

| 文件 | 现状 |
|---|---|
| `SC8/scripts/run_baoguan_web.py`／`run_baoguan_dashboard.py` | 模块顶层零 `sys.path` 操作；`zhuopin_platform`/`sc8` import 全部延迟到 `main()` 内部，纯靠全局 editable 指针解析 |
| `FI2/scripts/run_fi2_web.py` | 同上 |
| `QD-B/scripts/run_qd_b_web.py` | 同上 |
| `wecom-aibot-service/scripts/run_aibot_service.py` | 模块顶层第 31-33 行 `from zhuopin_platform...` **零保护**；第 38 行却已 `sys.path.insert(0, str(SERVICE_DIR))` 保护 `aibot_service` 自身包——同文件内两种待遇并存，是本变更要修的具体缺口的活样本 |
| `QD-A/scripts/run_prefill.py`／`run_calibration.py` | 第 19 行已有 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`，只解决场景自身包（`qda_prefill` 不依赖 `zhuopin_platform`，故现状已经正确、不需要改） |

## Goals / Non-Goals

**Goals:**
- 任一 worktree 内跑 `pytest` 或启动服务入口脚本，`import zhuopin_platform` 与本场景自身包解析到的必须是**该 worktree 磁盘上的代码**，与全局 editable 安装当前指向谁无关、与谁跑没跑过 `pip install -e` 无关。
- 保留 `pip install -e` 可选（IDE 自动补全/类型检查仍受益），但它是否被执行不再影响 `pytest`/服务入口的正确性。
- 新增场景的 scaffold 步骤天然带上这层保护（opener 模板与 §5 流程第 1 步同步改写）。

**Non-Goals（除队列 #300 已写死的两条外，本次再补充三条）：**
- 不引入 venv（队列已定，Non-Goal ⑵）。
- 不消除 `git push` 并发冲突（队列已定，Non-Goal ⑴）。
- 不覆盖"手敲 `python -c "import zhuopin_platform"` 这类临时诊断命令"——这类命令本就该看全局真实指向，看到的正是当前谁的 `pip install -e` 生效，不算本次要消除的"静默"，是刻意保留的可观测性。
- 不改变任何业务判定逻辑、不新增 audit 事件、不改变任何 spec 既有 REQUIREMENTS。
- 不为 QD-A 的两个入口脚本预先加平台底座路径保护——它们现在不依赖 `zhuopin_platform`，加了也用不上，属于为假设的未来需求预先设计（见「决策点 4」）。

## Decisions

### 决策点 1：路径引导代码的落点形态——自包含重复片段（推荐）vs. 共享 `_bootstrap.py` + 极简加载 stub

两个候选：

- **候选甲（推荐）：完全自包含的重复片段**，每份 `conftest.py`/入口脚本顶部直接写约 10 行纯标准库代码（见下方「代码形态」），逻辑本身零依赖 `zhuopin_platform`。
- **候选乙：indirection** —— 在 `5-平台底座/zhuopin_platform/_bootstrap.py`（注意：与 `zhuopin_platform` 包同级，不在包内部，因为它必须能在包尚未可 import 时被文件路径直接找到）放置实际的 sys.path 处理逻辑，每份调用方只放一段约 5 行的"向上找到这个文件→用 `importlib.util` 加载→调用"的极简 stub。

**选定候选甲**，理由：

- 候选乙看似"更 DRY"，但本变更要保护的逻辑本身极其简单且稳定（"从 `__file__` 向上找到 `5-平台底座/zhuopin_platform` 目录，插两条 `sys.path`"），不涉及任何会演化的业务语义（对比 #306 那 7 份重复实现是在各自演化列语义/转义规则，是真正有漂移风险的重复）。CLAUDE.md 系统级指导原则明确"三行类似代码好过一次过早抽象"——候选乙引入的 `importlib.util.spec_from_file_location` 间接层，换来的唯一收益是"未来若这段逻辑要改，只需改一处"，但改这段逻辑的概率极低（它只依赖"`5-平台底座/zhuopin_platform` 相对仓库根的路径"这一项目结构事实，本项目自 2026-06 建仓以来从未变过），成本却是每个调用点都多一层需要理解的间接调用，且候选乙本身也需要处理"repo 根标记文件缺失时怎么报错"这类边界，并不比候选甲更简单。
- 与 `run_aibot_service.py` 现有的 `sys.path.insert(0, str(SERVICE_DIR))`／`run_prefill.py` 现有的同类写法风格一致（均为自包含单行/单段，无 indirection），改动风格与既有代码库保持一致，降低认知负担。
- 若未来真的需要调整这段逻辑（如项目目录结构大改），届时是一次性的全项目 grep+批量替换（纯文本替换，无语义判断），不构成持续性维护负担。

**代码形态**（tests/conftest.py 与 scripts/run_*.py 两类文件通用，因为两者的"调用方相对场景根的层级"恰好相同——都是 `<scenario_root>/tests/conftest.py` 或 `<scenario_root>/scripts/run_xxx.py`，`__file__` 的 `.parent.parent` 都等于场景根）：

```python
# —— worktree 隔离引导（队列 #300）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")
```

`wecom-aibot-service` 的 `run_aibot_service.py` 额外要求：把现有第 35-38 行（`SERVICE_DIR`/`NAIVE_REPO_ROOT`/`sys.path.insert(0, str(SERVICE_DIR))`）与本段合并——`_HERE.parent.parent` 对该文件而言就是 `SERVICE_DIR`，天然等价，不需要保留两套。

### 决策点 2：repo 根发现方式——文件系统向上 walk（推荐）vs. `git rev-parse --show-toplevel` 子进程

`wecom-aibot-service/aibot_service/repo_paths.py::resolve_repo_root` 已有一套基于 `git -C <锚点> rev-parse --show-toplevel` 子进程调用的仓库根解析实现（#126 落地），本变更是否应该复用/移植这套逻辑？

**选定文件系统向上 walk（`(p / "5-平台底座" / "zhuopin_platform").is_dir()`），不复用 `repo_paths.py` 的 git 子进程方式**，理由：

- `repo_paths.py` 的场景是"服务常驻进程运行时、按需解析一次"，一次 `git` 子进程调用（约几十毫秒）可忽略；本变更的场景是**每次 `pytest` 收集测试时、每个 `conftest.py` 加载都要跑一次**，量级不同——pure Python 路径 walk 是微秒级，避免给测试收集引入不必要的进程派生开销与对 git 可执行文件在 PATH 中可用性的隐性依赖。
- `repo_paths.py` 本身在 `aibot_service` 包内——被本变更保护的调用方（`conftest.py`）此刻恰恰还不能保证 `aibot_service`/`zhuopin_platform` 可 import（这就是问题本身），不能反过来依赖它。
- 文件系统 walk 的判据（"祖先目录里是否存在 `5-平台底座/zhuopin_platform` 子目录"）对本项目当前结构而言是充分且稳定的标记——不需要 `.git` 目录/文件这类更通用但也更间接的判据。

### 决策点 3：改动范围——只改"真正存在冲突面"的文件，不做防御性扩面

**核实结论（本次 propose 阶段逐文件读取源码得出，非推断）**：

- `AI运营指挥中心/serve.py`：grep 全文件 import 语句，零 `zhuopin_platform`/场景包依赖（纯标准库 `http.server`），**不在冲突面内，不改**。
- QD-A 全场景（`tests/conftest.py`／`scripts/run_prefill.py`／`scripts/run_calibration.py`）：`run_prefill.py`／`run_calibration.py` 已有场景自身包路径保护（`sys.path.insert` 解析 `qda_prefill`）；`tests/conftest.py` 与其 5 份测试文件（`test_calibrate.py`/`test_doc_reader.py`/`test_field_extractor.py`/`test_scrubber.py`/`test_track_a_calibration.py`）逐行 grep import 语句，**只 import `qda_prefill`，零 `zhuopin_platform` 依赖**；`pip show qda-8d-prefill` 实测确认该包**从未被 `pip install -e`**（不存在任何全局指针可被"静默顶替"）。三点合一：QD-A 全场景**不在冲突面内，不改**——与"QD-A 不依赖 zhuopin_platform"（proposal.md 已知事实）相比，这一核实多确认了一层：即便 QD-A 未来某天依赖了 zhuopin_platform，其自身包 `qda_prefill` 本身也没有"被全局指针顶替"的暴露面，因为它压根不吃 editable 安装这套机制。
- 其余 6 份 `conftest.py` + 5 个入口脚本：均已确认存在 `zhuopin_platform` 和/或场景自身包的 import，**全部在冲突面内，需要改**。

**为何不防御性地也给 QD-A/serve.py 加保护**：CLAUDE.md 系统级指导原则"不为假设的未来需求设计"——QD-A 若未来真的接入 `zhuopin_platform`（如场景 CLAUDE.md 提到的"高置信字段接 audit"），届时该改动本身就会在同一个 PR 里显式加上 import，届时顺手加两行路径引导即可，不需要现在为一个尚不存在的依赖预先铺路。

### 决策点 4：opener 模板与 §5 流程第 1 步怎么改——`pip install -e` 降级为可选，不是删除

队列 #300 行内「丙的如实边界」③ 已经预判了这一点："配套须改 opener 模板与 §5 场景固定流程第 1 步——把『先 pip install -e』这一步删掉／改写为『路径自动引导，无需安装』，否则规则与机制会打架"。

**选定"改写为可选"而非"删除该步骤"**，理由：`pip install -e` 仍对 IDE（如 VS Code Pylance）的自动补全/跳转定义/类型检查有意义——这些工具通常依赖已安装包的元数据（`.egg-info`/`.dist-info`），本变更的 `sys.path` 运行时引导不会让 IDE 静态分析工具知道 `zhuopin_platform` 在哪。新表述：「`pip install -e` 可选执行（利于 IDE 自动补全），但不再是 `pytest`/服务入口能否正确 import 的前提——路径由 conftest.py/入口脚本自动引导。」

## Risks / Trade-offs

- **[风险] 若未来项目目录结构调整（如 `5-平台底座` 改名），全部约 12 处引导片段需要同步改**——缓解：这段判据是纯文本字符串（`"5-平台底座" / "zhuopin_platform"`），全项目 grep 该字符串即可定位全部需要同步的位置，是机械操作非语义判断；且目录改名本身就是一次影响面极广的变更，届时不会只有这 12 处需要改。
- **[风险] 新增场景若忘记在 scaffold 时加入引导片段，会退回到"依赖全局 editable 指针"的旧状态、且不报错**——缓解：opener 模板与 §5 流程第 1 步同步改写后，新场景的标准开工步骤天然包含这一步；且这本就是"新场景暂不受本次保护"而非"新引入一个更差的状态"，不构成倒退。
- **[权衡] 约 12 个文件各自多出约 10 行样板代码**——已在「决策点 1」论证过，权衡后选择接受这一"必要的重复"而非引入 indirection。
- **[风险] `sys.path.insert(0, ...)` 可能与 pytest 自身的 rootdir 插入机制产生优先级微妙差异**——缓解：本变更片段在 `conftest.py` **模块顶层、pytest 收集测试文件之前**执行，`sys.path.insert(0, ...)` 保证本变更插入的路径优先于任何既有 `sys.path` 条目（含 pytest 自己可能插入的 rootdir、含全局 site-packages 里的 editable 指针），这正是"消除静默冲突"的关键——顺序上必须最优先，不能是"追加"。

## Migration Plan

不涉及数据迁移（纯代码改动，无持久化状态）。

- **conftest.py 改动**：合入 `master` 后立即对所有后续 `pytest` 调用生效，无需任何部署动作。
- **服务入口脚本改动**：`.51` 三服务（SC8/FI2/QD-B）各自独立 venv，本就不受本次修复的具体故障影响，**不需要紧急重新部署**——随下次自然发布（下一次该场景有业务改动需要部署时）一并带上即可；企微机器人常驻服务（`ops/wecom-service-home`）与本机其它 CC session 共享全局 site-packages，是唯一真实受益方，**建议本次改动合入 master 后随下一次常规重启（如下一次功能上线的重启窗口）带上**，不构成独立的紧急部署事项。
- 回滚策略：`git revert` 本次改动提交即可，各文件回到"依赖全局 editable 指针"的旧状态（已知有限风险，非新增风险）。

## Open Questions

（无——以下三点已获 Shao Peishen 会话内拍板，均按推荐项执行，可 `/opsx:apply`。）

1. **决策点 1（片段架构）**：✅ 选定候选甲（自包含重复片段）。
2. **LAN 范围**：✅ 代码实现＋单测＋本地真实并行验证（两个 worktree 同时跑 pytest）现在（不在 LAN）就做；仅"重启企微机器人常驻服务"留到下次常规重启窗口，不构成独立紧急部署事项。
3. **决策点 4（opener/CLAUDE.md §5 措辞）**：✅ 改为"可选，利于 IDE"的表述，不直接删除该步骤。
