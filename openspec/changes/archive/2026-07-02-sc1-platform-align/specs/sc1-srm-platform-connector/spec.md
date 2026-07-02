## ADDED Requirements

### Requirement: SRMProvider 内部改用底座 XkySrmConnector
`SRMProvider._get_connector()` SHALL 通过 `from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector` 获取连接器，不再使用 `sys.path` 操作或跨工程引用。

#### Scenario: 底座 connector 正常初始化
- **WHEN** 环境变量已配置（XKY_APP_KEY 等），调用 `SRMProvider()._get_connector()`
- **THEN** 返回 `XkySrmConnector` 实例，无 sys.path 修改

#### Scenario: 连接器初始化失败抛 RuntimeError（接口不变）
- **WHEN** 环境变量未配置，`XkySrmConnector.from_env()` 抛异常
- **THEN** `SRMProvider` 包装为 `RuntimeError("SRM 连接器初始化失败: ...")`，调用方行为不变

### Requirement: DataProvider/ManualProvider/get_delivery_data 接口不变
SC1 SHALL 保留 `DataProvider(ABC)`、`ManualProvider`、`get_delivery_data()` 函数签名不变，上层 main.py 无需修改。

#### Scenario: ManualProvider 行为等价
- **WHEN** 调用 `ManualProvider(delivery_rate=92.0).get_delivery_rate("X")`
- **THEN** 返回 `DeliveryData(rate=92.0, source="人工录入")`，与切换前完全一致

#### Scenario: get_delivery_data 回退人工时行为等价
- **WHEN** `SRMProvider` 不可用（mock 抛 RuntimeError），调用 `get_delivery_data("供应商X")`
- **THEN** 返回 `DeliveryData(rate=None, source="数据不足")`，与切换前一致

### Requirement: 无 supplychain 跨工程引用
切换后 `src/data_providers.py` SHALL 不含 `sys.path` 操作或 `from supplychain` / `from src.data` 引用。

#### Scenario: grep 无跨工程 import
- **WHEN** grep `src/data_providers.py` 中 `sys.path` 或 `supplychain`
- **THEN** 无匹配
