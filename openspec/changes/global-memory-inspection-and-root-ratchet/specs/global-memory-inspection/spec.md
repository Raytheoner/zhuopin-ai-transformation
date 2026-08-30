## ADDED Requirements

### Requirement: 本机全局记忆 SHALL 每轮被巡检且零红时亦回显
sweep 每轮 MUST 对配置的本机全局记忆文件（首项 `~/.claude/CLAUDE.md`）执行三判据巡检，并 MUST 逐项打印「当前值／阈值／差额」形态的回显；**零告警时 MUST NOT 省略回显**（同第 4 类常驻告警既有纪律：连回显都没有时，无法区分「没问题」与「没跑」）。

#### Scenario: 全部合格
- **WHEN** 三判据均无发现
- **THEN** 日志仍出现「全局记忆巡检」一节，逐项列出核过的路径数、字节数与阈值差额

### Requirement: 文中本机路径 SHALL 逐个核存在性，不存在即告警
巡检 MUST 抽出文中形状为 `C:\…` 或 `~/…` 的片段（`~/` 按 `$env:USERPROFILE` 展开），逐个存在性核验；不存在的 MUST 告警并附**行号与原文片段**。误报 MUST 只报不改；漏报 MUST 记为已知边界，MUST NOT 因怕误报而收紧到漏报。

#### Scenario: 路径已迁走
- **WHEN** 文中写 `~/OneDrive/Projects/企业AI转型` 而该目录已不存在
- **THEN** 告警「路径不存在」，附行号与原文，人工订正后下一轮自动消失

#### Scenario: 散文被误认为路径
- **WHEN** 某片段形状像路径但实为散文
- **THEN** 报一条假阳性，人核一眼即可；MUST NOT 因此跳过整个文件的巡检

### Requirement: 版本快照 SHALL 被告警为「存取法、不存快照」
巡检 MUST 匹配版本号形态（`v?\d+\.\d+(\.\d+)?`）与已知模型代号词并告警；MUST 排除路径内版本段（如 `Python314`、`nodejs`）与队列编号（`#NNN`）等已知噪声。

#### Scenario: 写死的工具版本
- **WHEN** 文中出现 `Claude Code：v2.1.x`
- **THEN** 告警并给出判据一句：没有任何纪律以版本号为条件，写死只会静默变旧，要用时现取

### Requirement: 备份堆积 SHALL 被告警
巡检 MUST 统计受检文件同目录下的备份件（`CLAUDE.md*.bak*` 形态）个数与最旧件日期；超过 `GLOBAL_MEMORY_BAK_CAP`（默认 3）MUST 告警并列出个数、最旧件名与日期。MUST NOT 自动删除任何备份件。

#### Scenario: 备份攒到超阈值
- **WHEN** `~/.claude` 下有 5 个 `CLAUDE.md*.bak*`、最早 2026-06-24
- **THEN** 告警「备份 5 个 / 阈值 3，最旧 CLAUDE.md.bak（2026-06-24）」，由人决定删哪些

#### Scenario: 备份数在阈值内
- **WHEN** 备份 ≤ 3 个
- **THEN** 回显个数与阈值，不告警（同 A2「零超限亦回显」）

### Requirement: 受检对象读不到 SHALL 告警且 SHALL NOT 中止整轮
受检文件不存在或不可读时 MUST 作为一条告警上报（「受检对象自己不见了」亦属失真），MUST NOT 静默跳过，MUST NOT 让 sweep 整轮中止。

#### Scenario: 换机后路径失效
- **WHEN** `~/.claude/CLAUDE.md` 不存在
- **THEN** 告警「受检对象缺失」，sweep 其余各轮照常完成

### Requirement: 巡检 SHALL 只报不改
巡检 MUST NOT 自动修改任何本机全局记忆文件；一切改动 MUST 经 Shao Peishen 逐次授权后由人（或经授权的会话）执行。

#### Scenario: 发现失真
- **WHEN** 巡检报出路径失真
- **THEN** 只产生告警与订正建议，文件内容保持原样

### Requirement: 状态字段与行内自陈不一致 SHALL 产出改判候选清单
巡检 MUST 扫 §一 中状态字段为 `open`／`partial` 的行，若其状态列自陈命中外部阻塞措辞集（硬阻塞／已押后／待 Shao Peishen／待拍板／需人在场／留步／常驻不销 等），MUST 列为改判候选并给出建议字段（`blocked` 或 `timed=`）与命中的原话片段。清单 MUST 在机制类可动 WIP 阻断消息中一并给出。

MUST NOT 自动改写任何行的状态字段。MUST NOT 改变 `_count_mechanism_wip` 的计入口径（`partial` 仍计入——其中确有真可动者）。

#### Scenario: 主体完成、尾巴挂在外部条件上
- **WHEN** 某 `[S:partial]` 行自陈「apply 已完成、真实冒烟仍未做」
- **THEN** 列为候选，建议 `blocked`，附该原话片段；行本身不被改动

#### Scenario: 真可动的 partial 不应被误伤
- **WHEN** 某 `[S:partial]` 行自陈「Cowork 半完成、CC 半待领」
- **THEN** 不列为候选（无外部阻塞措辞），且其计入 WIP 的口径不变

#### Scenario: WIP 阻断时
- **WHEN** release 因机制类可动 WIP 超上限被阻断
- **THEN** 阻断消息除现有两条出路外，附带当前改判候选清单，使分诊无需人另起一棒

## MODIFIED Requirements

### Requirement: root `CLAUDE.md` 尺寸阈值 SHALL 为只降不升的棘轮
`CLAUDE_MD_ROOT_BYTE_CAP` MUST 取 48 KB（立包时实测 47,863 B）。每轮回显 MUST 在实测值低于阈值 1,024 B 以上时，提示「可将 cap 下调至 <实测值+512>」。调高阈值 MUST 在提交里显式说明理由，MUST NOT 为容纳新增内容而顺手调高。

#### Scenario: 瘦身后阈值可收紧
- **WHEN** `#381` 落地后 root 降至 42,000 B
- **THEN** 回显提示「可将 cap 下调至 42,512」，下一次触碰时收紧

#### Scenario: 有人让 root 变大
- **WHEN** 某次改动使 root 超过 48 KB
- **THEN** 当轮告警，要求同批 one-in-one-out 或显式说明理由调高
