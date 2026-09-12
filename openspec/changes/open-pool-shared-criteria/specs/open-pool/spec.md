## ADDED Requirements

### Requirement: 可 Open 池 SHALL 只有一个判定函数，推送器与看板 SHALL 共用它
可 Open 池的入池判据 MUST 只实现于 `zhuopin_platform.shared_tools.open_pool.judge_open_pool_row`。企微推送器（`aibot_service.open_pool_reminder`）MUST 直接 import 该函数；看板数据层（`工具-项目状态卡数据层.ps1`）MUST 经 `0-学习与工具/工具-可Open池.py` 子进程取该函数的输出，MUST NOT 在 ps1／JS 内另持一份判据。两侧对同一份队列真身算出的池 MUST 逐行相同（编号／域／状态三元组），并由断言测试锁死。

#### Scenario: 两侧对生产队列真身逐行相同
- **WHEN** 推送器 `build_pool_items_from_repo(root)` 与真跑 ps1 数据层的 `pool` 在同一份队列真身上各算一次
- **THEN** 两者的 (编号, 域, 状态) 集合逐行相等；任一侧私加过滤即测试变红

#### Scenario: 改判据只改一处
- **WHEN** `judge_open_pool_row` 的任一条判据改变
- **THEN** 推送器与看板的池同时改变，无需分别改动

### Requirement: 入池判据 SHALL 为 2026-09-02 裁定的看板判据
- `[S:open]` MUST 结构性入池；`[S:partial]` MUST 默认入池。
- `done／blocked／hold／timed=` MUST 结构性排除。
- 状态列含 `[A:` MUST 排除（不解析取值）。
- 状态列正文**或**任务列以 🛑 起首 MUST 排除（认两列，同 `_count_mechanism_wip` 2026-09-11 口径）。
- `[S:partial]` 且状态列开头片段（剥前导 `*`／空白、截到首个 `。`／`——`／`━━━` 之前）含「在办／在建／进行中／建造中」MUST 排除并单列（`poolEx`），MUST NOT 静默丢弃。
- `[S:partial]` 且开头片段以 ✅ 起首 MUST 入池并带 flag。
- 缺 `[S:]` 或缺 `[D:]` 的可动行 MUST 归 degraded 并单列（`poolDeg`），推送器 MUST 发可见告警，MUST NOT 猜域入池。
- 列数不符的行 MUST 归 skipped 并列出行号，MUST NOT 纳入判定。

#### Scenario: partial 尾巴待领入池
- **WHEN** 状态列为 `[S:partial][D:机] 🟡 半边待领`
- **THEN** 该行入池，状态 `partial`

#### Scenario: partial 自陈在办单列
- **WHEN** 状态列为 `[S:partial][D:机] 🔄 在办中（三步已完成两步）`
- **THEN** 该行不入池，出现在 `poolEx` 且带理由「partial 但开头片段自陈在办」

#### Scenario: 任务列 🛑 起首排除
- **WHEN** 任务列为 `🛑 排队中·暂非可动…`、状态列为 `[S:open][D:机] 待领`
- **THEN** 该行不入池

#### Scenario: 缺域行不猜域
- **WHEN** 状态列为 `[S:open] 待领`（无 `[D:]`）
- **THEN** 该行归 degraded，推送器发 RuntimeWarning，池中不含该行

### Requirement: 看板数据层调判定层失败 SHALL 显式「无法核验」
ps1 调 `工具-可Open池.py` 失败（python 不在位／脚本不在位／未输出 `@@POOL64@@`／JSON 解析失败／任一队列文件读取失败／非零退出）时 MUST 置 `src.pool.ok=false` 并给出指名道姓的原因，同时 MUST 置 `src.q1.ok=false`（JS 仅认 `q1`），MUST NOT 让池渲染为 0 行或绿色徽标。

#### Scenario: CLI 脚本不在位
- **WHEN** `$PSScriptRoot\工具-可Open池.py` 不存在
- **THEN** 输出 JSON 的 `src.pool.ok=false`、`src.q1.ok=false`，`why` 含脚本路径，`pool` 为空数组

### Requirement: CLI 契约 SHALL 纯 ASCII 且残缺结果 SHALL 显式报错
`工具-可Open池.py --json-b64` MUST 只在 stdout 输出一行 `@@POOL64@@` + base64(UTF-8 JSON)。任一物理队列文件读取失败时 MUST 在 `errors` 中列出并以退出码 2 结束，MUST NOT 把残缺结果当作完整的池。

#### Scenario: 一份队列文件缺失
- **WHEN** 业务场景那份文件不存在
- **THEN** `errors` 含该文件相对路径与原因，退出码为 2
