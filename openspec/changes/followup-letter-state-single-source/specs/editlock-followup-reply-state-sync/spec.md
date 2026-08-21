## ADDED Requirements

### Requirement: 拆件完成 SHALL 强制 README 转闭环态
`工具-共享文档编辑锁.py` 在**队列系统**目标的 `release` 时 SHALL 校验：若队列 §一 存在一条确定指向某封跟进信的入信行、其状态字段已 `[S:done]`（＝已拆件回灌），而该信在 README「现有跟进信清单」中的发送状态仍非闭环四态之一，MUST 拒绝 release（锁保持占用）。

违规说明 MUST 指明：入信行行号、该信编号、README 当前状态、可用的闭环四态取值，以及**该改哪个文件**。

本校验 MUST NOT 挂在 README 目标的 `release` 上——拆件回灌这个动作发生在队列一侧，挂在别处会惩罚与该漂移无关的编辑者。

#### Scenario: 已拆件而 README 未转态被拒
- **WHEN** §一 某入信行为 `[S:done]`、其归档文件名确定配对到某封信，而该信 README 状态为 `✅ 已推送 …`
- **THEN** release 返回非 0，输出含该信编号、该入信行号与目标文件名

#### Scenario: README 已属闭环四态任一即放行
- **WHEN** 该信 README 状态为 `✅ 无需回复`／`📨 已确认闭环`／`❌ 已作废`／`📥 已回件并回灌` 之一
- **THEN** release 正常通过

#### Scenario: 入信行尚未拆件不拦
- **WHEN** 该入信行状态字段为 `[S:open]`
- **THEN** release 正常通过（该情形归入信桥管辖，不归本校验）

#### Scenario: 第九态不算闭环
- **WHEN** README 该行状态为 `📨 回件已到，待拆件 <UTC>` 而入信行已 `[S:done]`
- **THEN** release 被拒绝

### Requirement: 配对 SHALL 确定，判不出即不拦
入信行与跟进信的配对 SHALL 仅按「归一化后的原信文件名 stem 逐字相等」判定，MUST NOT 使用包含匹配、编辑距离或最相似匹配。归一化 SHALL 限于剥除扩展名与专员回传时附加的确定尾缀（`-回复`／`-回件`）。

配对不上时 MUST NOT 拦截，也 MUST NOT 猜测对应关系。

#### Scenario: 纯文本回件不参与配对
- **WHEN** 入信归档文件名的主题段为 `文本反馈`
- **THEN** 不与任何信配对，release 不因此被拦

#### Scenario: README 行未带目标文件标注则判不出
- **WHEN** README 该行「主要事项」列不含队列 #241 的 `目标文件：` 标注
- **THEN** 该行不参与配对，release 不因此被拦

### Requirement: 逃生阀 SHALL 一次一用
本校验 SHALL 提供逃生阀标记 `转态豁免：〈理由〉`。取材面 MUST 限于**本次持锁的 note** 与**本次持锁期间触碰过的队列行**，MUST NOT 匹配队列文件全文——写在任意历史行里的同一标记若能长期生效，等于把这道门禁永久关掉且无人会发现。

命中逃生阀时 MUST 打印留痕，MUST NOT 静默放行。

#### Scenario: 本次触碰行内写豁免则放行并留痕
- **WHEN** 持锁期间修改的那一行内含 `转态豁免：…`
- **THEN** release 通过，且输出含「转态豁免」字样

#### Scenario: 队列文件里的陈年豁免字样不生效
- **WHEN** `转态豁免：` 只出现在本次未触碰的历史行中
- **THEN** release 仍被拒绝

### Requirement: 队列文件 SHALL 逐份解析后合并
入信行扫描 MUST 对每份物理队列文件独立解析后合并，MUST NOT 先拼接文本再解析一次——分区解析按标题定位、同名分区后写覆盖先写，拼接会使第一份的 §一 被静默丢弃。

#### Scenario: 业务场景文件里的入信行同样被看见
- **WHEN** 唯一的已拆件入信行位于 `跨桌任务队列-业务场景.md`
- **THEN** 该行被计入，release 被拒绝

### Requirement: 权威判据模块不可用时 SHALL fail-loud
`zhuopin_platform.shared_tools.followup_gate` 无法加载时，本校验 MUST 打印可见提示后跳过，MUST NOT 无声无息地不执行。CI SHALL 另有一条断言保证该模块在真实仓库中始终可 import。

#### Scenario: 模块缺失时打印提示
- **WHEN** 权威判据模块不可用
- **THEN** 输出含「未能加载」的提示，且校验返回空违规列表
