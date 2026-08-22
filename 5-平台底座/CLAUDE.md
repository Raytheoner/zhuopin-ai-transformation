# CLAUDE.md — `5-平台底座/`（底座目录级记忆）

> 本文件由根 `CLAUDE.md` §4「平台底座架构」与 §6.1「第三方库/API 文档查询工具」**原文原样下沉**而来（2026-08-22，`OP0822F`，A 档 A2＋A4）。正文一字未改。
> 🔴 **根 `CLAUDE.md` 里留有一行哨兵指向本文件**——哨兵被删，本文件对新会话就完全不可见。lint 校验同 `4-数字员工/CLAUDE.md` 首部说明。

## 4. 平台底座架构（zhuopin_platform）

可编辑安装的 Python 包，**一份代码处处复用**，是 IATF「单一可信源」审计的载体。各场景 `from zhuopin_platform... import`，彻底消除跨工程引用。**路径解析（队列 #300，2026-08-08 定）**：本机无 venv、多 CC worktree 共享同一套全局 `site-packages`，`pip install -e` 会把"哪份源码是权威"写成全机唯一指针，与 worktree"N 份平等副本"的前提矛盾——任一 worktree 跑一次 `pip install -e` 会把其余 worktree 的 import 静默顶替（返回值正常、测的是别人的代码）。故 `tests/conftest.py` 与服务入口脚本（`run_*.py`）顶部均已内置路径引导代码（从 `__file__` 向上找到本 worktree 的 `5-平台底座/zhuopin_platform`，插到 `sys.path` 最前），**`pip install -e` 现为可选步骤**（仅利于 IDE 自动补全/类型检查），不再是 `pytest`/服务入口能否正确 import 的前提。详见 `openspec/changes/archive/2026-08-08-worktree-import-path-bootstrap/`。

| 子系统 | 作用 | 现状 |
|--------|------|------|
| `audit/` | IATF 可追溯审计：`AuditLogger`+`AuditEvent`，JSONL 先行 / 9月 ClickHouse 汇聚（同接口切换） | ✅ 真骨架，对接它、勿重建 |
| `data_isolation_layer/` | OEM 隔离：`OEMRouter` 按客户路由、跨库抛 `CrossOEMAccessError` | ✅ 路由可用；RAG 待接 Chroma |
| `shared_tools/` | 连接器 / 通知器 / doc_parser 等共享件 | ✅ 已收割：连接器（zp/SRM/CSV）、`notifiers/`（企微 `wecom.send_markdown` + L2 `Notifier`）、`crm_notifier`；doc_parser 待质量旗舰落地 |
| `agents/` | 跨部门智能体逻辑 | 🔧 骨架 |

> **OEM 隔离边界**：只针对**研发/OEM 技术数据**（R 系列、知识库），**不针对采购的 SRM/ERP/CRM 供应商数据**。采购连接器不强加 OEM 路由；平台层把 `data_isolation_layer` 接口预留给后续研发/知识库场景即可。
> **质量域扩展（2026-06-11，Paul 认可）**：质量域 PPAP/FMEA 等 OEM 技术数据 = **硬隔离**（走 `data_isolation_layer`）；IQC/SPC 等公司自有制造数据 = **不隔离**；8D/客诉中**含特定 OEM 信息的部分按客户隔离**（RAG 检索/历史库分客户分库，比亚迪历史 8D 不进上汽检索结果）。即隔离边界从"研发技术数据"扩展到"含 OEM 信息的质量数据"，但仍不含公司自有制造/供应商数据。详见 `1-转型规划/质量域AI数字员工路线图.md`。

## 6.1 第三方库/API 文档查询工具

**集成新第三方库/API 前，先用 context7（Upstash Context7 MCP server）查最新文档。**

本项目依赖多个企业系统与第三方库（U9C / SRM / 企微 API / Chroma 向量库 / OCR 库等），版本更新频繁，官方文档可能比 AI 训练数据更新得更快。context7 可以拉取最新的 API 文档与代码示例，避免使用过时的调用方式或 breaking change。使用场景包括：
- 集成新 API 端点时查最新文档 + 官方代码示例
- 版本升级时快速定位 breaking changes（如 U9C、SRM）
- 选型对比（如 OCR 库版本性能基准）
- Chroma 向量库真正集成时查最新初始化方法与最佳实践

**使用方式**：已全局启用（`enabledPlugins:context7@claude-plugins-official`），在 Claude Code 对话框直接调用即可，如："context7，给我最新的 U9C Stock/Query API 文档"、"context7，对比 Tesseract vs PaddleOCR 最新版本"。

（于 2026-07-24 添加）

