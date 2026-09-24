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

## Codex 执行约定

- intent → proposal/design/tasks → 实现 → 逐项目测试 → review → 发布准备。项目 .agents/skills 下的 Codex 入口优先；原技能正文作规则与方法来源。遵守 Superpowers 先 Plan/Spec 后实现，不因切换模型省略人工闸。
- Claude 的 Task/Agent、Bash/Read/Edit、save_skill、set_session_title、scheduled-tasks、claude -p 是源端接口。采用当前 Codex 实际可用工具；不能靠改产品名宣称接口兼容。子代理只在当前用户或适用技能明确要求时使用，模型只能取当前工具允许值。
- 不使用 claude 作为 Codex 自动化后台。Codex 非交互入口是 codex exec。不得移植 --dangerously-skip-permissions 或绕过 Codex sandbox/hook trust；失败留证据并停止依赖步骤。
- 所有路径加引号。运行 Python 用 invoke.ps1 解析的隔离环境；不得在共享全局 site-packages 重装 editable 平台指针。按 CI 矩阵逐子项目跑 pytest，不在根目录混跑。
- mock/脱敏先行；OEM 技术数据隔离；AI 决策写 audit；L2 不代签；ASIL C/D 不自动修改/判定。ff 合入、生产 .51 部署、真实对外发送均按原规则取得针对该项的授权。
- 定时巡检无变化时保持安静；只有真实机器调度存在才说会自动继续。Windows 业务服务原位继承，不克隆造成双跑。
- hooks 是辅助守卫，须正常 /hooks 审阅信任后才生效；测试正负例通过不等于运行时已信任。原上下文 token 计量器依赖 Claude transcript，不移植为虚假的 Codex 数值。
- memory/history 只作检索资料，不凌驾于规则、队列或现时测试；原文不改，原凭据不复制。
- 完工报告结果、命令/证据、未闭合项；有用户动作时用纯编号列表；无决策写“本次无需你决策”。
