## Purpose

定义 `0-学习与工具/工具-队列查询.py` 的归档检索与机器可读输出能力——使"某个队列行号当前处于哪个载体、是否已完成"成为一个**可被程序消费**的问题，而不是只能由人读中文文案得出的结论。

背景：现状下该工具只查两份在办队列，且**"未找到"与"找到了"退出码同为 0**（实测 `--row 368 --section 一` 输出"✗ 未找到…"、`exit=0`）——属本项目「工具静默回退」族，任何依赖其退出码的调用方都会拿到一个看起来正常的成功。

## ADDED Requirements

### Requirement: 归档检索为可选开关
工具 SHALL 新增 `--include-archive` 开关，默认**关闭**。开启时，检索范围 SHALL 在既有两份在办队列之外，追加全部归档件。

归档件发现 SHALL 使用 glob `1-转型规划/0-全景路线图/跨桌任务队列-归档-*.md`；该 glob 是本规范定义的契约，归档件命名变更时 SHALL 同步更新本契约。

#### Scenario: 默认不查归档
- **WHEN** 不传 `--include-archive` 查询 §一 `#368`
- **THEN** 行为与本变更引入前**逐字一致**——输出"未找到"提示且退出码为 0

#### Scenario: 开启后可检出归档行
- **WHEN** 传 `--include-archive` 查询 §一 `#368`
- **THEN** 结果 SHALL 指出该行命中于 `跨桌任务队列-归档-202608.md`

### Requirement: 机器可读输出为可选开关
工具 SHALL 新增 `--format` 参数，取值 `text`（默认）与 `json`。`--format json` 时 SHALL 输出单个 JSON 对象，包含以下字段：

| 字段 | 语义 |
|------|------|
| `row` | 查询的行号 |
| `section` | 查询的章节 |
| `found` | 是否命中任一载体 |
| `carrier` | `live` / `archive` / `none` |
| `file` | 命中文件的仓库根相对路径；未命中为 `null` |
| `line` | 命中行的 1-based 行号；未命中为 `null` |
| `status_field` | 命中行状态列开头机器字段的取值；无法解析为 `null` |
| `done` | **最终完成判定** |
| `reason` | `live-open` / `live-done` / `archived` / `unresolved` |

#### Scenario: 默认输出不变
- **WHEN** 不传 `--format` 查询任一行号
- **THEN** 输出文本与退出码 SHALL 与本变更引入前逐字一致

### Requirement: done 字段的判定来源
`done` 字段 SHALL 按载体决定判定来源：`carrier` 为 `archive` 时 `done` SHALL 恒为 `true` 且 **MUST NOT** 参考 `status_field`；`carrier` 为 `live` 时 `done` SHALL 取决于 `status_field` 是否为 `done`；`carrier` 为 `none` 时 `done` SHALL 为 `false`。

`status_field` 与 `done` 允许不一致，消费方 SHALL 只读 `done`，`status_field` 仅供人工排查。

#### Scenario: 归档行状态字段与 done 不一致
- **WHEN** 以 `--include-archive --format json` 查询 §一 `#368`（其归档行 `cells[5]` 实际为 `[S:open][D:业] 🆕 未开工`）
- **THEN** 输出 SHALL 为 `carrier="archive"`、`status_field="open"`、`done=true`、`reason="archived"`

#### Scenario: 在办已完成行
- **WHEN** 查询 §一 `#395`（在办机制环境，状态列以 `[S:done]` 开头）
- **THEN** 输出 SHALL 为 `carrier="live"`、`done=true`、`reason="live-done"`

#### Scenario: 在办未完成行
- **WHEN** 查询 §一 `#397`（在办机制环境，状态列以 `[S:open]` 开头）
- **THEN** 输出 SHALL 为 `carrier="live"`、`done=false`、`reason="live-open"`

#### Scenario: 未命中
- **WHEN** 查询一个在全部载体中均不存在的行号
- **THEN** 输出 SHALL 为 `found=false`、`carrier="none"`、`done=false`、`reason="unresolved"`——消费方据此**照常派出**，MUST NOT 将其解读为已完成

### Requirement: 归档侧章节与行定位
归档检索 SHALL 复用与在办侧同一套行定位判据：章节标题匹配兼容 `## 一、`、`## §一 `、`### §一 ` 三种写法并支持单文件多个同章节表；单元格切分复用 `queue_table.split_row_cells()`；行匹配为 `cells[0]` 数值相等。各载体 SHALL 逐份解析后合并，MUST NOT 拼接文本后解析一次。

#### Scenario: 归档件内多个 §一 表全部纳入
- **WHEN** 检索 `归档-202608.md`（内含 4 个 §一 表）
- **THEN** 四个表内的行 SHALL 全部纳入检索范围

#### Scenario: 不与 §四 编号混淆
- **WHEN** 以 `--section 一` 检索 `#88`，而归档件 §四 章节内存在编号 `88` 的行
- **THEN** 该 §四 行 MUST NOT 被返回
