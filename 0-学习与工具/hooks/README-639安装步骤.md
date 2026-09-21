---
title: "Stop 读取面钩子（#639）· 人工安装单"
created: 2026-09-21
来源: 队列 §一 `#639`（泳道读取面切分），建造 session `OP-0921-I`
状态: ⏳ 等你（脚本＋单测已完成，仅缺 settings.json 一步）
预计耗时: 1 分钟（改一个 JSON）
---

# Stop 读取面钩子（#639）· 人工安装单

## 为什么只差这一步

`hooks-posttooluse-context-meter.ps1` 只在工具调用后触发——若某一轮回复不含工具
调用（纯文本收尾）就直接进 Stop，那一轮的 usage 永远不会被写进
`reports/context-meter/<sid>.json` 的 `lastContext`。实测同一条泳道：闸读到
223,309，`工具-Token用量度量.py`（逐行扫描整份 transcript）算出 230,874，差
7,565；当日四条逐条比对闸均偏低。

修法＝新增 `hooks-stop-context-meter.ps1` 作为第二个读取面，与 PostToolUse 共用
`hooks-context-meter-lib.ps1` 的状态读写逻辑，在 Stop 时机把纯文本收尾轮次的
usage 补写进同一份状态文件——`工具-opener批处理执行v2.ps1` 的轮询与收尾"最后一探"
读到的就是补齐后的真实值。单测 `test_hooks-stop-context-meter.py` 已用最小场景
实测复现：旧行为（只有 PostToolUse）残差 15,000，新行为（PostToolUse + Stop）残差
归零（见该文件 `test_读取面缺口_纯文本收尾轮次的usage只有Stop钩子补得上`）。

脚本本体落在 `0-学习与工具/hooks/`（不在 `~/.claude/protected-paths.json` 受控范围
内），CC 已经能写；唯独 `.claude/settings.json` 命中 `*/.claude/settings.json`
（`mode: block`）受控规则，必须由你手动加一行。

## 唯一要做的事

**改哪个文件**：`C:\Dev\zhuopin-ai\.claude\settings.json`（**项目**那份）。

现有 `hooks.Stop` 数组只有一个元素（`hooks-stop-decision-check.ps1`）。在它的
`hooks` 子数组里**追加**下面这一项（前面补一个逗号）：

```json
{
  "type": "command",
  "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-context-meter.ps1\"",
  "timeout": 10
}
```

即整个 `Stop` 键变成：

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-decision-check.ps1\"",
        "timeout": 10
      },
      {
        "type": "command",
        "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-context-meter.ps1\"",
        "timeout": 10
      }
    ]
  }
]
```

### 核验（跑完应看到 `True`）

```powershell
python -c "import json,pathlib;d=json.loads(pathlib.Path(r'C:\Dev\zhuopin-ai\.claude\settings.json').read_text(encoding='utf-8'));cmds=[h['command'] for s in d['hooks']['Stop'] for h in s['hooks']];print('hooks-stop-context-meter 已注册:', any('hooks-stop-context-meter.ps1' in c for c in cmds))"
```

## 装完之后（我来做，你只需回一句"装好了"）

新开一个 CC 会话跑几轮工具调用后正常收尾，核对 `reports/hooks-audit.jsonl`
新增一行 `hook=stop-context-meter, verdict=pass`，且同 session 的
`reports/context-meter/<sid>.json` 的 `lastTs` 与 Stop 时刻接近（证明确实在
Stop 时机补写了一次，不是只有 PostToolUse 在写）。
