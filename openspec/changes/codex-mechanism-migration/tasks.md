# Codex 机制迁移 Implementation Plan

For agentic workers: executing-plans；每项使用 TDD，最终独立 review。
Spec: source-spec.md；最新授权与冲突裁决见 intent.md。
Architecture: 保留现有调度和消费状态机，以统一 Codex provider 替换模型进程接缝。权限只使用 read-only/workspace-write 和 never，不绕过 sandbox 或 hook trust。信号与业务成果验收独立于进程退出码。

## 机器可读实施状态（证据见 progress.md；勾选不代表整体验收）

- [x] 1.1 实现统一 provider、暂停、argv、原生身份、上下文及异常清理；32项单测通过。
- [x] 1.2 验证真实只读工具调用与同thread resume，保留原生计量证据。
- [ ] 1.3 正常信任后核验原生 hook 正负例及完整会话审计。
- [x] 2.1 轮询守/注册器适配、sticky回归与VBS非零传播隔离验证。
- [ ] 2.2 实际轮询脚本到模型、工具、hook、回复的端到端验证。
- [x] 3.1 Codex生成器/lint、批处理/旧入口、隔离/失败/恢复/续棒/泄漏/限额/错峰实现和隔离测试。
- [ ] 3.2 全新工作树中的真实写入、测试、review、交接与产物机器核验。
- [x] 4.1 拆件provider、暂停、watcher无进展退避/停链与重启状态隔离验证。
- [ ] 4.2 真实拆件机制夹具的端到端验证及受控现场切换。
- [x] 5.1 建立技能/插件处置台账；按最新intent只验zhuopinAI必要依赖，无关项目保留现状。
- [x] 5.2 通过正常UAC停用三个旧任务，保存XML/哈希；五项Codex自动化仍暂停。
- [ ] 5.3 完成剩余必要能力验证、可版本化资产提交/获准合入、全新工作树有效继承和调度触发验证。
- [x] 6.1 独立原生审查四个关键接缝，四项缺陷均RED→GREEN。
- [x] 6.2 接力runner复用provider；新汇总状态探针及原生占号审计修复并验证。
- [ ] 6.3 最终审查与验收矩阵闭合，逐项授权后合入/现场切换；全部必要闸通过才开业务。

## 全局约束

1. 旧工作树、既有脏文件和凭据不动；隔离工作树开发，不复制 runtime.local.json 到版本库。
2. 生产 Global mutex 不用于测试；仅测试专用 Local mutex；探针/巡检/信号使用隔离夹具。
3. 累计 usage 不能充当当前上下文。无法取得受支持的当前计量时 fail closed，不放行无守卫泳道。
4. 所有恢复都停自动消费并保留信号；不调用 Claude，不启用重复调度。
5. 产物哈希、测试结果、工具/hook事件、原生 thread ID、调度状态联合验收。进程0和哨兵都不足以成功。

## Task 1：统一 provider

Files: 0-学习与工具/codex-handoff/model_provider.py、tests/test_model_provider.py、运行配置样例。
先测试：安全argv、新建与resume、旧模型名拒绝、会话映射、非零/超时/缺turn.completed、异常JSONL、失败保留证据、暂停不启动。
实现：动态解析已有本机 Codex 路径，继承已验证模型配置；结构化审计；超时终止自己创建的进程树；原生会话与业务run ID分开。
验收：隔离进程夹具通过；真实CLI一轮工具执行产生JSONL和hook证据。未通过不接生产。

## Task 2：轮询守及注册器

Files: 工具-轮询守.ps1、工具-注册轮询守计划任务.ps1、相关隔离tests。
先测试：无信号零调用、未知/失败/超时触发一次、sticky集合去重、互斥、模型失败透传、暂停保留信号。
实现：只替换模型接缝；注册器必须与包装同步；保留静默判据和一次消费。
验收：六类夹具及重启恢复；实际脚本→Codex→工具/hook→回复；不调用真实副作用探针。

## Task 3：opener执行器

Files: 工具-opener批处理执行v2.ps1、旧入口、生成器/lint的必要兼容项、相关tests。
先测试：隔离、限流错峰、泄漏、报告回收、非零停本泳道、仅缺哨兵一次补问、150k+15min/250k、上下文未知拒绝、恢复线程映射。
实现：使用provider，旧入口不再能起Claude；上下文来源必须真实且可核，不用累计usage。
验收：合法生成器/lint派单→新工作树写入→测试→review→交接；产物机器核验。

## Task 4：事件拆件

Files: aibot_service/patrol_dispatch.py、服务相关tests。
先测试：PID去重、秒退、失败退避、三次停链、落盘后重启、超时、信号不消费和新信号复查。
实现：注入provider和暂停接口；保留现有非阻塞状态机及审计，不用真实回件测试。
验收：隔离集成链完整；现场版本切换须受控且不盲目重启整个服务。

## Task 5：资产与调度

Files: 原生资产、技能插件处置台账、CommitSweep VBS注册器、部署/停止消费工具。
历史清单为34技能与9插件（10安装记录），不等于本线验收范围。按最新 intent 仅处置 zhuopinAI 必要依赖；中英文last30days及其他无关项目技能配置保留现状，留待所属项目处理，不继续补测。关键项目依赖实测。
CommitSweep先写非零夹具测试，再修退出码；新工作树验证版本化资产继承和原生apply_patch负例。
现场切换前导出Action/触发器/账户摘要和备份，计划触发后对模型事件和产物；五个Codex自动化保持PAUSED直到单消费者核验。

## Task 6：最终验收

最终独立review；修复关键问题并验证。矩阵标pass/fail/blocked/evidence-gap，不将计划勾为通过。
核对必要机制全部闭合，再请求尚需的逐项ff/生产动作授权；授权前准备好可审查发布件。
业务开工闸仅由全部必要项实测通过开启。

## Review Focus

参数含空格/非ASCII；resume权限继承；多个并发信号与服务重启；模型失败伪0；本地路径泄漏或凭据误入库。
