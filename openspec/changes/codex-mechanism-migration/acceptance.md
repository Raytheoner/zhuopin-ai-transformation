# 机制侧验收矩阵（未通过总闸）

检查点：6c2c041bd89d3ef7a8d4ea626609c3126884a897，分支codex/mechanism-migration-648。状态时间：2026-09-24T18:04:50.338984+08:00

**业务开发闸：关闭。三条消费者尚无完整原生端到端验收，Aibot现场仍有旧模型启动路径。**

| 必要项 | 状态 | 实证 / 剩余动作 |
|---|---|---|
| 统一provider及安全权限、失败/超时/清理、路由 | 单测通过；原生部分通过 | provider-final.txt：32；native-review-1和native-resume-1真实thread/工具/turn/计量；hook及产物未验 |
| 轮询守静默/sticky/失败/注册器 | 隔离验证通过 | provider-poll-final.txt：57通过2跳过（含当时provider）；三链原生轮询仍待 |
| opener生成/lint/旧入口/批处理 | 隔离验证通过 | 新套件已回归原入口，保留行为11、验证/并发7、合法生成/身份/PS5.1共3、变异/错峰及相关核心7；不能相加冒充独立总数 |
| 收工探针与原生占号审计 | 针对性回归通过 | downstream-green.txt：136通过25子测试，包含生成器回归；新状态不得静默漏报 |
| 事件拆件 | 模块隔离验证通过 | patrol-final.txt：34；包含无进展退避/三次停链/信号保留；真实服务尚未切换 |
| 接力runner | 单测通过 | handoff-provider-green.txt：20；末轮修复后受影响集合182通过/15子测试，另异常分支1通过；记录实施HEAD供review，额外漂移拒绝 |
| 原生hook与apply_patch负例 | 等用户正常信任 | 用户已明确稍后处理；不代写trust、不绕过。portable及新工作树仅合成验证通过 |
| 可版本化资产继承 | 检查点及全新checkout通过 | fresh-worktree-inheritance.json：6个核心blob一致，34技能，无runtime副本，共享runtime解析成功，工作树干净；不等于native hook生效 |
| Windows旧任务 | 三项已暂停 | runtime scheduler-export/pause-648-admin-*：XML、SHA256和enabled=false；轮询守、Claude体检、Claude插件补丁 |
| 单消费者调度/现场切换 | 未完成 | 五项Codex自动化PAUSED；Aibot受控切换、实际触发到证据闭环未验 |
| 技能/插件 | 部分验证 | asset-disposition.md逐项34/9；中英文研究引擎离线验证通过；在线能力、若干具体技能工作流不宣称已验 |
| 独立代码审查 | 两轮审查修复通过 | 初审四项、终审两项均复现修复；final-review-green.txt：182通过/15子测试；另HEAD取证失败分支1通过 |
| 发布/ff | 未授权执行 | 只有隔离WIP检查点，无push/ff/部署。期间主线sweep仅增两份治理文档，至69aa3ef1；合入前仍需核对与具体授权 |
| 历史覆盖 | 边界明示 | 原26份记忆保留主仓；复制被自动审批拒绝，本分支仅检索指针。Cowork主对话完整覆盖仍是已知证据缺口，不重启Claude |

## 不得隐去的测试事故

早期两次poll RED夹具被旧脚本忽略新参数后实际拉起封存CLI，日志报组织禁用访问；无成功消费。已即时告知并留档，原结果作废。后续夹具硬阻断旧CLI查找，当前实现移除旧调用路径。详见progress.md。此事故不能用后续通过覆盖。

## 继续验收所需

完成正常项目/hooks信任后，按tasks.md依次验证原生apply_patch正负例、三条消费者各自完整链路、新工作树真实写入→测试→review→交接。再把可审查发布件交逐项ff及现场切换授权。任何一项未闭合，都不得以计划、exit0、OPENER_DONE或本表存在为由启动业务开发。
