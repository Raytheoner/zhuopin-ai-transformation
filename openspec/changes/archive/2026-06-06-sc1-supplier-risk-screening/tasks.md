## 1. 项目初始化

- [x] 1.1 创建项目目录结构：`src/`、`reports/`、`tests/`
- [x] 1.2 创建 `requirements.txt`，添加依赖：`anthropic`、`requests`、`python-dotenv`
- [x] 1.3 创建 `.env.example` 文件，包含 `ANTHROPIC_API_KEY` 和 SRM API 配置项模板
- [x] 1.4 创建 `config.py`，从环境变量加载 API keys 和配置参数

## 2. 评分引擎实现

- [x] 2.1 实现 `src/scoring.py`：`DeliveryScorer` 类，按准时率百分比输出 1-5 分
- [x] 2.2 实现 `IQCScorer` 类，按合格率百分比输出 1-5 分，支持缺失值默认 2.5
- [x] 2.3 实现 `FinancialScorer` 类，按注册资本+成立年限双指标均值输出 1-5 分
- [x] 2.4 实现 `SingleSourceScorer` 类，五选一枚举输入输出 1-5 分，缺失默认 1
- [x] 2.5 实现 `RiskScoringEngine` 类，接收四维度评分对象，计算加权综合分，映射风险等级（含边界值逻辑）
- [x] 2.6 为评分引擎编写单元测试，覆盖所有边界值和缺失数据场景

## 3. 数据获取层实现

- [x] 3.1 实现 `src/data_providers.py`：定义 `DataProvider` 抽象接口（`get_delivery_rate`、`get_single_source_status`）
- [x] 3.2 实现 `SRMProvider` 类，对接携客云 SRM API 获取交付准时率和采购历史（复用 supplychain 项目已有 SRM 调用逻辑）
- [x] 3.3 实现 `ManualProvider` 类，返回 CLI 录入的数据（作为 `DataProvider` 接口的人工录入实现）
- [x] 3.4 实现 SRM API 调用失败时自动回退到 `ManualProvider` 的逻辑

## 4. CLI 数据录入界面

- [x] 4.1 实现 `src/input_wizard.py`：供应商基本信息收集（名称、编码、评估人），含必填校验
- [x] 4.2 实现 IQC 合格率录入提示，含范围校验（0–100）和"数据不可用"选项
- [x] 4.3 实现财务稳定性指标录入（注册资本、成立年限），含正数校验和"未知"选项
- [x] 4.4 实现单源依赖风险五选一菜单，含默认值处理
- [x] 4.5 实现 SRM 数据展示和人工覆盖确认交互流程

## 5. AI 文本生成

- [x] 5.1 实现 `src/ai_generator.py`：调用 Claude API（`claude-sonnet-4-6`），传入结构化评分数据，生成核心风险描述（≤3条，每条≤50字）
- [x] 5.2 实现建议动作生成 Prompt，内置风险等级-建议映射规则作为系统提示约束
- [x] 5.3 实现 AI 调用失败时的降级处理，返回占位文本不阻断报告生成
- [x] 5.4 实现 AI 生成文本的 SHA-256 哈希计算，用于审计日志存储

## 6. 报告生成器

- [x] 6.1 实现 `src/report_generator.py`：按标准模板生成 Markdown 报告，包含所有必要节
- [x] 6.2 实现各维度数据来源标注逻辑（`[SRM 自动]`/`[人工录入]`/`[人工覆盖]`/`[数据不足]`）
- [x] 6.3 实现报告文件命名规则和 `reports/` 目录自动创建
- [x] 6.4 实现报告末尾审批确认区模板
- [x] 6.5 验证生成报告在浏览器中的可读性（人工检查一份样例报告）

## 7. 审计日志模块

- [x] 7.1 实现 `src/audit_log.py`：`AuditLogger` 类，`append_record()` 方法原子写入 JSON Lines
- [x] 7.2 实现审计记录结构，确认不包含注册资本和 IQC 原始数值（红色数据保护）
- [x] 7.3 实现 `query_by_supplier(name)` 方法，输出历史评估摘要
- [x] 7.4 实现 `verify_integrity()` 自检方法，统计记录数、时间跨度、异常行检测
- [x] 7.5 为审计日志编写测试：验证财务原始数据不出现在日志文件中

## 8. 主程序入口与集成

- [x] 8.1 实现 `main.py`：`evaluate` 命令，串联完整评估流程（数据获取 → 评分 → AI 文本 → 报告 → 日志）
- [x] 8.2 实现 `main.py`：`query` 命令，按供应商名称查询审计日志历史
- [x] 8.3 实现 `main.py`：`verify` 命令，执行审计日志完整性自检
- [x] 8.4 添加 `--help` 文档，说明各命令用法

## 9. 端到端验证

- [ ] 9.1 用真实 SRM 数据（1 家已有历史的供应商）完整跑通评估流程，验证报告内容正确
- [x] 9.2 模拟 SRM API 不可用场景，验证回退到人工录入流程正常工作
- [x] 9.3 验证审计日志写入正确，且不含原始财务数值
- [x] 9.4 验证 `verify` 命令在正常日志和含损坏记录日志两种情况下的输出
- [x] 9.5 生成至少 3 份不同风险等级的样例报告，供采购经理审阅确认格式符合需求
