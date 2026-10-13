# PC-MVP有限恢复设计补件 v1

状态：待Shao Peishen明确批准；仅工程恢复差量，非业务设计重做。目标是让SC2已有成果经正式入口进入可用页面/报告交付，Q2可信结算独立处理，不阻塞SC2。

## 1 已证实的问题

SC2 task sc2-three-metric-cold-1013v5 的第二proposal attempt cbc66ec380224fd7b55d20531c2f3631已终止/busy=false；四件同原字节，只有四个untracked，HEAD仍b2933132b733756b30b94e309e2066bbd50d6e43。原生读取规划时sed非零，driver拒绝model proposal evidence incomplete；_proposal又要求clean，没有保全脏proposal接纳入口。不能把工具失败当成功或改私有state。

Q2 task q2-semantic-offline-source-1012v2 的implement edbd1a4edb4c4bcab5a9dc6cac2af3bd保留running/busy=true；outer已记录context_stopped，termination_gate仅D3_only satisfied。现recover必定fail closed，缺可信外层结算路径。Q9/FI14的原thread已超过150k，不应自动续原上下文。

证据：reports/lane-watch-1013/sc2-block-verified-1a.json；reports/pc-mvp-correction-1013/current-snapshot.json；官方Workflow status；workflow_driver.py::_proposal/recover、workflow_state.py::recover；原终止证据只从外层固定attempt目录读取。

## 2 新增正式入口的合同

**保全proposal接纳**：新增显式模式及模型写树外recovery approval。由外层同时校验task/attempt/thread、source HEAD/common-dir、原intent/源行、精确四件path/SHA、无busy、无staged/其它dirty、无链接逃逸及当前授权。先保存资产/失败证据清单；不搬、不删、不重写原四件。新独立Luna只读核对原失败与四件，给绑定四件哈希的可解析结论；outer重新运行strict、白名单、commit/seal。原失败attempt仍failed；新接纳attempt另记，delivery_accepted=false。仅SC2四件同已批SHA可机械承接原设计批准，不能批准新业务设计。

**可信结算**：recover只信外层固定目录与原state封存引用，不接纳caller拼出的observed JSON。重新校验process/request/result/session、终止seal、thread/attempt/workspace、文件来源/哈希和完整进程树终止证据。必须区分活进程、PID重用、父退出但子树不明、缺原文/来源完整性和未知。只有确证该attempt已安全终止，才在排他锁内写blocked终态和追加结算审计、按官方机制释放其运行锁；不写成功，不丢原termination_observation，不接受单一D3摘要。任一未知保持锁；不杀不明PID、不改ACL或hook。

**原任务有限冷接续**：SC2/Q2/Q9/FI14只在上述终止/绑定核对完成后，由Guardian明确恢复原任务/原树/原sealed批准。先对部分资产作逐路径hash清单，区分已验证/待修/不可读；不可读文件不删除。新增显式新上下文模式，禁止隐式恢复高上下文thread；没有新增业务task或第三棵SC2树。每段绑定必要输入和一个可运行里程碑，保存外层checkpoint及dirty哈希；checkpoint是部分成果，不能冒充实现验收。继续时必须复核同一HEAD、批准和完整路径集合，漂移则拒绝。CI/review/release gate保持原有严格要求，任何部分checkpoint都不能进入release。

**Guardian对账**：只对本补件列明的task允许依据新的可信恢复回执从blocked/安全终止态继续；保留原批次失败历史，现时阶段另记。不以退役/换批次/成功哨兵替代成果；不放宽任意blocked batch通用resume。正常调用路径及现有fail-closed默认不变。

## 3 SC2业务合同沿用

只在原12路径完成metrics缺陷、report/webapp与来源明细。#23原文XML段62/99–102、107–109、146–147；#24段22、24–31已有公式/期限/算术均值，来源绑定已放入原树SIGNED-DEFINITIONS.md，SHA7e1e87fec0ef8f6484923585a45a5f9a59ceb47c0b80260c4e8c7a2e051649b5。

不得无条件将下单/排程标为公式未绑定；完整且适用的已签原定义应计算。不得把“到统计日期”的状态公式静默替换成完成时间公式。原文09-07是**发布日期筛选边界**，不是可自行推广的滚动期次规则。新期次/G01、归属G02、零分母/平均成员G03、退货作废G04仍待核；仅影响依赖该规则的结果。可单独显示完整确定的行/物料结果，不能以确定子集冒充完整部门率。缺字段/历史/日历/页集为unknown，合法零为value=0。

采用原ID只读路径与default-off开关；同一snapshot_id/hash串联计算、页面、API、明细与audit。三指标、316、历史对账各有范围标签和独立验收。没有真实样本时只显示MOCK，不制作冒充真实的判例。

## 4 不改变的安全闸

原sealed intent/design/approval及旧attempt不改；没有任意state编辑接口；不改provider默认保护/生产consumer、鉴权、凭据、规则阈值、CI配置或全局环境。不授予ff、生产、真实数据、付款、外发或专业代签。候选机制须实际CI及独立Luna审查通过后才可由其正式入口处理指定任务；不通过不能借“恢复”继续业务。
