# Context
本设计细化已批准 source-spec.md，用户本轮授权及冲突裁决见 intent.md。实施工作树 codex/mechanism-migration-648；队列 #648。全部消费者验收前禁止业务开工。

# Goals / Non-Goals
目标：原生 Codex 进程、三消费者状态机、跨工作树 hook、可版本化资产与单一调度消费闭环。非目标：业务场景开发、改变人工签核、迁移凭据、恢复 Claude。

# Scope clarification
本线仅覆盖 zhuopinAI 项目的必要技能、配置和机制。中英文 last30days 属于行业研报项目，与本线无关，保留现状，不再检查、补测或配置；其他无关项目资产同样留待所属项目处理，不计入本次验收门槛。排除不代表已验收，也不删除或禁用原资产。
仅因出现在全局技能或源插件安装清单中，不足以判为 zhuopinAI 必要依赖；本项目实际依赖的通用工具仍按其本项目用途核验。

# Decisions
1. provider 使用 `-a never` 与 read-only/workspace-write；无旧模型回退，无 sandbox/hook trust 旁路。默认暂停，显式 enabled 才起一次进程。
2. 每次运行独立证据目录，source_id 与原生 thread_id 分开，进程/tool/turn/hook/产物各自记录；输出最多 output_needs_review，accepted 恒 false。外层验收不得从 exit0 或哨兵推导。
3. routine/design 只是任务路由，当前均显式继承用户模型；不宣称价格等价。实际模型取原生 rollout。
4. 上下文读取匹配 thread + workspace 的原生最近 token_count；不使用累计 usage。150k 开始宽限、250k 硬停；计量缺失停止。原生格式不是稳定 API，解析异常 fail closed。
5. poll 保留静默标记、sticky 集合与 Global mutex；仅测试副本改 Local。批处理保留隔离、串行/并行限额、错峰、泄漏检测、一次补问、续棒。patrol 保留非阻塞、PID/信号/退避/落盘。
6. Codex opener 明示环境；桌面标题 API 与 headless 审计分开。旧 guardian 不作为已迁移能力放行。旧格式可检索，消费者不执行源端 API。
7. hook 命令从 cwd 寻找 git root，runtime 从共享主仓解析；版本库不携带本机 runtime/consumer 开关。用户正常 /hooks 信任是实测前置，不代写信任数据库。
8. 调度现场切换独立于代码验收。保留原触发器、账户及信号；五项 Codex 自动化保持暂停。恢复只允许停止自动消费并留证据。

# Risks / Trade-offs
原生 hook 与 telemetry 格式依赖当前 CLI，必须实测；工作树新资产未合入 master 前不能宣称继承。服务现场旧消费者仍存在，切换须具体授权。测试隔离事故详见 progress.md，原失败结果不可当验收。

# Migration Plan
按 tasks.md 六阶段推进；证据矩阵逐项填实际结果。提交前做独立 review 和受影响测试；ff、现场切换分别申请具体动作授权。最后再验计划触发到产物审计。

# Open Questions
用户暂缓隔离项目 /hooks 信任；native 正负例与三消费者带 hook 端到端仍阻塞。历史 Cowork 完整覆盖是已声明证据缺口，不重启 Claude 取记录。
