---
title: "台面清理执行清单 · worktree 与 stash（2026-07-31）"
created: 2026-07-31
status: 生效
执行方: CC（本清单由 Cowork 环境保障线只读取证后起草，本线不执行破坏性操作）
执行环境: CC
覆盖队列行: "#165（台面卫生清理三合一）／#101②③（stash 认领核对）／#166（目录名与分支名错位）"
---

# 台面清理执行清单 · worktree 与 stash

> **本清单的性质**：Cowork 环境保障线**只读取证**产出的执行说明书，**不含任何已执行的删除动作**。所有破坏性操作交 CC 在本机执行。
> **取证时点**：2026-07-31 12:40–12:55 CST（沙箱 git 元数据直读 + 物理目录列举）。
> 🔴 **执行前必须重跑 §〇 的核验命令**——取证期间实测台面正在被并发改动，静态快照会过期，理由见 §〇。

---

## 〇、执行前必读：台面处于活动状态，快照会过期

取证的十几分钟内实测到三处变化，**说明有其他 session 正在动 worktree 与 master**：

| 观察 | 12:40 左右 | 12:50 左右 |
|---|---|---|
| master HEAD | `2921e03` | `7f75a4e`（+5 提交，含 FI2 v8 面板交付 #182/#183、#184 登记） |
| `.claude/worktrees/fi2-web-service-16da2a` | 已注册 worktree，分支 `claude/fi2-panel-ui-update-cb9b85` | **已注销**，物理目录空壳 |
| `.claude/worktrees/loving-mestorf-98749e` | 分支 `claude/qd-b-release-closure-b1a342` | 分支 `claude/notify-gap-batch-7f93ba` |

**结论与执行纪律**：

1. **执行前重跑核验三连**，以当刻真值为准，本清单的清单项只作"该怎么判、怎么删"的方法与依据：
   ```powershell
   git worktree list
   Get-ChildItem .claude\worktrees -Directory | Select-Object Name
   Get-ChildItem .git\worktrees -Directory | Select-Object Name
   git stash list
   ```
2. **本清单列为"可清"的项，若重跑时发现它已被重新注册或已有内容 → 立即跳过并回写队列行**，不按本清单硬删。
3. **建议在无并发 CC session 的时段执行**（例如确认无其他 CC 会话在跑时）。

---

## 一、取证结论总表（2026-07-31 12:50 快照）

- 物理目录 `.claude/worktrees/`：**18 个**
- `git worktree list` 在册：**7 个 linked**（+ 主工作区）
- `.git/worktrees/` 元数据：**9 条**
- 三者数量不一致的差额，即本次清理对象。

### 1.1 分支安全性（决定"能不能删"的唯一硬判据）

对**全部 17 个本地分支**跑了 `git rev-list --left-right --count origin/master...<branch>`：

> **ahead=0 的分支有 16 个**（即其全部提交都已是 `origin/master` 的祖先，**删 worktree 不会丢任何已提交内容**）。
> **唯一 ahead>0**：`feat/sc8-baoguan-v2-batch1`（ahead=1）——**该分支不在本次清理范围**，且无对应 worktree，原样保留（队列 #115 已核实其内容与已上线批 1 不重叠）。

⚠️ **ahead=0 ≠ 工作区干净**。worktree 里可能有**未提交**改动，沙箱读不到（其 `.git` 文件指向 Windows 路径，Linux 侧无法解析）。**故每删一个有内容的 worktree 前，CC 必须在本机先跑** `git -C "<worktree路径>" status --porcelain`，**有输出即停手、回写队列行交 Shao Peishen 判**。

---

## 二、A 类：空壳物理目录（0 文件、无 `.git`、git 已不认）—— 10 个

判据：`ls` 顶层条目 = 0，目录内无 `.git` 文件，`git worktree list` 不包含它。**已非 worktree，纯残壳。**

| # | 目录名 | 备注 |
|---|--------|------|
| A1 | `cross-desk-queue-139-143851` | |
| A2 | `fi2-web-service-16da2a` | 取证期间刚被注销，**执行前重新确认** |
| A3 | `qd-b-release-closure-b1a342` | `.git/worktrees/` 另有同名陈旧元数据（见 §四） |
| A4 | `queue-git-sync-worktree-fbc10f` | |
| A5 | `queue-numbering-alert-criteria-855665` | 07-30 CC 三件套任务遗留，07-30 体检时尚未出现 |
| A6 | `r7-price-check-baseline-8b819f` | |
| A7 | `supply-board-batch1-fixes-93ba23` | |
| A8 | `supply-board-data-verification-23220c` | |
| A9 | `wecom-listener-macos-migration-ab5815` | Mac 迁移线已整体暂缓（#82/#90） |
| **A10** | **`affectionate-herschel-c26958`** | ✅ **已并入本批（Shao Peishen 2026-07-31 拍板选项 A）**，另须一并删分支，见 §五 |

**执行方式（A1–A10，逐个）**：

```powershell
Remove-Item -Recurse -Force ".claude\worktrees\<目录名>"
```

🔴 **绝对不要用 `git worktree remove`**——队列 #125 已实证该命令**非原子失败**：遇到句柄锁会先把目标目录清空、最后一步才报 `Permission denied`，报错文案让人误以为"什么都没发生"。本类目标本就已空，用 PowerShell 直删无此风险。

**准空壳 1 个**：`fi2-regression-queue-reconcile-07bab3`（顶层仅 `.claude` 一项，内为 `settings.local.json`，无 `.git`）——同 A 类处理，删前可 `Get-ChildItem -Recurse` 扫一眼确认无其他内容。

---

## 三、B 类：仍在册、有内容的 worktree —— 7 个

| # | 物理目录 | 实际 checkout 分支 | ahead | 处置 |
|---|---------|-------------------|:---:|------|
| B1 | `wecom-service-home` | `ops/wecom-service-home` | 0 | 🔴 **绝不可动**——企微机器人常驻运行目录，服务中 |
| B2 | `sweep-criteria-sync-fix-7eb8a7` | `claude/sweep-criteria-sync-fix-7eb8a7` | 0 | 可清（#165(b) 已取证：`工具-落库sweep.py` 与主工作区版逐字节哈希相同） |
| B3 | `fi2-validation-prep-66ed2c` | `claude/fi2-validation-prep-66ed2c` | 0 | 可清（#165(b) 已取证：其内容是被 master 超越的陈旧副本） |
| B4 | `dreamy-ramanujan-35e2e8` | `claude/fi2-web-service-16da2a` | 0 | 可清 · **需先跑 `status --porcelain`** |
| B5 | `loving-mestorf-98749e` | `claude/notify-gap-batch-7f93ba` | 0 | ⚠️ **取证期间分支刚变过，疑为活动中**，执行前二次确认；有内容即跳过 |
| B6 | `musing-pascal-68d14e` | `claude/four-services-temp-auth-3c6bd5` | 0 | 可清 · **需先跑 `status --porcelain`** |
| B7 | `qd-b-grayscale-improvements-9dbe6f` | `claude/qd-b-grayscale-improvements-9dbe6f` | 0 | 可清 · **需先跑 `status --porcelain`** |

**执行方式（B2–B7，逐个，四步不可跳）**：

```powershell
# ① 先查未提交改动——有输出即停手，回写队列行，不删
git -C ".claude\worktrees\<目录名>" status --porcelain

# ② 确认分支 ahead=0（双保险）
git rev-list --left-right --count origin/master...<分支名>

# ③ 干净则物理删除（不用 git worktree remove）
Remove-Item -Recurse -Force ".claude\worktrees\<目录名>"

# ④ 清理 git 元数据
git worktree prune
```

---

## 四、C 类：`.git/worktrees/` 陈旧元数据 —— 2 条

`affectionate-herschel-c26958` 与 `qd-b-release-closure-b1a342` 两条元数据目录的 `gitdir` 文件已空/不可读，`git worktree list` 已不显示它们。

**执行方式**：`git worktree prune`（幂等，A/B 类删完后统一跑一次即可）。

---

## 五、✅ `affectionate-herschel-c26958` —— Shao Peishen 已拍板**选项 A：并入本次清理**

> **2026-07-31 拍板 + 取证补记（本节结论已从"排除"改为"并入"，下方原始背景保留备查）**
>
> **拍板**：Shao Peishen 2026-07-31 选**选项 A**——按 A 类删除目录，**并一并删除分支** `claude/md2word-checkbox-control-089198`，队列 #125 随之销行。
>
> **前提已取证成立**：2026-07-31 14:06 本机只读核查 `Get-Process -Id 49720` → **该进程已不存在**（不再运行）。即事故当时的占用方早已退出，**不存在"删掉正在被使用的东西"的风险**——这正是选项 A 成立的关键条件，已实测、非假设。
>
> **残余风险（已知、Shao Peishen 显式接受）**：若 PID 49720 生前在该 worktree 内确有未提交编辑，删除后永久不可恢复。**最坏损失面仅限那部分未提交在途改动**，不涉任何已完成/已合并成果（分支 ahead=0、无独有提交；#76 的成果由另一分支合入 master）。
>
> **CC 执行时的两条补充**：① 该目录顶层条目为 0（已被 #125 事故清空），直接 `Remove-Item -Recurse -Force` 即可；② **别忘了删分支**——只删目录不删分支，台面数字仍对不齐：
> ```powershell
> Remove-Item -Recurse -Force ".claude\worktrees\affectionate-herschel-c26958"
> git worktree prune
> git branch -D claude/md2word-checkbox-control-089198
> ```

**以下为拍板前的原始背景，保留备查**：该目录是**队列 #125 的 P0 事故对象**——2026-07-27 `git worktree remove` 非原子失败清空了它，事后查出当时有一个**与本项目无关的 `claude.exe` 进程（PID 49720，`--model deepseek-reasoner`）**占用它，无法排除其中有未提交工作丢失。#125 明确记载「已止损，worktree/分支原样保留未删，交 Shao Peishen 核实」。

**已知事实（#125 已核）**：分支 `claude/md2word-checkbox-control-089198` ahead=0、无独有提交；其对应任务（#76 md2word 真复选框）已由另一分支完成并合入 master。**最坏损失面仅为该目录内未提交的在途改动。**

~~**处置建议（需 Shao Peishen 一句话）**~~ → **已于 2026-07-31 拍板选项 A，见本节顶部**：
- ~~**选项 A（推荐）**：确认 PID 49720 已不再运行、且不关心其中可能的在途改动 → 按 A 类删除，同时删本地分支 `claude/md2word-checkbox-control-089198`，#125 一并销行。~~ ← **已选**
- ~~**选项 B**：继续保留现状（成本≈0，但台面数字永远对不齐，每次体检都要重新解释一遍）。~~

---

## 六、D 类：3 条 stash —— 逐条已比对，结论均为"内容已被取代，可 drop"

> #165(c) 原写"本次未展开比对，比对确认已落库前保留不动"——**本次已展开比对，结论如下**。

### stash@{0} · `SAFETY-2026-07-27-主工作区陈旧态修复前快照`（07-28 00:39）

- **是什么**：主工作区"陈旧态"修复前的安全快照，10 个文件、+42/−998 行。
- **关键**：那 −998 行里包含 QD-B 的 `report_items.py`(−230)／`xlsx_report.py`(−261)／三个测试文件的**删除**——即该快照捕获的是**"文件已被误删"的坏状态本身**，不是想保住的成果。
- **核验**：这三个文件在**当前 master 全部存在**（`git cat-file -e master:<path>` 逐一通过）。
- **结论**：**可 drop**。它保护的那个状态正是我们不想要的那个。

### stash@{1} · `wip before pull check`（07-23 20:22，#101②）

- **是什么**：跟进 README 的 +5/−1（落款签名纪律、唐燕萍信一律 Word、两条 README 追行）。
- **核验**：4 处内容中 **3 处已在 master**；唯一"不在 master"的是 `财务部-唐燕萍-跟进-2026-07-23-round1价格异常核实3例` 那条 🆕 待发行——而该信已被 Shao Peishen 07-23 判为**重复起草、不发、已删**，README 里现有的是对应的「已删除记录」行。**它不在 master 是正确的，不是丢失。**
- **结论**：**可 drop**。#101② 的"查明属哪条线"答案＝财务/跟进 README 线，内容已全部被取代。

### stash@{2} · `cowork-uncommitted-macmini-queue-edit-2026-07-23`（07-23 17:43，#101③）

- **是什么**：队列 +3 行（#88 Mac mini 迁移行 + `B-0723监听迁移` 批次）＋ 采购接力 +6/−1（#87 完工、批次拍板、批 1 部署、姚跟进信四段 loop 时间线）。
- **核验**：
  - 队列 `#88` 行 → **已被 #90 承接**，#90 行内白纸黑字记着"开场词原引用 #88，撞保供看板批1同日已用的 #88，按协议〇.6 改为 #90"；
  - `B-0723监听迁移` 批次 → #90 行同样记着"经核实并不存在，本次为首次登记"，已由正式登记取代；
  - 采购接力四段 → 该文件是**滚动覆盖**型（frontmatter 明写"每次收工覆盖"），现已滚到 07-29／07-27 节；四段的**事实内容**在队列 #87／#88 行与 CLAUDE.md 中完整留痕。
- **结论**：**可 drop**（实质被取代，非字面存在于同一文件）。

**执行方式（三条统一，建议先留档再 drop）**：

```powershell
# ① 先各导一份 patch 存到仓库外，成本≈0，万一日后要查
git stash show -p "stash@{0}" > "$env:TEMP\stash0-safety-20260727.patch"
git stash show -p "stash@{1}" > "$env:TEMP\stash1-readme-20260723.patch"
git stash show -p "stash@{2}" > "$env:TEMP\stash2-macmini-20260723.patch"

# ② 从高到低 drop（索引会重排，务必倒序）
git stash drop "stash@{2}"
git stash drop "stash@{1}"
git stash drop "stash@{0}"

# ③ 核验清零
git stash list
```

---

## 七、#166 目录名与分支名错位 —— 取证有新发现，修法建议随之升级

#166 原判为"**5/8 错位**"。本次取证发现问题比"错位"更进一层：

| 物理目录 | 07-30 体检记录的分支 | 07-31 实测分支 |
|---|---|---|
| `fi2-web-service-16da2a` | `claude/supply-board-batch1-fixes-93ba23` | `claude/fi2-panel-ui-update-cb9b85` → 随后注销 |
| `loving-mestorf-98749e` | `claude/qd-b-release-closure-b1a342` | `claude/notify-gap-batch-7f93ba` |

**即：同一个物理目录会被不同任务反复 checkout 到不同分支。** 目录名不只是"一次性取错了"，而是**在时间维度上根本不承载稳定语义**——因此：

- **#166 修法 ①（创建时目录名取分支名尾段）效果有限**：目录被复用后，名字照样会对不上后来的分支。
- **修法 ② `WHOAMI.md` 同样需要升级**：不能只写一次，须在**每次 checkout 到新分支时刷新**，否则一样会过时（等于把陈旧从目录名搬到了文件里）。
- **建议增补修法 ③（最省事、天然不会过时）**：凡需要判定"这个 worktree 是什么活"的场合（体检／清理／对账），**一律以 `git -C <path> branch --show-current` 的当刻实测为准，不看目录名**；把这条写进协议〇.5 与 `zhuopin-queue-audit` 的孤儿扫描步骤，比维护命名约定更可靠。

---

## 八、收尾核验（清理完必须跑，三者数量应一致）

```powershell
git worktree list                                        # 在册数
(Get-ChildItem .claude\worktrees -Directory).Count        # 物理目录数
(Get-ChildItem .git\worktrees -Directory).Count           # 元数据数
git stash list                                            # 应为空
```

**预期终态**（§五 已拍板选项 A，故 A 类共 10 个全清）：
- **物理目录 = `.git/worktrees` 元数据 = `git worktree list` 在册数，三者一致**；
- 保底只剩 **B1 `wecom-service-home`**（绝不可动）；B2–B7 中凡 `status --porcelain` 无输出的均已清掉，**有输出而跳过的须逐个在队列 #165 行内写明目录名与跳过原因**（否则下期体检会当新发现重报一遍）；
- **stash 清零**（`git stash list` 无输出）；
- 本地分支少一条 `claude/md2word-checkbox-control-089198`。

**若因并发/未提交改动实际跳过了某些项**：不算失败，**但必须回写**——把"跳了哪几个、为什么"写进 #165，这条比"清干净"更重要，是下期体检不重复劳动的唯一依据。

---

## 九、回写要求（CC 执行完必做）

1. 队列 **#165** 回写：逐类实际删了几个、跳过了哪些及原因、收尾核验三数是否一致；三条 stash 的 drop 结果。
2. 队列 **#101②③** 销行（stash 认领核对结论已在本件 §六 给出，CC 执行后即可销）。
3. 队列 **#166** 回写：采纳哪种修法（建议 ②+③），并同步协议〇.5。
4. 若触碰 §五，**先等 Shao Peishen 一句话**再动，结论回写 **#125**。
5. 按协议〇.7 改队列前 `acquire`（新行用 `--reserve`）、改完 `release`；改动登 §二 批次。
