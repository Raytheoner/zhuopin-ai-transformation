# zhuopinAI · Codex 接力入口

本仓库 C:/Dev/zhuopin-ai 是业务、代码、文档、OpenSpec 与队列的唯一正本。项目内称 Shao Peishen；真实 Windows 路径中的 Paul Shao 保留。中文沟通，术语保留英文。

## 开场与权威来源

1. 先读根 CLAUDE.md：它在本次迁移中继续承载原项目业务纪律；不要把历史 Claude/Cowork 专属命令直接执行在 Codex。
2. 读 1-转型规划/0-全景路线图/session接力-Phase1收口.md；按下表加载场景规则。真实规则位于 .claude/rules/，不是 .codex/rules/。
3. 用 0-学习与工具/codex-handoff/invoke.ps1 -Mode Probe 获取现时 HEAD、队列摘要、工作树与运行环境。队列只走工具-队列查询.py --digest --actionable 或 --row N，禁通读/grep 真身。
4. 本机能力映射、待迁移项与执行阶段见 0-学习与工具/codex-handoff/README.md。旧工作树、分支和未提交修改不可清理。

| 操作 | 必读来源 |
|---|---|
| 场景/平台实现 | .claude/rules/场景建造与合规.md；4-数字员工/CLAUDE.md 或 5-平台底座/CLAUDE.md；所属子目录 CLAUDE.md |
| 队列/接力/落库 | .claude/rules/队列与落库.md；用既有锁工具 acquire → 写 → 登记 → release |
| git/时间/证据 | .claude/rules/两桌同步与取证.md；0-学习与工具/取证方法知识库.md |
| 人员/跟进信 | .claude/rules/跟进信与专员.md；6-人才与组织/人员名录-称谓与性别-正本.md |
| 全景/排期 | .claude/rules/文档与全景治理.md；1-转型规划/0-全景路线图/CLAUDE.md |

## 默认建造合同（2026-10-14，§四313已批准）

正本：`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`。普通默认由本会话串行实现，不自动调用Guardian --run、headless批处理或互审子任务。每片只携带目标/版本/必要函数/失败用例/下一步/禁项，自然结束时保存检查点后继续；同一已批任务不反复Probe、prepare、全景加载或设计确认。最终完整pytest及业务/audit自动验证绑定实际候选，不能过滤/改断言/随意skip取得全绿。具体ff仍逐项批准，仅在干净目标和可快进关系下ff-only；不默认push、生产或外发。旧task/plan/state/lock不自动改写，不能用新流程伪装成旧Workflow阶段已通过。

## Codex 执行约定

- 转场接力按 `.claude/rules/队列与落库.md`「接力卡 R5」执行：一页精简摘要、`[Win]MMDD` 标题前缀、唯一执行会话，以新会话能准确接续为完成标准。
- intent → proposal/design/tasks一次批准 → 单主会话串行切片实现 → 定向pytest与检查点 → 最终受影响项目完整回归 → 本地整合/发布准备。普通非安全相关新任务不默认派实现或review代理，不以模型报告句式作为代码质量闸；用户明确要求独审、冻结旧合同或安全相关人工审核仍按对应范围执行。项目 .agents/skills 下的 Codex 入口优先，已批目标不逐片重审。
- Claude 的 Task/Agent、Bash/Read/Edit、save_skill、set_session_title、scheduled-tasks、claude -p 是源端接口。采用当前 Codex 实际可用工具；不能靠改产品名宣称接口兼容。默认不派子代理、不并发开泳道；只有用户针对该任务明确要求时才派生，技能模板的扇出步骤不构成授权。获准派生时显式gpt-6-luna/high，不继承父模型；当前工具不支持时报告缺口。
- 不使用 claude 作为 Codex 自动化后台。Codex 非交互入口是 codex exec。不得移植 --dangerously-skip-permissions 或绕过 Codex sandbox/hook trust；失败留证据并停止依赖步骤。
- 所有路径加引号。运行 Python 用 invoke.ps1 解析的隔离环境；不得在共享全局 site-packages 重装 editable 平台指针。按 CI 矩阵逐子项目跑 pytest，不在根目录混跑。
- mock/脱敏先行；OEM 技术数据隔离；AI 决策写 audit；L2 不代签；ASIL C/D 不自动修改/判定。ff 合入、生产 .51 部署、真实对外发送均按原规则取得针对该项的授权。
- 定时巡检无变化时保持安静；只有真实机器调度存在才说会自动继续。Windows 业务服务原位继承，不克隆造成双跑。
- hooks 是辅助守卫，须正常 /hooks 审阅信任后才生效；测试正负例通过不等于运行时已信任。原上下文 token 计量器依赖 Claude transcript，不移植为虚假的 Codex 数值。
- memory/history 只作检索资料，不凌驾于规则、队列或现时测试；原文不改，原凭据不复制。
- 完工报告结果、命令/证据、未闭合项；有用户动作时用纯编号列表；无决策写“本次无需你决策”。

## 定夺项答复格式（2026-10-11，Shao Peishen 明确要求）

- 凡需 Shao Peishen 定夺，按编号列出可直接作答的选项，每项明确标一个推荐项，并简述选项影响；状态同步与需定夺事项分开。
- 末尾必须给单独代码块形式的可复制粘贴答复模板，标明粘贴端为本 Codex 会话；多项可合并为一个块，编号与上文一致，涉及批准时绑定对应计划版本及范围。
- 推荐项不等于默认授权。具体实施、设计审、仓库外修改、ff、生产部署、对外发送等需要明确批准的事项，未答仍待批；已批准事项不重复询问。
