# Tasks — U9C 连接器收敛（u9c-connector-convergence）

> 收敛设计四点已拍板（方案 A）。design.md 待 Paul 审过再 apply。
> 工作流：先写测试再实现；保留 mock 回退；只读、凭据不进 git、审计如实标源。
> **本轮真实化范围 = 仅 BOM**（外网只开 AuthLogin+BOM/Query）；CommonEntity 类留 TODO。

## 1. 删前确认 + 抢救（护栏）
- [x] 1.1 grep 复核 `U9CConnector` 零场景 import（删前确认：仅 `test_u9c_connector.py` + 自身包；`shared_tools/__init__.py` 仅 docstring 提及，无 import）。
- [x] 1.2 U9C 实体名映射已抢救进 `5-平台底座/连接器收敛设计-ZpConnector与U9CConnector.md` 附录 A。

## 2. 删除 U9CConnector 骨架
- [x] 2.1 删 `shared_tools/u9c_connector/`（整包）。
- [x] 2.2 删 `tests/test_u9c_connector.py`（4 骨架测试）。
- [x] 2.3 全平台测试跑通无残留 import 断裂（`shared_tools/__init__.py` docstring 同步更新）。

## 3. ZpConnector 整定为唯一规范连接器（先写测试后实现）
- [x] 3.1 类/方法文档澄清职责边界 + base host-only 约定（class docstring 重写）。
- [x] 3.2 `U9C_DATA_SOURCE=mock|real`（默认 mock）+ `RealEndpointNotReadyError`；real 模式 fail-loud（`_fallback_or_failloud` 闸；`get_production_plan` 接入）。**fail-loud 有测试覆盖**（`test_u9c_data_source.py`）。
- [x] 3.3 显式 opt-in 回退（`allow_mock_fallback`/`U9C_ALLOW_MOCK_FALLBACK`）：CSV + 审计 `CSV_mock` + UserWarning（非权威）+ 测试。
- [x] 3.4 审计来源按端点分别标（Q1）：BOM→`U9C_webapi`、zp 视图→`zp_ERP`、real 降级→`CSV_mock`、mock→`CSV` + 测试。
- [x] 3.5 CommonEntity 类方法加 TODO + 解锁条件注释（get_production_plan/get_inventory/get_suppliers，引用附录 A）。

## 4. BOM 真实路径 + 集成测试
- [x] 4.1 BOM 单一来源 = `ZpConnector.get_bom_for_products`；无第二处实现（U9CConnector 已删）。
- [x] 4.2 外网 BOM 真实集成测试 `test_u9c_real_integration.py`（默认跳过，`U9C_RUN_REAL=1` + 凭据下跑）。
- [x] 4.3 ZpConnector 既有测试 + 平台全量回归不退化（116 passed）。

## 5. 配置与红线
- [x] 5.1 新建根 `.env.example`（U9C/SRM/WECOM/Anthropic 变量名，**只名字不放值** + host-only 注释）；`.env` gitignored、`.env.example` committable、无 .env 被 git 跟踪。
- [x] 5.2 凭据只从 `.env`/SecretsProvider 注入，代码零硬编码；OAuth2 无需 `U9C_API_PASSWORD`。
- [x] 5.3 SC8 回归零改动（master 20 passed；PR #8 走 get_bom_for_products 不受影响）。

## 6. 收尾
- [x] 6.1 全部测试绿：平台 116 passed + 1 skipped（真实集成 gated）；SC8 回归 20 passed 无退化。
- [ ] 6.2 archive → 开 PR，停下等 Paul 审，**先不合 master**。

---
**完成定义**：U9CConnector 已删（实体映射保全）；ZpConnector 唯一规范、含 `U9C_DATA_SOURCE` 开关 + 真实来源审计 + CommonEntity TODO；BOM 单一来源；SC8 零改动回归绿；`.env` 约定 host-only、凭据不进 git。
