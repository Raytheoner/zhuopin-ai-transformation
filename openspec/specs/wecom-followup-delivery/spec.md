# wecom-followup-delivery Specification

## Purpose
TBD - synced from change wecom-aibot-channel (change remains active, not yet archived; §7/§8 部分验收项与晋档条件仍待观察/待 Paul 定，见 tasks.md). Update Purpose after archive.

## Requirements

### Requirement: 按指定跟进信推送
系统 SHALL 提供推送函数，接收「部门AI专员跟进」README 表格中某一行的引用，读取对应 `.md` 正文（+ `.docx` 附件，若存在）经智能机器人连接器推送到项目群。系统 MUST NOT 自主扫描 README 全表并自动决定推送哪一封（推送动作由调用方显式指定具体某一行）。

#### Scenario: 显式指定单封信推送
- **WHEN** 调用方传入 README 中某一行的行标识（如日期+收信人+主要事项）
- **THEN** 系统读取该行对应的 `.md`/`.docx` 文件并发起推送，不触碰表格其他行

### Requirement: 门禁②——仅定稿可发
推送函数 MUST 在发送前读取 README 该行「发送状态」列，仅当其值严格等于约定的"待发"标记（如 `🆕 待发`）时才允许发送；任何其他取值（含空、已发、待 Paul 对齐等）MUST 拒绝发送并记录拒绝原因，不得放宽此断言。

#### Scenario: 状态列为待发，允许发送
- **WHEN** 目标行「发送状态」列值为约定的待发标记
- **THEN** 系统执行推送

#### Scenario: 状态列非待发，拒绝发送
- **WHEN** 目标行「发送状态」列值不等于约定的待发标记（如为空、"已发"、"待对齐"等任意其他值）
- **THEN** 系统拒绝发送，抛出明确错误说明当前状态，审计记录 `action="delivery_rejected", reason="not_finalized"`

### Requirement: 发送成功后 README 状态回填
推送成功后，系统 SHALL 原子性地将 README 该行「发送状态」列回写为"已推送"标记并附带时间戳，不得遗漏回填导致重复推送风险。

#### Scenario: 推送成功回填状态
- **WHEN** 推送函数成功完成一次发送
- **THEN** README 该行状态列更新为"✅ 已推送 <时间戳>"，审计记录本次推送与回填动作

#### Scenario: 回填失败不掩盖发送成功事实
- **WHEN** 推送已成功但 README 回填写入失败（如文件被占用）
- **THEN** 系统必须明确报错并保留审计中"已发送但未回填"的可追溯记录，不得静默忽略，避免同一封信被误判"待发"而重复推送
