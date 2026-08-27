---
title: "Claude-Env-HealthCheck 心跳信号 · 人工安装步骤"
created: 2026-08-25
来源: 队列 #398 ⑴（CC，worktree `queue-398-mech-signal`）
状态: ⏳ 待 Shao Peishen 人工执行（AI 工具被 PreToolUse 守卫拦截，非技术障碍）
---

# Claude-Env-HealthCheck 心跳信号 · 人工安装步骤

## 为什么这一步只能你手动做（不是偷懒，是守卫按设计拦住了）

`~/.claude/protected-paths.json` 把这两条路径列为 ISO 26262 受控范围、`mode: block`：

```
"*/.claude/hooks/*"
"*/.claude/settings.json"
```

CC 尝试写入 `~/.claude/hooks/health-check-staleness.ps1` 时被 `pretooluse-guard.ps1`
按规则拦下（拦截记录已进 `~/.claude/audit-blocks-20260825.log`）。**这是守卫在正常
工作，不应绕过**——绕过的办法都存在，但绕过一次，这条守卫此后就不再是守卫了。
故按其提示"走人工变更流程并留痕"，把两处变更留在此处等你执行。

## 已经做完、不需要你动手的部分

| 项 | 状态 |
|---|---|
| 停摆根因定位（电池闸，已实测复现＋复测修复） | ✅ 已完成 |
| 计划任务设置修正（电池闸关、补跑开、超时 2h） | ✅ 已完成 |
| `~/.claude/health-check.ps1` 写心跳 `health-check-status.json` | ✅ 已完成 |
| `health-check.ps1` 新增 `[4] 自身信号完好性` 自检 | ✅ 已完成 |
| 钩子脚本本体（含六场景反例测试全过） | ✅ 已写好，见同目录 `health-check-staleness.ps1` |
| **把钩子装进 `~/.claude/hooks/` 并在 `settings.json` 注册** | ⏳ **等你** |

> 在你完成安装前，每月体检会稳定报出两条发现——
> 「[4] 心跳告警钩子脚本不存在」「[4] settings.json 未注册 SessionStart 心跳钩子」。
> 这是**故意**的：留步项自己会喊，不靠人记得。

## 第 1 步：复制钩子脚本

```powershell
Copy-Item `
  "C:\Dev\zhuopin-ai\0-学习与工具\定时任务源码\health-check-signal\health-check-staleness.ps1" `
  "C:\Users\Paul Shao\.claude\hooks\health-check-staleness.ps1"
```

## 第 2 步：在 `~/.claude/settings.json` 的 `hooks` 对象里加一个 `SessionStart` 键

与既有的 `PreToolUse` / `PostToolUse` / `Stop` 平级，整段照抄：

```json
"SessionStart": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "pwsh -NoProfile -File \"C:\\Users\\Paul Shao\\.claude\\hooks\\health-check-staleness.ps1\"",
        "timeout": 10
      }
    ]
  }
]
```

> 🔴 路径**必须带双引号**——本机用户目录含空格，这是全局 CLAUDE.md 已入法的一条
> （`patch-plugin-quotes.ps1` 那条教训的同一个坑）。

## 第 3 步：验收（两条，缺一不可）

```powershell
# ① 手动跑一次体检，确认 [4] 两条发现消失、findingCount 下降
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Paul Shao\.claude\health-check.ps1"
(Get-Content "$env:USERPROFILE\.claude\health-check-status.json" -Raw -Encoding UTF8 | ConvertFrom-Json).findings

# ② 开一个新的 Claude Code 会话，确认会话开头出现 [环境体检] 横幅
#    （当前有 5 项 CLAUDE.md 叠加超阈的发现，所以横幅**应该**出现；
#     若把那 5 项处理干净了，横幅会转为完全静默——那才是终态）
```

## 告警判据（装好之后它按这四条说话）

| 条件 | 含义 |
|---|---|
| 心跳文件不存在 | 从未跑过，或被删 |
| `lastRun` 距今 > **40 天** | 月度任务给足一次补跑窗口仍未跑 |
| `ok = false` | 跑起来了但中途崩了 |
| `findingCount > 0` | 跑通了，但**结论没人看**（§一 #82 教训的直接对策） |

四条都不成立时**完全静默**，不产生噪音（已由阳性对照测试固定：输出长度必须为 0）。

⚠️ **40 天这个阈值是按月度周期机械推出的，不是业务口径**；若你要改成别的数，
改 `health-check-staleness.ps1` 顶部的 `$STALE_DAYS` 即可。

## 反例测试留痕（六场景，2026-08-25 实跑全过）

| 场景 | 期望 | 实测 |
|---|---|---|
| A 真实心跳 7 项发现 | 告警，只列前 3 条 + 折计数 | ✅ |
| B 心跳文件缺失 | 告警 | ✅ |
| C 心跳陈旧 55 天、零发现 | 告警「已 55 天未运行」 | ✅ |
| D 上次异常终止 | 告警「异常终止」 | ✅ |
| E 刚跑过 ＋ 零发现 | **完全静默**（输出长度 0） | ✅ |
| F 心跳文件是坏 JSON | **钩子自己出声**，不得静默 | ✅ |

场景 F 是这套设计的关键：守卫自己坏了必须出声，否则就重犯 #398 要修的那个错。
