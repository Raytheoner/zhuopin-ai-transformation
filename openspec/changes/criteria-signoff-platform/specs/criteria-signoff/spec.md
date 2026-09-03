## ADDED Requirements

### Requirement: 未签认判据 SHALL 恒为 None 且读取 SHALL fail-loud
平台底座 MUST 提供 `zhuopin_platform.criteria_signoff`，其中一条尚未签认的判据 MUST 以 `None` 作为其存储值，且任何**读取其值**的调用 MUST 抛 `CriterionNotSignedOffError`。

读取路径 MUST NOT 返回 `None`、MUST NOT 回退到任何内置默认值、MUST NOT 以 `warnings.warn` 后继续执行代替抛出。

异常信息 MUST 含三项，使调用方当场可知如何解除：这条判据要定什么（`question`）、应由谁签认（`owner`）、以及可选备注（`note`）。

#### Scenario: 读未签认判据抛异常
- **WHEN** 调用方读取一条 `signoff` 为 `None` 的判据的 `.value`
- **THEN** 抛 `CriterionNotSignedOffError`，且异常信息含该判据的 question 与 owner

#### Scenario: 经注册表读取同样抛
- **WHEN** 调用方经 `CriteriaRegistry.value_of(key)` 读取一条未签认判据
- **THEN** 抛 `CriterionNotSignedOffError`——多一层间接不构成旁路

#### Scenario: 未声明的 key 抛而非静默返回空
- **WHEN** 调用方读取一个本场景未声明的判据 key
- **THEN** 抛 `UnknownCriterionError`，使「拼错了」无法伪装成「还没签认」

### Requirement: 读值路径 SHALL NOT 提供任何默认值旁路
`criteria_signoff` 的公开读值 API MUST NOT 接受默认值参数，MUST NOT 提供 `get_or_none` 之类的宽松别名，注册表 MUST NOT 定义 `__getattr__` 容错回退。

`Criterion.value` MUST 是 property（而非可加参数的方法）；`CriteriaRegistry.value_of` 的签名 MUST 恰为 `(self, key)`，不得含带默认值的形参、不得含 `*args`/`**kwargs`。

该约束 MUST 由单测直接断言函数签名，使后续任何人加回默认值参数时 CI 立刻转红。

#### Scenario: 加回 default 参数即 CI 红
- **WHEN** 有人把 `value_of` 改成 `value_of(self, key, default=None)`
- **THEN** `test_no_default_bypass_in_public_api` 失败

#### Scenario: 状态查询不得成为取值旁路
- **WHEN** 调用方使用 `is_signed()` / `unsigned_keys()` / `signed_keys()`
- **THEN** 返回的只有布尔与 key，永不含判据的值

### Requirement: 签认 SHALL 是实名可追溯记录，四项全必填
一次签认 MUST 记录四项且**全部无默认值**：签认人实名 `signed_by`、签认日期 `signed_on`、落档凭据 `evidence`、生效规则版本 `rule_version`。

任一项为空白字符串，或为占位词（`TBD` / `TODO` / `N/A` / `待定` / `待确认` / `未定` / `无` 等）时，MUST 在构造期抛 `CriterionContractError`——占位词不构成签认。

签认 MUST 以「返回新判据对象」的方式发生（`Criterion.signed(value, signoff)`），判据对象 MUST 不可变；MUST NOT 提供就地赋值的 setter。

#### Scenario: 占位词签认人被拒
- **WHEN** 构造 `Signoff(signed_by="TBD", ...)`
- **THEN** 抛 `CriterionContractError`

#### Scenario: 签认不改动原对象
- **WHEN** 对一条未签认判据调用 `.signed(值, Signoff(...))`
- **THEN** 返回一条新的已签认判据，原判据仍为未签认、读它仍抛

### Requirement: 判据 SHALL 不得处于「有值无签认」或「有签认无值」状态
判据构造期 MUST 强制两条不变式：
- `raw_value` 非 `None` 而 `signoff` 为 `None` ⇒ 抛 `CriterionContractError`（禁止「填了数没人签」）；
- `signoff` 非 `None` 而 `raw_value` 为 `None` ⇒ 抛 `CriterionContractError`（禁止空签）。

因 `None` 在本模块内的唯一含义是「未签认」，签认结论若为「不设阈值」MUST 签成显式值（如 `False` / `{}` / 哨兵对象），MUST NOT 签成 `None`。

#### Scenario: 填了数却无签认记录被拒
- **WHEN** 构造 `Criterion(key=..., question=..., owner=..., raw_value=0.9)` 而不给 `signoff`
- **THEN** 抛 `CriterionContractError`，信息提示「要么补 Signoff、要么把值撤回 None」

#### Scenario: 签成「不设阈值」须显式
- **WHEN** 签认结论是不设限
- **THEN** 签成 `False` 等显式值可读出；签成 `None` 在构造期即被拒

### Requirement: 场景 SHALL 以注册表登记全部判据并可整体查缺
每个场景 MUST 用 `CriteriaRegistry(scenario, [Criterion, ...])` 在一处登记其全部待签认判据。

注册表 MUST 在 key 重复时抛 `CriterionContractError`（重复 key 会使后者静默盖掉前者，必有一条判据从此无人守）。

`require_all_signed()` MUST 一次性列出**全部**未签认判据（含各自 owner 与 question）后抛，MUST NOT 报第一条即停。空注册表 MUST NOT 视为「全部已签认」——`fully_signed` MUST 为 `False`，`require_all_signed()` MUST 抛。

#### Scenario: 整体查缺一次列全
- **WHEN** 场景有 2 条判据均未签认，调用 `require_all_signed()`
- **THEN** 异常信息同时含两条 key、两条 question 与其 owner

#### Scenario: 空注册表不放行
- **WHEN** 某场景注册表未声明任何判据
- **THEN** `fully_signed` 为 `False`，`require_all_signed()` 抛——「没有判据」与「判据都签完了」不是一回事

### Requirement: RULE_VERSION SHALL 与签认状态双向一致
`CriteriaRegistry.assert_rule_version(rule_version)` MUST 双向校验：
- 尚有判据未签认而版本号不含 `unsigned` 标记 ⇒ MUST 抛（骨架会被下游误当已定稿引用）；
- 判据已全部签认而版本号仍含 `unsigned` 标记 ⇒ MUST 抛（版本号在撒谎）。

本要求收拢 FI5/FI6/FI8/FI9/FI10 五份场景各自手写的 `assert "unsigned" in config.RULE_VERSION`（其中每一份都只查了前一个方向）。

#### Scenario: 版本号未自陈 unsigned
- **WHEN** 场景仍有未签认判据，`RULE_VERSION` 为 `"fi5-v1.0"`
- **THEN** 抛 `CriterionContractError`，信息列出未签认的 key

#### Scenario: 全签完了仍挂 unsigned 标记
- **WHEN** 场景判据已全部签认，`RULE_VERSION` 仍为 `"fi5-...-unsigned-..."`
- **THEN** 抛 `CriterionContractError`，提示升版

### Requirement: 底座 SHALL NOT 收入场景特有内容
`criteria_signoff` MUST NOT 包含任何具体判据名、值的形状约束、或领域文案——那是场景数据，进底座即等于底座替场景定业务口径。

本模块 MUST NOT 建模以下三类缺口（各只在五个财务场景中出现 1 次，rule-of-three 未触发，且场景包明确要求「性质各不相同、分别立牌不合并」）：数据面**权限缺口**（FI8 银行余额取数授权）、数据源**存在性未核实**（FI9 工时系统）、**前置未满足**（FI10 芯片价格 API / 队列 `#475`）。三者是否纳入 MUST 由 design 审裁定，MUST NOT 由实现方自行合并进判据模型。

#### Scenario: 场景判据名不出现在底座可执行代码
- **WHEN** 检视 `criteria_signoff` 的可执行代码
- **THEN** 不含 `TRAVEL_STANDARD_TABLE`、`BANK_BALANCE_ACCESS` 等任何场景侧标识名，且无任何按场景分支的逻辑（场景编号仅作为构造参数字符串传入，并可出现在 docstring 中用于记录来源）
