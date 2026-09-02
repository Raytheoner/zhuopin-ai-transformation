## ADDED Requirements

> ⚠️ 本 delta 按 proposal「开放点 1」的**选项 1（形态 C ＋ baseline 棘轮）**写就，
> 因为 openspec 要求 proposal 必须携带至少一份可校验的 delta。
> 🔴 **design 审若改选其它选项，本 delta 须整体重写**——它不是已定稿的口径。

### Requirement: 队列表格行 SHALL 受「包进度须写指针」告警约束
`工具-队列结构lint.py` SHALL 对两份物理队列文件扫描 openspec 包名提及；
一个**提到了活跃 openspec 包名、却未在同一行内给出 `tasks.md` 指针**的行 SHALL 被报为告警。

一期该告警 MUST NOT 计入 `lint()` 返回值与进程退出码——它 MUST 只作告警。
理由：判据精度已实测不足（proposal 取证 2、3），一条判不准却能拦 push 的门禁会被绕过，
绕过的将是 lint 本身。

扫描面 MUST 沿用既有 `_table_data_rows`：**§一 非 `[S:done]` 的行 ＋ §四 全部行**。
§二 批次行 MUST NOT 进入扫描面——它天然是 commit 历史记录。
本判据 MUST NOT 另开一套「队列长什么样」的解析。

告警说明 MUST 同时给出：违反了什么、以及**出路**（该包 `tasks.md` 的相对路径）。
只写「别这么写」而不给出路的说明 MUST NOT 视为合格输出。

#### Scenario: 点了包名却没给指针即告警
- **WHEN** 一条 `[S:open]` 的 §一 行写有「变更包 `lane-watch-mode`，`tasks 2.1` 未执行」且全行无 `tasks.md`
- **THEN** 报一条告警，说明中含该行编号、含包名、含 `openspec/changes/lane-watch-mode/tasks.md`

#### Scenario: 已写指针的行不告警
- **WHEN** 一条 §一 行提到 `lane-watch-mode` 并写有「进度见 `openspec/changes/lane-watch-mode/tasks.md`」
- **THEN** 不报告警

#### Scenario: 告警不改变退出码
- **WHEN** 全库仅有本类告警、其余四项判据全过
- **THEN** `工具-队列结构lint.py` 退出码为 0

#### Scenario: §二 不在扫描面内
- **WHEN** 一条 §二 批次行提到 `lane-watch-mode` 且未写 `tasks.md`
- **THEN** 不报告警

### Requirement: 包名词表 SHALL 实时枚举，MUST NOT 写死
判据 SHALL 在运行时枚举 `openspec/changes/` 与 `openspec/changes/archive/` 下的目录名作为包名词表。
判据 MUST NOT 在代码或配置里内嵌一份包名清单——那会成为第二份「本项目有哪些包」的权威源，
必然漂移（同根 `CLAUDE.md` OP-0819-A ⑴「一份拆成两份」）。

包名匹配 MUST 按长度从长到短，使 `fi2-recon-mvp` MUST NOT 被 `fi2-recon-report` 的子串匹配窃取。

`openspec/changes/` 目录不存在或不可读时，判据 MUST 报出一条指明该情况的告警，
MUST NOT 回退成空词表后照常扫描（fail-loud，同 `#352` baseline 的既有原则）。

#### Scenario: 新建的包当天即被词表覆盖
- **WHEN** `openspec/changes/` 下新增一个目录 `foo-bar`，随后队列某活行提到 `foo-bar` 且无指针
- **THEN** 该行被报为告警，无需改动任何代码或配置

#### Scenario: 归档包同样在词表内
- **WHEN** 队列某活行提到一个已在 `openspec/changes/archive/` 下的包名且无指针
- **THEN** 该行被报为告警

#### Scenario: 词表不可达时 fail-loud
- **WHEN** `openspec/changes/` 目录不存在
- **THEN** 报出恰好一条含「包名词表不可达」的告警，且 MUST NOT 输出「扫描通过」

### Requirement: 存量 SHALL 由 baseline 冻结，只报新增
baseline SHALL 是一个入库的 JSON 文件，键＝`§区#行号`、值＝该行冻结时的告警包名数。
判据 MUST 按「计数棘轮」比较：`当前数 > 冻结值` 才报告警。

行键 MUST 跨两份物理队列文件全局唯一且 MUST NOT 含文件名——行在两份队列文件之间搬家
MUST NOT 产生告警。

当前数少于冻结值时 MUST NOT 报告警，但 MUST 作为「漂移」计数并输出——漂移是可以收紧
baseline 的信号。

工具 SHALL 提供 `--emit-baseline`，按 baseline 格式把当前命中集打到 **stdout**。
工具 MUST NOT 提供任何直接改写 baseline 文件的开关——一个能一键抹平的告警，
在第一次挡住人的那天就会被抹平。

baseline 文件不存在或无法解析时，判据 MUST 报出一条指明「baseline 文件不存在／无法解析」
的告警，MUST NOT 回退成空 baseline 后照常扫描。

#### Scenario: 存量行不报
- **WHEN** 某行命中 2 个包名且 baseline 记该行为 2
- **THEN** 不报告警

#### Scenario: 已 baseline 的行再点一个新包即报
- **WHEN** 某行命中 3 个包名而 baseline 记该行为 2
- **THEN** 报告警，说明中含「新增 1 个」

#### Scenario: 纯搬家不报
- **WHEN** 一个 baseline 行整行从队列文件 A 移到队列文件 B、内容一字未改
- **THEN** 不报告警

#### Scenario: emit 不写盘
- **WHEN** 以 `--emit-baseline` 运行
- **THEN** JSON 出现在 stdout，baseline 文件本身未被修改

#### Scenario: baseline 缺失时 fail-loud
- **WHEN** baseline 文件不存在
- **THEN** 报出恰好一条含「baseline 文件不存在」的告警

### Requirement: 豁免 SHALL 经行内标记且 MUST NOT 静默
行内写有 `包进度豁免：〈理由〉` 的行 MUST NOT 报告警。
该逃生阀的理由 MUST 写在队列行内，MUST NOT 以命令行开关的形式提供——命令行参数是会话级的、
随窗口关闭即消失，而这条逃生阀要治的恰恰是「越过之后没人知道为什么」。

§一 状态列为 `[S:done]` 的行 MUST NOT 报告警——根 `CLAUDE.md` §1「历史记录不追改」。

两类豁免 MUST 被按原因分类计数并打印；MUST NOT 静默放行。
已豁免的行 MUST NOT 写入 `--emit-baseline` 的产出——它们永远不会被报，
写进去只会让读 baseline 的人误以为那些行是被 baseline 放行的。

#### Scenario: 行内标记豁免且被计数
- **WHEN** 一条 §一 行的状态列含 `包进度豁免：本行是判据定义行，须引用包名并谈进度`
- **THEN** 不报告警，且该行以原因「行内标记」进入豁免计数

#### Scenario: 已完成历史行豁免且被计数
- **WHEN** 一条 `[S:done]` 的 §一 行提到某包名且无指针
- **THEN** 不报告警，且该行以原因「`[S:done]` 历史行」进入豁免计数

#### Scenario: 豁免行不入 baseline
- **WHEN** 队列中存在 `[S:done]` 或带 `包进度豁免：` 的命中行
- **THEN** 这些行的键不出现在 `--emit-baseline` 的产出里

### Requirement: 判据 SHALL 如实登记自己的覆盖率缺口
判据的输出 MUST 声明它覆盖不了「整段散文陈述过期包状态」这一形态
（proposal 取证 3：`#439` 的包名与最近进度词实测相距 664 字）。

判据 MUST NOT 以「已上判据」冒充「队列复述包进度已被解决」——
本项目已有反面教材：队列 `#82` 告警建成 9 天、每天在跑、一次都没真响过。

#### Scenario: 输出含覆盖率缺口声明
- **WHEN** 判据正常跑完并打印统计行
- **THEN** 输出中含一句明示「本判据只覆盖『点了包名却没给指针』，覆盖不了散文式过期陈述」
