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
