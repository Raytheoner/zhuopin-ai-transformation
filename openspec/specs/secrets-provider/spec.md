# secrets-provider Specification

## Purpose
TBD - created by archiving change platform-hardening-p2. Update Purpose after archive.
## Requirements
### Requirement: SecretsProvider Protocol 接口
平台 SHALL 提供 `SecretsProvider` Protocol（`runtime_checkable`），接口为 `get(key: str) -> str`；key 不存在时 MUST 抛 `KeyError`，不返回空字符串或 None。Protocol 位于 `shared_tools/secrets.py`，不引入外部依赖。

#### Scenario: get() 返回对应值
- **WHEN** `provider.get("XKY_APP_KEY")` 且 key 存在
- **THEN** 返回对应的字符串值，无异常

#### Scenario: get() key 不存在时抛 KeyError
- **WHEN** `provider.get("NONEXISTENT_KEY")`
- **THEN** 抛出 `KeyError`，不返回空字符串

### Requirement: EnvSecretsProvider 从环境变量读取
`EnvSecretsProvider` SHALL 实现 `SecretsProvider`，从 `os.environ` 读取；构造时可传入可选的 `override: dict[str, str]`（用于测试注入，优先于 `os.environ`）。

#### Scenario: 从环境变量读取
- **WHEN** 环境变量 `XKY_APP_KEY=test_key`，调用 `provider.get("XKY_APP_KEY")`
- **THEN** 返回 `"test_key"`

#### Scenario: override 优先于环境变量
- **WHEN** 构造时传入 `override={"XKY_APP_KEY": "override_val"}`，环境变量也设置了同名 key
- **THEN** `provider.get("XKY_APP_KEY")` 返回 `"override_val"`

### Requirement: 连接器 from_env() 接受 SecretsProvider 注入
`XkySrmConnector.from_env()` 与 `ZpConnector.from_env()` SHALL 接受可选参数 `secrets: SecretsProvider | None = None`；`None` 时降级使用 `EnvSecretsProvider()`（行为不变，向后兼容）。连接器内部读取凭证 MUST 通过注入的 `secrets.get(key)` 而非直接 `os.environ`。

#### Scenario: 默认行为不变（无注入）
- **WHEN** 调用 `XkySrmConnector.from_env()`（不传 secrets）且环境变量已设置
- **THEN** 连接器正常构造，凭证从 os.environ 读取

#### Scenario: 测试时通过 override 注入假凭证
- **WHEN** 传入 `secrets=EnvSecretsProvider(override={"XKY_APP_KEY": "fake"})`
- **THEN** 连接器使用 `"fake"` 作为 app_key，不读真实环境变量

