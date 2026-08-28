---
title: "写入时刻哨兵 · 人工安装单（一次做完三步）"
created: 2026-08-29
来源: 队列 §一 #433 建造棒 OP-0829-A（worktree `hooks-sentinels-apply`）；openspec 变更包 `project-hooks-write-time-sentinels`
状态: ⏳ 待 Shao Peishen 人工执行（AI 工具被 PreToolUse 守卫按设计拦住，非技术障碍）
预计耗时: 5 分钟（三步都是改一个 JSON ＋ 跑一条核验命令）
---

# 写入时刻哨兵 · 人工安装单

> **一次做完三步**：① 注册两个哨兵钩子；② 修 `.claude.json` 的双信任记录；③ 顺手把 `#398` 那个挂了 4 天的 SessionStart 心跳钩子一并装上。
> 三步互相独立，**但第 ② 步不做，第 ① 步可能白装**——见下方「为什么第 ② 步不是可选项」。

---

## 为什么这一步只能你手动做（不是偷懒，是守卫按设计拦住了）

`~/.claude/protected-paths.json` 把这几条路径列为受控范围、`mode: block`：

```
"*/.claude/hooks/*"
"*/.claude/settings.json"
"*/.claude/protected-paths.json"
"*claude_desktop_config.json"
```

**通配前缀 `*/` 让「项目的」那份配置也一并命中** ⇒ CC 写不了，必须由你执行一次。

**这是守卫在正常工作，不绕。** 绕过的办法都存在，但绕过一次，这条守卫此后就不再是守卫了。

**一次性成本，之后免疫**：哨兵脚本本体落在 `0-学习与工具/hooks/`（**不**在上述 patterns 内）⇒ **注册之后改脚本、调判据、加哨兵都不再需要你动手**，只有第一次注册需要。

---

## 已经做完、不需要你动手的部分

| 项 | 状态 |
|---|---|
| 公共框架 `hooks-common.ps1`（输入解析／fail-open／心跳／审计留痕／逃生阀） | ✅ 已完成 |
| H3 乱码哨兵 `sentinel-mojibake.ps1` | ✅ 已完成 |
| H4 代词哨兵 `sentinel-pronoun.ps1`（名录零硬编码） | ✅ 已完成 |
| 端到端单测 36 条（真跑脚本、真喂 hook JSON、真断言退出码） | ✅ 36 passed |
| 落库 sweep 第 9 类常驻告警「哨兵零心跳」（可被恢复自动解除） | ✅ 已完成 |
| 上线形态开关 `sentinels-mode.json`（当前 `warn`，观察期两周） | ✅ 已完成 |
| **把钩子注册进项目配置 ＋ 修双信任记录 ＋ 装 #398 心跳钩子** | ⏳ **等你（本单三步）** |

---

## 第 ① 步：注册两个哨兵钩子

**改哪个文件**：`C:\Dev\zhuopin-ai\.claude\settings.json`（**项目**那份，不是 `~\.claude\` 那份）。

现有内容的顶层是 `extraKnownMarketplaces` / `enabledPlugins` / `permissions` 三个键。**在 `permissions` 后面加一个平级的 `hooks` 键**，整段照抄：

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\sentinel-mojibake.ps1\"",
          "timeout": 10
        },
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\sentinel-pronoun.ps1\"",
          "timeout": 10
        }
      ]
    }
  ]
}
```

改完整份文件应该长这样（**注意 `permissions` 那一行末尾要补一个逗号**）：

```json
{
  "extraKnownMarketplaces": { "…原样不动…" },
  "enabledPlugins": { "…原样不动…" },
  "permissions": { "…原样不动…" },
  "hooks": { "…上面那段…" }
}
```

> 🔴 **为什么写主仓绝对路径、而不是 `$CLAUDE_PROJECT_DIR`**：一是本机 hook 命令走 PowerShell，`$CLAUDE_PROJECT_DIR` 那种写法在这里不展开（现有几个钩子也全用绝对路径）；二是写主仓绝对路径后，**所有 worktree 跑的都是同一份脚本**，不会出现「某个 worktree 里的哨兵是三周前的旧版」这种静默漂移。脚本自己会用 `git rev-parse --git-common-dir` 把心跳与名录都锚回主仓。
> 🔴 **路径必须带双引号**——本机用户目录与项目路径含空格与中文，这是全局 CLAUDE.md 已入法的一条。

### 核验（跑完应看到两条命中）

```powershell
python -c "import json,pathlib;d=json.loads(pathlib.Path(r'C:\Dev\zhuopin-ai\.claude\settings.json').read_text(encoding='utf-8'));h=json.dumps(d.get('hooks',{}),ensure_ascii=False);print('mojibake:', 'sentinel-mojibake' in h);print('pronoun :', 'sentinel-pronoun' in h)"
```

**预期输出**：

```
mojibake: True
pronoun : True
```

---

## 第 ② 步：修 `.claude.json` 的双信任记录（🔴 不是可选项）

### 为什么第 ② 步不做，第 ① 步可能白装

`C:\Users\Paul Shao\.claude.json` 的信任表里，**同一个目录有两条斜杠方向不同、结论相反的记录**（2026-08-29 06:5x 实测，仍在）：

| 键 | `hasTrustDialogAccepted` |
|---|---|
| `C:\Dev\zhuopin-ai` | **True** |
| `C:/Dev/zhuopin-ai` | **False** ← 就是它 |

命中 `False` 那条时，命令行会原样吐出 `Ignoring 7 permissions.allow entries from .claude/settings.json: this workspace has not been trusted.` —— **项目配置被静默忽略**。

⚠️ 目前只实测到 `permissions` 被忽略，**hooks 是否同样受这道信任门控制未测**。但**不能推断的事恰恰是必须设防的事**：本项目已经吃过一次一模一样的亏（OP-0819-F，一个告警机制建成 9 天、每天在跑，却从来没有真正发出过一条消息）。

### 一条命令修掉（删掉那条正斜杠的假记录，反斜杠那条 True 保留）

```powershell
$p="$env:USERPROFILE\.claude.json"; Copy-Item $p "$p.bak-20260829"; $j=Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json; $j.projects.PSObject.Properties.Remove('C:/Dev/zhuopin-ai'); $j | ConvertTo-Json -Depth 100 | Set-Content $p -Encoding UTF8; "已备份到 $p.bak-20260829"
```

### 核验（应只剩反斜杠那一条，且为 True）

```powershell
python -c "import json,pathlib;d=json.loads((pathlib.Path.home()/'.claude.json').read_text(encoding='utf-8'));[print(repr(k),'->',v.get('hasTrustDialogAccepted')) for k,v in sorted(d.get('projects',{}).items()) if k.rstrip('/\\').lower().endswith('zhuopin-ai')]"
```

**预期输出**（只有一行）：

```
'C:\\Dev\\zhuopin-ai' -> True
```

---

## 第 ③ 步：装上 `#398` 那个 SessionStart 心跳钩子（合并进本单，省你一次动作）

2026-08-29 06:5x 实测：`~\.claude\settings.json` 的 `hooks` 只有 `PostToolUse` / `PreToolUse` / `Notification` / `Stop` / `SubagentStop` 五个键，**没有 `SessionStart`** ⇒ `#398` 那份安装单至今未执行（已挂 4 天）。

按 `0-学习与工具/定时任务源码/health-check-signal/README-安装步骤.md` 执行它的第 1、2 步：

```powershell
Copy-Item "C:\Dev\zhuopin-ai\0-学习与工具\定时任务源码\health-check-signal\health-check-staleness.ps1" "$env:USERPROFILE\.claude\hooks\health-check-staleness.ps1"
```

然后在 `~\.claude\settings.json` 的 `hooks` 对象里加一个与 `PreToolUse` 平级的 `SessionStart` 键：

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

### 核验

```powershell
python -c "import json,pathlib;d=json.loads((pathlib.Path.home()/'.claude'/'settings.json').read_text(encoding='utf-8'));print('SessionStart 已注册:', 'SessionStart' in d.get('hooks',{}))"
```

**预期输出**：`SessionStart 已注册: True`

---

## 装完之后：三条验收（我来做，你只需回一句「装好了」）

| # | 验收 | 判据 |
|---|---|---|
| 1 | **哨兵真的在岗** | 随便让 CC 写一次 `.md`，`reports/hooks-heartbeat.json` 的 `lastRun` 应更新到当刻 |
| 2 | **H3 在生产真实拦下一次** | 构造一个含 U+FFFD 的写入，当日 `audit-blocks` 日志新增一行、事件列为 `warn` |
| 3 | **补答 P0-1 未答的那半问** | 请你在 **Cowork** 里做一次受控 Edit（改任一 `.md` 一个字），然后我查心跳有没有该次记录——这能确定**项目级** hooks 对 Cowork 到底生不生效（10 分钟，P0 探针只证否了「全局」那一半） |

---

## 上线形态：warn 两周，不打断你

当前 `0-学习与工具/hooks/sentinels-mode.json` 是 `"mode": "warn"`：**命中只留痕计数、不打断写入**（退出码 0）。

- 两周观察期＝**2026-08-29 → 2026-09-12**（你 2026-08-29 答第 3 问选 (a)）。
- 转 `block` 的判据＝warn 期误报 **≤1 次/周**；误报计数看 `~\.claude\audit-blocks-<日期>.log` 里事件列为 `warn` 的行。
- 转 block 的操作＝把那个 JSON 里的 `warn` 改成 `block`。**不需要动脚本、不需要再改任何配置件、不需要重启会话**——这一步 CC 自己就能做，不用再找你。

---

## 三条已知边界（如实写，不藏）

1. **对 Cowork 是否生效仍未知**。P0 探针只证否了「全局 `~\.claude\` 的 hooks 对 Cowork 无效」（它的 `HOME` 是 MSIX 容器内每会话一份的沙箱）；**项目级**这一半必须装完才能测，就是上面验收第 3 条。收益面按「仅 CC」计，若届时证实 Cowork 也吃，是净赚。
2. **新建的 worktree 首次进入时若没接受信任对话框，那个 worktree 里的哨兵可能不生效**——信任记录是**按目录**存的（实测 `.claude.json` 里每个 worktree 各占一条）。零心跳告警只在**连续 3 天全无心跳**时才响，抓不住「只有某一个 worktree 哑了」这种局部失效。
3. **sweep 自己停摆时，零心跳告警一起哑**——这与 `#398` ⑴ 判过的「再建一个后台守卫只是把失效模式往外挪一层」是同一个洞；治它的正是本单第 ③ 步那条会话横幅钩子。**所以第 ③ 步不是搭便车，它补的是第 9 类告警自己的盲区。**
