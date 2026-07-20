---
status: 生效
title: "Claude Code 自学路径 × 卓品智能 AI 转型技术方案"
---

# Claude Code 自学路径 × 卓品智能 AI 转型技术方案

> **适用人：** Paul（卓品智能运营 VP，资深软件工程背景，已完成 supplychain 小型项目）
> **目标：** 系统掌握 Claude Code 全功能，并将其作为建设公司 AI 全景的主要工程工具
> **时间估算：** 自学约 12-15 小时（可分 3-4 个周末），随后结合公司项目边学边建

---

## 一、整体思路：学习与建设并行

你不是在为了学而学，而是要**边学边建公司的 AI 体系**。因此本教程将每个学习模块直接对应卓品智能的一个落地场景：

| 学习阶段 | Claude Code 功能 | 对应公司场景 |
|---------|----------------|------------|
| 第1周末 | CLI + Memory + Slash Commands | 供应链项目优化，建立公司级 CLAUDE.md |
| 第2周末 | Skills + Subagents | 第一个数字员工：供应商风险初筛 (SC1) |
| 第3周末 | MCP 协议 | 接通 ERP/SRM 只读接口 |
| 第4周末 | Hooks + Advanced + Plugins | 自动化流水线 + 部门级插件打包 |

---

## 二、第一部分：Claude Code 系统自学路径

### 前置确认（30分钟）

在开始学习之前，先确认你的环境已就绪：

```bash
# 确认 Claude Code 已安装并登录
claude --version        # 应显示 2.1+
claude "hello"          # 测试基本对话

# 进入你已有的 supplychain 项目
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain
claude "用一句话描述这个项目的主要功能"

# 进入 claude-howto 学习项目
cd C:\Users\Paul Shao\OneDrive\Projects\claude-howto
```

**你的起点判断**：已完成 supplychain 项目 → 属于 Intermediate 级别，从模块 3 开始可加速。

---

### 模块 1：CLI 基础与模式切换（30分钟）

**学习文件**：`10-cli/README.md`

这是你在 CI/CD 脚本和自动化流水线中最常用的功能。

#### 核心命令速查

```bash
# 交互模式（最常用）
claude                              # 进入对话

# 非交互（脚本化，用于自动化）
claude -p "分析这个文件的风险"       # 打印模式，输出后退出
cat supplier_data.csv | claude -p "识别高风险供应商"

# JSON 输出（用于程序处理）
claude -p --output-format json "提取供应商名称和评分"

# 恢复/管理会话
claude -c                          # 继续上次会话
claude -r "session-name" "继续"    # 按名称恢复
```

#### 实操练习（在 supplychain 项目中执行）

```bash
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain

# 练习 1：非交互分析
claude -p "列出这个项目目前缺少什么功能，按优先级排"

# 练习 2：管道处理
ls -la | claude -p "哪些文件最近修改过？可能是数据文件？"

# 练习 3：JSON 输出
claude -p --output-format json "这个项目用了哪些技术栈？"
```

**关键收获**：`-p` 是你日后写自动化脚本的核心标志。

---

### 模块 2：Memory — 让 Claude 记住你的公司（45分钟）

**学习文件**：`02-memory/` 目录，重点看 `project-CLAUDE.md` 和 `personal-CLAUDE.md`

Memory 是 Claude Code 最被低估的功能。正确配置后，Claude 永远知道你是谁、你的项目是什么、你的代码规范是什么——**无需在每次对话中重复解释**。

#### Memory 的三个层级

```
~/.claude/CLAUDE.md              # 个人全局记忆（你的偏好、背景）
/项目根目录/CLAUDE.md             # 项目记忆（团队规范、架构）
/子目录/CLAUDE.md                 # 子模块记忆（该目录特定规则）
```

#### 实操：建立卓品智能个人记忆

```bash
# 创建个人全局记忆（一次设置，永久生效）
# Windows 路径：C:\Users\Paul Shao\.claude\CLAUDE.md
```

在 `~/.claude/CLAUDE.md` 中写入（用 Claude Code 在对话中直接让它帮你生成）：

```markdown
# 个人偏好

## 我的背景
- 卓品智能运营VP，分管供应链
- 资深软件工程背景，20年前做过嵌入式 C 开发
- 现在主要做工程管理和运营决策，需要清晰的技术文档

## 工作语言偏好
- 技术讨论优先用中文
- 代码注释用英文
- 文档输出：中文主体，关键术语保留英文

## 回答风格偏好
- 直接给结论，不要过多铺垫
- 复杂步骤用编号列表
- 代码示例要完整可运行
- 给我工程师视角的解释，不用从零开始讲基础
```

#### 实操：建立 supplychain 项目记忆

```bash
# 进入项目，创建 CLAUDE.md
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain
```

在项目根目录创建 `CLAUDE.md`（让 Claude 帮你分析项目后自动生成）：

```bash
# 在 Claude Code 交互模式中
claude
> 分析这个项目的技术栈、主要功能和代码结构，
> 然后帮我生成一个 CLAUDE.md 文件，让未来的 Claude 会话
> 立刻理解这个项目的上下文
```

**验证效果**：

```bash
# 新开一个会话，什么都不说，直接问
claude "这个项目的核心预测逻辑在哪个文件？"
# 如果 Memory 正确，Claude 应该直接定位，而不是说"请先介绍项目"
```

---

### 模块 3：Slash Commands — 你的专属快捷指令（30分钟）

**学习文件**：`01-slash-commands/` 目录

Slash Commands 是你在日常工作中最频繁使用的入口。一行 `/命令` 触发复杂的多步任务。

#### 安装 claude-howto 示例命令

```bash
# 在 supplychain 项目中安装
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain
mkdir -p .claude\commands

# 复制示例命令
cp C:\Users\Paul Shao\OneDrive\Projects\claude-howto\01-slash-commands\*.md .claude\commands\
```

#### 立刻尝试

```bash
claude
> /optimize         # 代码优化分析
> /pr               # 准备 PR 描述
> /generate-api-docs # 生成 API 文档
```

#### 实操：为卓品智能创建第一个业务命令

创建 `.claude/commands/supplier-risk.md`：

```markdown
---
description: 快速评估一个供应商的风险等级
---

# 供应商风险快速评估

分析以下供应商信息，输出风险评分（1-5级）和关键风险点：

供应商信息：$ARGUMENTS

评估维度：
1. 财务稳定性（注册资本、成立年限）
2. 历史交付准时率
3. 质量合格率趋势
4. 单源依赖风险
5. 地理/政治风险

输出格式：
- 综合评分：X/5
- 主要风险（≤3条）
- 建议跟进动作
```

使用方式：

```
/supplier-risk 供应商名称：XX电子, 注册资本：500万, 交付准时率：85%, 主营：电阻电容
```

---

### 模块 4：Checkpoints — 安全实验的保障（30分钟）

**学习文件**：`08-checkpoints/README.md`

这个功能特别适合你这样的工程管理背景——在做大型重构或复杂实验时，随时可以回滚。

#### 核心操作

```
# 在 Claude Code 对话中：
# 每次你发消息，系统自动创建 checkpoint

# 回退到上一个状态：
按 Esc 两次   →   出现 Rewind 菜单

# 5个选项：
1. Restore code and conversation  （代码 + 对话都回退）
2. Restore conversation only      （只回退对话）
3. Restore code only              （只回退代码）
4. Summarize from here            （从这里生成摘要）
5. Never mind                     （取消）
```

#### 实战使用场景

```bash
# 场景：你想让 Claude 重构 supplychain 的预测模块，但不确定结果
claude
> 帮我重构预测模块，改用更精确的算法

# 如果结果不满意 → 按 Esc Esc → 选 1 → 完全回到重构前
# 然后换一个思路重试
> 改用时序分析方法重构预测模块
```

**关键认知**：Checkpoints 让你可以大胆让 Claude 做实验，失败了不怕。

---

### 模块 5：Skills — 构建可复用的"数字员工能力"（1小时）

**学习文件**：`03-skills/` 目录（重点看 `code-review/SKILL.md`）

Skills 是 Claude Code 的核心差异化功能，也是你构建"数字员工"的基本单元。一个 Skill = 一个可被自动触发的专项能力。

#### Skill 的结构

```
~/.claude/skills/
└── supplier-risk-screener/        ← Skill 名称
    ├── SKILL.md                   ← 核心：Skill 的触发条件和行为
    ├── scripts/                   ← 可选：辅助脚本
    └── templates/                 ← 可选：输出模板
```

#### 安装示例 Skills

```bash
# 安装 code-review skill
cp -r C:\Users\Paul Shao\OneDrive\Projects\claude-howto\03-skills\code-review %USERPROFILE%\.claude\skills\
```

#### 实操：创建卓品第一个数字员工 Skill

创建 `%USERPROFILE%\.claude\skills\supplier-risk-screener\SKILL.md`：

```markdown
---
name: supplier-risk-screener
description: 供应商风险初筛数字员工。当用户提供供应商名称、询问供应商风险、
             或粘贴供应商数据时自动触发。输出标准化风险评估报告。
version: 1.0
author: 卓品智能 AIOps
---

# 供应商风险初筛 Skill

## 触发条件
- 用户提到供应商名称 + 评估/风险/审查等词
- 用户粘贴包含供应商数据的表格
- 用户执行 /supplier-risk 命令

## 执行流程

### 第一步：数据采集
提取以下信息（用户提供 + 系统查询）：
- 基础信息：名称、注册资本、成立年限、主营业务
- 交付数据：近12个月准时率、近期延迟记录
- 质量数据：IQC 合格率、近期不良记录
- 外部信号：是否有公开负面新闻

### 第二步：评分计算
| 维度 | 权重 | 评分说明 |
|-----|-----|---------|
| 交付准时率 | 35% | >95%=5分, 90-95%=4分, 85-90%=3分, <85%=1分 |
| 质量合格率 | 30% | >99%=5分, 97-99%=4分, 95-97%=3分, <95%=1分 |
| 财务稳定性 | 20% | 注册资本、年限综合判断 |
| 单源风险 | 15% | 是否有替代供应商 |

### 第三步：输出报告
格式如下：

**供应商风险评估报告**
- 评估对象：[名称]
- 综合风险等级：[1-5级，1=极低风险，5=极高风险]
- 评分详情：[各维度得分]
- 核心风险：[≤3条具体风险描述]
- 建议动作：[分级处理建议]
- 数据来源：[说明数据可靠性]
- 评估时间：[timestamp]

## 合规说明
- 本评估为辅助决策，最终采购决策需采购经理人工确认
- 评估结果自动记录至审计日志（满足 IATF 16949 追溯要求）
```

**验证**：

```bash
claude
> 帮我评估一下 XX半导体，注册资本2000万，成立8年，
> 最近12个月交付准时率91%，IQC 合格率97.5%，是我们MCU的唯一供应商
# Skill 应自动触发，输出标准格式报告
```

---

### 模块 6：Subagents — 让专家团队协作完成复杂任务（1.5小时）

**学习文件**：`04-subagents/` 目录

Subagents 是多智能体架构的基础，对应你规划中的"跨部门 Agent 协同"。

#### Subagent vs Skill 的区别

| | Skill | Subagent |
|--|-------|---------|
| **触发方式** | 自动检测，轻量 | 主 Agent 主动委派 |
| **上下文** | 共享主上下文 | 独立隔离上下文 |
| **适用场景** | 单一专项任务 | 复杂多步、需要专业深度 |
| **对应公司场景** | 供应商评分、报告生成 | 合同全文审核、跨部门协同 |

#### 安装示例 Subagents

```bash
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain
mkdir -p .claude\agents

copy C:\Users\Paul Shao\OneDrive\Projects\claude-howto\04-subagents\code-reviewer.md .claude\agents\
copy C:\Users\Paul Shao\OneDrive\Projects\claude-howto\04-subagents\test-engineer.md .claude\agents\
```

#### 实操：创建卓品供应链专属 Subagent

创建 `.claude/agents/contract-reviewer.md`：

```markdown
---
name: contract-reviewer
description: 采购合同专项审核 Agent。负责解析采购合同 PDF/Word，提取关键条款，
             与公司标准条款库对比，识别风险偏差。
tools: Read, Bash, Write
---

# 采购合同审核专家

你是卓品智能的采购合同审核专家，具备汽车电子行业采购合同审核经验。

## 你的职责
对采购合同进行系统化审核，重点检查：

1. **交付条款**：交期、提前期、延迟罚则是否合理
2. **质量条款**：PPM 目标、IQC 标准、不合格品处理流程
3. **IATF 合规条款**：是否包含可追溯性要求、变更通知义务
4. **价格保护**：价格锁定期、涨价条款、汇率条款
5. **风险分担**：不可抗力、单源替代、缺货责任

## 审核流程
1. 读取合同文件，提取关键条款
2. 与公司标准条款逐项对比
3. 识别缺失条款和偏差项
4. 输出审核报告（通过/有条件通过/退回）

## 输出格式
**合同审核报告**
- 合同方：[供应商名称]
- 审核结论：通过 / 有条件通过（X条待改） / 退回（Y条必改）
- 偏差条款：[逐条列出]
- 缺失条款：[列出缺失的必要条款]
- 风险评级：低/中/高
- 建议：[具体修改建议]

## 合规边界
- 审核结论为建议性意见，需法务/采购经理最终确认签字
- 完整审核记录保存供 IATF 审核追溯
```

#### 测试多 Agent 协作

```bash
claude
> 我有一份采购合同需要全面评估，既要审核合同条款，
> 也要同时评估这个供应商的风险等级，给我一份综合报告
# 主 Agent 会自动调用 contract-reviewer + supplier-risk-screener
```

---

### 模块 7：MCP 协议 — 打通企业系统（1小时）

**学习文件**：`05-mcp/` 目录

MCP（Model Context Protocol）是你接通 ERP/SRM/CRM/WMS 的关键。这是技术含量最高的模块，但对你 ECU 工程背景来说不难。

#### MCP 的本质

```
Claude Code  ←→  MCP Server  ←→  外部系统
                               （ERP/数据库/API）
```

MCP Server 是一个轻量级进程（Node.js 或 Python），它暴露一组工具，Claude 可以调用。

#### 第一步：用现有 MCP 上手

```bash
# 安装文件系统 MCP（最简单，无需配置）
claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem C:\Users\Paul\Documents

# 测试
claude
> 列出我文档目录下最近的文件
```

#### 第二步：理解 MCP 配置格式

参考 `05-mcp/database-mcp.json` 的结构：

```json
{
  "mcpServers": {
    "erp-readonly": {
      "command": "python",
      "args": ["-m", "erp_mcp_server"],
      "env": {
        "ERP_DB_HOST": "192.168.1.100",
        "ERP_DB_PORT": "5432",
        "ERP_DB_USER": "ai_readonly",
        "ERP_DB_PASS": "${ERP_READ_TOKEN}"
      }
    }
  }
}
```

#### 第三步：规划卓品的 MCP 接入架构

```
未来 6 个月 MCP 接入优先级：

P1（7-8月，基建期）：
  ├── ERP 只读接口（采购主数据、PO、交货记录）
  ├── 文件系统（供应商文档、合同库）
  └── 本地向量数据库（Chroma）

P2（9-10月）：
  ├── SRM 供应商管理数据
  ├── WMS 库存数据
  └── 外部征信 API

P3（11月+）：
  ├── CRM 客户数据
  ├── MES 生产数据
  └── 银行流水 API（财务部）
```

---

### 模块 8：Hooks — 自动化与合规守护（1小时）

**学习文件**：`06-hooks/` 目录

Hooks 对你特别重要——IATF 16949 要求 AI 辅助决策必须有完整审计轨迹，Hooks 就是实现这个的工具。

#### 4类 Hook 事件

```
PreToolUse    → Claude 使用工具前触发（可以拦截）
PostToolUse   → Claude 使用工具后触发（记录日志）
SessionStart  → 会话开始
UserPromptSubmit → 用户提交消息时
```

#### 关键实践：IATF 审计日志 Hook

```bash
# 创建审计日志 hook
mkdir -p %USERPROFILE%\.claude\hooks
```

创建 `%USERPROFILE%\.claude\hooks\audit-log.sh`（Windows 用 .ps1）：

```powershell
# audit-log.ps1
# 记录所有 AI 辅助决策，满足 IATF 16949 追溯要求

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logDir = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\audit-logs"
$logFile = "$logDir\$(Get-Date -Format 'yyyy-MM').jsonl"

# 从环境变量读取 Hook 上下文
$event = @{
    timestamp = $timestamp
    event_type = $env:CLAUDE_HOOK_EVENT
    tool_name = $env:CLAUDE_TOOL_NAME
    session_id = $env:CLAUDE_SESSION_ID
    user = $env:USERNAME
}

# 追加写入日志（append-only，满足审计要求）
$event | ConvertTo-Json -Compress | Add-Content -Path $logFile
```

在 `~/.claude/settings.json` 中配置：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "powershell -File ~/.claude/hooks/audit-log.ps1"
          }
        ]
      }
    ]
  }
}
```

#### 安装学习示例 Hooks

```bash
# 参考 claude-howto 的 hook 示例
# 建议先看懂以下文件：
# 06-hooks/security-scan.sh   → 安全扫描的逻辑
# 06-hooks/log-bash.sh        → 命令日志
# 06-hooks/notify-team.sh     → 团队通知
```

---

### 模块 9：Advanced Features — 掌控复杂任务（2小时）

**学习文件**：`09-advanced-features/`

#### Planning Mode（最重要）

复杂任务在执行前先做规划，避免走弯路：

```bash
claude
> 我需要为采购部建立完整的供应商风险管理系统，
> 请先给我一个详细的实施计划，不要开始编码

# Claude 进入 Plan Mode，输出详细步骤后等待确认
# 你审查计划 → 调整 → 确认后才开始执行
```

#### Extended Thinking（深度推理）

```
# 在 Claude Code 中按 Alt+T（Windows）或 Option+T（Mac）
# 触发扩展思考模式

# 适用场景：
# - 设计复杂的多Agent架构
# - 分析供应链风险的根因
# - 评估不同技术方案的权衡
```

#### Background Tasks（长任务不阻塞）

```bash
# 适合长时间运行的任务，如批量处理供应商数据
claude
> 在后台分析我们 ERP 中过去 2 年所有供应商的交付记录，
> 生成风险趋势报告，完成后通知我
```

#### Permission Modes

```bash
claude --permission-mode acceptEdits    # 自动接受文件修改（谨慎用）
claude --permission-mode plan           # 只规划不执行
claude -p "批量处理" --dangerously-skip-permissions  # 完全自动化（CI 场景）
```

---

### 模块 10：Plugins — 将成果打包分发（2小时）

**学习文件**：`07-plugins/`

Plugins 是你向公司其他部门分发 AI 能力的方式。一个 Plugin = 完整的部门数字员工工具包（Commands + Agents + Skills + MCP 配置）。

#### Plugin 结构

```
供应链-数字员工/          ← Plugin 包
├── .claude/
│   ├── commands/         ← 该部门的快捷命令
│   ├── agents/           ← 专属 Agent 定义
│   └── skills/           ← 专属 Skill
├── .mcp.json             ← 该部门的 MCP 接入配置
├── CLAUDE.md             ← 该部门的工作上下文
└── README.md             ← 使用说明
```

**终极目标**：为采购部打包 `procurement-digital-team.plugin`，安装一个命令搞定所有配置。

---

### 自测清单

完成全部模块后，用以下场景测试你是否真正掌握：

- [ ] **L1**：`/supplier-risk XX供应商 注册资本500万 准时率85%` → 自动输出风险报告
- [ ] **L2**：粘贴一份合同文本 → `contract-reviewer` 自动审核并输出偏差报告
- [ ] **L3**：`claude -p "分析本周到货记录，找出异常" < erp_export.csv` → 脚本化运行
- [ ] **L4**：一个 Agent 发现供应商风险 → 自动触发另一个 Agent 检查 FMEA → 生成联动报告
- [ ] **L5**：为采购部打包一个完整 Plugin，IT 同事一键安装即可使用

---

## 三、第二部分：卓品智能 AI 全景技术架构方案

> 基于规划文件（更新于 2026-06-05）和 Claude Code 能力体系，给出从 supplychain 项目扩展到企业 AI 全景的工程路径。

### 核心架构：Hermes 记忆体系 × SuperPowers 建造方法论

两者是垂直分工，不是并列层级：

- **SuperPowers**（建造层）：OpenSpec 管需求 + Claude Code 管执行，负责高质量开发每一个数字员工
- **Hermes 四层记忆架构**（运营层）：让数字员工上线后越用越聪明，通过分层记忆实现自我进化

```
┌─────────────────────────────────────────────────────────┐
│                   卓品智能 AI 全景架构                    │
│                                                         │
│  ┌──── SuperPowers 建造层（开发期使用）───────────────┐  │
│  │  OpenSpec 需求规格 → Claude Code 开发执行          │  │
│  │  brainstorming → writing-plans → subagent-dev     │  │
│  │  test-driven-development → requesting-code-review  │  │
│  └────────────────────────────────────────────────────┘  │
│                         ↓ 上线                           │
│  ┌──── Hermes 四层记忆（运营期自动运行）──────────────┐  │
│  │  L1: CLAUDE.md 冻结快照（稳态事实，保证缓存命中）  │  │
│  │  L2: Auto Memory（SQLite，自动记录新场景和异常）   │  │
│  │  L3: Memory Flush（上下文压缩前自动沉淀关键事实）  │  │
│  │  L4: Skills 程序性记忆（SuperPowers skills + 自建）│  │
│  └────────────────────────────────────────────────────┘  │
│                         ↓ 学习反馈                       │
│  ┌──── MCP 系统集成层 ────────────────────────────────┐  │
│  │  SRM MCP（已接通）│ ERP MCP │ CRM MCP │ WMS MCP   │  │
│  │  Chroma 向量DB    │ 外部征信API │ 审计日志          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──── 合规约束层（贯穿所有层）──────────────────────┐  │
│  │  OEM客户数据隔离  │  IATF审计轨迹  │  ISO26262边界  │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

### 从 supplychain 项目起步的扩展路径

你已有的 supplychain 项目是最好的起点，按以下路径扩展：

```
现有 supplychain 项目
        ↓
Step 1（7月）：加 CLAUDE.md + Audit Hook → 变成"合规可追溯"的版本
        ↓
Step 2（7月）：加 SC1 供应商风险 Skill → 第一个数字员工上线
        ↓
Step 3（8月）：加 ERP MCP 接口 → 从真实数据驱动
        ↓
Step 4（9月）：加更多 Agents → 扩展成采购部完整数字团队
        ↓
Step 5（10月+）：打包成 Plugin → 复制到财务、质量、销售部门
```

---

### 七月启动：具体工程任务清单

以下是 2026年7月的具体编码任务（Paul 主导 + AIOps 配合）：

#### 第 1-2 周：数据基建

```bash
# 任务 1：supplychain 项目升级为企业基础项目
cd C:\Users\Paul Shao\OneDrive\Projects\supplychain

# 1.1 建立完整的 CLAUDE.md（项目、合规约束）
# 1.2 部署 IATF 审计日志 Hook
# 1.3 配置 OEM 客户数据隔离逻辑（不同知识库实例）

# 任务 2：搭建本地向量数据库
# 用 Chroma（轻量，无需复杂运维）
pip install chromadb
# 创建三个隔离的 collection：
# - supplier_knowledge_base（供应商评估历史）
# - procurement_cases（采购决策案例）
# - contract_clauses（合同条款知识库）

# 任务 3：ERP 只读 MCP Server（Python 版本）
# 参考 05-mcp/database-mcp.json 的结构
# 编写只读 SQL 查询接口，接入 ERP 供应商主数据表
```

#### 第 3-4 周：第一个数字员工上线

```bash
# 任务 4：完善 SC1 供应商风险初筛 Skill
# - 接入本地向量数据库（历史评估案例）
# - 接入 ERP MCP（实时交货记录）
# - 完善输出格式，满足采购经理实际使用需求

# 任务 5：并轨测试
# 用 5-10 家供应商同时做 AI 评估 + 人工评估
# 对比一致性，修正 Skill 规则

# 任务 6：输出《供应商风险初筛试点报告》
```

---

### 关键技术决策（需要你拍板）

| 决策点 | 推荐方案 | 备选方案 | 决策时间 |
|-------|---------|---------|---------|
| **ERP 集成方式** | 只读 SQL（最快、最安全） | ERP 厂商 API | 7月第1周 |
| **向量数据库** | Chroma（本地部署） | Weaviate（云端） | 7月第1周 |
| **OEM 数据隔离** | 不同 Chroma Collection | 不同服务器实例 | 7月第2周 |
| **审计存储** | ClickHouse append-only | PostgreSQL | 7月第2周 |
| **AIOps 工具链** | Claude Code + Python | LangChain + OpenAI | 已决策：Claude Code |

---

### 18 个月工程里程碑

| 时间 | 工程交付物 | 对应规划场景 |
|-----|----------|------------|
| 2026-07 | supplychain 升级 + IATF 审计 Hook | 基建 |
| 2026-07 | SC1 供应商风险 Skill v1 上线 | SC1 |
| 2026-08 | ERP MCP 接入 + SC2 采购周报 Agent | SC2 |
| 2026-09 | SC3/SC4 上线 + 财务/销售/运营启动 | SC3-4 + Phase 3 |
| 2026-10 | 工程研发+质量部启动，六部门全入轨 | Phase 4 |
| 2026-12 | 采购部 Plugin 打包，可复制模板成熟 | Phase 6 |
| 2027-01 | 跨部门 Hermes 路由（供应链⇄质量联动） | 跨部门 Agent |
| 2027-04 | AI CoE 试运行，知识图谱基础版上线 | AI CoE |
| 2027-07 | AI-First 工作模式，探索对外赋能 | S3 深化期 |

---

## 四、工具链现状与下一步行动

### 已完成（2026-06-05）

| 工具 | 状态 | 说明 |
|------|------|------|
| Claude Code | ✅ v2.1.160 | 全局安装 |
| SuperPowers | ✅ v5.1.0 | 14个Skills，全局插件 |
| OpenSpec | ✅ v1.4.1 | 全局 npm 安装 |
| 全局 CLAUDE.md | ✅ 已创建 | Hermes L1 个人记忆 |
| 全局 Agents | ✅ 已全局化 | 采购/库存/物流 3个 |
| SRM MCP | ✅ 已接通 | supplychain 项目 |

### 下一步（按优先级）

1. **学习路径**：从模块 4（Checkpoints）继续——1-3 已通过 supplychain 项目实践掌握
2. **7月第1周**：用 OpenSpec `openspec init` + `/opsx:propose` 为 SC1 供应商风险初筛写规格
3. **7月第2周**：SuperPowers `brainstorming → writing-plans → subagent-driven-development` 开发 SC1 Skill
4. **7月底前**：决策 U9C ERP MCP 接入方案（只读SQL vs 厂商API），确认 AIOps 负责人

---

## 五、配套实战材料（VP 软实力补强）

本文是"技术全景"；下面两份聚焦"VP 带 AI 干活"的实操短板，配套使用：

- **《VP实战补强-git环境与审AI产出》** — 讲"为什么、怎么想"：git 基本功、开发环境意识、审 AI 产出的三块速查。
- **《VP实战练习册-可直接跑》** — 讲"现在敲哪几行"：三个真命令练习（① git 手感 / ② 环境意识 / ③ 审 SC8 二十个测试，含文末自检答案）+ claude-howto 模块→卓品实战桥接表。建议从练习③ 开始。

---

*文档版本：2026-06-10（修订）| 工具链状态：SuperPowers v5.1.0 + OpenSpec v1.4.1 + 全局记忆已配置 | 新增：配套实战补强 + 可跑练习册*
