# 技能与插件处置台账（#648，未整体验收）

本台账区分原生执行、能力替代、源端安装退役和功能未验收。归档不算迁移；不重启 Claude、不复制凭据。源插件安装不再执行，但保留原始资产。

## 范围优先规则

本线仅覆盖 zhuopinAI 项目的必要技能、配置和机制。中英文 last30days 属于行业研报项目，与本线无关，保留现状，不再检查、补测或配置；其他无关项目资产同样留待所属项目处理，不计入本次验收门槛。排除不代表已验收，也不删除或禁用原资产。 下列全量清单是历史盘点，不是待办数量；仅 zhuopinAI 实际需要的条目构成本线验收项。

## 34 项技能入口

| 入口 | 当前处置/验证状态 | 实证与边界 |
|---|---|---|
| brainstorming | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| diagnosing-superpowers | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| dispatching-parallel-agents | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| executing-plans | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| finishing-a-development-branch | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| openspec-apply-change | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| openspec-archive-change | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| openspec-explore | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| openspec-propose | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| openspec-sync-specs | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| receiving-code-review | 本次实际使用 | 两轮真实只读审查共六项发现，经复现、修复及针对性回归；不宣称覆盖全部分支 |
| requesting-code-review | 两次原生只读审查完成 | native-review-1、native-final-review 有真实工具事件和审查成果；首个未能读文件的子代理不计入 |
| source-command-opsx-apply | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| source-command-opsx-archive | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| source-command-opsx-explore | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| source-command-opsx-propose | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| source-command-opsx-sync | 入口保留，CLI依赖验证 | OpenSpec strict 验证成功；archive/sync 等写操作未为了验收而调用 |
| subagent-driven-development | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| systematic-debugging | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| test-driven-development | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| using-git-worktrees | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| using-superpowers | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| verification-before-completion | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| writing-plans | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| writing-skills | 三个项目入口压力验证通过 | skill-pressure-baseline/green，仅证明指定路由与停点场景，不外推全技能覆盖 |
| zhuopin-codex-handoff | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| zhuopin-followup-letter | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-kickoff-prompt | 原生指令压力验证及隔离真实链通过 | 原生生成器格式覆盖旧标题骨架要求，skill-pressure-baseline/green；合法生成/lint/DryRun到native-batch-v4真实工具、测试、hook与交接已验证 |
| zhuopin-lan-closeout | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-lane-watch | 模式/停点压力验证通过；guardian未迁移 | 默认看护者不得擅改无头；显式无头仍须信任/隔离等前置；压力验证不等于编排功能通过 |
| zhuopin-queue-audit | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-rebaseline | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-requirement-grill | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-send-followup | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |

## 9 个插件（firecrawl 原有两条安装记录）

| 原插件 | 处置 | 已有证据与剩余边界 |
|---|---|---|
| superpowers | 原生项目技能包替代源端插件安装 | 本次 plan/TDD/worktree 工作实际使用；子代理审查路径未成功；两次替代原生只读审查完成并推动六项修复 |
| claude-code-setup | 源端自动化安装退役；能力由 Codex 官方配置/原生工具承接 | 不执行源端 setup；本分支 provider/hook 及 OpenSpec 是实证，当前主仓hook已正常信任并实测；候选portable配置合入后另走正常信任 |
| context7 | 源端 MCP 安装退役；官方文档检索按当前可用工具承接 | 本次已查 Codex 官方 hook/noninteractive 文档；无同名已安装的虚假声明 |
| frontend-design | 源端插件安装退役；可用原生前端开发流程按需承接 | 本次无前端业务任务，不声明视觉交付已验收 |
| document-skills | 原生 documents/spreadsheets/presentations/pdf 能力替代源端安装 | 当前原生技能可用；本次未生成业务文档，不声明渲染链已验收 |
| firecrawl（2 scopes） | 原安装保留归档；网页读取由当前 web/browser 按权限承接 | 官方文档抓取已实际使用；大批量爬取非本轮已验能力 |
| last30days | 范围外：行业研报项目，保留现状 | 历史离线证据 research-en.txt 保留；本线不再补测或配置，不阻塞 zhuopinAI 验收 |
| last30days-cn | 范围外：行业研报项目，保留现状 | 历史离线证据 research-cn.txt 保留；本线不再补测或配置，不阻塞 zhuopinAI 验收 |
| outlook | 源端安装不执行；外部账号能力等待具体连接验收 | 本轮无真实邮件发送授权，不连接或发送测试邮件；不能宣称邮件流程已迁移可工作 |

明确边界：本项目实际采用的能力必须满足其对应验证和授权要求；无关项目的能力不在此裁定可用性、不纳入待验收。上述部分验证不满足“全部必要机制通过”；最终必要项清单和处置结论还需随三消费者及接力链验收闭合，不能用本台账替代它们。
