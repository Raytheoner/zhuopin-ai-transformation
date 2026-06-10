## 1. 基础准备

- [x] 1.1 新建 git 分支 feat/sc1-platform-align
- [x] 1.2 安装底座：`pip install -e ../../../5-平台底座/zhuopin_platform`；验证 import zhuopin_platform.audit 可用
- [x] 1.3 新建 `pyproject.toml`（声明 `zhuopin_platform` 依赖），确认 SC1 可作为独立包安装

## 2. 先写/更新测试（SuperPowers 先测后实现）

- [x] 2.1 更新 `tests/test_audit_log.py`：断言适配平台 JSON 格式（`record["decision"]["supplier_name"]` 等），保留红数据保护测试，新增 `verify_chain()` 3 条记录通过 + 篡改后失败两个场景
- [x] 2.2 新建 `tests/test_srm_platform.py`：ManualProvider 接口等价、get_delivery_data 回退行为等价、SRMProvider mock 底座 connector 正常调用、无 sys.path 残留
- [x] 2.3 确认 `tests/test_scoring.py` 已有测试全绿（基线，不改）

## 3. 实现审计切底座（audit_log.py 重写）

- [x] 3.1 重写 `src/audit_log.py`：删除本地 AuditLogger 主体 JSON 写入逻辑，实现 `SC1AuditAdapter` 薄包装（`append_record()` 签名不变，内部建 `AuditEvent(scenario="SC1", ...)`，委托平台 `AuditLogger.record()`）
- [x] 3.2 实现 `verify_chain()`（委托平台）、`query_by_supplier()`（委托 `query_by()`，映射返回格式）、`verify_integrity()`（委托平台 + 补齐兼容字段）
- [x] 3.3 跑 `tests/test_audit_log.py`，确认全绿（9/9）

## 4. 实现 SRM 连接器切底座（data_providers.py 手术）

- [x] 4.1 修改 `SRMProvider._get_connector()`：删除 `sys.path` 操作和跨工程 import，改为 `from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector`
- [x] 4.2 跑 `tests/test_srm_platform.py`，确认全绿（12/12）

## 5. 更新调用侧与集成验证

- [x] 5.1 更新 `main.py`：`from src.audit_log import AuditLogger` → `from src.audit_log import SC1AuditAdapter as AuditLogger`（一行改动，调用侧不变）
- [x] 5.2 跑全部测试 `pytest tests/ -v`，确认全绿（50/50：9+29+12）
- [x] 5.3 grep 验证：`src/audit_log.py` 无 `json.dumps` 写入；`src/data_providers.py` 无 `sys.path` 和 `supplychain`

## 6. 收尾

- [x] 6.1 git commit（feat/sc1-platform-align 分支）8fd73fb
- [x] 6.2 停下报告 Paul 测试结果（测试数/等价对照结论/残留检查），等待审查合并
