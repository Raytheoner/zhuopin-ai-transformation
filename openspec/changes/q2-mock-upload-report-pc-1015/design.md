## Context

See proposal.md。已读Q2已确认intent、原D1–D8/design/tasks、webapp/feed_source/models/engine及#612/#652/#661/#681来源。主仓`webapp.py`SHA256=`27D263FE6B329717C173C596142655C88132159E41C7F3B942F57167D1DFB27E`：现有GET固定样本和ping，未有上传。#661展示已归档。#652原离线实现的模型线程最新为interrupted/notLoaded，Workflow仍busy=true、delivery_accepted=false且留context_stopped；只保留事实，不称仍在后台跑，不清旧busy/claim或重做其51测局部成果。

## Goals / Non-Goals

**Goals:** 给档1增加合成JSON文件输入与同一份报告的可访问闭环；保留已签引擎结果及来源/规则版本，成功必须有精确结果与audit证据。独立于#652八个离线模块。

**Non-Goals:** 真实PPT/DOCX/PDF与QD-A接线、真实/新语义模型、人工改分/专业签认、正式退回签发、门户全局改造、生产/永久端口、旧Workflow结算。原L2和两项PENDING不变。

## Decisions

### D1 只增加4条产品/测试路径

场景根`4-数字员工/质量部/Q2-8D报告AI判定/`内：新`q2_8d_verdict/mock_upload.py`（typed输入、受控结果/审计适配及表单片段），修改`q2_8d_verdict/webapp.py`（既有factory增加可选显式配置/可信权限hook与路由接线），新`tests/test_mock_upload.py`、修改`tests/test_webapp.py`。没有新依赖/模板文件/平台或原8个离线文件。沿原#612；若实际归属/字节已变化先核新写者，不覆盖。主会话串行、仓库内ignored独立tree，普通检查点与分离自查。

### D2 合成输入必须完整标记，复用现有typed引擎

UTF8 JSON合同`q2_mock_input/v1`：`schema_version`、`mode="MOCK"`、`customer_id="MOCK-OEM-A"`、`project_id="MOCK-PROJECT-A"`、非空`source_version`、`source_ref`以`mock:`起头、`extracted_at_utc`为带时区ISO时点或null、`report`。report显式含`report_id/sections/scene/template/safety_related/safety_confidence/asil_level/trace_fields/is_external`，逐项映射现有EightDInput；无任意meta、expected或专业规则覆盖。场景/模板/置信枚举按现有合同核，不把未勾选/未知/低置信提升确认；段落可为空并交原结构闸，不把解析失败当空段。JSON大小≤2MB，重复key/未知字段/错误类型/路径型source/跨客户/非MOCK拒绝。只解析JSON，不执行上传内容、不打开source_ref。

示例下载从既有合成`feed_source.load_mock()`投影输入，不带expected/真实件；下载同时标明合成来源版本。生成器不得重写原样本或黄金预期。原始上传字节/hash、用户明确版本/时点与运行保存时点分别保留；没有源时点显示未提供。

### D3 计算行为沿原引擎和签认，不扩大分析

用既有`VerdictEngine(semantic=PendingSemantic(), audit=None)`执行单份输入；外层为本操作写唯一、可验链的合成审计。直接复用`Verdict.to_dict()`和既有详情/页样式。原结构闸、分数、区间、规则/红线状态、处置建议、安全分流均不改；语义未上线不能变最终等级。C/D由既有AsilExcludedError在评分前退出，报告不生成。不执行旧离线source、不签PENDING、不加入黄金答案或新阈值。原只读GET汇总/ping/共享口令门禁契约保留，不借新入口改变原身份语义。

### D4 成功须绑定精确来源、规则与结果

仅在本候选ignored运行根保留源、不可变结果、pending及audit。操作键绑定原始输入hash/规则集hash和版本/合同版本；durable pending保留首次规范payload和时点，重试回读同一结果，不覆盖旧对象。source/result写入fsync→hash回读；平台AuditLogger.jsonl/record(AuditEvent)→按scenario/action及operation/object/input/result hash回读唯一事件→verify_chain有效/非空且无降级error→原子不覆盖发布→再回读才显示成功。失败保留pending/audit现场并返回503，不显示空报告或保存成功。

审计action采用独立`mock_upload_report`，automation_level=L1、evaluator显式synthetic演示身份；原结果business automation level仍为既有L2建议，二者分列。audit仅opaque操作/对象ID、hash、规则版本和MOCK来源，不含原文/客户/段落/风险明文；结果保留在受控对象。查看/导出也核原对象与audit，不能用最新不相关事件充数。

### D5 入口复用前缀，写入默认deny

在`/quality/q2`下增加`/mock-upload`（表单）、`/mock-upload/example/<token>`（合成示例JSON）、POST`/mock-upload`、GET`/mock-results/<id>`、GET`/mock-results/<id>/export`。新读/写/导出均消费可信注入权限；默认关闭，必须显式MOCK演示开关+注入synthetic身份/权限才启用。请求头/body不能自授身份；不修改原口令或SSO。表单CSRF/同源、大小上限、HTML转义、no-store与安全错误；无凭据/权限/安全设置修改。成功303明确HTML，API保留明确JSON。

### D6 临时访问、验证与原记录

获批后在`reports/q2-mock-upload-pc-1015/worktree`分支`codex/q2-mock-upload-pc-1015`固定创建时主线HEAD；证据、runner、JSONL/JUnit、临时数据仅本任务reports。提供只绑127.0.0.1的临时演示，说明进程/重启后失效及恢复命令；保留FI5/FI14/Q9入口，不新增永久端口/任务/生产监听。先分片TDD，再Q2完整pytest和原黄金/UI必要回归，源规则与PENDING字节不变，实际浏览器下载示例→上传→查看/导出→audit回读。完成后回写原#612，#652原state与claim保持。

## Risks / Trade-offs

- 合成JSON不是专员真实Office上传 → 此片只交MOCK路径，质量部16真实使用问题保留；真实解析与材料权限另闸。
- 同场景旧#652未结算 → 精确排除其8文件及engine/config；归属再核，冲突停止，不清状态。
- 作者自查没有第二审阅人 → 与现行串行规则一致，完整测试/实际操作留证，ff/发布仍需逐项批准。

## Migration Plan

新入口默认关闭，候选不合主线；失败关闭新写入并保留对象/审计，原GET展示仍可用。无生产迁移或旧数据删除。专业G-01/G-02/G-04、真实身份与真实源/部署均后置，不阻本片合成实现。
