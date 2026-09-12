## ADDED Requirements

### Requirement: `--repair` 对已塌列的行放开前置门，但要求全量列值输入
`edit-row` SHALL 提供 `--repair` 开关。当目标行在**本次编辑之前**的列数已不等于该分区预期列数（即已经塌列）时：

- 未传 `--repair`：行为与现状一致——拒绝一切操作（含 `--set`／`--append`），不因本能力的引入而改变。
- 传 `--repair`：放开"改之前列数是否合法"这一前置门，但 MUST 要求本次调用一次性提供该分区**全部列**的值；仅提供部分列（通过按列名的 `--set`／`--append` 部分覆盖）MUST 被拒绝，并提示"`--repair` 要求全量列值"。

`--repair` 路径 MUST NOT 豁免 `editlock-write-backtick-span-guard`（反引号游程闭合性校验）与 `editlock-write-postwrite-column-readback`（写入后列数回读校验）——这两项校验对 `--repair` 路径的新写入内容同样适用；`--repair` 只豁免"改之前是否已经损坏"这一个前置判断，不豁免"改完之后是否合法"。

#### Scenario: 已塌列行不传 `--repair`，行为不变
- **WHEN** 目标行编辑前列数不等于该分区预期列数，且本次调用未传 `--repair`
- **THEN** `edit-row` 拒绝本次调用（含仅 `--append` 的调用），不修改目标文件——与引入本能力之前的行为一致

#### Scenario: 已塌列行传 `--repair` 并提供全量列值，放行
- **WHEN** 目标行编辑前列数不等于该分区预期列数，本次调用传入 `--repair` 且提供了该分区全部列的值，且新值全部通过反引号游程闭合性校验
- **THEN** `edit-row` 放开前置门，写入该行；写入后仍须通过写入后列数回读校验

#### Scenario: 已塌列行传 `--repair` 但只提供部分列值，仍拒绝
- **WHEN** 目标行编辑前列数不等于该分区预期列数，本次调用传入 `--repair`，但只通过 `--set`／`--append` 提供了部分列的值
- **THEN** `edit-row` 拒绝本次调用，提示"`--repair` 要求全量列值"，不修改目标文件

#### Scenario: `--repair` 不豁免反引号闭合性校验
- **WHEN** 已塌列行传入 `--repair` ＋ 全量列值，但其中某一列的新值含未闭合反引号游程
- **THEN** `edit-row` 依据 `editlock-write-backtick-span-guard` 拒绝写入，不因传入 `--repair` 而放行

#### Scenario: `--repair` 不豁免写入后列数回读校验
- **WHEN** 已塌列行传入 `--repair` ＋ 全量列值，写入后重新读回、切列得到的列数仍不等于该分区预期列数
- **THEN** 依据 `editlock-write-postwrite-column-readback` 自动回滚，不因传入 `--repair` 而放行一个仍然不合法的结果
