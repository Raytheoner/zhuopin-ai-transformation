# 技能与插件处置台账（#648，未整体验收）

本台账区分原生执行、能力替代、源端安装退役和功能未验收。归档不算迁移；不重启 Claude、不复制凭据。源插件安装不再执行，但保留原始资产。

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
| receiving-code-review | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| requesting-code-review | 正在功能验证 | 首个子代理未读取到文件；native-review-1 只读原生审查进行中 |
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
| writing-skills | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-codex-handoff | 本次实际使用 | 本分支 intent/design/tasks、RED→GREEN、native worktree 与 progress 证据；不宣称覆盖技能全部分支 |
| zhuopin-followup-letter | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-kickoff-prompt | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-lan-closeout | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-lane-watch | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-queue-audit | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-rebaseline | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-requirement-grill | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |
| zhuopin-send-followup | 保留，具体工作流未验收 | 需要对应业务输入或独立机械夹具；不得按 frontmatter 通过宣称可用 |

## 9 个插件（firecrawl 原有两条安装记录）

| 原插件 | 处置 | 已有证据与剩余边界 |
|---|---|---|
| superpowers | 原生项目技能包替代源端插件安装 | 本次 plan/TDD/worktree 工作实际使用；子代理审查路径未成功，替代只读审查进行中 |
| claude-code-setup | 源端自动化安装退役；能力由 Codex 官方配置/原生工具承接 | 不执行源端 setup；本分支 provider/hook 及 OpenSpec 是实证，hook 信任仍待用户 |
| context7 | 源端 MCP 安装退役；官方文档检索按当前可用工具承接 | 本次已查 Codex 官方 hook/noninteractive 文档；无同名已安装的虚假声明 |
| frontend-design | 源端插件安装退役；可用原生前端开发流程按需承接 | 本次无前端业务任务，不声明视觉交付已验收 |
| document-skills | 原生 documents/spreadsheets/presentations/pdf 能力替代源端安装 | 当前原生技能可用；本次未生成业务文档，不声明渲染链已验收 |
| firecrawl（2 scopes） | 原安装保留归档；网页读取由当前 web/browser 按权限承接 | 官方文档抓取已实际使用；大批量爬取非本轮已验能力 |
| last30days | 保留海外平台引擎，源端 hook 不执行 | 原始离线 dates/normalize/dedupe/render 测试通过，证据 research-en.txt；在线API和Codex技能入口仍待验收 |
| last30days-cn | 保留国内平台引擎，与英文版互补 | 47项离线 dates/normalize/dedupe/HTML 测试通过，证据 research-cn.txt；在线数据源和Codex技能入口仍待验收 |
| outlook | 源端安装不执行；外部账号能力等待具体连接验收 | 本轮无真实邮件发送授权，不连接或发送测试邮件；不能宣称邮件流程已迁移可工作 |

明确边界：尚未验收的可选外部能力不得用于业务开发或对外动作。上述部分验证不满足“全部必要机制通过”；最终必要项清单和处置结论还需随三消费者及接力链验收闭合，不能用本台账替代它们。
