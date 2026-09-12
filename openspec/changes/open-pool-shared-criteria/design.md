# open-pool-shared-criteria Design

> 判据主体已裁定（2026-09-02，`#312`），不在此重审。D1／D2 是裁定原文未逐字覆盖、本班按既有裁定推导后**已按此实现**的两处细节，须 Shao Peishen 追认（改判只动 `open_pool.py` 一处，两侧自动跟随）。D3 起为不需他点头的实现取舍。

## D1 🟡 🛑 排除**认两列**（状态列正文 **或** 任务列以 🛑 起首）

裁定 ⑵ 原文「正文以 🛑 起首者排除」，看板判据自述「同 `工具-共享文档编辑锁.py::_count_mechanism_wip` 口径」；而该口径已于 2026-09-11（`OP-0911-N`，design D-B 甲）改为**认两列**——`#381` 形态：任务列「🛑 排队中·暂非可动」、状态列不含 🛑，只认状态列会把自陈「暂非可动」的行计入。本班实测生产队列 **`#382`／`#448`** 即此形态，此前**两侧都**把它们推成「可开工」（反向误报，与裁定 ⑵ 要消灭的 `#439`／`#440` 同族）。

⇒ 实现取**两列任一以 🛑 起首即排除**（`open_pool.judge_open_pool_row` 第 4 条）。当前生产影响 ＝ 池少 2 行（70 而非 72）。
**若追认 (b) 只认状态列**：改一行，`#382`／`#448` 回到池里，与 WIP 口径分叉、须另登记。**推荐 (a)**。

## D2 🟡 缺 `[D:机|业]` 域字段的可动行归 **degraded**（单列 `poolDeg`，不入池）

看板 ps1 原正则 `\[S:(\w+)…\]\[D:(.)\]` 要求 `[D:]` 在位，缺则落 `$poolDeg`；推送器原实现 `[D:]` 可选、缺则以 `domain=None` 入池。两者不一致，裁定原文未提。取看板口径的理由两条：⑴ 看板按 `[D:机/业]` 分组渲染，域为 None 的行会**计入 N 却渲染不出来**——数与页面对不上，是最难发现的失效形态；⑵ `#523`（2026-09-09）已裁「缺域行不猜域、只告警」。实现：归 degraded、推送器发 `RuntimeWarning`，`工具-可Open池.py` 人读模式单列。当前生产 open/partial 行**无一缺域**，零即时影响。
**若追认 (b) 缺域也入池**：改一行；看板须同批改 JS 渲染「域未标注」组，否则回到 ⑴ 的失效形态。**推荐 (a)**。

## D3 两侧共用的形态 ＝ Python 权威模块 ＋ ps1 子进程调 CLI 薄壳（不需他点头）

两侧语言不同（Python／PowerShell），「同一个判定函数」只能是跨进程调用。方向取 ps1 → Python：推送器本就是 Python、可单测、可 import；反向（Python 调 ps1）会让每日定时任务依赖 PowerShell 且判据落在不可单测的脚本里。ps1 自身已有先例「直读权威源」（WIP 上限从 `工具-共享文档编辑锁.py::MECHANISM_WIP_CAP_DEFAULT` 正则取值，不写死副本）。

**契约**：CLI `--json-b64` 输出一行 `@@POOL64@@` + base64(UTF-8 JSON)，**stdout 纯 ASCII**——PowerShell 解码子进程 stdout 走 `[Console]::OutputEncoding`，在 Windows-MCP 等无控制台宿主里不可控，`机／业` 若被按 GBK 解就整卡分组失效**且不报错**；base64 把编码问题从通道上拿掉，且不碰 `[Console]`（无控制台时改它会抛）。

**脚本路径取 `$PSScriptRoot`、数据根仍取 `$root`**：生产两者同为 `C:\Dev\zhuopin-ai`；单测从 worktree 起 ps1 时得以用 worktree 的代码算主 checkout 的数据（对账测试 ⑶ 即靠此成立）。

## D4 fail-loud 落点：连带标 `q1`（不需他点头，但如实写代价）

JS 的可 Open 池卡与 `poolN` 徽标只认 `src.q1`（`renderPool` ＝ `srcBad(d,['q1'])`），`index.html` 在仓库外、本班够不着。若判定层失败只标新键 `src.pool`，JS 会走「§一 未解析出任何行」分支、徽标却渲染**绿色 0**——正是该文件反复记录的「看起来最健康的时候恰是坏掉的时候」。⇒ 失败时同时 `Set-Src 'q1' $false`，**代价＝任务看板卡一并显示「无法核验」**（理由串里写明是池判定层失败）。Cowork 侧日后把 JS 改成 `srcBad(d,['q1','pool'])` 后，ps1 那一句可删。

## D5 推送器的「非静默降级」保留并前移顺序告警（不需他点头）

`[A:` 写在 `[D:` 之前会让域解析为 None、行归 degraded（D2）；若先报「缺 [D:]」会掩盖真因，故 `_warn_if_assigned_before_domain` 先于 degraded 判定出声（既有单测 `test_reversed_field_order_emits_runtime_warning` 钉住）。
