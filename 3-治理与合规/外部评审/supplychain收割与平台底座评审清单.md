---
status: 在办
title: "卓品智能 AI 转型项目：供应链收割与平台底座评审清单 (只读)"
---

# 卓品智能 AI 转型项目：供应链收割与平台底座评审清单 (只读)

本报告针对 `zhuopin_platform` 平台底座、`openspec` 的 platform-harvest-connectors 方案，以及 `supplychain` 收割推进策略进行了只读审计，从**架构边界**、**合规红线**、**测试质量**、**收割决策**及**真实库切换准备**五个维度进行了深度评估。

报告发现已按照**严重程度由高到低**进行了排序，并附带了具体文件与行号的指向链接。

---

## 汇总统计
* **【Blocker / 严重缺陷】**: 2 项 (涉及 L2 门禁协议漏洞与工作流空转)
* **【High / 高风险】**: 3 项 (涉及本地审计易篡改、多线程日志写损坏与回退审计缺失)
* **【Medium / 中风险】**: 2 项 (涉及平台与业务层耦合、连接器网络重试容错漏洞)
* **【Low / 低风险】**: 3 项 (涉及打包相对路径缺陷、静态类型冲突与静默降级排障困难)

---

## 评审清单（按严重度降序）

### 1. 【Blocker】L2 人工门禁协议设计漏洞：无属性默认放行风险 (合规/门禁)
* **具体位置**: 
  - [contracts.py:L16-L22](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/crm_notifier/contracts.py#L16-L22)
  - [dispatch.py:L45-L50](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/notifiers/dispatch.py#L45-L50)
* **问题描述**: 
  在 `contracts.py` 中定义的通知消息协议 `NotificationMessage` 并没有声明 `requires_confirmation` 字段。而在 `dispatch.py` 的 L2 门禁判定 `_is_high_risk` 方法中，使用了动态属性获取：
  ```python
  if getattr(message, "requires_confirmation", False):
      return True
  ```
  如果上层场景开发者实现了满足 `NotificationMessage` 契约的消息，但由于该属性不在 Protocol 强约束中而遗漏了 `requires_confirmation` 的定义，门禁会将其默认识别为 `False`。此时只要严重度不是 `critical`（例如 `warning` 级的延期通知），派发器就会**直接执行自动外发**，彻底突破 IATF 规定的 "推客户必须人工确认" 的合规红线。
* **合理化建议**: 
  1. 在 `NotificationMessage` 协议中显式声明 `requires_confirmation: bool`，使其成为静态类型检查的强约束。
  2. 秉持安全失败（Fail-Safe）原则，将门禁默认行为改为：如果未显式标记 `requires_confirmation=False`，则一律拦截并转入人工审核流程。

---

### 2. 【Blocker】L2 门禁在生产中处于“空转”状态：缺乏持久化与审批流程支持 (合规/切真实库)
* **具体位置**: 
  - [dispatch.py:L60-L62](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/notifiers/dispatch.py#L60-L62)
* **问题描述**: 
  当 `Notifier.send` 拦截了未人工确认的高风险通知时，代码仅仅是返回 `False` 并在审计日志中记录 `notification_send_blocked`，而拦截下来的**草稿数据（Draft）没有在任何地方进行持久化**（如写入数据库的待审批队列）。由于场景运行多为异步或单次脚本任务，程序结束时这些草稿会在内存中直接丢失，L2 级别的管理人员在现实中根本无法“查看草稿”、“编辑修改”或“点击确认放行”。这导致 L2 门禁机制在真切库后无法跑通完整的闭环业务。
* **合理化建议**: 
  在切换真实库前，必须引入持久化数据库模型（如 `pending_approvals`），在拦截发生时将草稿持久化存储。同时，需要构建对应的审批 API/UI 界面，供 L2 管理人员检索、编辑、审批，并通过传入 `confirmed_by="审批人姓名"` 再次触发 `send` 动作。

---

### 3. 【High】本地审计日志易篡改：难以单独满足 IATF 16949 的防篡改与不可抵赖性 (合规/审计)
* **具体位置**: 
  - [sinks.py:L19-L30](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/audit/sinks.py#L19-L30)
* **问题描述**: 
  当前 Phase 1 使用的 `JsonlSink` 只是将审计日志以明文 JSONL 追加写入本地磁盘文件。任何拥有该服务器或容器运行权限的人员均可直接编辑、伪造或删除这些日志文件。由于缺乏加密签名或防篡改机制，这不符合 IATF 16949 对系统核心决策“3年留存、可归责、不可抵赖”的强合规审计审计标准。
* **合理化建议**: 
  1. 引入轻量级防篡改机制：对每条写入的审计行计算含混淆密钥的 Hash 校验和，甚至引入 Hash 链（即当前行的 hash 包含上一行的 hash），使篡改行为极易被检测。
  2. 尽快在 9 月落地 `ClickHouseSink` 并限制其网络访问控制，通过数据库本身的 Append-Only 特性和权限管理来确保审计的不可篡改。

---

### 4. 【High】多线程并发写文件可能导致审计与调试日志损坏 (架构/测试)
* **具体位置**: 
  - [connector_audit.py:L75-L86](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/connector_audit.py#L75-L86)
  - [sinks.py:L25-L29](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/audit/sinks.py#L25-L29)
* **问题描述**: 
  `ZpConnector` 在解析 BOM 时，使用 `ThreadPoolExecutor` (默认 5 个 Worker) 并行多线程向用友 U9C 发起 BOM 查询。由于并发执行，多线程会同时写 `DebugLog` 文件（如果启用）以及 `JsonlSink` 审计文件。然而，这两个类的写操作都没有使用线程锁（`threading.Lock`）进行同步保护。在 Windows 和 Linux 下，虽然追加写入在底层文件描述符上可能表现出一定的原子性，但在 GIL 切换、缓冲区刷新或日志内容较长时，并发写入极易发生数据行穿插交叉（Interleaving），进而导致损坏的 JSONL 文件（`json.JSONDecodeError`）。
* **合理化建议**: 
  在 `JsonlSink` 和 `DebugLog` 中增加一个 `threading.Lock` 互斥锁，确保多线程执行 API 请求时的文件写操作被严格串行化。

---

### 5. 【High】ZpConnector 回退路径丢失审计日志 (架构/审计)
* **具体位置**: 
  - [connector.py:L373-L386](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py#L373-L386)
* **问题描述**: 
  在 `ZpConnector` 初始化时，它持有一个用于回退的 `self._fallback = CSVConnector(fallback_dir)`。但是，初始化时**并没有将审计器 `self._audit` 传入 fallback 连接器中**。这导致当 ZpConnector 调用 `get_production_plan()`（暂无 API，直接走 CSV 回退）或者 `get_bom()` 在没有产品数据而回退到 CSV 时，完全不会触发任何审计事件写入，使得这些离线/回退的数据访问脱离了 IATF 的留痕范围。
* **合理化建议**: 
  在 `ZpConnector.__init__` 实例化 `CSVConnector` 时，将 `audit` 参数一并传入：`self._fallback = CSVConnector(fallback_dir, audit=audit)`，从而保证回退访问也记录轻量访问痕迹。

---

### 6. 【Medium】平台层与具体业务逻辑强耦合：OEM 路由器与邮件模板硬编码 (架构边界)
* **具体位置**: 
  - [router.py:L13-L20](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/data_isolation_layer/router.py#L13-L20)
  - [draft.py:L42-L69](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/crm_notifier/draft.py#L42-L69)
* **问题描述**: 
  1. 在 `router.py` 中，支持隔离的 OEM 客户映射（`REGISTERED_OEMS`，如 "比亚迪"、"上汽"）和通用集合（`GENERAL_COLLECTIONS`，如 `kb_supplier`、`kb_quality_cases`）被硬编码写死在底座包内。如果未来新签约了 OEM 客户，或者新增了质量/财务场景的 Collection，就必须修改底层平台包的代码并重新部署。
  2. 在 `draft.py` 中，CRM 通报邮件的 LLM Prompt（`你是一家 SMT 电子制造工厂的...`）和商务逻辑判定硬编码在了平台层中。如果业务团队需要调整邮件措辞，也必须修改底座代码。这违反了“底座提供通用机制，场景定义具体策略”的分层架构原则。
* **合理化建议**: 
  1. 将 OEM 映射关系和 Collection 名录改为从全局配置文件（如 `config.yaml`）、数据库或者环境变量中读取，使 `OEMRouter` 具有动态配置的能力。
  2. 将 `crm_notifier` 的邮件 Prompt 模板以及具体 business copy 下放到 SC8 场景层中，平台层仅保留通用的 LLM 交互与 Notification 派发引擎。

---

### 7. 【Medium】连接器异常重试与容错存在未覆盖路径 (测试/切真实库)
* **具体位置**: 
  - [connector.py:L128-L145](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/srm_connector/connector.py#L128-L145) (SRM 连接器)
  - [connector.py:L179-L196](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py#L179-L196) (Zp 连接器)
  - [connector.py:L198-L220](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py#L198-L220) (BOM 查询)
* **问题描述**: 
  1. 连接器的 `_post` 机制里虽然设计了重试，但是在 `try` 块里直接执行了 `json.loads`。如果网络层面虽然通了，但网关由于故障（如 502 Bad Gateway）返回了 HTML 报错，`json.loads` 将抛出 `JSONDecodeError`。因为 `except` 仅捕获了 `URLError`，该异常会立即抛出并中断重试循环，导致 API 在面临瞬时网关抖动时无法实现真正的容错。
  2. `ZpConnector._zp_post` 的异常处理不一致：对于 `HTTPError` (如 500/503) 会捕获后立即 `raise RuntimeError`，这意味着完全不会发起重试；但对于 `URLError` (如 SSL/超时) 却能够进入重试循环。在实际切库后，如果 ERP 服务器由于瞬间拥堵抛出 503，连接器会立即崩掉。
  3. `ZpConnector._u9c_bom_post`（BOM 并行批量查询接口）完全没有任何重试和网络异常捕获机制，一旦发生微小的网络闪断就会导致整个场景崩塌。
* **合理化建议**: 
  1. 重构连接器的 `_post` 异常处理：在 try-except 中捕获 `(urllib.error.URLError, json.JSONDecodeError, http.client.IncompleteRead)` 等一系列常见网络与解析异常，保证遇到非标准 JSON 响应时也能正常重试。
  2. 保证重试逻辑在 `HTTPError` 5xx 状态码时也生效（可以排除 4xx 参数错误）。
  3. 将重试与异常处理逻辑引入到 `_u9c_bom_post` 中。

---

### 8. 【Low】相对路径硬编码缺陷：打包部署时 csv_loaders 会失效 (架构边界)
* **具体位置**: 
  - [csv_loaders.py:L24](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/csv_loaders.py#L24)
* **问题描述**: 
  `_DEFAULT_DIR` 的解析方式为 `Path(__file__).resolve().parents[2] / "tests" / "fixtures"`。如果 `zhuopin_platform` 作为一个通用的 Python 包打包成 Wheel 安装到真实的生产环境或 Docker 容器中，它的 `tests` 目录（位于打包目录外）是不会被分发的。此时，一旦在生产环境触发 CSV 回退路径且没有传入自定义路径，代码就会直接抛出 `FileNotFoundError` 导致崩溃。
* **合理化建议**: 
  1. 将脱敏的 mock CSV 夾具直接移到包命名空间内部（如 `zhuopin_platform/shared_tools/fixtures/`），并在 `pyproject.toml` 中将其配置为包数据分发。
  2. 使用 `importlib.resources` 动态寻找包内数据资源，不再依赖不安全的外部相对路径。

---

### 9. 【Low】静态类型定义冲突：AccessTrace 违反 AuditSink 契约 (架构/测试)
* **具体位置**: 
  - [sinks.py:L14-L16](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/audit/sinks.py#L14-L16)
  - [connector_audit.py:L54-L57](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/connector_audit.py#L54-L57)
* **问题描述**: 
  `AuditSink` 协议明确规定 `write` 方法必须接受 `AuditEvent` 实例：
  ```python
  class AuditSink(Protocol):
      def write(self, event: AuditEvent) -> None: ...
  ```
  而在 `ConnectorAudit` 中，注入同一个 Sink 后调用的却是 `self._sink.write(AccessTrace(...))`。虽然因为 Python 的动态特性（以及两者都有 `to_dict()` 方法）使得运行时能侥幸跑通，但在静态类型检查（如 mypy 或 Pyright 严格模式）下会报明显的类型不兼容错误。
* **合理化建议**: 
  在 `AuditSink` 协议中，将 `write` 参数放宽为支持 `AuditEvent | AccessTrace` 的联合类型（或者为它们定义一个共享的序列化 Protocol）。

---

### 10. 【Low】LLM 调用失败被静默降级：缺乏故障告警，阻碍生产排障 (测试/切真实库)
* **具体位置**: 
  - [draft.py:L145-L147](file:///c:/Users/Paul%20Shao/OneDrive/Projects/企业AI转型/5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/crm_notifier/draft.py#L145-L147)
* **问题描述**: 
  `generate_draft` 在调用 Claude API 遇到网络超时、凭证失效、速率限制等任何异常时，都会静默（Silent Catch）转而返回普通的 `template_draft`，以体现高可用。虽然保证了“不崩”，但在真实的生产环境中，这会导致 AI 生成草稿的功能无声无息地退化为呆板的模板，而运维人员/AIOps 无法从任何日志中得知 Anthropic 接口已经坏掉。
* **合理化建议**: 
  在降级的分支中加入日志报警（如 `logger.warning`）或向内部群机器人发送推送，提示 LLM 调用已失败并已启用退化模板，确保系统故障可被即时感知。

---

## 针对收割决策 D1-D6 的深度批评

* **关于 D1 (models.py 拆分)**: 
  **赞同**。把 `data_loader` 拆成平台 `models.py`（纯类型）和 `csv_loaders.py`（CSV加载）是正确做法，完美解耦了平台通用层与 SC8 业务层的关系。但是 `csv_loaders` 中对 `tests/fixtures` 的硬编码打包缺陷（见第 8 项）是目前遗留的最大技术债，应予以纠正。
* **关于 D2 (SRM 审计改版)**: 
  **中立偏批判**。移除 SQLite 本地调试库有利于简化结构，但物理上全量 req/resp 移入 debug 文件后存在**多线程写损坏风险**（见第 4 项）。此外，采购连接器在此处由于脱离了 isolation 路由，完全无法将 `oem_context` 关联到访问痕迹中，若遭遇供应商违规越权审计，追溯链条可能存在断裂。
* **关于 D3 (Protocol 解耦)**: 
  **赞同，但需防范静态安全边界崩溃**。使用 `DelayNoticeInput` 协议有效降低了平台通知层和场景层的耦合度。但由于 Protocol 遗漏了 `requires_confirmation` 关键属性，直接架空了 L2 门禁（见第 1 项）。
* **关于 D4/D5 (目录与注入模式)**: 
  **赞同**。目录分子包布局合理，方便了各连接器的后续扩展与夹具隔离。依赖注入 `AuditLogger` 在单元测试中表现良好。
* **关于 D6 (模板降级)**: 
  **批判**。直接降级且不发出报警是一个糟糕的运维设计，它掩盖了真实的 API 异常（见第 10 项）。

---

## 切真实库前必须补齐的短板 (生产发布红线)

为了系统在真正面对 ERP、SRM 和实际数据库时不会引发宕机、数据污染或合规越权，开发团队在切真实库前**至少必须补充以下五个机制**：

1. **写操作的幂等性与补偿机制（Idempotency & Compensation）**
   当 AI 自动向 ERP 下发采购订单（SC5 真实落地后）或者确认 SRM 交期时，如果遇到网络闪断，重试逻辑极易导致重复提交。必须在 API 报文中引入**幂等键（Idempotency Key，如 UUID）**，且需要编写应对写入失败时的**事务回滚或反向撤销机制**（例如在 ERP 创建订单失败时，反向清理 SRM 的占用标记）。
2. **连接器输入/输出的强 Schema 校验（Pydantic Validation）**
   目前连接器直接解析 JSON 返回结果并凭直觉做字典取值（如 `r.get("itemCode")`）。如果用友 U9C 或携客云 SRM 进行系统升级、修改了关键字段名称，或者返回了脏数据，系统会在各场景深处抛出零星的 `KeyError`/`TypeError`。在切库前，必须在连接器边界引入 **Pydantic Schema 校验层**，确保只要 API 数据流出连接器，就一定满足类型和内容的强契约。
3. **支持 L2 门禁的数据库持久化“待审批队列”与 API**
   目前的 L2 门禁拦截后，草稿在内存中被直接丢弃。必须在真实数据库中增加一个 `notification_queue` 状态机，处于 `pending_approval` 状态的消息只有被授权的 L2 责任人调用 `approve(message_id, user_name)` API 后，才会触发派发器发送。
4. **敏感凭据的安全存储与动态解密（Secrets Management）**
   虽然当前凭据使用环境变量 `.env` 隔离，但在生产环境中将 U9C/SRM 密钥以明文写在 `.env` 中具有较高的安全风险。切真实库时，生产部署必须对接公司级密钥管理系统（如 Vault、K8s Secrets 等），实现凭据的动态注入与加密传输。
5. **SRM 访问限流与并发窗口限制（Rate Limiting）**
   携客云 SRM 的 OpenAPI 有严格的**限流红线**（30秒内限制重复访问、查询跨度限制在60天内，否则抛错误码 `900301`）。虽然底座增加了 90 秒缓存，但并不能完全杜绝多实例部署时的并发超限。真实切库前必须在底座层面引入 **Client-side 令牌桶限流算法** 或限流重试退避时间。
