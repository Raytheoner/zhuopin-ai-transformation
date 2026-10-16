# 326A实施与验收记录（2026-10-15）

冻结proposal/design/tasks/spec/计划及原批准hash不改；本记录在同一变更包内记录实际执行。暂不归档：浏览器实机验收与具体发布尚未闭合。

已完成1.1/1.2、2.1–2.5及3.1；3.2中正常HTTP真实件上传、受控模型、结果和实际下载/独立回读已完成，2026-10-16补齐桌面Excel打开及五表实机查看；浏览器手工选文件/下载仍未核。3.3检查点/R5/原任务回写完成；3.4发布准备继续，未作ff/push/生产/外发。

候选eae205cc194fe60d8303b56c503b82a7c34404f4；17产品/测试路径＋场景说明。Q2完整149通过、QD-A56完整旧证据复用；无过滤/skip。合成端到端两份不同内容给出可解释不同得分，防静态返回。真实39项含20语义项全填，84/B为动态比较结果，未硬编码；转人工、专业签认false。

证据目录reports/q2-real-document-pc-1015/：real-delivery-receipt.json绑定源/对象/实际下载hash/39-20及19-432-22-2-1302、9公式缓存/唯一有效审计1条；junit-final-01.xml绑定149；probe-receipt.json及两个业务operation记录固定Luna/high/零工具调用/未披露实际模型版本。一次评分＋一次引用修正，原值保全；后续恢复明确禁止新增调用。五表渲染生成并逐一查看；渲染进程结束1如实记录，不替代实际xlsx回读。

发布准备：基线62e6d71c→eae205cc；主仓现取e86366fa不是候选祖先，且工作区有其他会话修改，当前ff-only不可执行。先在已隔离范围保全候选及报告，实机段完成后准备干净整合版本及实际目标/回滚/冒烟，再集中提交具体发布批准。生产模型运行/真实身份接入及更多真实件不得由本机演示推定已授权。无新授权请求，已批部分已执行。

2026-10-16接续：Excel实机证据收据ui-acceptance-2026-10-16/receipt.json绑定下载件SHA256 202a999e0a997a586c6c023fb34281e0f88e1c5995e711c30f213107edd07a27与4张原生截图。五表逐页查看，原文件字节未变；没有新增模型调用。浏览器控制工具因URL识别不足停止，Shao Peishen明确稍后手工核验；该项责任和剩余范围写回原612/326，不以程序化上传替代。

Ruling：按用户最新指令，浏览器手工验收与质量反馈不作为发布准备的前置；最终发布仍保留对应实机/权限闸。现取主仓740f5bb9与候选分叉。仅提取原321A/323及326A已批准的Q2/QD-A共22路径到仓库内干净整合树；不将候选其他历史业务改动带入主仓、不覆盖主仓脏文件、不恢复旧Workflow。整合结果变更运行上下文后重跑Q2及QD-A完整回归；原模型评分与不变原文/Excel证据复用。

发布准备检查点（2026-10-16T07:30:20+08:00）：独立整合候选c8a31b049e27f5db3bedbbec09c6ef945b5ce36d，父740f5bb9，只含已批Q2/QD-A 22路径。Q2完整149/QD-A完整56通过，零skip；整合运行时复制同件成功对象回放、Excel/ZIP下载、唯一audit验链均通过，禁止新增模型客户端未触发。实际服务器仍原临时进程，未替换，最后健康HTTP200。§四329及release-preparation-v1-2026-10-16.md SHA256 ee4a27c96d08e2dcbb96226ee2eb80710dd4e8d2e435ec5a8eaa02377ddd8b9e集中供审ff-only＋产品push；主仓脏文件保全，生产可信身份/服务器模型条件和浏览器手核未闭。原326A功能未改，未ff/push/生产/外发。

2026-10-16T07:35:50+08:00补只读上线条件：LAN状态on；原Q2WebServer Running/SYSTEM、0.0.0.0:8098仍PID3640，webapp SHA878ce4a275cddc7f0d50d3218ddc9809971564a289fe78b52c68f8d98659d521，与10-08部署记录同。经实际C:/q2/.venv/Scripts/python.exe核Python3.14.5、健康200；Flask/Waitress在，pptx/PIL/openpyxl/xlsxwriter/xlrd缺。SSH账户PATH未找到codex，仅记录该账户可见性，不推断SYSTEM账号或模型权限；未调用模型/业务GET、上传/安装/改凭据/重启/写服务器。前两次PowerShell探针受控制台访问及CLI引号影响，原错误/exit1留存；最终Python stdin只读探针成功，不把工具失败当生产故障。原件production-readiness-2026-10-16.json、production-readiness-details-2026-10-16.json、production-readiness-runtime-2026-10-16.json及脚本均留在本任务目录，hash/最终结果入release-candidate-receipt.json。329冻结审批正文SHA未变；生产真实身份、依赖安装及服务模型通道仍非本次ff/push授权。

329A消费与执行前核验（2026-10-16T07:45:40+08:00）：Shao Peishen原答已保存approval-329A.json，绑定冻结发布v1 SHA256 ee4a27c96d08e2dcbb96226ee2eb80710dd4e8d2e435ec5a8eaa02377ddd8b9e，不重问。用git status --porcelain/rev-parse/ls-remote及22路径SHA回读核本地/远端master同740f5bb9、候选c8a31b04 clean且仍可ff祖先关系；但目标97项未净（含本线5项，其余或共享92项），依本件第3/4节未尝试merge/push，未代提交/stash/覆盖/reset/清理。未因批准放松前置，亦未重跑未变205测或新增模型。阻塞证据329A-execution-preflight.json列出路径与恢复步骤；主仓变干净后1015按现有329A接续，不重复审批。无后台恢复任务。

可独立推进的准备：production-dependency-inventory.json列出被已验本机环境实际使用的python-pptx1.0.2/Pillow12.3.0/openpyxl3.1.5/XlsxWriter3.2.9/xlrd2.0.2与Requires-Dist，任务xlrd既有wheel hash沿用。只作未来部署依赖核对，不是服务器已安装、兼容已验或新增安装授权；没有下载/安装包、触发模型、改服务/账户/权限或新外发。原候选、代码包、真实报告/审计和329冻结正文hash保全。

97项归属核验与§四330单项供审（2026-10-16T08:15:43+08:00）：按用户要求完成97状态项/123文件的登记、署名、任务和范围反查；85项精确匹配本轮官方§二回取，其余12项单列原件/任务/范围，未猜历史未提交作者。归属10组，逐项处置均原位保全；28迁移参考原作者未核、OP-1002-Z保全已登记且28/28原SHA未变；1010旧展示包12删除都有归档对应（11正文仅EOL差异、tasks有原收口记录）；两条规则追加原作者未核，不归1015改规则。Sweep Ready、上次结果0不代表各预登记可提交，未触发全仓Sweep或更改就绪状态。
原位123文件与22已批Q2/QD-A路径零交集；索引无暂存，实际read-tree --dry-run -m -u 740f5bb9 c8a31b04 exit0，索引前后SHA均0e31dccc7a299425141ffadb6c939a7c3444221df723707fd97858e58837e691；未尝试merge/push。report/official traces/protected-manifest/approval-binding-330.json均在本任务dirty-ownership-2026-10-16/。329A继续有效；仅新增供审openspec/changes/q2-real-document-pc-1015/dirty-target-execution-amendment-v1-2026-10-16.md第1–6节，SHA256 b606455eb7d22084d477e2fa09caa7521775fd0210bc95d21144613c0087140a，替换本次全仓干净前置为全局无暂存+22路径干净无类型/遮挡冲突+其他原位文件执行前后rawSHA/存在性不变。其他329A条件不变、无全仓清理/代提交/机制修改；明确批准后连续按既有ff-only/正常push/有限同hash重制边界执行。原205测代码/依赖未变，不因台账重跑；无新模型/服务器写入/安全设置或外发，浏览器本人手核及专业签认仍未闭。

330A消费、有限同hash重制与正式代码push（2026-10-16T08:27:53+08:00）：原文批准及SHA绑定保存execution-330A/approval-330A.json；329A继续有效，未重复审批。执行前发现Sweep已落本线5个文档提交，master/origin同15e5c606；差量仅R5、implementation、原329/330供审文件及业务队列，不含其他产品/依赖。在本任务仓库内release-330A-worktree（codex/q2-release-330a-1015）按原22文件rawSHA复制并正常提交，新候选e4c6da8d53f02972bc4278ab8e291a18e6ce7e52，父15e5c606f740c2a153094f48c6a17481c8c6b427；22 rawSHA/逐Git blob和Q2/QD-A/平台完整Git树与c8a31b04全同，净差22路径，旧205测按已批准边界复用，未重跑未变代码。
既有共享锁内先取原97项及新增差量的124路径hash/大小/存在性、未跟踪/删除状态保护快照，确认索引无暂存/无未合并、22路径无交叉/遮挡/父子类型或符号链接逃逸，实际read-tree --dry-run -m -u exit0且索引SHA不变。正常git merge --ff-only e4c6da8d后先保护回读，再正常git push origin master:refs/heads/master exit0；2026-10-16T08:26:22+08:00 ls-remote确认origin/master与本地master同e4c6da8d。ff后和push后保护均124/124原位字节/大小/存在性及原状态相同、产品无工作树diff，未stash/重建删除现场/清理/代提交他人。逐阶段证据execution-330A/prepared.json、protected-before.json、after-ff.json、after-push.json及git-push-result.json；随后本线原行/R5写回属于授权记录动作，时间段与Git保护检查分开。原演示、旧树、真实件与审计均未替换，无新增模型/生产/权限/安全/外发。
剩余：浏览器本人手核、生产可信身份/单客户访问接线、服务正常账户模型通道、服务器5依赖兼容及实际部署、专业签认/全10件校准。继续Q2本线适配与部署准备，不等质量反馈；本次ff/push完成不销原612、不归档326业务任务、不宣告生产或业务验收通过。

代码push后继续的生产接入只读准备（2026-10-16T08:35:34+08:00）：独立HTTP探测现网Q2:8098 ping200、门户:8090 ping200、公开登录选择页200，OAuth与mock登录链接同时存在，未发起登录/OAuth回调或读取凭据。证据execution-330A/public-readiness-live.json。多步SSH/文件元数据探测曾被项目读侧钩子以无法解析读取拒绝，未绕钩子、未改工具；改用不读文件的公开HTTP读取获得上述有限事实，生产门户代码指纹仍未取得。
本仓源码逐文件hash及分界见execution-330A/post-push-readiness.json：Q2运行器仍loopback/local:1015及同件白名单；网关仅首页路由，过滤Cookie，尚未注入可信个人身份/屏蔽调用方身份头，Origin/Host/会话与30s代理对600s有界模型行为需要原维护方契合。不能只改host或用共享口令/调用方X-Zp-Identity放真实件。原240官方行已有OAuth配置落位历史及回调记录，不把旧CLAUDE的凭据尚未申请当现况，不修改240或认领门户/机制。
最小恢复顺序：门户原维护方按既有载体验真SSO并给出可信个人身份、单客户授权与会话代理合同；1015再围绕已有Q2访问回调设计最少适配并绑定文件/测试，实际新增实施一次集中审批；服务正常账户模型通道和5库兼容核清后形成可审部署件再走具体生产闸。无复制凭据/模拟SYSTEM、无安装或服务重启，不因质量反馈停止已批构建。当前330只完成代码ff/push；生产、浏览器本人手核、专业签认与10件校准仍未闭。

Q2生产接入四类归属核验及§四331一次供审（2026-10-16T09:04:10+08:00）：用户要求继续准备、已有授权直接做、不争写。已读原冻结design/tasks与329/330边界；原162官方归档、197done、240已含凭据落位/回调历史，当前digest及1013/1011只读任务未发现Q2门户接入活跃执行者。候选责任分配写“建议/待认领”，未假定1013/IT已接手，未恢复已完成行或给其他任务发消息。
已获只读现网任务/监听身份/固定源码SHA与公开HTTPS入口：Q2实际SYSTEM，门户实际Administrator，网关任务Ready不能当进程未运行；四核心源LF与主仓一致。公开HTTPS正常证书200，OAuth start只解析302未跟到企微，callback仍http且无8443。来源reports/q2-production-intake-1015/{runtime-ownership,listener-identity,public-origin,ownership-evidence}.json。未读.env/auth/config凭据、未登录/重启/改账户。此前C:/q2/.venv缺5库只证明被测解释器，不自动算监听进程sys.prefix；同账户模型及实际环境仍是外部前置。
已直接准备8项原已测依赖的Win64/CPython3.14wheel，逐包PyPI SHA及活跃传递闭包通过，冻结离线ZIP SHA256 4a7f5cb182cf72f93641b7828dc8434de7448cba47713982f048ad039de5118a，12,379,981bytes；未安装服务器/共享环境。项目隔离Python无pip时未补装pip，改用stdlib读取公开元数据/下载同版本wheel。首次新增范围网关基线实跑84passed/0skip/exit0，JUnit在gateway-baseline.xml；旧Q2/QD-A205测代码不变未机械重跑。Q2不存在受控ps1部署文件已由rg--files核名，未绕过两次不存在路径的读取拒绝去找旧分支脚本。
一次设计/实施包已冻结openspec/changes/q2-real-document-pc-1015/production-integration-v1-2026-10-16.md第1–6节/D1–D8，SHA256 35973d8e2cd4cb26626568d6e1a60b05ab358c1ae278e5653a6997d04f900257；1015仅Q2精确17文件，门户原维护方6文件需先承接；Q2独立真实OAuth用途凭证合同避免旧mock30天Cookie冒真，不关闭全局mock或改新凭据/角色。申请现有1013会话双向内部协调及正常服务身份至多1合成Luna/high探针（90s，零工具/真实数据，失败不重试），不是新SYSTEM任务或账号/CLI安装。包内已有文件/新增路径当前清洁，未写产品。实际候选未形成，不泛批新ff/push/生产或外发。原612/R5及本线§二登记，质量反馈不列前置。

331A明确批准消费（2026-10-16T10:23:28+08:00）：原文及冻结SHA35973d8e2cd4cb26626568d6e1a60b05ab358c1ae278e5653a6997d04f900257存reports/q2-production-intake-1015/approval-331A.json；Q2 17路径由1015隔离串行，门户6路径待1013协调原维护方先认领。允许既有会话双向内部协调；不派新代理/审核链或改对方模型。合成探针最多1次，正常服务账户/既有通道尚未证，暂未消费；不新建SYSTEM任务冒测。原331冻结正文不改，原612/331保持partial；新ff/push/生产/真实评分/CLI安装/账号凭据权限/外发不在范围。


331A检查点与331B认领（2026-10-16T11:00:08+08:00）：Q2精确17路径已实现，隔离候选55f5d55ca0cb65a20b73d3e5f080b0f99da4652e，完整pytest200 passed/零跳过（q2-full-03.xml）。初轮198通过/1竞争失败及稳定RED保留；最小修复状态快照后worker退出误报中断，不重放模型。331B已从1013实际用户消息回读（source_user_message=01a142a4-d43a-7e83-b9ae-1880fd84e468）；门户六路径现由1015在同树串行认领，旧197/done保留，不再等待原维护方。先完成Q2离线包/DryRun/缓存回放，再进入门户D2–D3；不扩文件/权限映射。正常SYSTEM入口、CLI及8库实际环境仍未证，探针0/1，未新ff/push/生产/真实评分/外发。证据reports/q2-production-intake-1015/approval-331B.json及progress.md。

331A/B候选交付（2026-10-16T11:24:35+08:00）：8ca9d627a52d1283b5f7c213a2acde2ff4f46a52，精确23路径、完整355测零跳过；Q2包SHA44740b0a15f9dee160ab1a2da376c769158566cc41fc9d8a20e2da7c0570e650，联审包SHA12ad3c566166196c56f01ecfefc54221899e27962e533a8bab1b255548125f97。原612/R5留真实前置，candidate-delivery.json记测试/代码hash/恢复。合成接缝与原件缓存回放均0外部模型，原store/audit保全；正常SYSTEM入口、现有CLI及实际生产私有环境尚未证，探针0/1。无后台/活动占写，未新ff/push/生产/账号凭据变更/评分/外发；不宣告业务验收。文档最后提交不改变测试代码，依照D7复用绑定回归，不机械重跑。

1013运维入口补查回执（2026-10-16T11:31:12+08:00，原612/§331）：近期Codex会话与正式队列digest未找到新的SYSTEM现存合规Codex入口或模型回执；这是已查范围的未命中，不推定全机无CLI。SYSTEM的Q2服务计划任务不能代算模型调用入口，Administrator SSH也不能代算SYSTEM。责任缺口仍为现役Q2运维/IT提供正常入口、现有CLI绑定及实际私有8库/模型通道回执，尚未确认承接。D5继续0/1，不改写/重放SYSTEM任务、不安装/登录/复制凭据或换账号；候选8ca9d627与355测不变，无新ff/push/生产/评分/外发。证据reports/q2-production-intake-1015/operations-reply-1013.json。


正常SYSTEM通道查清与§332供审（2026-10-16T12:16:28+08:00，原612）：实测Q2WebServer/SYSTEM→start-q2.ps1→C:\q2\.venv；SSH下该绝对解释器8锁定库缺7，非SYSTEM导入证明。指定8个CLI位置未命中、无现成模型任务；平台53文件逐SHA同候选。原成功CLI事件observed_model=null，当前D5非空条件会阻断；不伪造观测、不消费探针。无认证API探路TimeoutError仅属SSH该URL，不推定Codex后端/其他身份不可用，已停止重试。离线CLI+8wheel运行包346503108 bytes/SHA60e92275bfcf7fa75965b81b3be855b9db0ca0f4c8f85701b95ac60168b5bef7，解出版本/SHA通过，无秘密/真实数据，未安装。推荐陈承运维接口（IT部#13历史操作依据，尚无本次承接）；公司服务认证/正常出口需其协调真实管理员。§332绑定openspec/changes/q2-real-document-pc-1015/normal-system-unblock-v1-2026-10-16.md第1–5节/SHA12ddf7787850198fccf83803ad92fdc8e543320dee1e7f9d0c751d3cdf9dd151，集中申请Q2精确10路径、旁路环境/精确CLI/私有8库、新建本件SYSTEM一次核验及仅新profile ACL/运维服务认证、D5明确CLI合同且observed保持null；均待答，不新增API计费/外发/真实评分/ff/push/生产。候选8ca9d627/355测及旧现场保持，D5=0/1。详细证据normal-channel-gap-summary.json。
