## Context

平台底座（`zhuopin_platform`）已在 SC8 MVP 中验证可用，但在切真实库之前，Antigravity 评审发现 4 项 P2 加固缺口：审计可篡改（#3）、连接器无边界校验（切库红线②）、SRM 无限流退避（切库红线⑤）、凭证无抽象（切库红线④）。本设计文件描述四项改动的技术方案，须与现有 SC1/SC8 接口完全向后兼容，全程 mock 测试，不连真实库。

## Goals / Non-Goals

**Goals:**
- `JsonlSink` hash-chaining：每条 JSONL 行含 `prev_hash` 字段（前一条的 SHA-256），`verify_chain()` 可检测任意行被删除/篡改。
- `XkySrmConnector` 进程级令牌桶：每个 endpoint 共享一把令牌桶（1 token/30s），`_post()` 在发请求前消耗令牌，满了则等待；900301 错误额外触发指数退避（base 30s，上限 3 次）。
- 连接器 Pydantic 边界校验：SRM 响应（`lineList` 行 / `itemList` 行）和 zp ERP 响应（PO 行 / BOM component 行）经 Pydantic 模型解析，`ValidationError` 转换为 `ConnectorValidationError`（带 source、field、raw 上下文）。
- `SecretsProvider` Protocol：`get(key: str) -> str`，`EnvSecretsProvider` 从 `os.environ` 读；`ZpConnector`/`XkySrmConnector` 的 `from_env()` 新增可选 `secrets: SecretsProvider = None` 参数，默认行为不变。

**Non-Goals:**
- Vault / K8s Secrets 真实实现（Protocol 预留，实现留给 Phase 2 凭证管理专项）。
- ClickHouseSink hash-chain（9 月再叠加，当前只改 JsonlSink）。
- SRM 多进程/多机器限流（令牌桶仅进程级；跨进程协调留 Redis/分布式锁，Phase 2）。
- `_u9c_bom_post` 重试容错（P2-#7，本 PR 不含，另开任务）。
- P3-#9 完整联合类型修复（本次只修 `ConnectorAudit.trace()` 的直接写入路径）。

## Decisions

### D1：hash-chain 算法 — SHA-256 over 磁盘原始行字节（Paul 修订）

`prev_hash = sha256(raw_line_bytes_on_disk)`：对**实际写入磁盘的原始字节行**（含末尾 `\n`）做 SHA-256 十六进制摘要，不重新序列化。第一条 `prev_hash = ""`（genesis）。

**理由（修订）**：哈希磁盘原始行而非重算 canonical form，`verify_chain()` 直接对每行原始字节重算哈希与 `prev_hash` 字段比对，避免重序列化时 JSON key 顺序、Unicode 转义、浮点精度等细节导致的误报——磁盘上存什么就哈希什么，无二义性。

**关键推论**：`_last_hash` 保存的是"上一条**已写入磁盘的原始行字节**的 SHA-256"，写入流程：① 构造 event dict（插入 `prev_hash`）→ ② `json.dumps(..., ensure_ascii=False)` 得到 line_str → ③ `line_bytes = (line_str + "\n").encode("utf-8")` → ④ 写入文件 → ⑤ `_last_hash = sha256(line_bytes)`。

**测试要求**：补"key 乱序插入 event dict"测试 —— 即使写入前 dict 键顺序不同，`verify_chain()` 应仍通过（因为哈希对象是落盘后的固定字节，不依赖 key 排序）。

**备选**：HMAC-SHA256（Phase 2 再叠加，当前不需防读者伪造整链）。

### D2：_last_hash 为类级路径字典（Paul 修订）

`_last_hash` 改为**类变量** `_last_hashes: dict[str, str] = {}`，key = `str(log_path.resolve())`，与 `_locks` 完全对称。两个 `JsonlSink` 实例指向同一文件时共享同一个 hash 游标，交替写不断链。

`write()` 流程：在 `self._lock` 内 → 取 `prev = JsonlSink._last_hashes.get(key, None)` → `None` 时读文件末尾最后一行（`_read_last_line()`）计算初始哈希（文件不存在则 `""`）→ 写入 → 更新 `JsonlSink._last_hashes[key]`。

**测试要求**：补"双实例同文件交替写"测试 —— 两个 `JsonlSink(same_path)` 实例交替各写 3 条，最终 `verify_chain()` 返回 `ok=True, total=6`。

### D3：令牌桶 — 进程级类变量，每 endpoint 一把桶

`XkySrmConnector` 类变量 `_buckets: dict[str, _TokenBucket]`，key = path（如 `/purchase/answer.json`）。`_TokenBucket(rate=1/30, capacity=1)` 令牌漏斗，`consume()` 若无令牌则 `time.sleep()` 至下一令牌可用。

**理由**：进程级共享符合"同账号 30s 不重复"的 SRM 限制（单进程内多实例共享同一账号）；不需要外部状态。多进程并发是 Phase 2 问题。

**900301 退避**：900301 触发时在当前重试逻辑之上额外 sleep `30 * 2^(attempt-1)` 秒（最多 3 次），不静默丢失。

### D4：Pydantic 校验 — 只校验连接器输入/输出边界，不侵入 dataclass

SRM/zp 响应的每个"行"对象用 `class SrmAnswerLine(BaseModel)`、`class ZpPurOrderRow(BaseModel)` 等校验，校验通过后手动构造内部 `SrmDeliveryOrder`/`PurchaseOrder` dataclass。`ValidationError` 捕获后抛 `ConnectorValidationError(source, field, raw)`。

**理由**：内部 dataclass 是平台契约（SC1/SC8 已用），不能改为 Pydantic 模型（会破坏现有测试夹具的构造方式）；只在边界加一层校验，不侵入平台契约。

**备选**：把 dataclass 全换成 Pydantic BaseModel——破坏契约，不选。

### D5：SecretsProvider 放位置 — `shared_tools/secrets.py`，不新建子包

Protocol + `EnvSecretsProvider` 共放 `shared_tools/secrets.py`，`from zhuopin_platform.shared_tools.secrets import SecretsProvider, EnvSecretsProvider`。连接器 `from_env()` 加 `secrets: SecretsProvider | None = None` 参数，`None` 时降级 `os.environ`，向后兼容。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| hash-chain 读最后一行有 I/O 开销 | `_last_hash` 实例变量缓存，只在初次写时读文件末尾 |
| 令牌桶 `time.sleep()` 阻塞调用线程 | 仅在 SRM 调用路径；BOM 并行查询走 zp ERP，不共享此桶 |
| Pydantic 模型与真实 API 字段不同步 | 字段标注 `Optional` 为主，仅 must-have 字段标 required；`ValidationError` 含 `raw` 上下文便于调试 |
| `verify_chain()` 无法追溯历史文件（旧记录无 prev_hash） | 旧文件 genesis 处理：首条无 `prev_hash` 字段视为合法 genesis，`verify_chain()` 从首条有 `prev_hash` 的记录开始验证 |

## Migration Plan

1. 改动纯在平台底座；SC1/SC8 无需修改（向后兼容）。
2. 旧 JSONL 审计文件：`verify_chain()` 遇无 `prev_hash` 字段的记录视为 genesis，向前兼容。
3. 连接器 `from_env()` 新参数 `secrets` 默认 `None`（降级 `os.environ`），存量调用不变。
4. 所有改动先合入 `feat/platform-hardening-p2`，全部测试绿 → Paul 审 → 合并 master，SC8 真实切换分支基于此 master。

## Open Questions

| 问题 | 建议 |
|------|------|
| SRM 令牌桶是否需要支持多进程（AIOps 后台 + 定时任务并发）？ | MVP 先进程级；Phase 2 再接 Redis 分布式令牌桶，接口不变 |
| Pydantic 是否已在 pyproject.toml 依赖？ | 需确认；若无则加入 `[project.dependencies]`（>=2.0） |
| `verify_chain()` 失败时是否触发企微告警？ | 本次只返回 `ChainVerifyResult`，告警由调用方（AIOps 定时任务）负责；Phase 2 |
