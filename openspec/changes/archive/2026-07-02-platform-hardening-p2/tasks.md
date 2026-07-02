## 1. 基础准备

- [x] 1.1 确认 `pydantic>=2.0` 已在 `5-平台底座/zhuopin_platform/pyproject.toml` 依赖中（无则添加）
- [x] 1.2 创建 `shared_tools/secrets.py`（`SecretsProvider` Protocol + `EnvSecretsProvider`）及对应测试
- [x] 1.3 创建 `shared_tools/connector_errors.py`（`ConnectorValidationError` + `RateLimitError` 异常类）

## 2. 审计 hash-chain（audit/sinks.py）

- [x] 2.1 先写测试：`test_audit_hash_chain.py` 覆盖 genesis 首条、链接正确、多线程不断链、verify_chain 完整/删行/改行四个场景
- [x] 2.2 为 `JsonlSink` 添加 `_last_hash` 实例变量缓存 + 在锁内计算 `prev_hash` 并写入每条记录
- [x] 2.3 实现 `ChainVerifyResult` dataclass 和 `JsonlSink.verify_chain()` 方法
- [x] 2.4 为 `AuditLogger` 添加 `verify_chain()` 代理方法（非 JsonlSink sink 返回 ok=True, total=0）
- [x] 2.5 跑全部审计测试（含原有 SC1/SC8 audit chain 测试），确认全绿

## 3. SecretsProvider 凭证抽象

- [x] 3.1 先写测试：`test_secrets_provider.py` 覆盖 get 正常、key 不存在抛 KeyError、override 优先于 os.environ
- [x] 3.2 实现 `SecretsProvider` Protocol 和 `EnvSecretsProvider`（含 override 参数）
- [x] 3.3 改造 `XkySrmConnector.from_env()` 接受可选 `secrets` 参数，内部读凭证改走 `secrets.get()`
- [x] 3.4 改造 `ZpConnector.from_env()` 同上
- [x] 3.5 跑 SC1/SC8 已有测试，确认向后兼容全绿

## 4. 连接器 Pydantic 边界校验

- [x] 4.1 先写测试：`test_srm_connector_validation.py` 覆盖缺字段拦截、类型不符拦截、有效响应通过
- [x] 4.2 先写测试：`test_erp_connector_validation.py` 覆盖 PO 行缺料号拦截、BOM 行校验通过
- [x] 4.3 在 `srm_connector/connector.py` 添加 `SrmAnswerLine`、`SrmItemRow` Pydantic 模型，在解析路径加校验
- [x] 4.4 在 `erp_connector/connector.py` 添加 `ZpPurOrderRow`、`U9cBomComponent` Pydantic 模型，在解析路径加校验
- [x] 4.5 跑全部连接器测试，确认全绿

## 5. SRM 令牌桶限流退避

- [x] 5.1 先写测试：`test_srm_rate_limiting.py` 覆盖首次通过、30s 内第二次等待、多实例共享桶、900301 退避、60天跨度校验
- [x] 5.2 实现 `_TokenBucket` 类（类变量 `_buckets`，进程级 per-endpoint 桶）并集成到 `XkySrmConnector._post()`
- [x] 5.3 在 `_post()` 中对 `900301` 错误码实现指数退避（`30 * 2^(attempt-1)` 秒，最多 3 次，超限抛 `RateLimitError`）
- [x] 5.4 在 `get_receive_board()` 入口添加查询跨度 ≤60 天校验（超限抛 `ValueError`）
- [x] 5.5 跑全部 SRM 测试，确认全绿

## 6. 最终集成验证

- [x] 6.1 在平台底座目录运行全部测试（`pytest tests/ -v`），确认无回归
- [x] 6.2 在 SC8 目录运行 `pytest tests/ -v`，确认 20/20 仍全绿
- [x] 6.3 更新加固清单 `3-治理与合规/外部评审/平台底座加固待办清单.md`，P2 已完成项打勾
- [x] 6.4 git commit（分支 `feat/platform-hardening-p2`），停下报告 Paul 测试结果，等待审查合并
