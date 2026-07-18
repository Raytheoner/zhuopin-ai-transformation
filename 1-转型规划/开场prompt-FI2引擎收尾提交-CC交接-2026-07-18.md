---
title: "开场 Prompt · FI2 三单匹配引擎 v3（feat/fi2-v3-recon-engine）—— 收尾提交交接"
created: 2026-07-18
执行方: Claude Code（主工作区，非 worktree）
来源: 跨会话对账审计（2026-07-18，队列 #48），发现主工作区长期处于 detached HEAD 未收尾
status: 待执行
---

# 开场 Prompt —— FI2 v3 引擎分支收尾提交（CC）

> 用法：新开 CC session，让它读本文件交接。**这是"收尾"任务，不是继续开发新功能**——FI2 引擎代码本身没有任何未提交内容，需要做的只是：把该走的文件提交推送、把不该留的杂物清掉、决定分支下一步去向。

**开场词（复制即用）**：

```
读 1-转型规划/开场prompt-FI2引擎收尾提交-CC交接-2026-07-18.md + CLAUDE.md 当前进度恢复上下文，按文件执行；开干前问我 2-3 个澄清。
```

**【设置】分支：`feat/fi2-v3-recon-engine` ｜ worktree：☐**（续在办活，不勾——直接在主工作区继续，不新建 worktree）

## 背景一分钟

2026-07-18 跨会话对账审计（队列 #48）发现：主工作区（企业AI转型根目录，Paul 平时直接打开的那份，不是 `.claude/worktrees/` 下的临时目录）长期停在 **detached HEAD**，卡在 `feat/fi2-v3-recon-engine` 分支尖端（commit `4f8459d`），没人把它收尾提交、也没切回具名分支。审计当时**全程未触碰**这个分支和这个目录（只读核实），现在把收尾这件事正式交接出来。

**好消息**：`git status` 确认 **FI2 引擎代码本身没有任何未提交改动**（`.py`/测试/openspec 全部干净）——working tree 里唯一的"脏"是 9 个跟 FI2 无关、混进这个工作区的文档类文件（大概率是有人在这个目录里顺手编辑队列/质量域文档时留下的）。所以这不是一个"还有代码没写完"的收尾，纯粹是 git 层面的整理。

## 当前状态（2026-07-18 核实，开工请重新跑一遍确认没变）

- 本地 `feat/fi2-v3-recon-engine` **ahead 5 / behind 44** 于 `origin/master`（分叉挺久了，越拖 rebase 越难，建议这次一并处理）
- 本地分支比它自己的远程 `origin/feat/fi2-v3-recon-engine` **领先 1 个提交**（`4f8459d`，内容是"队列0716-0717 worktree纪律+git收口/服务恢复登记"——这个提交本身也跟 FI2 无关，是当时顺手在这个分支上提交的文档改动）
- working tree 9 个脏文件，逐一比对 `origin/master` 后结论如下（审计已核实，可直接照办，不用重新比对）：

| 文件 | 状态 | 处置建议 |
|---|---|---|
| `1-转型规划/0-全景路线图/跨桌任务队列.md` | 陈旧（比 master 少两条协议+多条已过期内容，且 master 后续已加到 #50） | `git checkout origin/master -- <path>` 丢弃 |
| `1-转型规划/CC质量专线-prompt-2026-07-04.md` | 与 origin/master 字节级一致 | 丢弃（无差异，checkout 也行） |
| `1-转型规划/session接力-质量域场景落地.md` | 与 origin/master 字节级一致 | 丢弃 |
| `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` | 陈旧（缺 master 后续一处措辞更新） | 丢弃 |
| `6-人才与组织/部门AI专员跟进/质量部-陈忱-跟进-2026-07-16-*.md/.docx`（未跟踪） | 与 origin/master 上已有的同名文件字节级一致 | 直接删除本地这两份（`rm`），master 已有 |
| `1-转型规划/QD-B极简版先上线-最小任务集-2026-07-09.md`（未跟踪） | 与 origin/master 字节级一致 | 删除 |
| `1-转型规划/QD-B立项门禁-上线收口清单-2026-07-09.md`（未跟踪） | 与 origin/master 字节级一致 | 删除 |
| `1-转型规划/0-全景路线图/本周计划-2026-07-17.md`（未跟踪，142 行） | ⚠️ **master 上不存在，审计未深读内容，是否还有价值未判断** | **开工先看一眼内容再决定**：若已被 `本周计划-2026-07-18.md`（如果存在）取代则删；若仍有独有信息，按惯例 commit 进 `0-全景路线图/session接力-Phase1收口.md` 同批或单独一个小 commit 收进 master，别静默丢 |

## 任务分段

**A · 清理杂物**：按上表处置 8 个确认陈旧/重复的文件；`本周计划-2026-07-17.md` 先读内容再决定去留。

**B · 推送已提交的那 1 个 commit**：`4f8459d` 内容与 FI2 无关，正常 `git push origin feat/fi2-v3-recon-engine`（fast-forward，无需特殊处理）。

**C · 判断分支下一步去向（这是本次真正需要拿主意的部分）**：分支落后 master 44 个提交，继续拖会越来越难合并。跟 Paul / 财务专线确认：
  - FI2 v3 引擎这批改动是否已经到了可以 rebase 到最新 master 上、走 PR/合并流程的节点？还是仍在活跃开发中，先只做 A/B 两步、暂不 rebase？
  - 若决定 rebase：`git rebase origin/master`，冲突大概率出现在跟这 44 个提交里其他人动过的公共文件（如平台底座 `shared_tools/`）上，逐一按内容新旧判断，不盲目全取一边；rebase 完整体测试跑绿再推。
  - 若暂不 rebase：至少把 A/B 做完、主工作区退出 detached HEAD（`git checkout feat/fi2-v3-recon-engine`，此时会指向同一个 commit，不产生任何改动，只是把"游离头指针"变回"具名分支"，避免下次又有人手滑把它清掉）。

## 收工要求

- 完成 A/B 后，**必须**把主工作区从 detached HEAD 切回具名分支（`git checkout feat/fi2-v3-recon-engine`），不要让它继续游离状态。
- 若做了 C 的 rebase，收工前跑一遍相关测试套件（FI2 场景 + 平台底座公共测试）确认零回归，再 push（rebase 后需要 `git push --force-with-lease origin feat/fi2-v3-recon-engine`，因为 commit 历史改写了）。
- 收工把结果回写 `1-转型规划/0-全景路线图/跨桌任务队列.md` 的 #48 行（在原内容后追加，不要覆盖已有内容），并跑一遍收工台账脚本。
