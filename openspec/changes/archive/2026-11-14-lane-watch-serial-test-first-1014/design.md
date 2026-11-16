# 泳道看护串行与测试优先差量 v1

状态：设计与实施范围待集中批准；现有代码和运行配置未改变。

## Context

现状证据：guardian_adapter.py:140默认max_parallel=4；plan/run仍可扇出。workflow_driver.py:595以整个intent构建模型prompt，618行后再追加implement授权。旧SC2原生session:11先要求读全景/实施计划，最终context248927；定位摘要在reports/pc-mvp-correction-1013/sc2-context-triage-1014.json。最近SC2静态分段交付为53693daf、258pass/0skip，证明应以可运行增量收口，不能因旧运行锁尚未结算而否认另外真实验收成果。旧锁仍按原合同保留。

## Goals / Non-Goals

目标是替换未来普通业务的默认看护行为，减少模型调用与重复确认，不创建另一层执行器。本次不重写Workflow状态机、recover、review解析器或ff工具，不部署消费者；不追溯改写旧attempt、sealed plan、claim或已批设计。现有业务任务的具体ff不包含在本变更批准中。

## Decisions

1. **单主会话串行**：标准模式主会话自己实现和验证，不调用Guardian --run、无头批处理或subagent-driven-development派实现/审查子任务。小片边界按可验证功能节点，不按批次数量。用户明确要求headless时才用既有入口；本差量仍只支持并行度1，超限在任何派生调用前拒绝，旧计划原字节保留。
2. **测试优先**：批准目标/设计只确认一次。每片定向pytest→检查点→下一片；最终对应项目完整pytest、golden与功能/审计自动验收。普通代码不强制模型形式review，不用报告句式作为代码质量闸。不改测试来迁就缺陷。ASIL C/D禁区、A/B人工签认、OEM隔离、L2与业务签认仍按原规则；它们是权限/业务事实，pytest不能签字。
3. **输入缩减**：主会话只定向读当前片所需函数与测试。默认不创建headless模型，避免再用旧全量intent拼接实现上下文。若用户明示旧headless方式，原Workflow合同完整保留；不是通过生成假review报告跳过旧stage。旧合同与新标准模式的证据分别命名，不混报。
4. **本地闭环**：当前主线是master，不新建一个名为main的并行正本。合入复用既有受控工具，以具体候选授权、绑定实际HEAD的测试、范围、干净目标和祖先关系为前置，ff-only；更新R5。缺逐项授权只集中问该候选，已授权不重问。本轮主仓存在他人在办修改，禁止为合入而清理。push/生产仍须明确指令。

### 实施白名单

1. AGENTS.md：加入新默认运行合同及其与冻结旧合同的边界。
2. .claude/rules/场景建造与合规.md：将未来默认“能开尽开/独立域并行”改为单主会话，保留合规与业务目标。
3. .agents/skills/zhuopin-lane-watch/SKILL.md：Codex优先入口指向新默认，无默认headless/代理review。
4. 0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md：当前规范更新；历史已发生记录保留。
5. 0-学习与工具/codex-handoff/README.md：新默认/明确选择旧headless的兼容说明。
6. 0-学习与工具/codex-handoff/guardian_adapter.py：新计划并行默认/上限1；执行前检查超限旧计划，不改历史数据。
7. 0-学习与工具/codex-handoff/tests/test_guardian_adapter.py：默认串行、超限拒绝、拒绝零模型副作用、正常串行阶段推进。

另只允许本OpenSpec四件、既有ignored reports及正常队列/R5登记；不安装依赖，不改仓库外配置，不激活后台。若以上7路径不足，先报告精确差量，不能扩大到新的恢复或release工具。

## Risks / Trade-offs

- 测试存在盲区 → 将明确业务验收节点转为自动检查，测试数不等于业务完整；允许用户明确要求一次定向review，但不默认互审循环。
- 串行降低独立任务并发吞吐 → 以减少重复读取、审查与协调换取可运行增量；不编造百分比收益。
- 老计划可能并行且claim仍在 → 仅拒绝新启动，不清claim、不改plan、不自动迁移；已运行任务不被本变更中断。
- 文档版本与代码不同步 → 同批修改Codex入口/源规范/规则，直接测试实际执行前拒绝路径；配置存在不等于现场调度已生效。

## Migration Plan

按tasks在当前会话串行实施。先验新默认RED，再最小补丁与定向GREEN，最后handoff子项目完整CI。自查实际diff及测试证据，不派独立review代理。本次设计批准不代替任何具体ff；候选验收后只准备绑定commit的本地合入请求。回退保持旧已提交版本，若回退需要改主线，同样逐项授权；不重置既有脏文件或历史状态。
