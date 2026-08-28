## ADDED Requirements

> 🔴 **归档前置**：本能力目前只存在于两个尚未归档的变更包
> （`followup-letter-state-single-source`、`followup-reply-pairing-latest-letter`）的 delta 中，
> 尚未 sync 进 `openspec/specs/`，故本包只能用 `ADDED`。归档任一包之前，三者须按
> design.md D7 的对照一次对齐。**本包不得先于那两个包归档。**

### Requirement: 桥二 SHALL NOT 写闭环终态，其天花板为第九态
`工具-共享文档编辑锁.py` 在 `release` 时的自动转态，MUST NOT 再把任何跟进信写为闭环终态 `📥 已回件并回灌`。机器可写的最高状态 SHALL 为既有第九态 `📨 回件已到，待拆件 <UTC>`。

**本 Requirement 取代**前序变更包中的「拆件完成 SHALL 由机器代写闭环态」。退休理由：`[S:done]` 是拆件方的**自陈**，把它直接换算成闭环终态，等于让闸读一份由被守护方自己写的字段；2026-08-28 实撞中 `质量部#10`／`采购部#19` 两封信因此在回灌尚未发生时即显示闸开。

MUST NOT 新造与第九态同义的第三个状态字符串 —— 第九态已逐字表达同一件事，且已有判据、幂等分支与溯源回指契约。

#### Scenario: 已 [S:done] 只写到第九态
- **WHEN** §一 某入信行为 `[S:done]` 且确定配对到某封信，该信 README 状态为 `✅ 已推送 …`
- **THEN** release 通过，该信状态被写为第九态，**不含** `📥 已回件并回灌`

#### Scenario: 已是第九态则为空操作
- **WHEN** 桥一已在回件到达时写过第九态
- **THEN** 桥二不改动该行，README 逐字未变

#### Scenario: 重跑幂等
- **WHEN** 对同一批入信行连续两次 acquire/release
- **THEN** 第二次 README 内容逐字未变

### Requirement: 回灌去向 SHALL 以机器字段 `[R:…]` 记在入信行
拆件回灌完成时，SHALL 在 §一 入信行状态列写入机器字段 `[R:<分区>#<行号>]`（可多值，如 `[R:一#427,一#334]`），与既有 `[S:…]`／`[D:…]` 同族同位，由同一套机器字段解析器读取。

MUST NOT 引入新的自然语言标记来表达同一件事 —— 该字段承载的内容（「派生去向」）本就是拆件巡逻章程 §三.4 已要求写出的东西，本变更只是把它从自由文本挪到机器读得到的位置。

#### Scenario: 单值与多值均可解析
- **WHEN** 入信行状态列含 `[S:done][D:机][R:一#427,一#334]`
- **THEN** 解析出两个回灌去向引用

#### Scenario: 缺该字段不影响既有机器字段解析
- **WHEN** 行内只有 `[S:done][D:机]`
- **THEN** `[S:…]`／`[D:…]` 解析结果与本变更前逐字相同

### Requirement: 缺 `[R:…]` SHALL 低噪提示，SHALL NOT 拦截 release
入信行已 `[S:done]` 但未写 `[R:…]` 时，桥二 MUST NOT 写终态、MUST NOT 拒绝 release，SHALL 在 notes 中输出一行低噪提示，指名是哪一行。

🔴 MUST NOT 升级为拦截：代价不对称——漏写一个字段的后果是闸多锁一会儿（可恢复），而拦死 release 的后果是队列锁放不掉、全线停摆。

#### Scenario: 缺字段不拦
- **WHEN** §一 #500 为 `[S:done]` 但无 `[R:…]`
- **THEN** release 返回 0，输出含指名到行的低噪提示，README 逐字未变

### Requirement: `[R:…]` 引用落空 SHALL 拦
若 `[R:…]` 声明的队列行在两份队列真身中均不存在，MUST 返回违规、拒绝 release，并指名是哪一个引用落空。

理由与既有「判出来却定位不到行 SHALL 拦」同源：写下了一个指向不存在之物的引用，说明另有异常，MUST NOT 静默跳过。

#### Scenario: 引用落空即拦
- **WHEN** 入信行写 `[R:一#9999]`，该行不存在
- **THEN** release 返回非 0，输出含 `一#9999`

### Requirement: 逃生阀 SHALL 保留且语义 SHALL 明确
`转态豁免：〈理由〉` SHALL 继续有效，其语义 SHALL 为「机器本次不写任何状态」。取材面 MUST 限于本次持锁的 note 与本次持锁期间触碰过的队列行，MUST NOT 匹配队列文件全文。

#### Scenario: 本次触碰行内写豁免则机器不写
- **WHEN** 持锁期间修改的行内含 `转态豁免：…`
- **THEN** release 通过，README 状态列逐字未变，输出含「转态豁免」字样

#### Scenario: 陈年豁免字样不得叫停机器
- **WHEN** `转态豁免：` 只出现在本次未触碰的历史行中
- **THEN** 桥二照常按新天花板写第九态
