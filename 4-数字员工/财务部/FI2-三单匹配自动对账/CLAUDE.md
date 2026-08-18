# CLAUDE.md — FI2 三单匹配自动对账（场景级进度笔记）

> 本文件是 FI2 场景的本地记忆/进度笔记，与 FI1/采购(SC*)/质量(QD*)场景分开。
> 项目级上下文见仓库根 `CLAUDE.md`；FI2 规划权威见全景规划 §2.1.4 FI2 块、实施计划 §一财务表、
> 跨场景前置数据总表 FI2 行、`1-转型规划/FI2-三单匹配口径-mock备料.md`、
> `1-转型规划/FI4-三单匹配-就绪清单与MVP细化.md`（编号 FI4 即 FI2 内容，同一份口径）。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）；排期若变只在此记并提示 Paul 通知 Cowork。
>
> ✅ **v8 核对面板已发布上线（2026-07-31，队列 #182/#183）**：唐燕萍回件权威规格书（v8 改造
> 指令及效果图）驱动的面板重建——六段式平铺 → 结论看板 + 展开/并拢主表（10 列窄表，点击行号
> 展开三张单据卡片 + 六个校验块），免责声明按其给定文案上线（#183），⑤"超差不代表一定是记账
> 错误"提示语并入"四维匹配"校验块、仅 PO↔AP 有差异时底部自动带出。**只改 `fi2/webapp.py`
> 展示层，`match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/
> `config.py`/`models.py` 一行未动**——判据/容差零改动。v8 规格新增的 OCR 字段校验/重复发票
> 检测/税率合规/PO变更检测四维，本引擎均未实现（税率合规·重复检测明确属"二期"、OCR 选型未
> 就绪、PO变更检测已于队列 #80 评估后明确不采纳），面板如实标注"🔷 二期未接入"灰色徽标，不
> 伪装已判定。地址不变：http://192.168.100.51:8094/ 。详见 §「部署状态」v8 段。
>
> ✅ **面板真实数据接入·轮1已发布上线（2026-08-03，design D19，队列 #214/§四#43）**：面板
> `u9c` 模式此前从未被端到端驱动过——现已接线真实 PO（`Purchase/Query`）+ 真实 AP（`AP/Query`），
> 发票段从"无条件如实报错"改为"若场景内已备好人工誊录小样（`data/real_round1/invoice.csv`，
> 财务红色数据，`.gitignore` 覆盖不入库）则读取，未备好维持现状 fail-loud"，面板显式标注
> "⚠️ 发票为人工誊录小样，OCR 未接入"。**判据零改动**：`match_engine.py`/`result_classify.py`/
> `price_check.py`/`config.py`/`models.py` 一行未动，只改 `feed_source.py`（新增
> `invoice_sample_dir` 可选参数）与 `webapp.py`（接线+标注）。真实端到端验证：6 组真实 AP 号、
> 10 料品，3 例 AP-PO 单价超差与 round-1（D18-f）逐位精确一致，证明接线正确、判据未变；详见
> `1-转型规划/FI2-round1真实验证报告-2026-08-03-面板轮1.md`。真实部署 `.51:8094` 冒烟通过
> （见 §「部署状态」D19 段）。发票源仍是人工誊录小样，非规模化自动直读——**这是第一轮**，
> 规模化路径仍是 OCR（队列 #59/#82/#127 round-2），本轮不改变该依赖关系。
>
> ✅ **面板 6 项显示问题已修复上线（2026-08-05，队列 #250）**：唐燕萍用轮1的 6 个真实
> AP 单号跑通后回件"判定逻辑结果与预期一致，仅面板显示 6 处问题"——PO 卡片"不含税
> 金额"/"价税合计"写反、PO/AP 单价未改未税、AP 单号·行号误显示 PO 行号（根因＝
> `feed_source._map_u9c_ap_row` 从未捕获真实 `DocLineNo`，只映射了 PO join 用的
> `SrcPOLineNo`）、发票号与 AP 行号多值折叠时裸露"+"、⑥行级映射缺 AP 行号且发票号
> 重复。**只改 `fi2/webapp.py`（新增 `_po_untaxed_gross`/`_ap_real_line`/
> `_sorted_unique`/`_u9c_ap_real_line_no` 等展示层辅助函数）+ `fi2/feed_source.py`
> （新增 `raw_ap_rows()` 只读访问器）**，`match_engine.py`/`result_classify.py`/
> `price_check.py`/`recon_report.py`/`config.py`/`models.py` 一行未动。**判定口径
> 零漂移三重证明**：判定文件 git diff 为空；真实复现 KPI 计数 5/2/3（10 项料品）与
> 08-04 那轮完全一致；她举证的 `ZPCG20250902009` 现显示的未税/价税合计与其给出的
> U9 真值精确一致。真实部署冒烟过程中额外发现并修复两处次生问题（⑥重写引入、非
> 她原始清单）：链条格式对已含"AP-"前缀的 `ap_no` 又叠一层前缀；多值"/"拼接未去重
> 未排序。详见 §「部署状态」2026-08-05 段、队列 #250。
>
> ✅ **发票源改道·税务导出 Excel 接入已建成（2026-08-07，队列 #295，openspec 变更包
> `fi2-tax-export-ingest` 已 apply+archive，独立 worktree
> `fi2-tax-export-excel-d3938b`）**：唐燕萍 2026-08-04 拍板 OCR 方案作废（8 张发票货物
> 名称/规格精确匹配仅 65.8%），改税务系统导出 Excel；2026-08-06 回件把落盘目录
> （`.51:D:\airead`）／导出责任人时点（李姣龙，工作日 10 点前）／新增文件判据（我方自记
> 已处理清单，不看文件名/mtime）／完整性校验口径（漏票/跨期/红冲作废三维**先都不设**，
> 她的选择非遗漏）四个决策点全部定死，并把她做 65.8% 比对用的 8 张真实发票导出件放入
> 该目录。**开工第一步真实探测即推翻原计划假设**：#249 局部定稿假设的"以发票号字面
> join AP.InvoiceNo"经真实核对证伪——`AP/Query.InvoiceNo` 实测 5/6 只存后 8 位截断值
> （非全串），且该字段服务端过滤是 CONTAINS 语义非精确匹配（哨兵值验证过），改用「数电
> 发票号码后 8 位查询 + 客户端 suffix 二次校验」，8 个真实样本 **8/8 唯一命中正确
> ap_no**（含 round-1 因 302 重定向/182 行合并大票而失败的两单，本次 Excel 路径天然
> 绕开两个失败原因）。**新增 `fi2/tax_export_ingest.py`**（Excel 解析 + ap_no 反查 +
> item_code 反查——用已确定的 ap_no 反查该 AP 单行项目，按(数量,含税单价)唯一匹配时
> 赋值我方真实料号，命中 0/≥2 行不猜测、留痕待人工核对 + 内容哈希已处理清单幂等）+
> `scripts/ingest_tax_export.py`（手动触发 CLI，Q3 默认(a)不挂定时）+
> `ZpConnector.get_ap_lines_by_invoice_no`（平台连接器新增方法）。**`feed_source.py`/
> `match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/
> `config.py`/`models.py`/`webapp.py` 全部零改动**——产出的 `invoice.csv` 走既有
> `invoice_sample_dir` 通道原样消费。**真实数据如实观察（不预设通过率）**：ap_no 反查
> 8/8 唯一命中；item_code 反查 40/198（约20%）唯一命中，未命中集中在 182 行的合并结算
> 大票 AP-2026050057（151/182），正常大小发票（sample 1/3/4/5/6）仅 6 行未解析、
> sample 2/7 100% 命中——低命中率不是 bug，是「同一 AP 单下多个数量+单价组合易重复」
> 这一真实数据特征，已在 design 登记为已知风险，未解析行不猜测直接排除+留痕。**全量
> 回归零漂移**：FI2 128 passed+7 skip（原107+7，+21，`match_engine`等六个判定/展示
> 文件字节级零 diff）、平台 262 passed+1 skip（原259+1，+3）。**真实部署 `.51:8094`**：
> `sync-to-server.ps1` 推送成功+服务器 venv 补装 `openpyxl`（sync 脚本不自动重装依赖，
> 仅首次 `deploy-server.ps1` 会，已登记）；冒烟三件套全绿；**在 `.51` 服务器本机（非
> 笔记本、非本地拷贝）直接对真实 `D:\airead` 跑摄取 CLI**，产出与本机验证完全一致
> （40 行解析成功）+ 二次运行验证幂等（0 新处理文件）+ 中文字段 UTF-8 字节级核验（"套"
> 编码正确，SSH 终端显示乱码纯属编码显示问题非数据损坏）。产出 `invoice.csv` 已用
> `FeedSource` 直接验证可被既有判定管线消费（`linked=40/orphaned=0`，ap_no 100% 有效）。
> **未做（如实登记）**：本次未改 `webapp.py`，故摄取产出物**未接入面板默认展示路径**
> （面板 u9c 模式仍固定读 D19 的 `data/real_round1/`）——只交付摄取能力本身，是否/如何
> 接入面板默认路径留待下一步评估；第 2 层（定时扫描+失败告警）按 Q1 默认(a)后置未做。
> 详见队列 #295／#249，openspec 归档 `archive/2026-08-07-fi2-tax-export-ingest/`。
>
> ✅ **第2层（定时扫描+失败告警）+ 摄取产出接入面板默认展示路径已建成（2026-08-10，
> 队列 #82，独立 worktree `layer2-scheduled-scan-alerts-fff92e`）**：领取 #82 剩余范围
> 两项（08-10 唐燕萍首次真实按约投放后由 CC 回填标注）。**① 第2层**：新增
> `fi2/tax_export_scan.py::scan_once()`——原样复用 `tax_export_ingest.ingest_directory`/
> `write_invoice_csv`（判据零改动），新增两件事：文件级失败判定（`sheet_missing`/
> `field_missing`/`parse_error`——今天 #82 sheet 名事故正是这一类，12 个真实文件
> 100% 失败但手动 CLI 退出码仍是 0、无人会注意到）与行级诊断（`ap_no_zero_match` 等，
> 真实数据约 89% 属预期噪声，见队列 #82 08-10 回填）严格区分，只对前者告警；命中时经
> 既有群 webhook 逃生通道（`WECOM_WEBHOOK_URL`）通知 Shao Peishen——按
> `3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2
> 判据（本告警主题是"机制自身故障"非业务内容），不经 aibot、不触达唐燕萍；webhook
> 未配置时静默跳过（不阻断扫描），同 `alert_webhook.py` 既有降级方式。新增
> `scripts/scan_tax_export_scheduled.py`（计划任务专用入口，与手动 CLI
> `scripts/ingest_tax_export.py` 并存不改、共享同一 `out-dir`/`ledger`，谁先跑到都一样）
> + `register-tax-export-scan-task.ps1`（`.51` 本机运行，`Fi2TaxExportDailyScan`，
> 每天 10:30，SYSTEM+ServiceAccount，同 `Fi2WebServer` 既有先例）。**② 摄取产出接入
> 面板默认展示路径**：`webapp.py` 新增 `_resolve_invoice_sample()`——`u9c` 模式发票段
> 固定目录解析优先读 `data/tax_export/invoice.csv`（税务导出摄取，规模化路径），仅当
> 缺失/无产出时才回落 `data/real_round1/invoice.csv`（D19 人工誊录小样，仅 8 张样本、
> round-1 验证专用），两者皆缺仍 fail-loud（行为不变）；报告页新增对应 banner 如实
> 区分标注"税务导出摄取"或"人工誊录小样"，不混淆两者，判定口径
> （`match_engine.py`/`result_classify.py`/`price_check.py`/`config.py`/`models.py`/
> `feed_source.py`）一字未动。**新增 gitignore 规则**：`data/tax_export/` 此前未被
> 任何既有规则覆盖（含真实 ap_no/单价/金额，同 `data/real_*` 红线，此次补上）。**测试**：
> 新增 `test_tax_export_scan.py`（10 用例，全程假连接器/假发送函数）+ `test_webapp.py`
> 新增 4 用例（税务导出优先/两者皆备优先税务导出/税务导出缺 csv 回落/两者皆缺
> fail-loud），另有既有 5 处 round-1 测试补做 `_TAX_EXPORT_DIR` 隔离（防止本地
> worktree 真实存在 `data/tax_export/invoice.csv` 时产生非确定性）。全量回归零漂移：
> FI2 143 passed+9 skip（原129+9，+14）、平台 289 passed+1 skip（不变）。
>
> ✅ **`.51` 部署+计划任务注册+真实端到端验证已完成（2026-08-10 续，Shao Peishen 回 LAN
> 后接续）**：**① 部署**——`sync-to-server.ps1` 推送成功，`Fi2WebServer` 新进程存活
> （`NEW_PID=3308`），`/api/ping` 200。**② 修复一处新坑**：`register-tax-export-scan-task.ps1`
> 首次远程执行报 `ParserError`——复现 CLAUDE.md 已知坑"`.51` 内建 Windows PowerShell 5.1
> 按 ANSI 读中文语法错"，本文件新建时漏加 UTF-8 BOM（`deploy-server.ps1`/
> `sync-to-server.ps1` 均已带、本行新增件唯一漏掉的一处）；已补 BOM、新起 commit
> `75d7116`→rebase→push（`7ff9865`），重新 scp 单文件到 `.51` 后注册成功。**③ 计划任务
> 真实验证**：`Get-ScheduledTask` 确认 `Fi2TaxExportDailyScan` 状态 Ready；
> `Start-ScheduledTask` 手动触发一次，`Get-ScheduledTaskInfo` 确认 `LastTaskResult=0`
> （成功）、`NextRunTime` 已排到次日 10:30；直接跑 CLI 二次确认幂等——20 个文件（8
> round-1+12 真实批量）全部命中已处理清单跳过，0 新处理、0 新解析行。**④ 面板真实
> 验证**：真实 POST `/run`（u9c 模式，`ap_doc_nos=AP-2026070071`，真实数据）——报告页
> 确认渲染"发票=u9c+税务导出摄取"标签 + 对应 banner 完整文案，未出现"人工誊录小样"或
> 报错，KPI 卡与真实数据量级吻合（3 自动通过/3 微差消化/大量 BLOCK退回，对应
> `invoice.csv` 现累计 3000+ 行）。**⇒ 摄取产出接入面板默认展示路径已在生产环境验证
> 生效，第2层定时扫描机制已上线运行。**
>
> 🔴 **源头断供检测已补齐——"文件没来"此前完全沉默，实测已沉默 7 天（2026-08-17，
> 队列 #82，独立 worktree `followup-dispatch-apply-25679f`，commit `8ac00ac`）**：本轮
> 领取 #82 时派单前提是"她每日投放、我方无定时触发、漏取一天积压一天"，**取证结果
> 与之相反、且两半都反了**——⑴ 我方定时触发早已上线（08-10 建成部署，08-17 当日
> 10:30 照跑、`LastTaskResult=0`、`NumberOfMissedRuns=0`）；⑵ **停的是源头侧**：
> `D:\airead` 最新文件停在 2026-08-10 13:11，此后 08-11/12/13/14/17 共 **5 个工作日
> 零新投放**。**交叉验证排除了"处理后被移走"这一可能**：ledger 20 条与目录 20 个文件
> 精确一致，`invoice.csv` mtime 停在 08-10 15:34、3110 行未变。**⇒ 真正的缺口不是
> 派单件说的那个，而是它的对偶且更隐蔽的那个**：第 2 层只覆盖"文件来了但摄取不了"，
> 对"文件根本没来"完全沉默——无新文件时扫描退出码 0、零诊断、零告警，机制看起来
> 一切健康，**实际上整整一周无人知晓**。**本轮补齐**：`tax_export_scan.py` 新增
> `detect_source_silence()`——以 ledger 中最大 `processed_at` 为锚（**零新增载体**，
> ledger 本就逐文件记录处理时刻，是现成且唯一的真相源），距今超 N 个工作日仍无新
> 文件即告警，阈值默认 **3 个工作日**（`--silence-workdays` 可调）。**三条边界**：
> 只在工作日判定（周末空扫不告警，她的投放口径本就是工作日）／空 ledger 不算断供
> （"还没开始"≠"停了"，性质不同不混用同一条告警）／有新文件即证明源头活着，绝不
> 判断供（两类告警互斥，文件级失败优先）。**CLI 退出码语义分化**：`0`＝正常，
> `1`＝我方机制出问题（查代码/连接/目录），`2`＝源头断供（我方正常，需人去问源头
> 一声）——两者处置动作完全不同，故不共用一个非零码；告警正文亦显式写明"扫描机制
> 本身运行正常，是源头没有新文件"，不让读者误判为我方故障。**已知边界（如实登记）**：
> 工作日只按周一~周五算、不含中国法定节假日，长假后可能早报一次（宁可早报不可漏报，
> 早报代价只是问一声）。**测试**：`test_tax_export_scan.py` +15 用例（含真实事故复现
> ——08-10→08-17 恰为 5 个工作日），FI2 **158 passed+9 skip**（原 143+9）、平台
> 295 passed+1 skip；判定口径九文件（`match_engine`/`result_classify`/`price_check`/
> `config`/`models`/`feed_source`/`recon_report`/`webapp`/`tax_export_ingest`）
> `git diff` 为空。**真实部署 `.51` + 四关冒烟全绿**：`sync-to-server.ps1` 推送
> （`NEW_PID=8752`）／`/api/ping` 200／关键页 200（`X-Auth-Token`，口令未出服务器）／
> 真实 `POST /run`（u9c 模式，`AP-2026070071`）200 且报告页确认命中"税务导出摄取"、
> 未出现"人工誊录小样"、无 Traceback。**新检测已真实触发验证**：`.51` 上真跑一次
> ——正确报出"已连续 **5 个工作日** 无新增导出文件（阈值 3），最后一次成功摄取
> 2026-08-10T07:21:02Z"，与独立推算一致；真实退出码 **2**；`Start-ScheduledTask`
> 手工触发后 `LastTaskResult=2`，端到端链路（计划任务→CLI→检测→留痕）打通。
> ⚠️ **故 `Fi2TaxExportDailyScan` 的 `LastTaskResult` 此后将持续为 2 直到源头恢复
> 投放——这是有意的可见信号，不是故障**，见到 2 请按上方退出码语义处置（去问源头，
> 不必查代码）。**两处如实登记（非遗漏）**：① `WECOM_WEBHOOK_URL` 至今仍未配置，
> **故本告警与既有告警一样暂时发不出去、仅退出码可见**——该 URL 是 08-10 已登记、
> 至今未决的 Shao Peishen 待决项，现在有两类告警都在等它，紧迫性已升级；② **未代为
> 联系唐燕萍**——"她这一周停投了"是否/如何回话属对外动作，归 §四 #59 业务总线拍板，
> CC 不代决不代发；本轮亦未起草财务部#13（串行闸锁着，财务部#12 于 2026-08-07 推送
> 至今未回件）。详见队列 #82。
>
> 🔴 **⑤ `WECOM_WEBHOOK_URL` 仍未配置，本次刻意未擅自决定，如实登记为真实开放决策点
> （需 Shao Peishen 提供）**：核实 `.51:C:\fi2\.env` 无此项；核实仓库根 `.env` 现有的
> 唯一 `WECOM_WEBHOOK_URL` 其注释明写"采购内部工作群"（业务部门群）；
> `5-平台底座/.env` 的通用 `WECOM_WEBHOOK_URL=`（空）与三个
> `WECOM_WEBHOOK_URL_{FINANCE,QUALITY,PROCUREMENT}`（业务部门群，按
> `3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md`
> §2.3/§5.1 应退役）均不适用——**若把采购群或财务群 webhook 填进 `.env` 会直接违反
> 该决策件"业务部门不感受到 webhook 机制"的核心诉求**，本行告警对象应是决策件
> §5.1 所指"Shao Peishen 与陈承新建的运维群"，**该群 webhook 是否已建/其 URL 目前
> 不在任何 `.env` 中**，本次未获取到，未配置、未猜测。当前状态＝告警机制已建成
> 待命（webhook 未配置时按设计静默跳过，不阻断扫描），**功能完全等待该 URL 到位
> 即可生效，无需再动代码**。详见队列 #82。

## 定位（Paul 2026-07-07 拍板；口径 2026-07-09 v3 修正）
- FI2 = 财务/采购交叉场景，**2026-09 启动**。财务域 2026 年唯一按期落地场景（FI1 因需求变更暂缓封存）。
- 自动化等级 **L3**（建议/预警，人工确认，不自动过账）；L4（自动过账/拦截）待查准/查全率达标后另行晋级。
- **MVP 范围（v3 口径）**：FI2-1 数据准备与完整性校验 + FI2-2 **AP 单 vs INV 按料品汇总归集匹配**（PO 降级为 AP-PO 单价前置参照，非逐行匹配主体），四维＝料品/数量/未税金额/税额，结果分五类（🟢完全匹配/🟡金额微差/🔴明细错位/🔴数量金额不符/🔴无发票支撑）；**新增 AP-PO 单价强制比对**（堵配票改金额控制漏洞）。**"明细错位"检出仍是核心价值点**（总额对、料品间错位的成本失真场景，粒度从 PO 行改料品）。
- **明确不做·二期**：FI2-3 税率专项 / FI2-4 查重 / FI2-5 容差专项收口 / FI2-6 退单（初期仅拦截通知，闭环后置）/ FI2-7 考核 / FI2-8 学习。FI3（付款校验）为独立场景，不在本次范围。
- OEM 隔离【不适用】：FI2 读供应商/ERP 内部数据（PO/GRN/AP/发票/付款凭证），按根 CLAUDE.md §4 不强加 OEM 路由。

## Design 决策（Paul 2026-07-07 拍板 D2-D5 + 2026-07-09 v3 补充 D10-D13，详见 `openspec/changes/fi2-recon-mvp/design.md`）
1. **D2 临时容差口径**：数量 ±2% 或 ±N 个（两者取宽松者）/ 未税金额尾差 ±0.5 元/料品 / 税额尾差 ±0.5 元/料品（v3：原"税率必须一致"布尔维度改数值容差）。全部落 `config.py`，唐燕萍 R1-R7 规则草案（约 2026-08 底）定稿后只替换配置/规则版本号，不改引擎。
2. **D3/D11 五类判定边界 + 判定优先级 + "明细错位"算法（v3：粒度从 PO 行改料品）**：判定优先级（命中即停）＝ 无发票支撑 > 明细错位 > 数量金额不符 > 金额微差 > 完全匹配。"明细错位"＝同一 `ap_no` 下 ≥2 个料品未税金额差异同时超尾差容差、方向相反（一多一少）、且该 AP 单总额差异在 AP 级容差内——单料品超容差或同向超容差均不判错位（避免假阳性）。
3. **D4 L3 建议路由**：仅四类非完全匹配（金额微差/明细错位/数量金额不符/无发票支撑）强制标 `needs_review` 转人工；完全匹配类标 `l3_suggested_pass`（AI 建议通过，**未过账**），不强制逐笔人工，可批量抽查。
4. **D5 mock 五表结构**：`po_lines`/`grn`/`ap_lines`（v3 新增）/`invoice`（v3 改字段）/`payment`，接口通后 loader 换真实源、字段映射在接入层做，不改 `match_engine.py`/`result_classify.py`。
5. **D10 核对对象调整（v3）**：实际配票流程核对对象是 **AP 单 vs INV**（PO 降级为价格前置参照）；GR 保留加载，本次匹配数学暂不消费（供未来 FI2-1 完整性校验用）。
6. **D11 匹配粒度调整（v3）**：按 `(ap_no, item_code)` 双向聚合 AP/INV（天然吸收多对一/一对多/多对多），四维改「料品+数量+未税金额+税额」；迭代方向 AP 驱动（AP 是即将触发付款的一方，核验 INV 是否支撑）。
7. **D12 新增 AP-PO 单价强制比对（v3）**：独立模块 `price_check.py`，R7 容差占位 ±3%（唐燕萍授权定稿），报告聚合层合并——完全匹配料品若价格超差仍强制 `needs_review`（分类字段不变）。
8. **D13 黄金用例来源（v3）**：CC 按 v3 定稿文档自拟 strawman，唐燕萍 R1-R7 交付后批改，非专家定稿。
9. **D14 R1/R5/R7 定稿真值落地（2026-07-10/16）**：数量容差改精确匹配 ±0；未税金额新增比例备用 ≤0.5%；税额容差改按料品有效税率动态换算（非独立固定值）；**新增 R5 门禁**（整单差异总额分级 L2/L3，仅对"金额微差"生效，**Paul 2026-07-16 已拍板不扩大到"明细错位"，为最终口径**）；R7 真值 ±2%（外币过渡规则/方案一升级位因缺前置数据未实现，**Paul 2026-07-16 已确认明确推迟**，列 future-work，待清单到位后再评估）；新增料品编码归一化预处理（`item_normalize.py`，覆盖空格/全半角/括号/"-"vs"/"）。详见 `openspec/changes/fi2-recon-mvp/design.md` D14。

## 复用底座资产（照搬 FI1 场景模式）
- **数据接入三源统一接口**：`fi2/feed_source.py`，`data_source="mock"|"csv"|"u9c"`，切源不改匹配引擎；`u9c` 未就绪时抛 `zhuopin_platform.shared_tools.connector_errors.RealEndpointNotReadyError`（fail-loud，不静默回退）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（`scenario="FI2"`，append-only hash-chain，IATF 3 年）。每料品匹配判定写 `action="item_match"`（v3 改名，原 `line_match`）；L3 改判写 `action="l3_override"`。
- **L3 改判 CLI**：`fi2/confirm.py`（比照 FI1 `confirm.py`），v3 改判键 `--ap-no`/`--item-code`（原 `--po-no`/`--line-no`），`--reason` 必填、幂等、写审计。
- **金额脱敏纪律（design D7，延伸至 D12）**：审计/报告只记 `qty_diff_pct`/`untaxed_amount_diff_pct`/`tax_amount_diff_pct`/`price_diff_pct`（差异比例）与分类结果，**不落原始发票/AP 单价、未税金额、税额绝对值**；比对运算过程中金额参与内存计算，不持久化明细金额。

## 红线（建造时守住）
- 先 mock 跑通逻辑，再切真实库（`csv`/`u9c` 接口就绪后另行提交变更包晋档 2）。
- 每料品匹配判定/分类写平台 `audit`（append-only，金额脱敏，见上）。
- L3 门禁：四类非完全匹配 + AP-PO 价格超差 均强制人工确认，不自动过账；MVP 无 L4 自动执行入口。
- AI 结论恒为"建议/预警"，结案在财务人员——报告 disclaimer 显式标注"未过账"。

## 已知真实端点行为坑（ZpConnector/zp API，跨场景通用——SC8 等其他场景复用同一连接器时同样适用）

首碰新端点几乎每次都会踩到服务端的意外行为，本节汇总已实测确认的几类，供此后"首碰新端点"时对照排查（发现新坑随时补记于此，勿散落在各处进度段里找不到）：

1. **`AP/Query` 批量过滤参数 SQL 列名错误（2026-07-20 发现，07-21 IT 修复）**：`supplierCode`/`itemCode`/`invoiceNo` 三个过滤参数曾触发"列名无效"异常，只能 `docNo` 单查——**报错型**，至少能立刻发现调用方式不对。见 design D15-a①/D16。
2. **`Stock/Query` 的 `IsProdCancel` 拼 SQL bug（原厂已知问题，另案跟催）**——同为报错/异常类，非静默类。
3. **`POChange/Query` 过滤参数名不是 `docNo`，是 `PODocNo`（2026-07-28 发现，队列 #80）**——**静默返回全表**，是本清单里目前唯一一类"参数名传错、服务端不校验、不报错，直接吐回全量无关数据"的坑，比①②更危险：调用方若不主动核对返回条数/内容，会在毫无异常信号的情况下拿到完全错误的数据集当成功处理。探测时验证：传 `docNo=<任意值>` → 恒定返回全表 Total=2412（与传值无关）；传对 `PODocNo=<单号>` → 才正确过滤（如 `PODocNo=ZPCG20220815002` → Total=24）。该端点另有结构性限制：只到 PO 单据级（`PODocNo/ChangeDocNo/ChangeType/TaxRate/TaxAmt/NonTaxAmt/TotalAmt/ChangeFields`），无 `ItemCode`/`DocLineNo`/单价字段，给不出行项级最新单价——这也是队列 #80"R7 改用 POChange/Query 最新价"方案最终不采纳的直接原因，详见决策件 `1-转型规划/FI2-R7单价比对基准决策件-2026-07-23.md`（已作废勘误段）+ design D18-f 补充段。

**通用教训**：此后任何"首碰新端点"，除了验证正常路径返回的字段/信封结构，**必须额外做一次"故意传错参数名"的对照测试**——正常返回报错/校验失败是好现象（说明服务端会校验），恒定返回同一份"全表"或"默认值"则是危险信号（说明参数被静默忽略），必须在正式接入连接器前查清楚，不能只测"传对参数会怎样"。

## 状态
- 2026-07-07：场景工程 scaffold + OpenSpec propose（D2-D5 Paul 认可）+ `/opsx:apply` 完成 **v1 MVP**（`models`/`feed_source`/`match_engine`/`result_classify`/`recon_report`/`confirm`/`run` 七模块，32 tests 全绿），commit `0d19918` 入库 master（未 archive）。
- **2026-07-09（v3 口径修正，CC）**：唐燕萍团队回传应付会计实操细化（核对对象 AP vs INV/料品汇总归集/发票源 U9C 附件/AP-PO 单价校验），Paul 全盘采纳。在本变更包内原地调整（未新开变更包）：
  - `models.py` 新增 `APLine`/`PriceCheckResult`，`InvoiceLine` 改挂 `ap_no`，`LineMatch`→`ItemMatch`（`(ap_no,item_code)` 键）。
  - `feed_source.py` 新增 `ap_lines` 加载，`partition_invoices` 改按 `ap_no` 判孤立。
  - `match_engine.py` 重写为 `build_item_matches`（AP 驱动料品汇总）+ `detect_misaligned_items`（料品级配对）+ `assign_category`（无发票支撑/明细错位/数量金额不符/金额微差/完全匹配）。
  - 新增 `price_check.py`（AP-PO 单价强制比对，R7 占位 ±3%）。
  - `result_classify.py`/`recon_report.py`/`run.py`/`confirm.py` 随口径同步调整；`recon_report` 新增价格超差强制 `needs_review` 的合并路由。
  - 重建 mock+golden 五表夹具（新增 `ap_lines.csv`），覆盖五类判定+明细错位正反例+价格超差/未超差+多对一/一对多/多对多聚合+孤立发票。
  - 全部单测重写，**43 tests 全绿**（含黄金基准零偏差回归、价格校验覆盖、`u9c` fail-loud 冒烟）；`python -m fi2.run`/`python -m fi2.confirm` 手工验证通过；`openspec validate fi2-recon-mvp --strict` 通过。
  - 落分支 `feat/fi2-v3-recon-engine`（未合 master，待 Paul 审）。
  - **下一步（2026-07-10 已由唐燕萍团队提前交付，见下条）**：① ~~唐燕萍 R1-R7 规则草案交付（约 2026-08 底）~~；② U9C 财务接口/OCR 就绪（7/15 双反馈门）后切 `csv`/`u9c` 真实源；③ 真实验证通过后 `/opsx:archive`。
  - **未做（组 7 待数据闸，组 8.2-8.4 待真实验证/黄金用例专家批改）**：真实数据验证、`/opsx:archive`、strawman 黄金用例专家批改。
- **2026-07-10/16（R1/R5/R7 定稿真值落地，队列 #14/#16，design D14，CC）**：唐燕萍团队 R1-R7 规则草案较原计划提前 7 周交付（《FI2-FI3-规则定稿-交CC-2026-07-10.md》），在同一分支 `feat/fi2-v3-recon-engine` 原地落地：
  - `config.py` 替换真值：数量 ±0（精确匹配）/未税金额新增比例备用 ≤0.5%/税额改按料品有效税率动态换算（不再是独立固定容差）/R7 人民币 ±2%；`RULE_VERSION` 升版 `fi2-v3-tangyanping-2026-07-10`。
  - **新增 R5 门禁**（`recon_report._l2_gated_ap_docs`）：整单（AP 关联 PO 行）未税金额差异总额 ≤¥1 或 ≤0.5% → "金额微差"降级 `l2_self_resolved`（AP 自行消化）；仅对"金额微差"生效——CC 从紧解读（"无发票支撑"/"明细错位"/"数量金额不符"三类不因总额小而降级），**Paul 2026-07-16 已拍板确认不扩大到"明细错位"，此范围为最终口径**（design D14-b）。价格超差优先级高于本门禁。报告状态由二态扩为三态，`summary` 新增 `l2_self_resolved`。
  - 新增 `item_normalize.py`（料品编码归一化预处理：去空格/全半角/括号/"-"与"/"等价类），接入 `match_engine.build_item_matches` 聚合 key；**不含**模糊匹配/置信度分档/自学习长线机制（留待真实数据接入）。
  - `models.ItemMatch` 新增 `ap_tax_rate` 字段（税额动态容差换算用）。
  - R7 外币供应商过渡规则（"容差内连续 2 次同向偏移推人工抽查"）与"方案一"原始外币单价+汇率升级位均**未实现**（缺供应商清单 + 跨运行历史状态两个前置），已登记 future-work（`tasks.md` 10.12），未来另行提交变更包。
  - 单测：`test_match_engine.py`/`test_recon_report.py` 各新增用例覆盖 R1/R5 新行为，新增 `test_item_normalize.py`（7 用例），`test_golden.py` 按真值更新（AP-1010 金额微差→L2 自行消化）；**全量 61 tests 全绿**，`python -m fi2.run` 手工验证通过。
  - openspec design.md 补 D14、tasks.md 补第 10 节、三份 spec delta（match-engine/recon-report/price-check）补 Requirement，均已同步。
  - **未做**：R5 门禁分母颗粒度（"整单"取 AP 引用的 PO 行集合 vs 整张 PO 单）仍待唐燕萍团队批改（design D14 Open Questions，门禁范围本身 Paul 已拍定不再是开放项）；R7 外币过渡规则/方案一升级位（Paul 07-16 已确认明确推迟，future-work，待外币供应商清单到位后再评估）；真实数据验证仍按 8 月底排期不变。
- **2026-07-16（Paul 两拍板，收口 D14 遗留开放点，CC）**：① **R5 门禁范围不扩大到"明细错位"**——D14-b 的 CC 收紧解读即为最终口径，不等唐燕萍团队批改这一项了（分母颗粒度仍待）。② **R7 外币过渡规则/方案一明确推迟**——Paul 认可"先上最小 MVP"，当前实现（外币供应商行按人民币同一 ±2% 处理、不触发增量抽查）维持不变，待 IT/唐燕萍团队提供外币供应商清单后再评估是否要做"连续 2 次同向偏移推人工抽查"的跨运行历史状态机制。两项均为**文档口径确认，代码无需改动**（此前实现已是这两条的目标状态）；design D14 Open Questions/tasks.md/proposal.md/spec delta 已同步落字。
- **2026-07-20（真实 U9C 财务接口接入 + R7 外币真值 + 三实测点，队列 #60，design D15，CC）**：唐燕萍团队 07-17 交付 API 接口文档（财务数据闸实质解除，队列 #6/#47），财务数据整备正式开工。
  - **三实测点真实只读探测**（服务器 `192.168.100.49:6666`）：①批量查询——`Purchase/Query`/`GR/Query` 不传 docNo 即返回全表+分页/`supplierCode` 过滤均有效；**`AP/Query` 服务器端有真实 SQL bug**（`supplierCode`/`itemCode`/`invoiceNo` 三个过滤参数均触发"列名无效"异常），只能 docNo 单查，已书面跟催 IT（陈承，`6-人才与组织/部门AI专员跟进/IT部-陈承-跟进-2026-07-20-*.md`，机器人已推送）；②`FinalPriceTC`(PO)与`TaxPrice`(AP)均为含税单价，同 `(po_no,line_no)` 实测精确一致，R7 比对基础成立，`price_check.py` 无需改动；③原币直比机制验证成立（`...TC` 字段本就是原币存储非折算字段），三家外币供应商专属数值样本受①限制未定向核实，留 8 月真实小样本阶段优先覆盖。
  - **真实连接器接入**（design D15-b，Paul 拍板：连接器落平台 `ZpConnector`、复用 `STOCK_API_BASE`/`STOCK_API_KEY`）：`ZpConnector` 新增 `get_purchase_lines`/`get_gr_lines`/`get_ap_lines(doc_no)`（GET+apiKey，信封同 `Stock/Query`）。`fi2/feed_source.py` 的 `FeedSource` 新增 `u9c_connector`/`ap_doc_nos` 可选构造参数，`u9c` 源下 `load_po_lines`/`load_grn`/`load_ap_lines` 按"AP 单号驱动→去重 `SrcPONo`/`SrcRcvNo`→分别拉取"三步实现（同实例内缓存 AP 行，避免重复网络调用）；未注入连接器时维持现状 fail-loud（`test_u9c_fail_loud_all_loaders` 零回归）。`load_invoice`/`load_payment` 对 `u9c` 源继续无条件 fail-loud（Attachment/OCR 未就绪，队列 #59）。
  - **R7 外币供应商真值落地**：`config.FOREIGN_CURRENCY_SUPPLIERS = ("ZA0066", "ZA.0368", "ZA0020")`（艾睿/安富利/上海英恒，唐燕萍团队 07-14 回件，已用 `Supplier/Query` 真实核实三家均为在库真实供应商）。
  - **新增测试**：`test_fi_connector.py`（连接器方法，7 用例，全 mock/monkeypatch 不触网）+ `test_feed_source.py` 新增 3 用例（假连接器覆盖三步拉取/字段映射/缓存复用、缺 `ap_doc_nos` 报错、Invoice/Payment 仍 fail-loud）+ `test_price_check.py` 新增 1 用例（R7 三家配置值守护）+ 新增 `tests/test_real_integration.py`（比照 SC8 范式，`FI2_RUN_REAL=1` 门禁，默认跳过不触网，含"IT bug 修复回归哨兵"用例）。平台 200 passed+1 skip（新增 7）、FI2 65 passed+4 skip（新增 4 mock 用例 + 4 gated 真实用例），零回归。
  - **⚠️ 发现一个影响面更广的问题（2026-07-20 当场发现，已知会 Paul）**：Paul 确认财务三单接口与既有库存/预测订单**同一 apiKey**后，用该 key 做真实活连通验证时发现**该 apiKey 当前对`Purchase/GR/AP/Stock`全部端点均返回 `401 Invalid api-key`**——而同一 key 数小时前（本 session 内）在这些端点上还能正常查询真实数据。因为 `Stock/Query` 正是 SC8 保供看板 `.51` 部署依赖的实时库存源，此 key 失效**可能正在影响 SC8 生产服务**，已作为独立风险单独上报（不在本次 #60 范围内处理，超出 FI2 场景）。
  - **未做**：真实小样本对账验证仍按 8 月底排期（本次只到"真实源代码可用"，未做批量真实跑批）。
- **2026-07-22（AP/Query 期间/余额过滤参数解锁验证，design D17，队列 #70，CC）**：陈承 07-21 群回复——`AP/Query` 三过滤参数列名修复（07-20 报的 SQL bug）之外，同批还新增 `dateFrom`/`dateTo`（按立账日期 `AccrueDate`）+ `minBalance`（余额下限）参数，正式库已同步部署；D16-a 当时"服务器无日期区间参数"的结论已过时。真实探测确认：两个新参数单独/组合可用，`minBalance` 语义为下限（非精确匹配/上限）。`ZpConnector.get_ap_lines_by_supplier` 增补同名可选关键字参数（缺省行为与 D16 完全一致，向后兼容）；**未做**供应商无关的整期批量方法（无真实调用方，避免预先建抽象）；**未接线** `FeedSource`/`fi2/run.py`（留待真实小样本阶段按需接入，见 tasks.md 13.6）。全量回归零漂移：平台 211 passed+1 skip（+3）、FI2 67 passed+7 skip（+2 真实用例，默认门禁 skip）。
- **2026-07-21（apiKey 恢复 + AP 批量查询 bug 意外一并修复，队列 #61 复验销行，CC）**：陈承回复根因——新版本 DLL 把 apiKey 从硬编码改读服务器 `Web.config` 的 `ZP_API_KEY`，部署时该配置项遗漏导致全端点 401；已补配置+`iisreset` 修复，确认 SC8 `.51` 保供看板不受影响。CC 复验：① `test_real_integration.py` 四个真实 schema 用例全绿；② 顺带用新 key 抽验 `Stock/Query`，返回数据与 07-20 已知真实值一致（R01A.0012 可用量 2,827,195），交叉核实陈承说法无误；③ **意外发现**——07-20 报给陈承的 `AP/Query` 批量过滤 SQL bug（`supplierCode`/`itemCode`/`invoiceNo` 均报"列名无效"）同批也被修复了（陈承回复未提及此项，推测是同一次 DLL 更新顺带修的）：`test_real_ap_query_batch_filter_now_fixed` 确认三个过滤参数 + 不传 docNo 全表分页均已正常。design D15-a①/tasks.md §11 已同步更新。全量回归复跑仍零回归（FI2 65+4skip、平台 200+1skip）。
- **2026-07-21（AP 批量自动取数改造，Paul 当场拍板，design D16，CC）**：批量查询 bug 意外修复后 Paul 直接拍板"改造成批量自动取数"，不停下等 design 审。**选型**：批量维度选**按供应商**（`supplierCode`）——服务器无日期区间参数、AP 行也无独立单据日期字段，"按期间"做不了；按供应商是唯一有真实业务含义且已验证可用的维度，也与 R7 三家外币供应商的既有关注点吻合。**实现**：`ZpConnector` 新增 `_fi_request`（单次 GET）+ `_fi_query_paginated`（循环分页直到拉满 `Total`）+ `get_ap_lines_by_supplier(supplier_code)`；`FeedSource` 新增 `ap_supplier_codes` 构造参数，与既有 `ap_doc_nos`（D15-b 手工模式）并存二选一（同时传入批量优先），下游 `load_po_lines`/`load_grn` 的派生管线复用不变。手工单号模式未删除，继续可用（财务专员只想追具体单号时仍可用）。**测试**：`test_fi_connector.py` +3（分页停止条件/空结果/URL 校验）、`test_feed_source.py` +3（批量驱动同管线/优先级/二者皆缺报错）、`test_real_integration.py` 新增 `test_real_get_ap_lines_by_supplier` 真实端到端验证——分页拉取艾睿（ZA0066）全部 AP 明细行，条数与服务器 `Total` 精确一致，已真实跑通。全量回归零漂移：平台 203+1skip（+3）、FI2 67+5skip（+2 net）。design D16 已落 `openspec/changes/fi2-recon-mvp/design.md`。
- **2026-07-23（round-1 真实数据验证，design D18，队列 #78，Paul 07-22 拍板"全力抢 8 月上旬"，CC）**：六项前置全清（引擎/规则/端点/批量/OCR选型/8样本到手），CC 领活+工期评估（3.5-5工作日）后正式建造，先出 design D18 停等 Paul 审（round-1 打法：CSV 快照+人工誊录发票解耦 OCR），Paul 07-23"按 CC 建议来；批准/apply"后实现：
  - **新增**：`ZpConnector.list_attachments`/`download_attachment`（首碰 `Attachment/List`+`Download`，探测干净无服务端 bug——但仅抽验 1/8 单的 `Download`，见下"教训"）；`fi2/run.py::run()`/CLI 接线 `u9c_connector`/`ap_doc_nos`/`ap_supplier_codes`（此前 `run()` 完全未接，`FeedSource` 支持但从未被调用）；新增可复用工具 `fi2/dump_u9c_snapshot.py`（真实 PO/GR/AP 落 CSV 快照，`.gitignore` 覆盖不入库）。
  - **round-1 真实验证结果**（8 组真实 AP 单中 6 组完整跑通，详见 `1-转型规划/FI2-round1真实验证报告-2026-07-23.md`）：**核心匹配逻辑（D11）10/10 料品判定"完全匹配"，零假阳性**；**AP-PO 单价校验（D12/R7）3/10 超差**（-6.1%~-44.7%，真实数据非误判，已溯源）。
  - **两组样本未完成**（原因均查明，非引擎缺陷）：AP-2025120181 撞上 `Attachment/Download` 真实服务端 302 重定向到 `localhost:5555`（不可达，需 IT/陈承跟进）；AP-2026050057 为跨多 AP 单合并结算大票（100行/8页），超出本轮人工誊录合理范围，留 round-2 OCR 阶段处理。
  - **方法论发现（未改代码，登记后续）**：① `Attachment/List` 正常不保证 `Download` 也正常，首碰端点探测应对每个待用样本做端到端抽验，不能只抽验其中 1 个（本次因此才在实现阶段才发现 AP-2025120181 的 302 问题）；② `price_check.py` 只比对 `Purchase/Query` 原始下单价，未消费 `POChange/Query` 变更后价格，可能对已变更 PO 产生假阳性超差告警（3 例中 1 例命中此风险，另 2 例排除、需业务侧核实）——独立后续设计评估项，未在本次范围内改代码。
  - **顺带修复两处真实 bug/隐患**：① `ZpConnector.audit=` 期望 `ConnectorAudit`（轻量连接器痕迹）而非业务 `AuditLogger`，两者物理分离（同 SC8 范式），最初误传导致真实调用 `AttributeError`（mock 单测覆盖不到，因为不触网不会走到 `_fi_request` 的 audit 调用）——已在 `run.py`/`dump_u9c_snapshot.py` 中改正；② 本 worktree `zhuopin_platform` 全局可编辑安装被另一 worktree 静默劫持（已知隐患，见跨会话记忆 [[project-shared-python-editable-install-collision]]），`pip install --force-reinstall --no-deps -e <本worktree>` 修复。
  - **测试**：`test_fi_connector.py` +7、新增 `test_run_u9c_wiring.py`（8 用例）、新增 `test_dump_u9c_snapshot.py`（2 用例）；全量回归零漂移：平台 218 passed+1 skip（原 211，+7）、FI2 77 passed+7 skip（原 67+7，+10 net）。
  - **未做**：OCR（腾讯云）自动直读集成——独立 round-2；`data/golden/` 合成基准未替换/扩充（design D18-e 已定，样本量偏小会降低回归覆盖面）；openspec 变更包本次**未 archive**（tasks.md 7.3/8.3/8.4 仍待 OCR round-2 + 更大样本量后收口）。
- **2026-07-28（FI2 最小 Web 服务发布收口，队列 #140，CC，独立 worktree `fi2-web-service-16da2a`，与 round-1 真实验证并行不占其带宽）**：财务域此前是四域唯一零 Web 入口场景（SC8 `:8091`／命令中心 `:8092`／QD-B `:8093` 皆已发布），业务总线 07-28 当日两次裁决（先判"排 round-1 之后"，后因"`recon_report` 六段式输出已定型、返工风险小"改判"今日可开工"）后动工。新增 `fi2/webapp.py`（Flask，六段式报告页：①总判定②完全匹配/L3建议通过③需人工确认④L2自行消化⑤AP-PO单价强制比对+R7口径说明⑥孤立发票+审计元数据，**逐字复用**`recon_report.build_report()`既有输出字段，未新增/未改写任何判定结构）+ `scripts/run_fi2_web.py`（启动入口，同 QD-B 范式）+ `deploy-server.ps1`/`sync-to-server.ps1`（端口 8094，复用 `ZhuopinDeploy.psm1`）。**数据源三选一**（Web 表单）：`mock`（内置合成演示数据，无需填参）／`csv`（应急桥接目录，即 round-1 已验证的"`dump_u9c_snapshot.py` 真实快照+人工誊录 invoice.csv"路径，不依赖 OCR）／`u9c`（真实直读 PO/GR/AP；Invoice 因 Attachment/OCR 未就绪对 u9c 源无条件 fail-loud，design D15-b 既定行为不变，Web 层如实报错而非静默假装完整）——三种模式均**逐字透传** `fi2.run.run()` 既有参数，Web 层零新增引擎逻辑。红线全部守住：只读取数不写回 ERP；R1/R5/R7 `config.py` 真值一字未动（⑤段仅展示当前配置值+口径说明，含 07-28 #80 真实探测"AP&lt;PO 常态"发现的提示性说明，不改判据）；结果分类原样透传，不伪装已判定。13 个新测试（`test_webapp.py`，覆盖 ping/disclaimer/三数据源正反例/凭据缺失如实报错/mock 全链路六段渲染），全量回归零漂移：FI2 90 passed+7 skip（原 77+7，+13）、平台 218 passed+1 skip（不变）。**真实部署 `.51:8094`**（计划任务 `Fi2WebServer`，SYSTEM+AtStartup，防火墙 `Fi2-WebServer-8094` LAN 全网段）：首次部署撞上已知坑——`deploy-server.ps1` 未存 UTF-8 BOM 导致 .51 内建 PowerShell 5.1 解析中文报语法错（同 SC8/QD-B 惯例补 BOM 后复跑即通）；`sync-to-server.ps1` 起初刻意不同步 `data/`（比照"不上生产服务器真实/黄金数据"红线），导致部署后 mock 演示选项 `FileNotFoundError`——补充只单独同步 `data/mock/`（纯合成、无真实供应商/金额数据，`data/golden`/`data/real_*` 仍不同步）后复测通过。**外部（非本机）冒烟全绿**：`/api/ping`/首页 200；真实 POST `/run` 跑通 mock（六段式渲染完整、料品总数 11、disclaimer 完整）与 csv（复用同一份 mock 目录当"快照目录"验证 csv_dir 表单参数路径）两种模式；u9c 模式**如实报错**"缺少凭证"（.51 上未配置 `U9C_*`/`STOCK_API_*`，本次部署未申请这些凭据——即便配置齐全，`u9c` 模式仍会在 `load_invoice` 步骤按 design D15-b 如实 fail-loud，是预期行为非缺陷，故本次未申请凭据不影响可用性判断）。AI 运营指挥中心门户财务域卡换真实入口（同 QD-B 07-23 惯例，nav 标签"建造中"→"灰度"）。**未做**：门户下方样例数据表（占位）保留未删，仅补充"请打开上方真实入口"提示（未做 procurement 域那样的 iframe 内嵌改造，范围外）；.env 内 U9C 真实凭据未配置（如需财务专员真实 u9c 单号/供应商在线取数，需另行申请凭据配置，属独立后续任务）。详见队列 #140。
- **2026-07-31（v8 核对面板改造，队列 #182/#183，CC，独立 worktree `fi2-web-service-16da2a`）**：唐燕萍 07-31 回件权威规格书（`7-外部文档/财务部/...FI2面板改造指令及效果图-382fedaf...docx`，用 python-docx 解压全文+两张效果图逐字比对，非文字脑补；同批发错的《改造后的FI2三单匹配面板效果》已由她本人声明作废，未采信）驱动的展示层重建。**红线（她原话"信息全保留，只换看法"）：只改 `fi2/webapp.py` 一个文件**——新增 `_run_with_detail()` 是 `fi2.run.run()` 同一套函数调用序列（FeedSource→partition_invoices→classify_all→check_ap_po_price→build_report）的原样复用，只多返回中间产出的原始 PO/AP/发票明细行供展开详情渲染单据卡片；`match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/`config.py`/`models.py` 零改动，判据/容差/五类判定优先级不变。**结构改造**：六段式平铺 → 结论看板（3 个 KPI 卡：自动通过/微差消化/BLOCK退回，配色取自规格 §4.1 给定 hex 值）+ 核对路径标签（PO↔AP 蓝/AP↔发票 橙）+ 10 列并拢窄表（点击行号展开）+ 展开详情（PO/AP/发票三张单据卡片+左边框配色区分 + 六个校验块：①四维匹配②OCR字段校验③税率合规④重复发票检测⑤PO变更检测⑥行级映射）+ BLOCK处理流程四步图。孤立发票并入主表一行（规格 3.8，不再单列"⑥孤立发票"区），计入 BLOCK 退回计数，总行数由 11 变 12（11 料品 + 1 孤立发票）。#183 免责声明按其给定文案+浅黄底加粗样式上线，位置在结论看板下方、主表上方。#175⑤口头指令：原独立第五段"超差不代表一定是记账错误"提示语，改为跟随"①四维匹配"校验块，仅当该行 PO↔AP 有差异（价格超差）时才在展开详情底部自动带出。**诚实边界（非伪装已判定，FI2 一贯红线）**：v8 规格新增的 OCR 8 字段校验/重复发票检测/税率合规/PO 变更检测四维，当前引擎均未实现（税率合规·重复检测明确属本场景"二期"范围，见上方「定位」段；OCR 选型未就绪；PO 变更检测已于队列 #80 评估后明确不采纳），面板如实标注"二期未接入"灰色徽标，不杜撰判定结果；"PO↔AP"列如实标注"(单价)"——本引擎该维度仅覆盖 R7 单价强制比对，非四维全覆盖；"料品名称"列如实展示为"料品编码"——`models.py` 无独立名称字段。展开卡片内的原始 PO/AP/发票金额字段（单价/不含税金额/税额等）为当次会话即时展示给财务人员本人看，**不落审计 JSONL/`fi2_reconcile_report.json`**（金额脱敏红线 D7 约束的是持久化，`build_report()` 调用参数与落盘内容较改造前完全一致）。**测试**：`test_webapp.py` 全量重写以匹配 v8 结构（KPI 卡/#183 免责声明位置与文案/⑤提示语条件带出/新维度诚实占位断言/展开收起脚手架/BLOCK操作按钮态），FI2 99 passed+7 skip（原95+7，净+4）、平台 244 passed+1 skip（零改动，验证判据零漂移）。**真实部署 `.51:8094`**：`sync-to-server.ps1` 推送成功（新 PID 存活确认）；冒烟三件套全绿——`/api/ping` 200；首页（经 `X-Auth-Token` 程序化访问，见队列 #160 共享口令门禁）200；真实 POST `/run` 跑通 mock 全链路，v8 结构关键字（KPI 卡类名/"本次共 12 项料品"/#183 免责声明/BLOCK处理流程/"二期未接入"/已知场景 AP-1000·AP-8000）逐项核对全部命中。**未做**：交付后需财务专线按 #144 范式请唐燕萍/李姣龙抽验确认（CC 不直接联系专员，登记待办见队列 §四）；"已补充待审核"状态（规格 3.6，业务补数据后回流的中间态）本引擎真实计算结果中不存在（无 ERP 回流自动感知机制），故"确认通过/退回"操作按钮当前不会出现，只有 BLOCK 初始态的"退回原因"信息按钮——若后续要接通该回流环节需另行评估，不在本次"只改展示层"范围内。详见队列 #182/#183。

- **2026-08-03（面板真实数据接入·轮1，design D19，队列 #214/§四#43，CC，本 worktree 内直接执行）**：唐燕萍 07-31 验收 v8 面板结构通过后唯一诉求"接真实数据"（队列 #191）。§四#43 拍板 (b)：本轮先接 PO+AP 两单真实数据、发票以人工誊录小样占位，并行跟催 OCR（#127）。openspec：在既有 `fi2-recon-mvp` 变更包内原地追加 D19（同 D14-D18 先例，未新开变更包），propose→design→**Shao Peishen 会话内批准**→apply。**改动范围仅两处，判据零改动**：① `feed_source.py` 新增可选 `invoice_sample_dir` 参数——u9c 源下提供即读取该目录 `invoice.csv`（复用既有 `_InvoiceRow` 边界校验），未提供维持现状 fail-loud；② `webapp.py` 固定指向场景内 `data/real_round1/`（只读展示型开关，非用户可填任意路径，避免路径穿越面）+ 报告页新增"⚠️ 发票为人工誊录小样，OCR 未接入"标注（`.disclaimer-d19` 样式）+ 数据源行发票列标注 `u9c+人工誊录小样`。`match_engine.py`/`result_classify.py`/`price_check.py`/`config.py`/`models.py` 一字未动。**round-1（D18）誊录原件已确认无法复用**（产出 worktree `fi2-web-service-16da2a` 已随台面清理删除，`.gitignore` 覆盖的 `data/real_*` 从未入库）——已用真实 `STOCK_API_BASE`/`STOCK_API_KEY`（只读 GET）重新拉取全部 8 组 AP 单，结果与 D18-f 逐字复现（6/8 可用，AP-2025120181 仍 302 到 localhost、AP-2026050057 仍为合并结算大票），逐张阅读 6 张发票 PDF 人工誊录（AP-2026060004 一票对应两个内部料号，按 AP 数量占比对半拆分，±0.01 分摊误差如实记录，非隐瞒）。**测试**：`test_feed_source.py` +2、`test_webapp.py` +3，全量回归零漂移：FI2 104 passed+7 skip（原 99+5，净+5）；mock 模式全部既有结构断言原样通过，构成判据零漂移的显式证明（本轮改动仅存在于 `data_source=="u9c"` 分支内）。**真实端到端验证**（直接调用面板同一入口函数 `_run_with_detail`，真实连接器）：10 料品（5 完全匹配自动通过+2 金额微差自动 L2 消化+3 例 AP-PO 单价超差 BLOCK），**3 例价格超差与 D18-f 逐位精确一致**（-44.72%/-6.11%/-8.22% vs 记录 -44.7%/-6.1%/-8.2%），AP-2026060004 两料品本轮判"金额微差"而非 round-1 的"完全匹配"，已查明系誊录 50/50 拆分产生的 ±0.01 分摊误差所致（非业务变化/非代码缺陷），详见 `1-转型规划/FI2-round1真实验证报告-2026-08-03-面板轮1.md`。**真实部署 `.51:8094`**（详见 §「部署状态」D19 段）：代码推送 + 发票誊录小样直接 scp 到服务器（不经 git，同 `data/real_*` 红线）+ **顺带发现并解决一处部署缺口**——`.51` 上 `C:\fi2\.env` 此前只有 `ZP_GATE_PASSWORD`，缺 U9C/Stock 全部凭据（`ZpConnector.from_env()` 构造直接报错），经 Shao Peishen 会话内确认后，从同一物理服务器上已配置完整凭据的 `C:\baoguan\.env`（SC8 保供看板）拷贝 8 行凭据（项目既定"同一物理服务器同一凭据、不新开环境变量"约定，非新引入凭据），重启服务后外部真实 POST `/run`（u9c 模式，6 组真实 AP 号）跑通，KPI 计数与本机验证完全一致（5/2/3）；mock 模式回归确认不受影响（12 行含 1 孤立发票，与既有基线一致）。**未做**：openspec 变更包本次未 archive（`fi2-recon-mvp` 因 14.13 OCR round-2 等既有开放项仍不满足整体归档条件，本节完工不代表整体可归档）；跟进信待起草提交 Shao Peishen 审核后按发送硬前置三条件（代码入 master+部署冒烟通过+真实案例复现，均已满足）发送。详见队列 #214、design D19、`1-转型规划/FI2-round1真实验证报告-2026-08-03-面板轮1.md`。

- **2026-08-07（发票源改道·税务导出 Excel 接入，队列 #295，openspec 变更包 `fi2-tax-export-ingest`，CC，独立 worktree `fi2-tax-export-excel-d3938b`）**：详见上方"当前进度"段完整记录。要点回填：openspec Q0 按默认(a)新建独立 capability（`fi2-recon-mvp` 未归档、无可挂靠的既有 spec），propose→design→apply→archive 全走完（`openspec/changes/archive/2026-08-07-fi2-tax-export-ingest/`）；真实探测推翻 #249 原计划的"发票号字面 join"假设，改用后 8 位+客户端 suffix 校验，8/8 真实样本唯一命中；新增 `fi2/tax_export_ingest.py`/`scripts/ingest_tax_export.py`/`ZpConnector.get_ap_lines_by_invoice_no`，三单核对判定六文件+展示层 `webapp.py` 全部零改动；全量回归 FI2 128+7skip（+21）/平台 262+1skip（+3）；`.51:8094` 真实部署+服务器本机对真实 `D:\airead` 跑通摄取（40行解析成功+幂等验证+UTF-8字节级核验）。**未接入面板默认展示路径**（webapp.py 未改，u9c 模式仍读 D19 的 `data/real_round1/`），仅交付摄取能力本身。详见队列 #295／#249。

## 关键依赖/前置（解锁条件）
- ~~🔴 唐燕萍（财务 AI 专员）R1-R7 规则草案~~ ✅ 已交付（2026-07-10，较原计划提前 7 周）——真值已落 `config.py`（见上）；黄金用例专家批改仍待唐燕萍团队（strawman 用例本身未经批改）。
- ~~🔴 U9C 财务接口（PO/GR/AP 配票）~~ ✅ 已接入（2026-07-20，design D15）+ ✅ **round-1 真实小样本验证通过**（2026-07-23，design D18，见上）；~~apiKey 一度失效~~ **✅ 2026-07-21 已由陈承修复**（见上）。~~🔴 OCR 选型仍未就绪~~ **✅ OCR 方案已作废、改道税务导出 Excel（唐燕萍 2026-08-04 拍板，队列 #249/#59/#127 同步关闭）+ 摄取能力已建成（2026-08-07，队列 #295，见上）+ 第2层定时扫描/失败告警＋摄取产出接入面板默认展示路径已建成并部署验证通过（2026-08-10，队列 #82，见上）**——面板 u9c 模式发票段现已优先展示税务导出摄取产出，`Fi2TaxExportDailyScan` 定时任务已上线运行。**唯一剩余开放项**：运维逃生通道 webhook（`WECOM_WEBHOOK_URL`）尚未配置，需 Shao Peishen 提供新运维群（其本人+陈承）webhook URL，见上方 08-10 段"⑤"。
- ~~🟡 AP 端批量查询 SQL bug~~ ✅ **2026-07-21 已由 IT 修复 + 批量自动取数已改造完成**（design D16，见上）——`FeedSource` 同时支持 `ap_supplier_codes`（批量，推荐）/`ap_doc_nos`（手工单号）两种驱动模式。
- 🟡 料品↔INV规格型号/项目名称映射表（v3 改名，原"物料编码映射表"）——真实场景前置，round-1 已用"人工对照 AP 配票记录反推映射"验证过匹配逻辑本身可靠（design D18-f），但**规模化映射表基础设施仍未建**，模糊匹配/置信度分档/自学习长线机制仍待真实映射表来源确认（本次仅落地"归一化预处理"子项 `item_normalize.py`）。
- ~~🟡 `price_check.py` 未消费 `POChange/Query`~~ ✅ **已评估完成，结论=不采纳（2026-07-28，队列 #80）**——真实探测证伪了"比对基准未跟进变更价"这个假设：`Purchase/Query.FinalPriceTC` 本来就是当前生效价（PO 每次变更审批后 ERP 原地更新主记录），`POChange/Query` 也是单据级无行项单价，给不出"某料品最新价"。`price_check.py` 维持现状不改，详见上方"已知真实端点行为坑"第 3 条 + 决策件已作废勘误段。
- 🆕 🔴 **`Attachment/Download` 对 AP-2025120181 返回 302 重定向到 `localhost:5555`**（round-1 发现，design D18-f）——需 IT（陈承）跟进，不阻塞其余样本；影响面未知（是否只此一单，还是某类附件存储路径的系统性问题），待 round-2 更多样本时再观察。
- ~~🟡 R7 外币供应商清单~~ ✅ 已落真值（2026-07-20，见上）；跨运行历史状态机制（"连续 2 次同向偏移推人工抽查"过渡规则）**Paul 2026-07-16 已确认推迟**，未就绪前按人民币同一 ±2% 处理，不算阻塞项。
- 🟡 FI3（付款校验）依赖本场景结果——FI2 先行，FI3 另起场景。

## 部署状态（2026-07-28 最小 Web 服务发布收口，队列 #140）

- **地址**：http://192.168.100.51:8094/ （仅 LAN，无登录鉴权，同 SC8/QD-B/命令中心惯例）
- **服务**：Flask+waitress，`fi2/webapp.py`（数据源三选一 mock/csv/u9c → 六段式对账报告页）+
  `scripts/run_fi2_web.py` 启动入口；计划任务 `Fi2WebServer`（SYSTEM + AtStartup，失败重启3次）；
  防火墙 `Fi2-WebServer-8094`（LAN 全网段）。
- **冒烟结果**：`/api/ping`/首页 200（外部非本机访问核实过，非仅本机回环）；真实 POST `/run`
  验证 mock 与 csv 两种模式均 200、六段式报告完整渲染、料品总数与固定夹具（11）一致；
  u9c 模式按预期报"缺少凭证"（.51 未配置 `U9C_*`/`STOCK_API_*`，未申请——即便配置齐全，
  `load_invoice` 步骤仍会按 design D15-b 如实 fail-loud，此为预期行为非缺陷）。
- **门户接入**：AI 运营指挥中心门户（`1-转型规划/AI运营指挥中心/AI运营指挥中心-框架原型-v0.1.html`）
  财务域卡已加真实入口链接 + wip-ribbon，nav 标签"建造中"→"灰度"；下方样例数据表保留
  （占位，未做 procurement 域 iframe 内嵌改造，范围外），补充"请打开上方真实入口"提示。
- **灰度范围**：唐燕萍（财务部）+ 李姣龙（一线核对人）；反馈渠道待与财务专线对齐（同企微机器人
  归档惯例，暂未新增专属反馈入口）。
- **红线保持**：只读取数，不写回 ERP；L2/L3 人工确认门禁照旧，disclaimer 显著标注"未过账"；
  R1/R5/R7 `config.py` 真值一字未动；结果分类原样透传不伪装已判定；u9c 源发票 fail-loud 如实报错。
- **回滚**：`schtasks /End /TN Fi2WebServer`（停）；`schtasks /Delete /TN Fi2WebServer /F`（注销）。
- ~~已知限制：u9c 模式需另行配置 `.env`...且仍会在发票步骤 fail-loud~~ **✅ 2026-08-03 已解除
  （design D19，详见下方 D19 部署段）**：`.env` 凭据已配置齐全，发票段在场景内已备好人工誊录
  小样时不再 fail-loud。**仍然如实的限制**：人工誊录小样非规模化方案（8 组样本、非 OCR 自动
  直读），规模化真实三单完整对账仍待 OCR round-2（队列 #82）；csv 模式配合
  `dump_u9c_snapshot.py`+人工誊录（round-1 已验证路径）仍可用，与 u9c 模式并存不互斥。
- **2026-07-30 共享口令门禁上线（临时止血，队列 #160，Paul 直接派单，独立 worktree
  `four-services-temp-auth`）**：`.51` 四服务（本场景8094/保供看板8091/命令中心8092/QD-B8093）
  此前均零鉴权、绑 0.0.0.0，LAN 内任何人可见真实供应商单价/AP单数据——真实暴露。`webapp.py::
  create_app` 接入 `zhuopin_platform.shared_tools.simple_gate.install_flask_gate`（HMAC签名
  Cookie 30天+X-Auth-Token程序化访问+登录页，密码环境变量 `ZP_GATE_PASSWORD` 未配置时自动
  no-op）；`/api/ping` 健康检查豁免。全量回归零漂移：FI2 95 passed+7 skip（原90+5）。真实部署+
  curl验证：`/api/ping`放行、未登录302、Token/Cookie 均放行，且用保供看板(8091)登录的 Cookie
  直接请求本服务成功（跨端口共享验证）。**非正式鉴权**——仅挡"随便谁都能打开"，正式身份走
  企微OAuth另待架构决策件；回滚：清空 `.env` 里 `ZP_GATE_PASSWORD=` 值+重启计划任务即恢复原状。
  详见队列 #160。
- **2026-07-31 v8 核对面板上线（队列 #182/#183）**：地址/端口/计划任务/防火墙规则均不变，仅
  `fi2/webapp.py` 展示层重建（六段式 → 结论看板+展开/并拢主表，详见上方"状态"段 07-31 条）。
  真实部署冒烟：`sync-to-server.ps1` 推送后 `Fi2WebServer` 新进程存活确认；`/api/ping` 200；
  首页（`X-Auth-Token` 头访问）200；真实 POST `/run`（mock）跑通，v8 结构关键字逐项核对命中
  （KPI 卡/#183 免责声明/BLOCK处理流程/"二期未接入"占位/已知场景行）。回滚 SOP 不变（见上）。
- **2026-08-03 面板真实数据接入·轮1上线（design D19，队列 #214/§四#43）**：地址/端口/计划
  任务/防火墙规则均不变，`sync-to-server.ps1` 推送 `feed_source.py`/`webapp.py` 改动后
  `Fi2WebServer` 新进程存活确认（`NEW_PID=1424`）；人工誊录发票小样 `invoice.csv`（真实供应商
  单价/金额，财务红色数据）**直接 scp 到 `C:\fi2\app\data\real_round1\`，不经 git**（同
  `data/real_*` 不入库红线，与 `sync-to-server.ps1` 现有"只推 `data/mock`"逻辑一致）。
  **顺带解决一处既有部署缺口**：`.51` 上 `C:\fi2\.env` 此前只有 `ZP_GATE_PASSWORD`，缺全部
  U9C/Stock 凭据（上方"已知限制"07-28 段记录的历史现状）——经 Shao Peishen 会话内明确批准，
  从同一物理服务器 `C:\baoguan\.env`（SC8 保供看板，已配置完整同一套凭据）拷贝 8 行
  （`U9C_API_BASE`/`U9C_USER_CODE`/`U9C_ENT_CODE`/`U9C_ORG_CODE`/`U9C_CLIENT_ID`/
  `U9C_CLIENT_SECRET`/`STOCK_API_KEY`/`STOCK_API_BASE`）到 `C:\fi2\.env`（项目既定"同一物理
  服务器同一凭据、不新开环境变量"约定，非新引入凭据源），重启 `Fi2WebServer` 生效。**真实冒烟
  三件套全绿**：`/api/ping` 200；首页（`X-Auth-Token`）200；真实 POST `/run`（u9c 模式，6 组
  真实 AP 号：`AP-2026070036/070035/060004/040083/060073/070071`）200，报告页正确显示
  "⚠️ 发票为人工誊录小样，OCR 未接入"标注 + 数据源行"发票=u9c+人工誊录小样"，KPI 计数
  5/2/3（自动通过/微差消化/BLOCK退回，共 10 项料品）与本机独立验证完全一致；mock 模式回归
  确认不受影响（12 行含 1 孤立发票，与既有基线一致）。回滚 SOP 不变（见上）；如需撤回本次
  凭据配置，删除 `C:\fi2\.env` 内新增 8 行 + 重启计划任务即可，不影响代码回滚。
- **2026-08-07 发票源改道·税务导出 Excel 摄取能力已建成（队列 #295）**：地址/端口/计划
  任务/防火墙规则均不变；`webapp.py` 本次零改动，**不影响面板行为**（u9c 模式仍固定读
  D19 的 `data/real_round1/`）。`sync-to-server.ps1` 推送 `fi2/`/`scripts/`/`pyproject.toml`
  （新增 `openpyxl>=3.1` 依赖）后 `Fi2WebServer` 新进程存活确认（`NEW_PID=8732`）；服务器
  venv 手动补 `C:\fi2\.venv\Scripts\pip.exe install openpyxl`（**已知缺口**：
  `sync-to-server.ps1` 只推代码不重装依赖，新增 Python 依赖须部署后手动补装一次，本次已
  补，未来若再新增依赖仍需重复此步）。**冒烟三件套全绿**：`/api/ping` 200；首页
  （`X-Auth-Token`）200；真实 POST `/run`（mock）200 全链路渲染正常。**新增摄取能力真实
  验证**（在 `.51` 服务器本机、非笔记本、非本地拷贝，直接读真实 `D:\airead`）：
  `python scripts\ingest_tax_export.py --export-dir D:\airead --out-dir
  C:\fi2\app\data\tax_export` 真实跑通，8 个真实导出文件、40 行成功解析（ap_no 反查
  8/8 唯一命中）、158 行如实标记未解析留痕（item_code 反查歧义/零命中，集中在 182 行
  合并结算大票）；二次运行验证幂等（0 新处理文件，8 个均命中已处理清单跳过）；产出
  `invoice.csv` 中文字段（如"单位"列"套"）UTF-8 字节级核验正确（`e5a597`），SSH 终端
  显示乱码纯属显示编码问题非数据损坏。产出目录 `C:\fi2\app\data\tax_export\` 现有真实
  已摄取数据，**但未接入面板 `u9c` 模式默认读取路径**（该路径仍固定 `data/real_round1/`，
  见上）——如需让面板展示改道摄取的数据，需另评估是否/如何切换该固定路径，不在本次
  "只建摄取能力"范围内。回滚 SOP 不变（见上），本次新增内容删除
  `C:\fi2\app\data\tax_export\`、`fi2/tax_export_ingest.py`、
  `scripts/ingest_tax_export.py` 即可完全撤回，不影响其余功能。
- **2026-08-10 第2层定时扫描/失败告警 + 摄取产出接入面板默认展示路径——已部署+真实
  验证通过**（队列 #82；代码建成时本机无 LAN 路由到 `.51`，Shao Peishen 回 LAN 后
  同 session 接续完成部署，非另开 session）。**部署**：`sync-to-server.ps1` 推送
  `webapp.py`/`fi2/tax_export_scan.py`/`scripts/scan_tax_export_scheduled.py`/
  `register-tax-export-scan-task.ps1`，`Fi2WebServer` 新进程存活（`NEW_PID=3308`），
  `/api/ping` 200。**注册**：`register-tax-export-scan-task.ps1` 首次执行撞已知坑
  （`.51` 内建 PowerShell 5.1 按 ANSI 读中文语法错，本文件新建时漏加 UTF-8 BOM）——
  已修复补 BOM（commit `75d7116`）、重新 scp 单文件后注册成功，`Fi2TaxExportDailyScan`
  状态 Ready。**真实验证**：手动 `Start-ScheduledTask` 一次，`LastTaskResult=0`；
  直接跑 CLI 二次确认幂等（20 个文件全部命中已处理清单跳过）；真实 POST `/run`
  （u9c 模式，`AP-2026070071`）确认报告页展示"发票=u9c+税务导出摄取"标签与对应
  banner，未见"人工誊录小样"或报错，KPI 与真实数据量级吻合。**⇒ 面板 u9c 模式发票段
  现已优先展示税务导出摄取产出；`Fi2TaxExportDailyScan` 每天 10:30 自动扫描运行中**。
  🔴 **唯一未解决项**：`.env` 的 `WECOM_WEBHOOK_URL` 仍未配置——核实仓库根/平台底座
  现有 webhook 均为业务部门群（采购/财务/质量），按通知通道架构决策件
  §4.2/§5.1，本行告警应走"Shao Peishen+陈承新运维群"逃生通道，其 URL 目前不在任何
  `.env` 中，**本次未获取、未配置、未猜测**（误填业务群 webhook 会直接违反该决策件
  核心诉求）；告警机制已建成待命，webhook 未配置时静默跳过不阻断扫描，功能等 URL
  到位即生效，无需再动代码。回滚：`schtasks /End /TN Fi2TaxExportDailyScan` +
  `/Delete /TN Fi2TaxExportDailyScan /F`。

## 路径引导（队列 #345，2026-08-18）—— 扁平部署布局下不再硬失败

- **改了什么**：本组件下列入口顶部的 #300 worktree 隔离引导，**找不到 `5-平台底座/zhuopin_platform` 标记时不再无条件 `raise`**：`fi2/run.py`、`fi2/confirm.py`、`fi2/dump_u9c_snapshot.py`（Web 服务入口 `scripts/run_fi2_web.py` 与两个 `scripts/*tax_export*` 早在 2026-08-10 队列 #82 已各自修过，本次未动）
- **为什么**：`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋ `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 `pip install -e` 进该服务 venv，全机唯一一份），**本就没有 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于把入口在生产布局上钉死。2026-08-18 SC8（8091）与 QD-B（8093）当天各自被它打挂过一次。
- **改法**（同 QD-B `dcc4162` / SC8 `a858769` 已验证范式）：找到标记 → 按 #300 原样前插（开发机 N 个平等 worktree 需确定性）；找不到 → 只插自身包路径、平台底座交环境解析（生产机唯一一份、无歧义）；**只有当环境里也没有 `zhuopin_platform` 时才 raise** —— 不引入静默失败。
- 🔑 **为什么这类雷本地测不出来**：**本地永远能找到仓库根标记**，全量测试全绿与它毫无关系。凡"引导/路径解析"类改动，**本地绿 ≠ 生产可启动**。
- ⚠️ **`tests/conftest.py` 刻意不改**：在 monorepo 内 fail-loud 是**有价值的**——测试就该跑在仓库里，找不到标记说明环境真错了，此时静默回退才是隐患。
- **收拢为平台底座共享函数** 见 `openspec/changes/platform-bootstrap-ensure-paths/`（已 propose，待 Shao Peishen 审 design，本次未 apply）。
