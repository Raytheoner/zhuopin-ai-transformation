# CLAUDE.md — `4-数字员工/`（场景建造目录级记忆）

> 本文件由根 `CLAUDE.md` §5「每个场景固定流程」**第 1-7 步原文原样下沉**而来（2026-08-22，`OP0822F`，A 档 A1）。正文一字未改。
> 🔴 **根 `CLAUDE.md` 里留有一行哨兵指向本文件**——哨兵被删，本文件对新会话就完全不可见（子目录 `CLAUDE.md` 不进系统注入）。故 `0-学习与工具/工具-CLAUDE进度段lint.py` 须加一条校验：根里每个哨兵指向的子目录 `CLAUDE.md` 确实存在（已登记 §一 待领行派 CC）。
> 🔴 **第 8 步（发布即刻起草跟进信，含串行闸三分支与发送三条硬前置）不在本文件，仍留在根 `CLAUDE.md`**——它可能在任何会话被触发，且违反后果落在外部同事身上（清单 C 档 C3；Shao Peishen 2026-08-22 答 (a)）。

## 每个场景固定流程（第 1-7 步）

  1. 进入 `4-数字员工/部门/场景名/`；`pip install -e .../5-平台底座/zhuopin_platform` **可选**（利于 IDE 自动补全/类型检查，**不再是** `pytest`/服务入口能否正确 import 的前提——`tests/conftest.py` 已内置路径引导，队列 #300，2026-08-08）；🔴 **新场景 scaffold 的引导代码不再靠「照抄既有场景」**：**唯一被允许的样板见 `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py` 模块 docstring**（5 行无分支 stub + `ensure_paths(__file__, <自身包根>[, strict=True])`；`tests/conftest.py` 一律带 `strict=True`，服务/CLI 入口不带）。**由 CI `bootstrap-stub-lint` 硬门禁强制**（`0-学习与工具/工具-引导样板lint.py`，非 stub 形态的内联引导即违规）——本条是指针，不是需要记住的规则。 🔴 **`.env` 凭据定位同理，且是另一半**（队列 #354，变更包 `env-anchor-collapse`）：**唯一被允许的写法＝一行 `from zhuopin_platform.env_anchor import load_env`**，见该模块 docstring；**不得再写「向上逐级找最近的 `.env`」**——那个写法从 linked worktree 跑时会命中该 worktree 自己的陈旧副本、**且不报错**（前两次同族事故漂的是状态文件，这次漂的是密钥）。由**同一个** lint 的第二条判据守（AST 锚定，不误伤讲解该反范式的散文）——本条同样是指针，不是需要记住的规则
  2. `openspec init`（首次）→ `/opsx:propose "场景描述"` → 生成 proposal + design + tasks
  3. **停下，Paul 审 design.md（技术决策拍板）**
  4. `/opsx:apply` → SuperPowers 先写测试再实现
  5. 真实数据验证（任务 N.1）→ `/opsx:archive` → git commit + push
  6. **当场写/更新场景 CLAUDE.md**（六段式：定位/决策/底座/红线/时间线/依赖）→ git commit
  7. **发布收口（Paul 2026-07-19 定）**：具备发布条件即部署到 `.51` + 部署段基本测试（`/api/ping`·关键页 200·一次全量重算）+ 回滚 SOP 在位 + 开灰度反馈入口 → 场景 CLAUDE.md 补「部署状态」段。**部署 + 部署段基本测试 = 建造模块收口**（非「代码跑通即完」）；发布条件四关与门禁见上「发布即收口纪律」。
