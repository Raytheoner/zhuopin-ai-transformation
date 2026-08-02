---
status: 生效
title: "Hermes × SuperPowers 协作架构"
---

# Hermes × SuperPowers 协作架构
## 卓品智能 AI 转型工程指南

> 更新：2026-06-05
> 基于：claude-howto 完整知识体系 + 卓品智能 AI 转型全景规划

---

## 一、两个框架的真实定义

在设计协作之前，先把定义对齐清楚。

### SuperPowers — 高质量交付的总工程师

SuperPowers 是 VibeCoding 的**执行框架**，本质是一套让 Claude Code 输出企业级质量的工程工具链：

> **安装状态**：SuperPowers v5.1.0 ✅（Claude Code 官方插件，全局已安装）
> **安装状态**：OpenSpec **v1.7.0** ✅（npm 全局安装，`openspec` 命令可用；2026-08-02 由 v1.4.1 升级，队列 #205-A。**版本单一可信源＝`0-学习与工具/环境依赖清单.md`**）

```
SuperPowers 完整工具链
│
├── OpenSpec（需求层）✅ 已安装
│   └── openspec init → /opsx:propose → 生成 proposal.md + design.md + tasks.md
│       在编码前将模糊需求转化为结构化规格，避免"AI 误解需求"返工
│       Token 消耗降低 30-50%，返工率下降 60%（实测数据）
│
├── CLAUDE.md 配置体系（上下文层）✅ 已配置
│   └── ~/.claude/CLAUDE.md（个人全局记忆，已创建）
│       各部门 CLAUDE.md（项目级业务规则，随数字员工开发建立）
│
├── 14个 Skills（执行层）✅ 已安装
│   └── brainstorming / writing-plans / subagent-driven-development
│       test-driven-development / requesting-code-review
│       executing-plans / dispatching-parallel-agents 等
│
└── code-review-graph（质量层）
    └── 两阶段审查：规范合规检查 → 代码质量检查
        确保 AI 生成代码满足 IATF 可追溯要求
```

**SuperPowers 的核心价值**：把"一次性的 AI 对话"升级为"可重复、可审查、高质量的工程交付流程"。

---

### Hermes — 让记忆驱动自我进化的四层架构

Hermes 是 Claude Code 的**记忆体系**，四层结构让智能体能跨会话学习、持续进化：

```
Hermes 四层记忆架构（优先级从高到低）

Layer 1：Managed Policy（公司级规范）
  位置：C:\Program Files\ClaudeCode\CLAUDE.md（Windows）
  内容：公司 AI 使用红线、IATF 合规要求、OEM 数据隔离规则
  管理者：IT + 法务（只有管理员可修改）
  作用：全公司所有 AI 会话的强制约束，不可被覆盖

Layer 2：Project Memory（项目级上下文）
  位置：项目根目录 CLAUDE.md 或 .claude/CLAUDE.md
  内容：部门业务规则、技术架构、历史决策记录
  管理者：AIOps（版本控制，团队共享）
  作用：每个数字员工的"岗位手册"

Layer 3：User Memory（个人偏好）
  位置：~/.claude/CLAUDE.md
  内容：个人工作风格、常用操作偏好
  管理者：每个使用者自己
  作用：Claude 记住你是谁、你怎么工作

Layer 4：Auto Memory（自动学习层）
  位置：~/.claude/projects/<project>/memory/
  内容：Claude 在工作中自动记录的模式、异常、新场景
  管理者：Claude 自动写入（人可以审查和编辑）
  作用：⭐ 这是 Hermes 实现"自我进化"的核心机制
```

**Hermes 的核心价值**：让每个数字员工**越用越聪明**——每次执行都在积累经验，下次遇到类似场景时自动调用历史知识。

---

## 二、两者的分工：建造 vs 进化

这不是两个并行工具，而是**垂直协作**：

```
┌─────────────────────────────────────────────────────────┐
│                    SuperPowers 层（建造）                  │
│                                                         │
│  OpenSpec 写规格 → Claude Code 建 Skill/Agent → 审查上线  │
│                                                         │
│  ▶ 负责：新数字员工开发、复杂任务执行、高质量交付              │
│  ▶ 使用者：AIOps 工程师、Paul（VP）                        │
│  ▶ 时机：每次新场景开发、每次 Skill 升级迭代                │
└──────────────────────────┬──────────────────────────────┘
                           │ 上线
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Hermes 层（运营与进化）                  │
│                                                         │
│  Layer 1 Managed Policy → 守住合规红线                   │
│  Layer 2 Project Memory → 加载业务上下文                  │
│  Layer 3 User Memory   → 记住使用者偏好                   │
│  Layer 4 Auto Memory   → 自动记录新场景和异常              │
│                                ↓                        │
│  每周汇总 Auto Memory → AIOps 审查 → SuperPowers 升级     │
│                                                         │
│  ▶ 负责：日常运营、持续学习、自动触发、异常处理              │
│  ▶ 使用者：各部门员工（采购/财务/质量）                     │
│  ▶ 时机：数字员工上线后的所有日常执行                       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、自我进化闭环：Hermes 如何驱动 SuperPowers 迭代

这是整套框架最关键的设计——让系统不断自我升级：

```
                    ┌─────────────────────┐
                    │  日常运营（Hermes）   │
                    │                     │
                    │  采购经理使用        │
                    │  SC1 供应商评估      │
                    └──────────┬──────────┘
                               │
              遇到新情况（如：新型供应商、不寻常的风险模式）
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Auto Memory 自动记录  │
                    │                     │
                    │ ~/.claude/projects/  │
                    │ procurement/memory/  │
                    │ MEMORY.md            │
                    │                     │
                    │ "发现光伏类供应商评分 │
                    │  逻辑不适用，需要    │
                    │  专项评分模型"       │
                    └──────────┬──────────┘
                               │
                        每周自动汇总
                               │
                               ▼
                    ┌─────────────────────┐
                    │  AIOps 周度审查      │
                    │                     │
                    │  查看 Auto Memory    │
                    │  判断哪些值得迭代    │
                    └──────────┬──────────┘
                               │
                        触发 SuperPowers
                               │
                               ▼
                    ┌─────────────────────┐
                    │  SuperPowers 升级    │
                    │                     │
                    │  OpenSpec 更新规格   │
                    │  重写 SC1 Skill      │
                    │  code-review 验证    │
                    │  上线新版本          │
                    └──────────┬──────────┘
                               │
                    更新 Project Memory（Layer 2）
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Hermes 加载新版本   │
                    │  数字员工自动升级    │
                    └─────────────────────┘
```

---

## 四、卓品智能具体的 Hermes 记忆架构设计

### Layer 1：公司级 Managed Policy ✅ 已完成

文件：`C:\Program Files\ClaudeCode\CLAUDE.md`（公司级强制规范，需管理员权限）
个人全局记忆：`~/.claude/CLAUDE.md`（已创建，2026-06-05）

```markdown
# 卓品智能 AI 使用规范（公司级强制规范）
版本：v1.0 | 生效：2026-07-01 | 管理：IT 部门

## 核心红线（不可违反）
1. OEM 客户数据绝对隔离：比亚迪/上汽/理想数据不得交叉访问
2. ISO 26262 约束：AI 生成的安全相关代码必须经人工审核，不得直接合入
3. IATF 可追溯：所有 AI 辅助决策必须写入审计日志
4. 数据不出境：敏感业务数据（BOM/合同/客户数据）不发送至外部 API

## 数据分类规则
- 红色数据（绝不上传 AI）：客户价格协议、OEM 技术协议、员工薪资
- 黄色数据（脱敏后可用）：供应商名称、采购量趋势、质量统计
- 绿色数据（可直接使用）：公开行业信息、内部流程文档、历史分析案例

## AI 输出级别
- L1（建议模式）：AI 建议，人工决策，无需审批
- L2（辅助模式）：AI 执行，部门经理确认
- L3（自动模式）：AI 全自动，异常转人工（需提前审批开启）
```

### Layer 2：部门级 Project Memory（按部门建立）

每个部门数字员工项目有自己的 `CLAUDE.md`，随 Skill 版本迭代更新：

```
企业AI转型/
├── 4-数字员工/
│   ├── 采购部/
│   │   ├── CLAUDE.md          ← 采购部业务规则、供应商数据规范
│   │   ├── SC1-供应商风险/
│   │   ├── SC2-采购周报/
│   │   └── ...
│   ├── 财务部/
│   │   ├── CLAUDE.md          ← 财务数据规范、月结流程规则
│   │   └── ...
│   └── 质量部/
│       ├── CLAUDE.md          ← IATF 规范引用、客诉处理规则
│       └── ...
```

采购部 `CLAUDE.md` 示例核心内容：

```markdown
# 采购部数字员工上下文

## 业务背景
主要品类：MCU芯片、功率器件、被动元件、PCB
核心风险：单源依赖（尤其MCU）、lead-time波动、芯片短缺

## 供应商分级标准
- 战略供应商：年采购额 >500万，或唯一来源
- 优选供应商：准时率 >95%，合格率 >99%
- 观察供应商：近3个月有质量或交付异常
- 淘汰候选：准时率 <85% 且无改善计划

## 当前运行中的数字员工
- SC1 供应商风险初筛（v1.2，2026-08上线）
- SC2 采购周报生成（v1.0，2026-09上线）
- SC3 供应商绩效看板（开发中）

## @docs/supplier-scoring-model.md  ← 引用评分模型文档
## @docs/chip-shortage-watchlist.md  ← 芯片关注列表
```

### Layer 4：Auto Memory 配置（核心进化引擎）

为每个部门的数字员工项目开启 Auto Memory，并设置自动汇总 Hook：

```jsonc
// 采购部项目 .claude/settings.json
{
  "autoMemoryDirectory": "C:\\Users\\Paul Shao\\OneDrive\\Projects\\企业AI转型\\4-数字员工\\采购部\\auto-memory"
}
```

Auto Memory 会自动生成类似这样的学习记录：

```markdown
# 采购部数字员工学习记录
自动写入，最后更新：2026-08-15

## 发现的模式
- 台资供应商（台积电供应链）的风险评分需要加权：地缘政治风险系数 +0.5
- 光伏类供应商（不是我们主业）触发时输出"超出业务范围"更合适
- 采购经理标记"不一致"最多的场景：新成立子公司评估（历史数据不足）

## 待 AIOps 处理的改进建议
- [ ] SC1 v1.3：增加台资供应商地缘政治风险模块
- [ ] SC1：对成立 <2年 供应商给出"数据不足"提示，而非强行评分
- [ ] SC4：合同审核发现一类新的条款偏差："数据安全条款缺失"（3次）

## 本月成功率统计
- 执行次数：47次
- 采购经理确认"一致"：38次（81%）
- 标记"部分一致"：7次
- 标记"不一致"：2次
```

---

## 五、SuperPowers 在卓品的具体工作流

SuperPowers 的 4 个核心工具在公司场景的实际使用：

### 工具 1：OpenSpec（新数字员工立项时使用）

**何时用**：每次新建一个 Skill 或 Agent 之前，用 OpenSpec 把需求写清楚，避免"造完才发现做错了"。

以 SC3 供应商绩效看板为例：

```markdown
# OpenSpec：SC3 供应商绩效看板

## 问题陈述
采购经理现在靠季度人工收集供应商数据，更新滞后且覆盖不全。
需要一个自动化的实时绩效看板。

## 成功标准（可验证）
- [ ] 数据更新时效：≤24小时（从 ERP 拉取到看板展示）
- [ ] 供应商覆盖率：>95%（相比现在 <30%）
- [ ] 评分维度：质量(30%) + 交付(35%) + 成本(20%) + 配合度(15%)
- [ ] 预警触发：评分下降 >10% 时自动通知采购经理
- [ ] 自动化等级：L2（AI 评分，采购经理确认）

## 数据依赖（上线前必须就绪）
- ERP 采购/质量数据接口（只读 MCP）✅ 已有
- IQC 检验记录（需要 IT 开放接口）⬜ 待确认
- 供应商反馈记录（目前在邮件里，需要结构化）⬜ 待处理

## 排除在外（不做）
- 不包含供应商自评功能（那是 SC5 的事）
- 不包含自动触发采购决策（仅展示和预警）

## 验收方式
AIOps 用 5 家真实供应商跑一次，采购经理盲测打分是否与人工评估一致
```

### 工具 2：CLAUDE.md 配置（保证每次开发有完整上下文）

SuperPowers 在开发 SC3 时加载的上下文：
- Layer 1 Managed Policy（数据隔离、L2 规则）
- Layer 2 Project Memory（采购部业务规则、现有供应商分级标准）
- OpenSpec（SC3 的具体规格）

这三层合并后，Claude Code 写出的 Skill 天然满足合规要求、业务规则和规格标准。

### 工具 3：code-review-graph（上线前质量把关）

每个 Skill 上线前必须过 code-review-graph：

```
SC3 Skill 代码审查清单（SuperPowers code-review-graph）

合规审查（必过）：
✅ 不向外部 API 发送 ERP 原始数据
✅ 审计日志钩子已挂载
✅ 输出结果标注"建议模式，需采购经理确认"

业务逻辑审查：
✅ 评分权重与 OpenSpec 一致
✅ 预警阈值可配置（不硬编码）
⬜ 边界情况：供应商数据空值时的处理

性能审查：
✅ ERP 数据查询不超时（≤5秒）
✅ 不阻塞主线程
```

---

## 六、18 个月计划中 SuperPowers × Hermes 的分工时间线

### 2026年7-8月：Hermes 基建 + SuperPowers 首战

**Hermes 任务（基础设施）**：
```
Week 1-2：
- 建立 Layer 1 Managed Policy（公司级 CLAUDE.md）
- 建立 Layer 2 采购部 Project Memory
- 开启 Auto Memory，建立每周自动汇总机制
- 部署 IATF 审计日志 Hook
```

**SuperPowers 任务（第一个数字员工）**：
```
Week 3-4：
- OpenSpec 撰写 SC1 供应商风险初筛规格
- Claude Code 开发 SC1 Skill v1.0
- code-review-graph 审查通过
- 并轨测试（AI + 人工同时评估，对比一致性）
- 上线，Hermes 接管运营
```

**交接点**：SC1 上线那天，SuperPowers 完成使命，Hermes 开始接管——Auto Memory 开始记录每次执行的学习。

---

### 2026年9-12月：SuperPowers 批量建造，Hermes 并行学习

每个月 SuperPowers 开发 2-4 个新 Skill，Hermes 接管已上线的 Skill 并积累 Auto Memory：

```
9月：
- SuperPowers → SC3/SC4/FI1/S1 开发上线
- Hermes(SC1) → Auto Memory 第一次迭代，触发 SC1 v1.2 升级

10月：
- SuperPowers → SC5/SC6/R1/Q1 开发上线
- Hermes(SC1-4) → 4个 Skill 积累数据，第一次跨 Skill 协同测试

11月：
- SuperPowers → SC7/SC8/FI3/R2/R3 批量上线
- Hermes → 半年度 Auto Memory 汇总报告，指导 SuperPowers 优先迭代哪些 Skill

12月：
- SuperPowers → 打包第一个部门 Plugin（采购部完整工具包）
- Hermes → 建立跨部门记忆共享机制（供应链 ↔ 质量 Auto Memory 互引用）
```

---

### 2027年1月+：Hermes 驱动跨部门联动

当 6 个部门都有运行中的数字员工时，Hermes 的四层记忆开始发挥跨部门价值：

```
跨部门 Hermes 记忆共享示例：

采购部 Auto Memory 记录：
"供应商 XX 最近交付异常率上升，供应商评分从 3→2"

→ 触发 Layer 2 Project Memory 规则（已写入：
  "当供应商评分下降时，通知质量部审查该供应商来料 FMEA"）

→ 质量部 Hermes 加载上下文 + 执行 Q3 FMEA 复核

→ 质量部 Auto Memory 记录结果：
  "FMEA 复核发现 2 个新风险项，已推送给工程研发"

→ 研发部 Hermes 接收，R1 需求分析助手自动生成风险报告
```

这就是你规划中"跨部门 Agent 协同"的技术实现路径——不是靠硬编码的触发逻辑，而是靠 **Hermes 四层记忆的规则传导**。

---

## 七、你作为 VP 的操作界面

在这套架构里，你不需要亲自写每一行代码，但有三个核心职责：

### 职责 1：管控 Layer 1（公司级红线）
每季度审查一次 Managed Policy，判断是否有新的合规要求（如新 OEM 客户的数据要求）。这是你唯一必须亲自参与的技术决策。

### 职责 2：审批 OpenSpec（新数字员工立项）
每个新 Skill 开发前，AIOps 提交 OpenSpec，你审批：
- 业务价值是否明确？
- 数据依赖是否合规？
- 自动化等级是否合适？

**这就是数字员工的"组织架构审批"**，平均 15-30 分钟/个。

### 职责 3：审查 Auto Memory 月报
每月 AIOps 输出一份 Auto Memory 汇总报告（Hermes 自动生成草稿）：
- 哪些数字员工学到了新东西？
- 哪些需要 SuperPowers 升级？
- 有没有发现合规风险？

**这是你的 AI 转型仪表板**，替代传统的月度部门工作汇报。

---

## 八、一张图总结

```
你（VP）
│
├── 审批 OpenSpec design.md（新数字员工立项，15-30min/个）
│         │
│         ▼
│    SuperPowers（AIOps 操作）
│    /opsx:propose → design.md审批 → brainstorming
│    → writing-plans → subagent-driven-development
│    → requesting-code-review → 上线
│         │
│         ▼ 上线交接给 Hermes 运营
│    Hermes 四层记忆（自动运行，无需干预）
│    L1: CLAUDE.md 冻结快照（稳态事实）
│    L2: Auto Memory 自动记录新场景
│    L3: Memory Flush 压缩前自动沉淀
│    L4: Skills 程序性记忆随时调用
│         │
│         ▼ 每月汇总
├── 审查 Auto Memory 月报（替代传统部门汇报）
│         │
│         ▼ 发现改进点 → 触发新 OpenSpec
│    SuperPowers 升级迭代 Skill 版本
│
└── 每季度审查 Managed Policy（公司 AI 红线）
```

**一句话记住**：OpenSpec **定需求**，SuperPowers **建**，Hermes **跑并学**，你**把关**。

---

## 九、工具链当前状态（2026-06-05）

| 工具 | 版本 | 状态 | 对应层级 |
|------|------|------|---------|
| Claude Code | v2.1.160 | ✅ 全局安装 | 执行引擎 |
| SuperPowers | v5.1.0 | ✅ 全局插件 | 建造层（14 Skills）|
| OpenSpec | **v1.7.0**（2026-08-02 升级，原 v1.4.1） | ✅ 全局安装 | 需求层 |
| 全局 CLAUDE.md | — | ✅ 已创建 | Hermes L1 |
| 全局 Agents | — | ✅ 采购/库存/物流 | Hermes L4 |
| Auto Memory | — | ✅ 默认开启 | Hermes L2/L3 |

**下一个里程碑**：7月第1周，用 `openspec init` + `/opsx:propose` 为 SC1 供应商风险初筛写第一份规格文档。

---

*文档版本：2026-06-05（修订）| 工具链已完整就绪*
