# Q2 合成文件上传与单份报告 · 设计及4文件实施供审 v1

状态：待Shao Peishen一次明确批准本计划第1–5节及绑定OpenSpec实际design。未创建Q2产品树、改产品、跑新Q2产品测试或改旧Workflow。沿原#612（回件#681）承接，不另造业务任务。

## 1 具体问题与既有授权

质量部16反馈不能上传并取报告。主仓Q2现有GET只显示固定合成集合，未有上传路由；此为代码核实，非现网故障复现。既有Q2 intent/D1–D8及展示合同不重审。原8A只准离线语义8文件，明确排除Web/上传；51测局部成果与interrupted线程/旧busy=true都保全，不将其重新实现或更改状态。本次批准仅解决新增PC合成输入路径。

绑定`openspec/changes/q2-mock-upload-report-pc-1015/`的proposal/design/tasks和`specs/q2-mock-upload-report/spec.md`，design D1–D6定义全部行为；本计划与四件经strict验证后冻结hash，登记于原队列定夺行。不将design通过自动当作实现已批；本次选项A显式同时批准设计和以下实现范围。

## 2 精确4路径与typed接口

场景根`4-数字员工/质量部/Q2-8D报告AI判定/`：

1. 新`q2_8d_verdict/mock_upload.py`：严格输入、单次编排、源/结果/pending、audit适配、只读回读及导出。
2. 改`q2_8d_verdict/webapp.py`：原factory增加可选演示开关/可信权限与身份hook和受控路由，复用现有CSS/报告详情；既有默认GET/ping/门禁不变。
3. 新`tests/test_mock_upload.py`：输入、业务一致性、source/hash/idempotency/audit/存储失败与隐私。
4. 改`tests/test_webapp.py`：文件上传/结果/导出、权限/CSRF/同源/HTML与原门禁回归。

新增模块最小接口：`parse_mock_upload(raw: bytes) -> MockUploadInput`（frozen，包含EightDInput、源版本/时点和raw SHA）；`example_input(token: str) -> bytes`（只投影既有合成样本、不带expected）；`MockUploadService(root: Path, audit: AuditLogger)`；`submit(raw: bytes, actor: str) -> SavedMockReport`；`get(object_id: str) -> SavedMockReport`；`export(object_id: str) -> bytes`。SavedMockReport绑定opaque object/operation、source/result/rules hash、原Verdict payload与精确audit receipt。所有异常固定安全code；原始业务字段只留受控对象。

factory新增参数均有保守默认：`mock_upload_enabled=False`、`mock_upload_root: Path | None=None`、`mock_upload_access: Callable[[str, str | None], bool] | None=None`、`mock_upload_actor: Callable[[], str | None] | None=None`；未显式配置新操作deny。保留现有identity_resolver/audit_path签名及原展示行为，不从HTTP身份头/body授权新操作，不改共享口令。

不改engine/config/semantic/rules_loader/feed_source/models/样本/黄金/原8个offline路径、QD-A、共享平台/门户/CI/依赖。实施前若现时hash或归属变动须核他人变更，不能覆盖。本轮webapp已核SHA `27D263FE6B329717C173C596142655C88132159E41C7F3B942F57167D1DFB27E`。

## 3 执行位置与允许副作用

1015主会话串行，在`reports/q2-mock-upload-pc-1015/worktree`新隔离分支`codex/q2-mock-upload-pc-1015`，固定创建时主线HEAD。原Q2树/未提交8文件/Workflow/claim/失败证据一律保留，无Guardian接续、新代理链或机制更改。主仓仅本change/计划/证据及原任务按锁登记。仅任务reports下新UUID basetemp/JUnit、受控合成源/结果/pending/audit、runner与本地Git检查点；不删旧数据、不改ACL/全局editable，不安装依赖。

提供临时只绑127.0.0.1的演示入口，路径仍在`/quality/q2`内；无常驻/永久端口或计划任务，对外端口、门户注册与生产服务不改。保留FI5/FI14/Q9已有入口。进程/电脑退出后失效，交付提供真实PID/恢复命令。Python沿现时项目隔离环境；Windows不覆盖文件发布若sandbox拒绝，用受支持host执行请求并留证，不改安全设置。

## 4 串行实现和验证

1. parse/示例合同：行为RED→GREEN，2MB/重复key/unknown/type/enum/跨客户/非mock/source路径、显式null时点与空段分开；输入字节保全。示例不带expected。
2. 原引擎编排：同一EightDInput同结果，PendingSemantic、分数区间/原结构闸/红线/安全分流不变；C/D退出。真实源和语义调用为零。
3. 原子源/结果与audit：durable pending固定首次payload，幂等重试同对象；fsync/readback→唯一audit事件及有效非空验链→不覆盖发布→回读。写/查/链/发布故障分别注入，失败不显示成功，保留现场。audit字段无原文/客户明文。
4. PC表单、文件/JSON、报告、导出：新操作默认deny，可信演示双开关、CSRF/Origin/HTML转义/no-store、安全状态码和明确HTML导航。原只读UI/门禁全数保留。
5. 分片保存检查点，最终在Q2根完整`python -m pytest -q --tb=short --junit-xml=<任务reports>`，unique basetemp；仅此子项目。核4路径/规则样本/PENDING hash、必要黄金/UI回归、动态CI发现和引导；实际浏览器下载合成示例→上传→单份报告→导出/audit，同对象证据齐再记MOCK交付。无独立代理审查，主会话分离自查。

## 5 一次决定与停止边界

A（推荐）：批准绑定OpenSpec design D1–D6及本v1第1–5节，原#612独立4文件、主会话串行/隔离候选/合成验证/临时本机演示。获批后直接完成上述切片，不逐片重复审批。B：只保留供审件，暂不新增Q2上传实现；不影响已交FI5/FI14/Q9演示。

MOCK结构化JSON不等于真实Office解析；后者继续按质量部16需求留步。本次不含真实数据、真实语义/校准/专业签认、正式退回/付款、账号权限/凭据/安全设置变更、旧busy/claim清理、ff/push、门户/生产或外发。缺新产品路径/依赖或真正现时争写则停相应项报精确差量；已有审批不重问。
