# Mac端取用1113A2机制成果

目标分支：`codex/1113a2-mechanism-closeout`；来源仓库：`https://github.com/Raytheoner/zhuopin-ai-transformation.git`。基线：`6ce833345ed503dc916a37ca01d32c46ae26bd6c`。本分支是Windows隔离候选，不代表已合主线或Mac现场已验收。发布提交指针以原任务#715、最终答复和本分支Git历史为准。

## 获取与隔离查看

粘贴端：Mac终端，先进入现有卓品项目Git仓库。目录若已存在，保留现场另选目录名，不清理。以下只fetch并新增独立检出，不切换现有工作区：

```sh
git fetch origin codex/1113a2-mechanism-closeout
git worktree add --detach ../zhuopin-ai-1113a2-review FETCH_HEAD
git -C ../zhuopin-ai-1113a2-review rev-parse HEAD
```

## 继承内容

1. 需求由原队列汇集，原监听事件驱动回灌与人工转交文档沿同一反馈入口承接；已有安排与批准按原行证据恢复，不要求看护人重复搬运。需求索引、feature/refinement及原行为规格约束消费链。
2. 短入口仍为“开启泳道看护”“我已回LAN”。第一项合法工作由主会话直接认领并实施；阻塞记账后继续下一独立项，留步/收口前重查可做池。只读上下文的execution_ready=false不制造新审批。
3. 第一笔实质构建写入前，原行先落实唯一写方、原批准范围和精确触碰区，并由原锁工具完成§二预登记。尚未存在的合法路径仅在原预登记状态下可登记；普通实体校验、路径约束、锁和批准指纹仍有效。登记失败不写目标。
4. 同一OpenSpec tasks按主会话串行TDD执行。功能/audit验收绑定规格场景、真实候选和pytest原始JUnit；完成后同步主规格并归档，原队列销号。专业签认、真实源、LAN、外发和发布权限继续分闸。

## 文件边界

先看`docs/requirements/日常短入口与需求验收.md`、`反馈承接与原workflow使用.md`、`INDEX.md`及`docs/codex/mechanism-publish-1116/final-manifest.json`。构建入口为`0-学习与工具/codex-handoff/`的原driver/queue_context/feedback_intake/business_acceptance和对应测试；技能沿`.agents/skills/`及其明确导航的`0-学习与工具/skills源码/`读取。

保留Mac本地AGENTS、runtime、hooks适配、队列/锁和原写方。不要整树覆盖Windows根AGENTS中的绝对路径，不复制本机runtime、state、凭据或调度配置。Windows的invoke.ps1和PS1 guards沿Mac已有原生入口适配；本分支不授权新增后台执行器、启动巡逻、恢复暂停任务、合入或发布。

候选里的三条原队列记录及R5材料用于历史关联和可复现门禁，不是Mac实时队列快照，不据此重派已有人承接的业务。未携带1116KH、#563/#636、#670/SC7等业务候选或业务实现文件。FI9仅继承既有意图确认原文，Q2仅继承与基线六条行为完全相同的主规格载体，不扩展业务批准。

CLAUDE仅保留历史、兼容文件名和薄导航；现役规则读AGENTS路由的CODEX-RULES及docs/codex/rules。迁移映射31个目标均需存在，不能靠旧CLAUDE正文补缺。

## 验收边界

Windows隔离fixture已实际生成候选、先红后绿并回写，验证被阻项之后继续下一项；原生Hook的合成短口令已路由到现行技能。原始命令、JUnit、候选内容/哈希和调用回执见validation.json及functional*.json。模拟验收不等于自然会话或生产验收；Mac需在自己的隔离候选和原授权下复验，再开展自然短入口试跑。

周期回件拆件巡检保持PAUSED。本次无需Shao Peishen补批已有范围；不从Windows证据推导新的专业/生产/外发权限。
