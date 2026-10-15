# Q9 原24文件实施的执行差量 v1

状态：供Shao Peishen批准；未创建Q9新树、认领产品写入或运行Q9产品测试。沿原#653及`q9-apqp-evidence-pilot-1012v2`业务记录，不新增业务task或恢复机制。

## 1 已批准范围继续有效

5A已批准design，8A已批准合成实现、定向测试和项目CI；官方§四296及`PC双实施与两项恢复批准执行-2026-10-12.md`均已核。原计划`docs/superpowers/plans/2026-10-12-q9-apqp-evidence-implementation.md` SHA256 `b4438c22b1dfb4396bda5ef5c5f4ee3f9ec43e6963977f79dde727fccc26e075`，冻结design HEAD `1df48365385cf3a2e1c436fbe77466caaae80cd2` / SHA256 `fce1a7c85a7c5414985c36b21fd3b38178c319524084fcfa32f9db2a7f7da3c5`；原集合SHA `3d0a51f4acc8e4e588690209e378a55b14019584844caa2f24586417516b4e6c`。原24产品/测试路径、单合成客户/项目、显式版本/定位、八例MOCK、G01–G06 PENDING与Q4独立结果边界不变，不重审设计或实施功能范围。

首片闭环：合成资料清单→证据版本/定位→候选追溯和差异/抽取不足→带理由的演示人工追加裁决/更正→可回读报告及审计。不作APQP通过/失败、阶段放行、专业签认或正式35场景认定；未知安全属性转人工，ASIL C/D抽取前退出。

## 2 已核实执行阻塞

2026-10-15官方Workflow status返回busy=false、delivery_accepted=false；先前empty_changes，后续实现timeout，旧尝试及资料均保全。原固定树`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai`的Git只读HEAD/status均Permission denied，不能据此说旧树为空或没有部分成果。未重试绕过、改ACL、清锁、恢复Guardian或改旧状态。

8A第4–5节明确固定原树/Guardian/独立Luna执行合同。1013当前串行机制已实际合入并回读；本差量只解除本项旧合同的执行位置/方式限制，保留原设计、产品边界和验证要求。FI14的§317差量不自动套用于Q9。

## 3 唯一请求的执行差量

由1015主会话在仓库内ignored `reports/q9-pc-mvp-1015/worktree`创建独立分支`codex/q9-pc-mvp-1015`，固定创建时主线HEAD并留证；按原24路径直接分片实现、功能RED→GREEN、针对性测试、必要回归、逐项目完整CI、普通本地检查点和主会话分离自查。不新增自动代理链/Guardian批次/业务task，不修改机制或SC2，不触碰招聘项目。

原树、未提交成果、Workflow尝试/claim全部原样保全；不强行将旧状态标成功。可读Git设计和同字节原计划复用；受限部分保留“未核”，不冒用旧测试数。证据、输入副本、MOCK运行数据和临时演示runner仅存本项ignored reports；不改共享平台、门户注册、CI矩阵或24路径外产品文件。

复用已批Blueprint路径`/quality/q9-apqp-evidence-review`提供临时本机loopback演示；这是本项可访问验证，不新增永久场景端口、计划任务、对外监听或生产服务。FI5/FI14已有入口保留。若可用闭环必须扩大24产品路径或引入新依赖，停对应项报精确差量。

## 4 影响和边界

A（推荐）：批准本v1第3节执行差量，沿8A原24文件实施；收益为直接交付可操作的合成PC候选，旧受限成果继续保留未核。B：保留原执行合同，Q9继续等待旧树/Guardian前置；本会话不修机制。

不含ff、push、生产/门户发布、真实OEM或客户数据、扩大账号/数据权限、凭据或安全设置、删除/清理旧资产或锁、专业代签、阶段放行、外发。合成验收不替代真实/专业验收。获批后按原任务#653正式认领并核文件归属，直接实施，不再逐片请求同一授权。
