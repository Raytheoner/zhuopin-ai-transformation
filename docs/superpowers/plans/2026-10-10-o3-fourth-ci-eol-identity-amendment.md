# O3 第四CI诊断：精确EOL身份修订供审

记录：2026-10-10T18:32:50.890994+08:00。原批准计划A836D2…F78BE及两冻结脚本原样保留；本件仅申请下面两份新脚本替代执行入口。状态卡实际诊断尚未执行，原批准的一次额度未消费。

## 1. 已发生的准备失败

本人明确答复 `call_63258d6edd3549a48f3728dd03e0b658` 第0项「A：批准一次具体诊断及所列副作用（推荐）」已正式消费。根随后执行原生成器，实际退出1：`Candidate and main-tree import-closure file differs: 5-平台底座\zhuopin_platform\zhuopin_platform\__init__.py`。失败发生在UUID创建前；状态卡/pytest/网络/Job进程均0次，源码未改。原始失败及实际两树字节比较见 `reports/o3-fourth-ci-1010/preparation-failure-b74a2405534646e69d5f9ecf58dbc069/closure-difference.json`；不重新运行相同失败入口。

只有这个模块不同：候选540字节、12个CRLF，主仓528字节、LF；仅将CRLF替成LF后字节完全一致。其余四个最小import闭包文件逐字节相同。模块内容仅包docstring及version，无新增import；根已实际读过两树源。此证据不许可任意文本归一后相等。

## 2. 唯一修改

新生成器和runner各增加一个常量绑定：`5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py` 候选SHA `E76FDE183BF790D6CB3462FA0E90F334060C97426CA9F30152CC6738C4288D63`、主仓SHA `E7BA40C8B09F5839D2189DDF1EE6372E6FA7EB435DD1CA2C4E902082E9F86621`，必须同时精确匹配且CRLF→LF后字节相等；任一内容或hash改变仍拒绝。其他四闭包仍两树原字节SHA相同。生成器复制候选原始字节，runner复核副本是候选精确SHA，绝不改写任一仓源码或用通用忽略换行替代身份。

生成器manifest额外记录该精确pair；runner判据来自冻结常量，manifest不能放宽。候选HEAD0ad830234af70585d359df23123973eceeace3a3、状态卡BC774E…35DF、测试节点4990DD…360及八个P0–P7 stderr标记原样保持。

| 新执行文件 | SHA256 |
|---|---|
| `docs/superpowers/plans/o3-fourth-ci-1010/generate_diagnostic_copy_eol_identity.py` | `9422AA656EF6795EE34235C5BB7D27C2C1DFEAA99221ADEC6EA071F1081D6B68` |
| `docs/superpowers/plans/o3-fourth-ci-1010/run_diagnostic_once_eol_identity.py` | `B36EFB5895820453FC29A53F2AFAED014214B891D405729F1F74C8A7B87CE38F` |

完整diff见 `reports/o3-fourth-ci-1010/eol-amendment/*.py.diff`。根AST解析成功；runner的win_api/run_under_job/marker_summary/main AST与原件逐个一致。独立gpt-6-luna `/root/operations_readiness` 只读审查确认这两个SHA、唯一EOL分支、候选原字节复制及其他行为未改，未执行脚本；审查为静态准备闭合，不能当作运行或第四CI通过。

## 3. 获批后具体执行顺序

1. 根重核本件与两新文件SHA及原件保存状态；使用既有隔离Python `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe -B` 执行新生成器一次。若任一身份检查失败，留实际返回并停依赖runner，不改源、不自动重试诊断。
2. 根读取新UUID的manifest、diff与五副本SHA，核实诊断ps1 diff恰8条stderr标记、复制原字节及ignore边界成立。
3. 仅同UUID执行新runner一次（参数沿原runner的UUID目录）；180000ms主超时、原有各次最多5秒自身Job清理等待，保留原PowerShell选择、CI cwd、stdout `@@JSON@@` 契约与全部逻辑。原LAN条件成立时仍可能仅原.51:8091–8094四个/api/ping，每个最多3秒GET；不新增请求。
4. 新UUID保留stdout.bin/stderr.bin/source-manifest/metadata/实际exit/阶段时长，仅本机保存原日志，不打印外发。仅本次Windows Job归属树及自身PID定向清理；不杀全机进程、不清旧锁、不删证据。
5. 结果只定位状态卡阶段；第四pytest断言、修复、提交/对齐/ff、真实数据/专业/L2、生产和外发分别按现有闸审。

## 4. 申请决定

按上述精确EOL身份修订，批准两新SHA执行同一份已批准的一次诊断及原副作用。申请原因是原批准指定的两份脚本已经冻结；更换冻结执行文件需本人明确批准。本件不增加诊断次数、测试范围、网络目标或进程清理范围。批准前只登记正式计划/脚本/证据，继续其他已批准泳道。
