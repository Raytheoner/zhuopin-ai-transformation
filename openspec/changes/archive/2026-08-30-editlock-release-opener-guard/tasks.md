# tasks — editlock-release-opener-guard

> ✅ **design D1-D5 已审过（Shao Peishen 2026-08-30 答「审过」，整体通过、无点名修改）** ⇒ 可开工。执行环境：**CC**（写生产码、自行 commit+push、一任务一 worktree）。
> 🔴 **本包改的是 CC 自己收工要调的那把锁** —— 改坏了会把自己锁在外面。**每改一处先跑一次 `release --help` 与既有单测确认没把入口打断**，再往下走。

## 0. 前置

- [x] 0.1 design D1-D5 审通过（Shao Peishen 2026-08-30 答「审过」，记录于队列 §一 `#437`）

## 1. 实现

- [x] 1.1 从 `工具-opener块lint.py` 复用块解析与判据（`iter_fenced_blocks`／`settings_line`／`block_env`／`SESSION_TITLE_RE`／`EXCEPTION_TOKEN_RE`）；🔴 **不重写一份**（D3），并在 lint 与 release 两处各留一句「判据正本在此／调用点在彼」的指针——**实际复用面比清单更彻底**：直接调用 `check_block`（内部已含 `block_env`／`SUBTASK_TOKEN_RE`／`EXCEPTION_TOKEN_RE`），零第二份判据实现
- [x] 1.2 新常量 `OPENER_EXEMPT_MARK = "opener豁免："`
- [x] 1.3 `release` 增结构检查：取 ⑹ 那份脏文件列表 → 筛 `.md` → 扫 opener 块 → 按环境分流校验 → 不过即拒绝（fail-closed）
- [x] 1.4 🔴 **环境分流**（D4）：`CC` 校验；`Cowork` **不校验 title**；未声明环境**不校验**
- [x] 1.5 回显：无论有无发现都打印「已校验本次触碰的 N 个 `.md`，其中含 opener 块 M 个」；🔴 **措辞不得暗示全覆盖**（D2）
- [x] 1.6 逃生阀：note 或本次触碰的队列行内 `opener豁免：<理由>`；🔴 **不加 `--force` 开关**（D5）

## 2. 测试

- [x] 2.1 CC 块缺 `set_session_title` → 拒绝
- [x] 2.2 CC 块有 title 无例外句 → 拒绝
- [x] 2.3 写对的 CC 块 → 放行
- [x] 2.4 🔴 **Cowork 块无 title → 放行**（防误伤，本项不过则本线自己每次 release 都会被拦死）
- [x] 2.5 未声明环境的块 → 放行
- [x] 2.6 `opener豁免：` 在 note 里／在队列行里，两处各测一次 → 放行且理由落盘
- [x] 2.7 零 opener 块时仍有回显
- [x] 2.8 全量回归绿、零回归——`OpenerGuardReleaseTests` 新增 13 条 ＋ 既有 293 条，306 passed；**实现途中额外发现并修复一处未预见的 fail-closed/适用前提混淆缺陷**（不在 git 工作树内时旧代码误判为 fail-closed，改用 `_is_inside_git_work_tree` 前置判断后既有 39 条纯 tempdir 夹具用例全绿）；唯一未过的 `GenderPronounLintTests::test_roster_stays_in_sync_with_root_claude_md` 系本包触碰区之外的既有缺陷（CLAUDE.md §1 抽取正则失效）

## 3. 真实验活（不是 mock）

- [x] 3.1 **真阳性复现**：用真实历史版本跑，**必须被拦下**——拦不下就是本包没解决那 18 次里的任何一次。实测：目标文件在本仓库的 git 历史中，`set_session_title` 缺失版本对应提交 `a837b73`（`c7009f4` 未直接改动该文件正文，经核实 `a837b73`→`1323862` 才是缺失版→补写版的实际提交对），补写版为 `1323862`；用 `a837b73` 版跑 `_opener_guard_violations` 命中 1 处 F1、**正确拒绝**，`1323862` 版跑同一函数 0 违规
- [x] 3.2 **真阴性**：对当前仓库现存的 4 份合规派单件（本行自身 `#437` 派单件、`#312`、`#438`、`#435` 修复版）跑，opener 块 4 个，**零误报**
- [x] 3.3 **不误伤自己**：本 session 收工 `release` 时本守卫已生效且未拦错——实测回显「已校验本次触碰的 6 个 `.md`，其中含 opener 块 1 个」，正常释放

## 4. 收口

- [x] 4.1 `#284` 回写：形态① 改为「已由咽喉守住（**限已登记路径**）」，🔴 **不销号**——未登记路径仍是人守（D2）
- [x] 4.2 模板库 `补充三` 加一句指针：判据已挂 release 咽喉，正本仍在本节
- [x] 4.3 §二 批次登记 ＋ commit+push（ff-only）——批次 `B-0830_27_OP0830G_437收口回写`（登记队列文件自身）；代码侧（本工具＋测试＋模板库指针＋归档后的 openspec 四件＋本行派单件）走 worktree 分支 `claude/op0830g-release-opener-guard-a9e7af` 自行 commit+push（详见 tasks.md 同批说明）
- [x] 4.4 队列 `#437` 回写状态列开头 ✅ ＋ 实测（3.1 拦下、3.2 零误报）
- [x] 4.5 全部 [x] 后**当场** `/opsx:archive editlock-release-opener-guard -y`
