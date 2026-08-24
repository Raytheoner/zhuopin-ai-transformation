## ADDED Requirements

### Requirement: 队列表格行 SHALL 受称呼判据门禁约束
`工具-队列结构lint.py` SHALL 对两份物理队列文件的 §一／§二／§四 **表格数据行**扫描
`Paul` 字面量；命中数超出 baseline 冻结值的行 MUST 判为违规，且该违规 MUST 计入
`lint()` 返回值与进程退出码，MUST NOT 只作告警。

判据 MUST 大小写敏感，且命中前后 MUST NOT 紧邻拉丁字母——`PAUL_USERID`、`cc_to_paul`、
`paulista` 一类代码标识符 MUST NOT 被判违规。

违规说明 MUST 同时给出：正确写法（`Shao Peishen`）与逃生阀写法（`称呼豁免：`）。
只写「别这么写」而不给出路的说明 MUST NOT 视为合格输出。

#### Scenario: baseline 外的新增行即报
- **WHEN** 一个不在 baseline 中的 §一 行的状态列写有 `Paul 2026-08-24 拍板`
- **THEN** 该行被判违规，说明中含该行编号、含 `Shao Peishen`、含 `称呼豁免：`

#### Scenario: 代码标识符不被误伤
- **WHEN** 一行含 `PAUL_USERID`、`cc_to_paul=False`、`paulista`
- **THEN** 不判违规

#### Scenario: §二 与 §四 同在扫描面内
- **WHEN** §二 批次行的建议 message 与 §四 行的「等谁」列各含一处 `Paul`
- **THEN** 两行各报一条违规

### Requirement: 判据 SHALL 以 baseline 冻结存量、只拦新增
baseline SHALL 是一个入库的 JSON 文件，键＝`§区#行号`、值＝该行冻结时的命中数。
判据 MUST 按「计数棘轮」比较：`当前命中数 > 冻结值` 才算违规。

行键 MUST 跨两份物理队列文件全局唯一且 MUST NOT 含文件名——行在两份队列文件之间搬家
MUST NOT 产生违规。

已在 baseline 中的行再新增命中 MUST 判违规，MUST NOT 因「该行已在 baseline」而整行放行。

当前命中数少于冻结值时 MUST NOT 判违规，但 MUST 作为「漂移」计数并输出。

#### Scenario: 存量命中不报
- **WHEN** 某行命中 2 处且 baseline 记该行为 2
- **THEN** 不判违规

#### Scenario: 已 baseline 的行再加一处即报
- **WHEN** 某行命中 3 处而 baseline 记该行为 2
- **THEN** 判违规，说明中含「新增 1 处」

#### Scenario: 纯搬家不报
- **WHEN** 一个 baseline 行整行从队列文件 A 移到队列文件 B、内容一字未改
- **THEN** 不判违规

#### Scenario: 命中变少算漂移不算违规
- **WHEN** 某行命中 1 处而 baseline 记该行为 5
- **THEN** 不判违规，且该行进入漂移计数

### Requirement: 三类豁免 SHALL 生效且 MUST NOT 静默
路径与账户名形态（`Paul` 紧跟 ` Shao`）MUST NOT 判违规——根 `CLAUDE.md` §1「绝不替换路径里的
`Paul Shao`」。

§一 状态列为 `[S:done]` 的行 MUST NOT 判违规——根 `CLAUDE.md` §1「历史记录不追改」。

行内写有 `称呼豁免：` 标记的行 MUST NOT 判违规。该逃生阀的理由 MUST 写在队列行内，
MUST NOT 以命令行开关的形式提供。

`[S:done]` 与行内标记两类豁免 MUST 被按原因分类计数并打印；MUST NOT 静默放行。

#### Scenario: 路径与账户名不报
- **WHEN** 一行含 `C:\Users\Paul Shao\Claude\Sc`、`Paul Shao / S4U`、`` `Paul Shao` 的空格处截断 ``
- **THEN** 不判违规

#### Scenario: 已完成历史行豁免且被计数
- **WHEN** 一条 `[S:done]` 的 §一 行含 `Paul 2026-07-01 拍板`
- **THEN** 不判违规，且该行以原因「`[S:done]` 历史行」进入豁免计数

#### Scenario: 行内标记豁免且被计数
- **WHEN** 一条 §一 行的状态列含 `称呼豁免：本行是判据定义行，须引用 `Paul` 字面量`
- **THEN** 不判违规，且该行以原因「行内标记」进入豁免计数

### Requirement: baseline 不可达时 SHALL fail-loud
baseline 文件不存在或无法解析时，判据 MUST 返回一条指明「baseline 文件不存在／无法解析」
的违规，MUST NOT 回退成空 baseline 后照常扫描。

#### Scenario: baseline 缺失
- **WHEN** baseline 文件不存在
- **THEN** 返回恰好一条违规，其中含「baseline 文件不存在」

#### Scenario: baseline 损坏
- **WHEN** baseline 文件内容不是合法 JSON
- **THEN** 返回恰好一条违规，其中含「无法解析」

### Requirement: baseline 重刷 SHALL 需要显式落盘动作
工具 SHALL 提供 `--emit-baseline`，按 baseline 格式把当前命中集写到 **stdout**。
工具 MUST NOT 提供任何直接改写 baseline 文件的开关。

已豁免的行 MUST NOT 写入 baseline——它们永远不会被判违规，写进去只会让读 baseline 的人
误以为那些行是被 baseline 放行的。

#### Scenario: emit 不写盘
- **WHEN** 以 `--emit-baseline` 运行
- **THEN** JSON 出现在 stdout，baseline 文件本身未被修改

#### Scenario: 豁免行不入 baseline
- **WHEN** 队列中存在 `[S:done]` 或带 `称呼豁免：` 的命中行
- **THEN** 这些行的键不出现在 `--emit-baseline` 的产出里
