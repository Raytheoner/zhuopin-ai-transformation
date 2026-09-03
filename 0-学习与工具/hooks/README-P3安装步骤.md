---
title: "P3 hooks（ⓐⓒⓑⓓ）· 人工安装单"
created: 2026-09-04
来源: 队列 §一 `#381` 子项⑸（规格正本）；建造 session `P3hooks-OP0904A`；openspec 变更包 `cc-hooks-p3`
状态: ⏳ 待 Shao Peishen／Cowork 瘦身线人工执行（AI 工具被 PreToolUse 守卫按设计拦住，非技术障碍）
预计耗时: 3 分钟（改一个 JSON ＋ 跑四条核验命令）
---

# P3 hooks（ⓐⓒⓑⓓ）· 人工安装单

> **四枚 Claude Code hook 需要登记进项目 `.claude/settings.json`**：ⓐ `SessionStart`／ⓒ `PreToolUse`／ⓑ `UserPromptSubmit`／ⓓ `Stop`。
> **ⓔ（acquire 路由提示）／ⓕ（sweep rules 尺寸巡检）／ⓖ（opener 块 lint 扩三形态）三项已经在生产生效，不需要本单任何动作**——它们是对既有 Python 工具（`工具-共享文档编辑锁.py`／`工具-落库sweep.py`／`工具-opener块lint.py`）的直接代码修改，不经 Claude Code 的 hooks 事件系统。

---

## 为什么这一步只能你手动做

`~/.claude/protected-paths.json` 把 `*/.claude/settings.json`（`mode: block`）列为受控范围，通配前缀 `*/` 让"项目的"那份配置也一并命中 ⇒ CC 写不了，必须由你执行一次。**这是守卫在正常工作，不绕。**

**一次性成本，之后免疫**：四枚脚本本体落在 `0-学习与工具/hooks/`（不在受控 patterns 内）⇒ 注册之后改脚本、调判据都不再需要你动手，只有这次注册需要。

---

## 已经做完、不需要你动手的部分

| 项 | 状态 |
|---|---|
| ⓐ `hooks-sessionstart-context.ps1` ＋ 37 条单测（含本项 7 条） | ✅ 已完成，含对真实仓库的读时验活 |
| ⓒ `hooks-pretooluse-editlock-guard.ps1` ＋ 单测（含本项 11 条） | ✅ 已完成 |
| ⓑ `hooks-userpromptsubmit-standing-five.ps1` ＋ 根 `CLAUDE.md` 五处锚点 ＋ 单测（含本项 8 条） | ✅ 已完成，含对真实根 `CLAUDE.md` 的验活 |
| ⓓ `hooks-stop-decision-check.ps1` ＋ 单测（含本项 11 条） | ✅ 已完成 |
| ⓔ `工具-共享文档编辑锁.py` 路由提示 ＋ 9 条单测 | ✅ 已完成并生产生效（不需注册） |
| ⓕ `工具-落库sweep.py` rules 尺寸巡检 ＋ 16 条单测 | ✅ 已完成并生产生效（不需注册） |
| ⓖ `工具-opener块lint.py` 扩三形态 ＋ 单测 | ✅ 已完成并生产生效（不需注册） |
| **把四枚钩子注册进项目 `.claude/settings.json`** | ⏳ **等你（本单）** |

---

## 唯一要做的事：把 `hooks` 键改成下面这样

**改哪个文件**：`C:\Dev\zhuopin-ai\.claude\settings.json`（**项目**那份，不是 `~\.claude\` 那份）。

现有 `hooks` 键只有 `PostToolUse`（两枚哨兵）。**整段替换为下面这段**（`PostToolUse` 原样保留，新增 `SessionStart`／`PreToolUse`／`UserPromptSubmit`／`Stop` 四个平级键）：

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
  ],
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-sessionstart-context.ps1\"",
          "timeout": 10
        }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "Edit|Write|MultiEdit",
      "hooks": [
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-editlock-guard.ps1\"",
          "timeout": 10
        }
      ]
    }
  ],
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-userpromptsubmit-standing-five.ps1\"",
          "timeout": 10
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-decision-check.ps1\"",
          "timeout": 10
        }
      ]
    }
  ]
}
```

🔴 **路径必须带双引号、写主仓绝对路径**——理由与既有两枚哨兵完全同形（本机用户目录含空格；写绝对路径使所有 worktree 跑的都是同一份脚本，不会有"某个 worktree 里的钩子是旧版"这种静默漂移）。

**允许分批注册**：四个键相互独立，你可以先只加一个（比如 ⓐ `SessionStart` 风险最低、纯只读），核验通过再加下一个，不要求一次性四个一起上。

### 核验（跑完应看到四条命中）

```powershell
python -c "import json,pathlib;d=json.loads(pathlib.Path(r'C:\Dev\zhuopin-ai\.claude\settings.json').read_text(encoding='utf-8'));h=d.get('hooks',{});print('SessionStart      :', 'SessionStart' in h);print('PreToolUse        :', 'PreToolUse' in h);print('UserPromptSubmit  :', 'UserPromptSubmit' in h);print('Stop              :', 'Stop' in h)"
```

**预期输出**：四行全 `True`。

---

## 装完之后：四条验收（我来做，你只需回一句"装好了"）

| # | 钩子 | 验收动作 | 判据 |
|---|---|---|---|
| 1 | ⓐ SessionStart | 在项目下新开一个 CC 会话 | 开场横幅出现"🕐 …本地 / …UTC"字样，且主仓 `reports/hooks-audit.jsonl` 新增一行 `hook=sessionstart-context` |
| 2 | ⓒ PreToolUse | 不 `acquire` 直接尝试 `Edit` 两份队列文件之一 | 被拒绝（`exit 2`），审计新增一行 `hook=pretooluse-editlock-guard, verdict=violation` |
| 3 | ⓑ UserPromptSubmit | 随便发一条消息 | 上下文出现"📌 常驻五条：…"字样，审计新增一行 `hook=userpromptsubmit-standing-five` |
| 4 | ⓓ Stop | 让 CC 回复一段刻意缺 `(a)/(b)` 标签的"需你定夺"小节 | 该轮被拦下要求补全，审计新增一行 `hook=stop-decision-check, verdict=violation` |

**每一条通过后**，对应根 `CLAUDE.md`／`.claude/rules/队列与落库.md` 里的等量人守文本才能按 `#381` 硬约束「先验活、后降指针」进入下一步（openspec 变更包 `cc-hooks-p3` tasks.md §8，本次未做，前置条件即此四条验收）。

---

## 已知边界（如实写，不藏）

1. **仅 CC 生效**：P0 实测坐实（`根CLAUDE.md彻底瘦身-方案-2026-09-03.md` §五），Cowork 桌四枚钩子全不生效。ⓑ 因此对应的常驻五条同时**留在根文件正文**（不因 CC 侧验活而降指针），ⓓ 对应的"会话末需你定夺"格式判据同理——Cowork 侧仍靠人记得。
2. **ⓒ 只判"锁是否存在有效记录"，不判"是不是你持的"**：完全忘记 `acquire` 会被拦，但"A 持锁、B 也绕过直接改"这种更刁钻的场景不在本枚钩子管辖范围（既有幽灵副本检测另行兜底）。
3. **ⓓ 的半覆盖风险**（`#381`⑷评估⒞原话）：只覆盖 CC 桌的"需你定夺"格式检查，不构成两桌全局门禁——已在 `#155`（2026-09-04）知情重新拍板下仍建，design.md 决策点 2 有完整记录。
