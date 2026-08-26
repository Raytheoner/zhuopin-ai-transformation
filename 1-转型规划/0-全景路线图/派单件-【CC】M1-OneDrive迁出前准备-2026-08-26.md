---
title: "派单件 · 【CC】M1 · OneDrive 迁出前准备（零风险，可提前做完）"
created: 2026-08-26
执行环境: CC
派出线: 环境总线（Cowork）
授权: Shao Peishen 2026-08-26 批准迁移方案整体 ＋ 答「M1 现在就建行」
承接队列行: §一（M1，编号待锁空闲后补登）／母行 §一 #170「OneDrive 迁出」切片
方案正本: `3-治理与合规/仓库迁出OneDrive-迁移方案（未批准·方案阶段）-2026-08-25.md`
---

# 【CC】M1 · OneDrive 迁出前准备

## 开场词（复制即用）

▶ **粘贴端：CC**　✅ **本件可进泳道**（触碰区与现有泳道零重叠），也可单独开一个 CC 跑。

```
【设置】执行环境：CC ｜ 分支：master ｜ worktree：☑（onedrive-migration-m1，新 worktree，收工自删）｜ 工作区：共享主工作区 ｜ 派出线：环境总线（Cowork）
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[CC] M1-OneDrive迁出前准备
本次一件：读 `1-转型规划/0-全景路线图/派单件-【CC】M1-OneDrive迁出前准备-2026-08-26.md` 全文后按 T1→T4 执行。🔴 三条硬约束：① **本件零迁移动作**——不移动任何目录、不改任何计划任务的现有注册、不动 site-packages；产出全部是「改好字的源码 ＋ 一个待跑的脚本」，跑不跑由 Shao Peishen 在窗口日决定；② 迁移脚本必须**可在管理员 PowerShell 里一条命令跑完**，且**不得依赖仓库内的相对路径**（它执行时仓库正在被移动）；③ 任一处与方案件冲突即停下登记，不自行改判。收工回写队列行＋登记 §二 批次。
```

---

## 🔴 为什么 M1 值得单独做完：M2 那一步不能临场想

真正的移动窗口里，**执行者站在被搬的地板上**——`robocopy /MOVE` 会把 CC 自己的 worktree、`.git` 指针、正在写的日志一起抽走。所以 M2 只能是「**你在管理员 PowerShell 里跑一个早就写好的脚本**」。

**M1 的全部意义就是把那个脚本和它依赖的一切先准备好、验过、晾在那里。**

---

## T1 · B 类源码常量改字（13 处，其中 3 处是 2026-08-26 新查出的）

方案件 §二 B 类表为准。**逐项确认后改，改完 `git grep` 复核**。

**必须改（11 处 / 8 个文件）**：

| 文件 | 行 |
|---|---|
| `0-学习与工具/工具-落库sweep.py` | 418 `MAIN_WORKSPACE` |
| `0-学习与工具/工具-主工作区安全同步.ps1` | 27 `$REPO` |
| `0-学习与工具/工具-注册落库sweep计划任务.ps1` | 61 `$REPO` |
| 🔴 `5-平台底座/wecom-aibot-service/start-aibot-service-dev.ps1` | 54 `$MAIN_ROOT` |
| 🔴 `5-平台底座/wecom-aibot-service/run-decision-reminder-check.ps1` | 13 `WECOM_AIBOT_QUEUE_PATH` ／ 14 脚本绝对路径 |
| 🔴 `5-平台底座/wecom-aibot-service/run-followup-dispatch-check.ps1` | 13 ／ 14 同上 |
| `5-平台底座/wecom-aibot-service/register-decision-reminder-task.ps1` | 70 `$REPO` ／ 73 `$MAIN_WORKSPACE_QUEUE` |
| `5-平台底座/wecom-aibot-service/register-followup-dispatch-task.ps1` | 54 ／ 58 同上 |
| `4-数字员工/质量部/QD-A-8D不良分析/scripts/run_calibration.py` | 27 `ROOT` |
| `4-数字员工/质量部/QD-A-8D不良分析/tests/test_track_a_calibration.py` | 87 |
| `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_golden_product_class.py` | 21 |

🔴 **明确不改（2 处）**：
- `1-转型规划/AI运营指挥中心/sync_sales_data.py:30` —— 指向**另一个** OneDrive 项目 `Projects\SalesMarketing\`，本次不迁它
- `0-学习与工具/工具-仓库外载体扫描.py:35-37` —— `C:\Users\Paul Shao\Claude\*` 与 `.claude\skills`，是**仓库外载体**，不随本次迁移变化

⚠️ **🔴 三个 worktree 内脚本的特殊处置**：`start-aibot-service-dev.ps1` 等三个跑在 `ops/wecom-service-home` worktree 里。**master 上改完不等于生效** —— 须按既有纪律同步该 worktree 后重启（见 `专线opener模板库.md`「触碰企微机器人」条）。**本件只改 master 并把「同步 worktree ＋ 重启」写进 M2 脚本，不在 M1 内重启。**

**改完复核**：`git grep -n "OneDrive.Projects.企业AI转型" -- '*.py' '*.ps1'` 应只剩上述 2 处「明确不改」＋ `.md` 历史记录（`.md` 按「历史记录不追改」不动）。

---

## T2 · 给注册脚本加提权自检守卫（3 个注册脚本）

**理由（2026-08-25 T3 实测）**：S4U 任务的 `Register`／`Unregister`／`Enable`／`Disable` **一律需要 `SeTcbPrivilege`**，非提权全部「拒绝访问」。原担心的「先注销后注册留下任务没了」**已证伪**；真风险是 **非提权跑完四个任务原封不动、仍指旧路径，而脚本看起来「没报错」** ⇒ 迁移后静默停摆。

**守卫要求**：脚本**开头、动任何任务之前**判提权，未提权即 **fail-loud 退出**（明确报错并给出「请在管理员 PowerShell 重跑」）。

```powershell
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "本脚本注册/修改 S4U 计划任务，需管理员 PowerShell。当前非提权，已在改动任何任务之前退出。"
    exit 1
}
```

三个脚本：`工具-注册落库sweep计划任务.ps1`、`register-decision-reminder-task.ps1`、`register-followup-dispatch-task.ps1`。

---

## T3 · 写迁移脚本（M1 的核心产出）

**产出**：`0-学习与工具/工具-迁移到新路径.ps1`，参数 `-NewRoot`（默认 `C:\Dev\zhuopin-ai`）、`-WhatIf`。

🔴 **三条硬要求**：

1. **可从仓库外运行** —— 脚本执行时仓库正在被移动。**脚本自身须先被复制到仓库外**（如 `C:\Dev\`），且内部**不得引用任何仓库内相对路径**。
2. **每一步失败即停并明确报错**，不得继续。
3. **`-WhatIf` 模式把每一步要做什么原样打印出来，不执行** —— 窗口日先跑一次 `-WhatIf` 给 Shao Peishen 过目。

**脚本按方案件 §五 S1→S3 实现，逐步对照**：

| 步 | 要点（细节以方案件为准，此处只列易错点） |
|---|---|
| S1 停服 | 🔴 三层：`Stop-ScheduledTask` **不够** → 先杀守护 `start-aibot-service-dev` → 再杀 `run_aibot_service` python → **`Start-Sleep 90`（≥70 秒，避开守护 60 秒退避）** → 复核两者皆空 |
| S1 禁任务 | 其余三个 `Disable-ScheduledTask`（需提权，守卫已在 T2 加） |
| S1 OneDrive | 退出 OneDrive 客户端进程 |
| S2 前置 | 🔴 云端占位符计数须为 **0**（`Attributes -band 0x400000 -or 0x1000`），非 0 即停 |
| S2 复制 | `robocopy /MOVE /E /COPY:DAT /DCOPY:DAT`（🔴 **不用 `/COPYALL`**，含 SACL 需备份特权，实测 0.1 秒退 16） |
| S2 校验 | 🔴 文件数**不写死期望值**，改为「**源与目的地当场各数一次、相等**」；实测同日 1.5 小时内涨过 4,092 |
| S3 worktree | 🔴 **显式传每个新路径，禁止裸跑**：`$wts = Get-ChildItem "<新>\.claude\worktrees" -Directory \| % FullName; git -C "<新>" worktree repair @wts`。裸跑在复制场景会**改坏源仓库**、在移动场景**静默什么都不做** |
| S3 校验 | 🔴 **不得只看 `git worktree list`**（对 2 个「静默隐身」worktree 视而不见），须逐个 `git rev-parse --git-common-dir` 回读 |
| S3 fsck | `git fsck --full`（**不是 `--connectivity-only`**）——632 MB pack 刚被逐字节搬过 |
| S3 机器人 | 同步 `ops/wecom-service-home` worktree ＋ 重启（T1 那三个脚本住在里面） |
| S3 任务 | 重跑三个注册脚本 ＋ `ZhuopinAibotDevListener` 按 XML 改路径重注册；**四个都回读 `Execute/Arguments/WorkingDirectory` 确认新路径** |

**另出一份 `S0 固证` 小脚本**（或并入同一脚本的 `-Snapshot` 模式）：`git fsck` ＋ `rev-parse HEAD` ＋ 四个任务 XML 导出 ＋ 10 个 `direct_url.json` 留存 ＋ **整树备份到仓库外且非 OneDrive 的位置**。

---

## T4 · 备份替代目录与每周任务（Shao Peishen 2026-08-25 定）

新建 `OneDrive\Backups\企业AI转型-不入库件\`，每周 robocopy 增量同步 `.env`、`7-外部文档\`、`**\reports\`。

**M1 内只产出脚本与注册命令，不注册**（注册需提权，随 M2 一起做）。

---

## 收工要求

- **产出**：改好字的源码（T1）＋ 三个带守卫的注册脚本（T2）＋ `工具-迁移到新路径.ps1` 与固证脚本（T3）＋ 备份同步脚本（T4）
- **验证**：`git grep` 复核零残差；迁移脚本 `-WhatIf` 跑通并把输出贴进收工报告；三个注册脚本在**非提权**下跑一次，确认**在改动任何任务之前**就退出（守卫生效）
- 🔴 **本件不得触发任何实际迁移**；`C:\Dev\zhuopin-ai` 在 M1 结束时**仍不存在**
- 回写队列行＋登记 §二 批次；commit + push

---

## 次序与并行

- **M1 零依赖，可立即开工**，与现有泳道零重叠（触碰区＝上述 8 个源码文件 ＋ `0-学习与工具/` 新增脚本）
- **M2（迁移窗口）硬阻塞于 M1 完成 ＋ Shao Peishen 给出窗口日期**
- **M3（迁移后收口）硬阻塞于 M2**
