---
title: "ⓗ2 队列读侧门禁 hook · 人工安装单"
created: 2026-09-04
来源: 队列 §一 `#381` 子项⑸ⓗ2（规格正本）；建造 session opener `OP-0904-C`；openspec 变更包 `queue-read-write-guards`
状态: ⏳ 待 Shao Peishen／Cowork 瘦身线人工注册
预计耗时: 2 分钟（改一段 JSON ＋ 跑一条核验命令）
---

# ⓗ2 队列读侧门禁 hook · 人工安装单

> **一枚新 Claude Code hook 需要登记进项目 `.claude/settings.json`**：`PreToolUse(Read|Grep|Bash)`，脚本已就位、单测已过（26 条），只差这一步注册。

---

## 为什么这一步只能你手动做

`~/.claude/protected-paths.json` 把 `*/.claude/settings.json`（`mode: block`）列为受控范围 ⇒ CC 写不了，必须由你执行一次。**这是守卫在正常工作，不绕**——与 `cc-hooks-p3` 那四枚钩子（ⓐⓒⓑⓓ）注册时完全同形。

**一次性成本，之后免疫**：脚本本体落在 `0-学习与工具/hooks/hooks-pretooluse-queue-read-guard.ps1`（不在受控 patterns 内）⇒ 注册之后改脚本、调判据都不再需要你动手，只有这次注册需要。

---

## 已经做完、不需要你动手的部分

| 项 | 状态 |
|---|---|
| `hooks-pretooluse-queue-read-guard.ps1` ＋ 26 条单测 | ✅ 已完成（`test_hooks-pretooluse-queue-read-guard.py`，隔离沙箱跑，不碰生产队列文件） |
| `工具-队列查询.py --grep`（ⓗ1，本行同批交付） | ✅ 已完成并生产生效（不需注册，纯 CLI 新增参数） |
| `工具-共享文档编辑锁.py` release 校验 ⑪ 行长上限（ⓗ3，本行同批交付） | ✅ 已完成并生产生效（不需注册，全量回归 322 passed） |
| openspec 变更包 `queue-read-write-guards`（propose+design+apply） | ✅ `openspec validate --strict` 全库 157 passed |
| **把这枚钩子注册进项目 `.claude/settings.json`** | ⏳ **等你（本单）** |

---

## 唯一要做的事：给 `PreToolUse` 数组追加第二个条目

**改哪个文件**：`C:\Dev\zhuopin-ai\.claude\settings.json`（**项目**那份，不是 `~\.claude\` 那份）。

现有 `hooks.PreToolUse` 只有一个条目（ⓒ 编辑锁门禁，matcher `Edit|Write|MultiEdit`）。**在同一个数组里追加下面这个条目**（不要替换掉现有那个，两个条目并列）：

```json
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
  },
  {
    "matcher": "Read|Grep|Bash",
    "hooks": [
      {
        "type": "command",
        "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-queue-read-guard.ps1\"",
        "timeout": 10
      }
    ]
  }
]
```

🔴 **路径必须带双引号、写主仓绝对路径**——理由与既有四枚钩子完全同形（本机用户目录含空格；写绝对路径使所有 worktree 跑的都是同一份脚本，不会有"某个 worktree 里的钩子是旧版"这种静默漂移）。

### 核验（跑完应看到 `True`）

```powershell
python -c "import json,pathlib;d=json.loads(pathlib.Path(r'C:\Dev\zhuopin-ai\.claude\settings.json').read_text(encoding='utf-8'));pt=d.get('hooks',{}).get('PreToolUse',[]);print('PreToolUse 条目数：', len(pt));print('含 Read|Grep|Bash matcher：', any(e.get('matcher')=='Read|Grep|Bash' for e in pt))"
```

**预期输出**：`PreToolUse 条目数： 2`，`含 Read|Grep|Bash matcher： True`。

---

## 装完之后：两条验收（我来做，你只需回一句"装好了"）

| # | 场景 | 验收动作 | 判据 |
|---|---|---|---|
| 1 | 拦截 | 尝试 `Read` 两份队列真身之一（不经 `--row`/`--digest`） | 被拒绝（`exit 2`），提示改用查询工具；`reports/hooks-audit.jsonl` 新增一行 `hook=pretooluse-queue-read-guard, verdict=violation` |
| 2 | 放行 | 正常调用 `python 0-学习与工具/工具-队列查询.py --digest --grep <关键词>` | 正常输出摘要，不受影响；审计新增一行 `verdict=pass`（命中白名单） |

**每一条通过后**，`.claude/rules/队列与落库.md`「读侧禁通读」条目末句"机器守…待落地，落地前本条人守"才能按 `#381` 硬约束「先验活、后降指针」进入下一步（openspec 变更包 `queue-read-write-guards` tasks.md §5，本次未做，前置条件即此两条验收）。

---

## 已知边界（如实写，不藏）

1. **仅 CC 生效**：与既有四枚 P3 钩子同形（P0 实测坐实，`根CLAUDE.md彻底瘦身-方案-2026-09-03.md` §五），Cowork 桌本钩子不生效，`.claude/rules/队列与落库.md`「读侧禁通读」条目对 Cowork 桌仍是人守，不因 CC 侧验活而降级。
2. **只判结构化目标字段精确命中**：`Read`/`Grep` 只在目标路径**精确**等于两份队列真身或匹配归档命名规则时拦截，不做目录归属之类的模糊启发式；`Grep` 未传 `path`（最常见形态）时不拦——这是刻意的收窄，不是遗漏（design 决策点 1）。
3. **Bash 只在"读命令词 + 目标文件名"同时出现时拦**：单独出现 `grep`（如 `pytest -k grep`）或单独出现队列文件名（如 `git log -- <队列文件>`）均不拦；四个机制工具（编辑锁／队列查询／sweep／队列结构 lint）的调用整条放行，即使其参数里恰好同时出现"grep"字样与归档文件名（design 决策点 3）。
