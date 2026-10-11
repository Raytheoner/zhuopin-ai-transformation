# O3 P4：精确 EOF 差异证明补充执行计划

状态：具体供审；本补件尚未获批，未运行新生成器或 runner。

## 固定批准对象

正式计划目标：`C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-11-o3-p4-eof-entry-count-amendment.md`。正式新生成器目标：`C:/Dev/zhuopin-ai/docs/superpowers/plans/o3-p4-substage-diagnostic-1011/generate_p4_substage_copy_eof_v3.py`，SHA256 `11FB9FF1FD0CD4782E9873EECA4EBEE885F8B59B8245736414A80B04DA2A65DF`。根按候选原字节登记后重新核对 SHA，只有正式路径可启动；原冻结生成器不修改。

原计划 `2026-10-10-o3-p4-substage-diagnostic.md` SHA `B4220068BB73C6DC3D4372E025A6BC53F4562762058FF7EF8F28BBBBC6F7C43E`；启动权限补充 `2026-10-11-o3-p4-start-permission-amendment.md` SHA `36AB2C961CB86501B69D6B0024FE1C1F9558F7D8F47B91ACC208E404FB1107AF`。两项既有批准保留；本次更换生成器及差异证明需新的明确 A。

冻结 runner：`C:/Dev/zhuopin-ai/docs/superpowers/plans/o3-p4-substage-diagnostic-1010/run_p4_substage_once.py`，SHA `0026B2FB6D23271FE6B1C5B0F5FF7ED11EE2B7C2004C3AFF572A258906DB9320`。原生成器 SHA `4AD3BE7691D4DA768720F130AA79CBEDE0FAF53E9B4372048FF4442D31849E8E`；其 instrument()、13 anchors/markers、P7 分支与 generation `p4-substage-v1` 均保留。

Native：`C:/Users/Paul Shao/.codex/worktrees/o3-recovery-fix-1006/zhuopin-ai`，HEAD `0ad830234af70585d359df23123973eceeace3a3`。状态卡源 SHA `BC774E0C9965BE22981390AF7B3255525C87B07038ECB87E2CAB46FDF34A35DF`，CI节点 SHA `4990DDB836775D92DA18FC41998271FA77DDC5AF2BFCE305D30A18A77DAFB360`；原五文件 import closure 及唯一精确 EOL pair 逐项保留。

## 已观察事实与最小改动

36AB 获批重启在新 UUID `bed61fa7ce7c4b9d9a7de721e583a4b5` 的 diff guard 退出1；未产生 markers.diff/source-manifest.json，runner/本轮180秒诊断为0次。原始源 CRLF 分行、无终止换行，P7 原逻辑在副本末行添加单个 CRLF。字节比较证据：`reports/o3-fourth-ci-1010/p4-start-failure-1011/bed61fa7ce7c4b9d9a7de721e583a4b5-diff-analysis.json`，SHA `96DE24511AD1BE1C692667059B8AD3E874BD187348B2145ED2A94C65525EE348`。

1. 新生成器只接受上述冻结源 SHA、BOM、CRLF/no-EOF 形式，先核 Native HEAD、主仓同源、CI节点与原 closure/EOL pair。
2. instrument() 不变。真实 raw diff 必须为14 additions/1 deletion；比较基线仅取 source_raw 加一个 `0D0A`，EOF视图必须为13 additions/0 deletions且13标签顺序精确。不能宣称 raw 零删除。
3. 从副本剥离恰好13个有序 marker 行、恢复原BOM，字节必须等于 source_raw 加单个CRLF。所有证明在 UUID/输出目录创建前完成，任一失败停止。
4. manifest 仅追加 raw_diff_summary、marker_view_diff_summary、eof_separator_proof；如实写 separator_applied_to_copy=true、source_bytes_modified=false，明确该 CRLF 来自既有 P7 分支。markers.diff 是 EOF 比较视图。原 source 不改，副本不另 normalize。
5. 冻结 runner 不改、不读 markers.diff，既有字段/SHA/labels/closure门保留；新增字段只作证据，不能替代原门。兼容结论限静态源码审查。

## 获新 A 后的唯一执行序列

1. 根绑定本正式计划、新生成器和冻结runner全SHA及直接人批证据。用固定隔离 Python `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe -B`，工作目录 `C:/Dev/zhuopin-ai`，在 `require_escalated` 下调用上述正式新生成器一次。其 Git rev-parse/check-ignore只读、输入读取和新 ignored UUID 输出均在本次范围。不得因失败自动重试。
2. 生成成功后只读核新 UUID 的 manifest/copy/closure/两种diff/EOF字节证明及13 labels。任一不符停止、保留输出。新 UUID 只在 `C:/Dev/zhuopin-ai/reports/o3-fourth-ci-1010/runs/` 下；旧16ec、bed61及既有任何目录不复用、不覆盖、不清理。
3. 全部门通过后，仍用上述隔离Python，在 `require_escalated` 下按原B422命令调用冻结runner一次，传唯一新 run-dir；同轮首次180000ms诊断，原 cwd/PowerShell、条件 LAN .51 四个/api/ping GET保持原文。旧16ec已耗预算不续跑。本补件仅允许此次新生成及其首次runner，不允许第四pytest或修复。
4. 副作用限新UUID内状态卡/五文件闭包副本、markers.diff、manifest、原runner stdout/stderr/运行metadata与其 Windows Job 进程树。仅清理本次 Job 所属子进程；不碰其他进程/服务/原件/候选Git。所有失败保留证据并停止依赖步骤。

## 审查与边界

v1候选计划/identity和未通过审查保留。v2须根与独立Luna核对四项：字段真实性、正式路径/SHA、generator require_escalated副作用、纯编号清单。禁止pytest、业务代码修改、Git写入、ff、push、生产部署、真实对外发送。推荐A：批准本正式补件和上述唯一执行序列；B：保留停止。推荐不等于授权。

## v3：计数在 diff 迭代项拼接前完成

已登记v2生成器6818D6/计划BCF8DC仅作为历史供审件保留，发现计数遗漏后未运行。原EOF删除项不带换行，先join文本再splitlines会把下一新增原末行并到删除项，导致raw计数误拒。v3保留unified_diff迭代项list，先逐项计数14/1，再join用于原始文本SHA；不加终止符、不改raw数据。marker-view仍用源加单CRLF视图计数13/0，exact-byte proof、13markers、instrument()、runner及单次/sideeffects全部不变。新增count_basis明确计数依据。旧第2项BCF8DC供审问题已撤回启动用途，须针对本新正式计划及v3生成器SHA给明确A；不得凭旧版回答启动v3。根/独审仅作静态推理，不执行示例、生成器或测试。
