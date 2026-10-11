# O3 P4 启动权限补充与同轮首次诊断续跑

状态：具体供审批件；未新生成、未运行runner。只补启动入口，不改正式冻结脚本。

## 已消费事实

原计划 SHA B4220068BB73C6DC3D4372E025A6BC53F4562762058FF7EF8F28BBBBC6F7C43E 已获本轮第4项A。正式生成器单次 exit1，在git读取指定Native HEAD时内部exit128，发生于新UUID创建前；runner和180秒诊断调用均为0。根精确Test-Path为true，Native .git指向主仓 worktrees/zhuopin-ai18；同一固定Git读HEAD在默认sandbox下Permission denied，限定 require_escalated 后exit0、HEAD精确为0ad830234af70585d359df23123973eceeace3a3。因此没有候选丢失或HEAD漂移证据，启动权限是此处已证阻塞。

## 精确新增批准范围

原计划要求生成器失败即停、一次调用，不自行重试。此次请求授权：原同轮首次180秒诊断预算未消费；允许不变正式生成器再调用一次，并在全部身份/13marker/ignore门通过后首次调用不变runner。两条命令通过Codex的 `exec_command sandbox_permissions=require_escalated` 执行，仅释放本次明确操作所需sandbox权限；不改Windows权限、配置、hooks、全局路径或运行环境，不安装软件。

冻结生成器 `docs/superpowers/plans/o3-p4-substage-diagnostic-1010/generate_p4_substage_copy.py` SHA 4AD3BE7691D4DA768720F130AA79CBEDE0FAF53E9B4372048FF4442D31849E8E；runner同目录 `run_p4_substage_once.py` SHA 0026B2FB6D23271FE6B1C5B0F5FF7ED11EE2B7C2004C3AFF572A258906DB9320。两件字节不改。

1. 指定隔离Python `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe` SHA760E6890B3DB606715075976C3793BFCE092DC8BDF30D48C56CFCACCFDD07F25、Python3.14.5，带-B；正式生成器仅新增一次调用，`--candidate-root 'C:/Users/Paul Shao/.codex/worktrees/o3-recovery-fix-1006/zhuopin-ai'`。新UUID只由生成器创建，旧已消费16ec…仍禁用。
2. 新manifest/source SHA/闭包/EOL冻结配对、恰13条有序markers、ignored身份门全部通过后，使用同Python-B正式runner绝对路径及此唯一新UUID路径；只调用一次，180000ms。cwd、pwsh→powershell选择、四个条件LAN GET、原Windows Job归属和自身树清理、本机stdout/stderr留存均按原已批计划原封保留。
3. 不人工读取或向终端显示raw stdout/stderr正文；冻结runner仅按原计划解析stderr marker、读取stdout计算既定metadata字段，根与审阅者只查看metadata/markers/计时有效性。失败/超时停止保留，不重试、修脚本或跑第四pytest，不ff/push/生产；Job归属失败只按冻结runner清理自身挂起PID。
4. 新批准另建补充消费件，保留原失败消费及证据。若automatic approval review拒绝限定入口，停止依赖动作并报具体理由，不换入口绕过。

## 前置证据和独立审查

失败事实与限定只读HEAD结果记录于 reports/four-approvals-1011/start-amendments-177cccee-382f-4679-9569-6a0b730e38d0/failure-facts.json，SHA0B5808615A9E4E313E438FB00FE9330D9CC65D8E7C37A8DB667B8C25C24CF2C2。独立静审只核此新增调用/权限范围与原冻结脚本、budget和副作用一致；不生成或运行诊断。本计划正式登记并绑定SHA后须本人明确答A才执行。

## 正式供审登记

2026-10-11T07:42:30.1635680+08:00（上海）由根逐字节搬入上文独立静审版本；上文输入SHA 6AC80C6F685047862A4F59A5B45BFC284243163B8A9DFD98B1B431961B74DA69；独立静审 reports\four-approvals-1011\start-amendments-177cccee-382f-4679-9569-6a0b730e38d0/o3-independent-review-v2.json，SHA E272EC5FDF49D66AD515D1E15DCFC9C71EAE9599DF550837DD357D473F7160D8，passed/findings=[]。本登记段仅补身份，执行范围未变。仍待本人明确批准。
