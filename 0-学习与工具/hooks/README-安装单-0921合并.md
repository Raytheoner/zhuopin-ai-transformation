---
title: "钩子人工安装单 · 2026-09-21 合并版（两个钩子一次装完）"
created: 2026-09-21
来源: 队列 §一 `#639`（上下文闸读取面缺口 ＋ 重复调用去重守）
状态: ⏳ 等 Shao Peishen（脚本＋实测均已完成，仅缺 settings.json 一步）
预计耗时: 2 分钟（改一个 JSON，两处）
---

# 钩子人工安装单 · 0921 合并版

`.claude/settings.json` 命中 `~/.claude/protected-paths.json` 的 `*/.claude/settings.json`（`mode: block`），
CC 工具层拒写。**本方不从 PowerShell 旁路绕过你自己设的 block**，故这一步只能由你做。
两个钩子并在同一份安装单里，改一次文件、两处追加。

改哪个文件：`C:\Dev\zhuopin-ai\.claude\settings.json`（**项目**那份）。

## 一、`hooks.Stop` 追加 —— 补上下文闸的读取面缺口

**为什么**：`hooks-posttooluse-context-meter.ps1` 只在工具调用后触发；某一轮回复若不含工具调用（纯文本收尾）就直接进 Stop，那一轮的 usage 永远写不进 `reports/context-meter/<sid>.json` 的 `lastContext`。实测闸读 223,309 而度量工具算出 230,874，差 7,565；当日六条逐条比对闸均偏低，其中 `d5346e25` 闸读 248,640、真实 252,496 —— **越过 250k 硬线却没被截断**。单测 `test_hooks-stop-context-meter.py` 28/28 绿，最小场景残差 15,000 → 0。

现有 `Stop` 只有一个元素 `hooks-stop-decision-check.ps1`。在它的 `hooks` 子数组里追加（前面补逗号）：

```json
{
  "type": "command",
  "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-context-meter.ps1\"",
  "timeout": 10
}
```

## 二、`hooks.PreToolUse` 追加 —— 重复调用去重守

**为什么**：2026-09-20／09-21 两天 25 条会话（按 `requestId` 去重后）实测——`cache_read/工具调用` 从 19 次调用时的 60,972 涨到 130 次时的 161,652（贵 2.5 倍）；**完全相同的 (工具,目标) 重复调用占 18–47%**；Read 里 40–80% 是重读同一文件；最贵两条泳道各用 31／26 次 Edit 只改了 5 个文件。按曲线算去掉重复可让 `d5346e25` 从 21.0M 降到约 12.5M（−41%）、`d8a76b23` 从 17.4M 降到约 5.8M（−67%），**且不切分会话、不改业务代码**。

现有 `PreToolUse` 有两个 matcher。**新增第三个 matcher 条目**（不要塞进现有的 `Read|Grep|Bash` 那个，免得与队列读取守的判据纠缠）：

```json
{
  "matcher": "Read|Grep|Edit|Bash",
  "hooks": [
    {
      "type": "command",
      "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-dedup-guard.ps1\"",
      "timeout": 10
    }
  ]
}
```

## 三、装之前先知道它会拦什么（已逐条实测，不是自陈）

| 场景 | 行为 | 实测 |
|---|---|---|
| 第 1 次 Read 某文件 | 放行 | `exit=0` ✓ |
| 第 2 次 Read 同一文件、**文件未变**（mtime＋size 相同） | **拒绝**，提示回看／改定位读 | `exit=2` ✓ |
| 第 2 次 Read，但文件**已变**（自己刚 Edit 过） | 放行，不误拦 | `exit=0` ✓ |
| 同一文件第 3 次 Edit | **拒绝**，要求剩下改动一次性走 MultiEdit | `exit=2` ✓ |
| Grep 同 pattern 同 path 重复、目标未变 | 拒绝 | 同 Read 判据 |
| Bash 完全相同命令重复 | **只计数、不拦**（命令幂等性无可靠判据，误拒代价高） | 记 audit |
| 钩子自身异常 | fail-open，`exit 0`，不拦主流程 | 与既有 PreToolUse 钩子同口径 |

🔴 **逃生阀**：环境变量 `ZHUOPIN_DEDUP_GUARD=off` ⇒ 全放行但照旧计数（实测 `exit=0` ✓）。
**A/B 验收就靠它**：Run A 设 `ZHUOPIN_DEDUP_GUARD=off` 取现状基线，Run B 不设——同一份钩子、同一件活、**唯一变量是这个环境变量**，没有「装/不装钩子」带来的混淆项。所以这两个钩子你装一次就够，A/B 不需要你再动手。

状态文件落 `reports/dedup-guard/<session_id>.json`，一个会话一份，不跨会话累积。

## 四、装完怎么确认

```
pwsh -NoProfile -Command "(Get-Content 'C:\Dev\zhuopin-ai\.claude\settings.json' -Raw | ConvertFrom-Json).hooks.PreToolUse.Count; (Get-Content 'C:\Dev\zhuopin-ai\.claude\settings.json' -Raw | ConvertFrom-Json).hooks.Stop[0].hooks.Count"
```

预期输出 `3` 与 `2`。装完跟我说一句「钩子装好了」即可——**这条没有机器触发器，只能靠你这句话**，我的记性不构成触发器。
