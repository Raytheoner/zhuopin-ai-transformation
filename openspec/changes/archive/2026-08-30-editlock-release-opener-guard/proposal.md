# editlock-release-opener-guard Proposal

> **状态：✅ design 审已过（Shao Peishen 2026-08-30 答「审过」，D1-D5 整体通过、无点名修改）⇒ 可派 CC。**
> **承载队列行**：§一 `#437`（`[S:open]` 待领，2026-08-30 摘 🛑）。计数台账＝§一 `#284`。
> **openspec 门槛核对**：命中第 ③ 条「**改变既有模块对外语义**」——`release` 在相同输入下会新增一个拒绝分支 ⇒ 必走 openspec 含 design 审。

## Why

**形态① 的 lint 早就建成并在扫，2026-08-30 却仍发生第 18 次违反。**

`工具-opener块lint.py` 实现了两个失效形态的判据（① CC 块含 `【设置】` 而无 `set_session_title`；② 有 title 而无子任务例外句），但它扫的是 **git 已跟踪**的 `.md`（`_tracked_md_files`）。

🔑 **而 opener 的高危时刻恰恰是「刚写出来、还没 commit、马上就要粘出去」那几分钟——派出发生在跟踪之前，lint 结构性地看不到它。**

⇒ 形态① 名义上已机制化，实际对**新出的 opener** 仍是人守。**今天这 18 次违反，没有一次是被 lint 报出来的**——第 18 次是 Shao Peishen 在会话列表里看出 session 名丢了编号才发现的。

**通用判据（本包的立身之本）**：**门要装在动作必经的那个咽喉上；装在事后扫描器里，等于没装。**

## What Changes

给 `工具-共享文档编辑锁.py` 的 `release` 增加一道结构检查（与既有 ⑹ 登记完整性并列，同一处 fail-closed 语义）：

**本次持锁期间触碰的 `.md` 里，若含 opener 代码块，按块的执行环境分流校验**：

| 块环境 | 校验 | 不过的后果 |
|---|---|---|
| **CC** | 须有 `set_session_title` 行，且该行须含子任务例外句 | 拒绝 release |
| **Cowork** | **不校验 `set_session_title`**（该工具在 Cowork 侧不存在，`补充一` 2026-08-27 已实测） | — |
| 未声明环境 | 不校验（宁可漏，不误伤） | — |

**逃生阀**：本次 note 或本次触碰的队列行内写 `opener豁免：<理由>`，与既有 `登记豁免：`／`WIP豁免：` 同形。

## Non-Goals

- **不改 `工具-opener块lint.py`** —— 只**复用**它的判据函数（`iter_fenced_blocks`／`settings_line`／`block_env`／`SESSION_TITLE_RE`／`EXCEPTION_TOKEN_RE`），**不重写一份**。理由见 design D3。
- **不假装全覆盖** —— 覆盖边界见 design D2，必须如实写进回显。
- 不动 `_count_mechanism_wip`、不动 `_suggest_status_reclassification`（`#435` 子项 E 刚落地的邻居，同文件不同函数）。
- 不改模板库正文（`补充三` 仍是判据正本）。

## Impact

`0-学习与工具/工具-共享文档编辑锁.py`（release 结构检查段 ＋ 复用 import）＋ 其测试；`#284` 回写「形态① 已由咽喉守住（限已登记路径）」。
🔴 **不触碰** `.51`、不触碰队列写入路径本身、不触碰 sweep。
