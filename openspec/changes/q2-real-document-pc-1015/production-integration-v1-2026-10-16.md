# Q2生产接入 · 最小设计与实施包 v1

记录时刻：2026-10-16T09:04:10+08:00（北京时间）；原612、§四331单次供审，尚未批准新增实施/探针/协作发送。

> 执行方式：1015主会话使用executing-plans串行完成Q2部分；不派子代理、实现代理或自动审核链。门户原维护范围由1013协调承接，未认领前不写。用户既定执行方式覆盖技能的默认派生建议。

**Goal：** 将已交付的真实单件PPTX→39项完整AI建议→五表Excel，准备成能接入真实企微身份和现役门户的可验候选；本件尚不批准生产切换。

**Architecture：** 复用现役网关OAuth、权限映射及Q2访问回调；只为Q2新增真实OAuth来源凭证和会话代理合同。Q2保留单客户/同件白名单、进程内串行处理及原评分/审计；不建设身份平台、模型中台或调度框架。

**Tech Stack：** 现有Flask/Waitress、stdlib HMAC、现有Codex业务适配器gpt-6-luna/high、已验的8项Windows CPython3.14依赖闭包。无新业务规则或模型替换。

**Spec：** 本件§3 D1–D8；文件范围§4，授权范围§6。绑定原业务612；326A、329A、330A的冻结原件不改、不扩解。

## 1. 已有成果、目标与本次边界

主仓/origin产品提交均为`e4c6da8d53f02972bc4278ab8e291a18e6ce7e52`。原22路径及205测绑定、Excel实机及原HTTP回放证据已交；ff/push执行前后124保护路径字节/存在性保持。原临时本机演示、真实报告、旧树、原任务状态保全。新候选仍沿原612，在仓库内本任务独立worktree执行。

本次目标是在本机完成生产接入候选、合成网关联验、打包/回滚/预检工具，并查明正常服务账户模型前置。浏览器由Shao Peishen稍后手核；质量反馈不阻塞上述构建。专业签认/10件校准不因本件变成通过。

原329A/330A仅授权原22路径的具体整合，现已执行完毕；不套用于本次新增适配。实际候选形成并绑定hash、回归和运行环境后，再一次集中办理该候选的ff/push及具体生产切换闸，不对未形成的生产版本泛批。

## 2. 四类缺口、归属及已完成核验

取证基准为北京时间2026-10-16；细时刻、原回显及SHA见`reports/q2-production-intake-1015/ownership-evidence.json`及同目录原始回执。队列来源均为官方查询工具；未通读真身。

|领域|已经核实|实际责任与缺口|1015边界|
|---|---|---|---|
|身份|现网HTTPS健康/登录页200，OAuth与mock链接同时存在；OAuth start302给出的callback仍为http、无8443。网关4个核心源文件与主仓LF内容全同。原240已有OAuth配置落位历史，不能再按缺凭据派单。|原162环境线已归档、197合入已done；240保留IT外部前置/回调历史。本轮未找到Q2接入的活跃认领者。推荐1013协调原门户维护方明确承接；不虚报其已开工。|不写门户/权限映射/凭据；做Q2访问适配及本件接口合同。|
|网关会话|现网源码当前无显式Q2路由；Cookie被过滤，尚无经验证个人身份转交；默认代理30秒。旧mock签名会话最长30天，仅关闭登录开关不足以撤回已经签出的会话。|门户原维护范围；需限于Q2的真实身份来源、会话、Origin及异步303/轮询合同，不能用共享口令或原样X-Zp-Identity作真人证明。|只消费明确合同。对方未认领/接口变化时继续本线模拟，不替其修改源文件。|
|模型通道|Q2任务及8098实际进程为SYSTEM；8090实际进程为Administrator，而网关计划任务为Ready。SSH是Administrator，PATH及已列固定位置未见Codex，不代表SYSTEM或全机绝无Codex。未调用模型、未读取登录凭据。|现役Q2运维账户条件尚无可用证明，也未查到本次模型接入执行人。建议1013协调原Q2运维/IT陈承核正常服务账户入口；陈承的IT专员身份来自人员正本，本建议不冒称其已承接。|提供有界探针及回执消费；不新建SYSTEM任务、不模拟账户、不复制凭据、不安装CLI/改登录或服务身份。|
|依赖/部署|现有C:/q2/.venv解释器实测3.14.5/64位；此前该解释器探测缺5库。监听进程的ExecutablePath不能单独证明其sys.prefix/导入路径，实际启动环境仍需同身份回执。仓库Q2当前无受控部署/同步ps1脚本。|Q2业务代码、私有依赖及发布候选由1015负责；实际生产环境操作仍需具体候选批准。|已准备8项精确已测版本wheel；只构建Q2工具，不复原旧部署分支或修改共享Python。|

离线包已形成：`reports/q2-production-intake-1015/q2-production-dependencies-2026-10-16.zip`，12,379,981 bytes，SHA256 `4a7f5cb182cf72f93641b7828dc8434de7448cba47713982f048ad039de5118a`。含python-pptx1.0.2/Pillow12.3.0/openpyxl3.1.5/XlsxWriter3.2.9/xlrd2.0.2及lxml6.1.3/typing_extensions4.16.0/et_xmlfile2.0.0；逐wheel核PyPI摘要、CPython3.14/Windows64标签及非extra依赖闭包，无未锁传递项。只是下载/验包，没有安装或证明SYSTEM下EMF/模型可用。

本轮首次复验门户当前基线：在`5-平台底座/unified-portal-gateway`运行项目隔离Python的`-m pytest -q --tb=short`，临时目录和JUnit均在本报告目录；实际`84 passed in 1.00s`、exit0，无skip。`gateway-baseline.xml`留证；是既有mock测试，不是现网登录证明。Q2原205测代码/依赖未改，未机械重跑。

销售1011只读核到的范围为销售快照/页面；1014仍负责SC2，均不纳入。本轮不改规则、机制、全景、其他业务文件；不恢复已done的162/197或原旧task/claim。

## 3. 一次设计 D1–D8

### D1 单件、单客户和试评主体

资料仍仅既有PPTX：OEM-A-01/A0/ASIL B，源SHA256 `c8b52f55e0d2e76686619b7a8017e0a0bb90861393d5be57e9f9031d5842e069`。不扩客户/版本/格式/样本数，不加入招聘。

建议首批应用内名单只含`ShaoPeiShen`与质量专员陈忱的`ChenChen`，两者字面值均在既有名录/门户映射可核；不改门户部门角色或企微应用可见范围。需要本次批准这份Q2业务名单设计及实现，但本阶段不向两人开通生产真实上传。每名用户只操作/读取自身对象，actor写为`wecom:<userid>`，不把local:1015改名冒充真人；不共享其他用户对象。现有本机local分支保持原授权。

### D2 仅Q2的真实OAuth来源凭证（门户方负责）

沿用原OAuth换取userid及会话签名密钥，不复制密钥到Q2、不新建密钥。新增用途隔离的`zp_q2_oauth`签名Cookie，只在真实OAuth回调成功且state验证通过后签发；载荷含v=1、provider=wecom、aud=q2、userid及过期时间，签名域前缀固定`q2-wecom-verified-v1|`。Secure/HttpOnly/SameSite=Lax，Path=/quality/q2，最长8小时。旧zp_portal_sso、mock登录、应急登录都不能换取此凭证。

Q2路由必须验证该凭证和既有quality权限；没有凭证就引导真实OAuth流程，配置不全则明确不可用，不落到mock选择页自报身份。仅为Q2发起的OAuth流程使用固定公开origin `https://aiportal.equalitytec.com:8443`生成callback，保留https和端口，不信任调用方Host/X-Forwarded-*来决定回调。其他门户路由、现有mock入口和角色映射保持现状。实际真人登录仍须后续验收，起跳302不是登录成功。

### D3 Q2限定代理与后端信任合同（门户方＋1015分界）

门户新增`/quality/q2`白名单路由到现役8098；只对该路由删除调用方X-Zp-Identity/X-Zp-Auth-Method并从真实凭证重填：userid字面值、方法`wecom-oauth-q2-v1`。请求Cookie只转发Q2自己的`q2_review_session`；不把门户签名Cookie或秘密转给Q2。响应保留Q2 Set-Cookie/Location及no-store；Origin原样传递。

Q2只在底层socket REMOTE_ADDR为127.0.0.1/::1、生产profile已明确启用、既有共享门禁已配置且名单/方法一致时接受这两个头；不使用X-Forwarded-For判来源，不接受LAN直连伪造头。保留现役监听和旧只读路径，不改防火墙、不改其他端口。该合同信任本机原网关进程，不宣称防御已控制服务器本身的管理员。

真实POST继续只做接收→303对象地址，状态由GET轮询，模型在既有单线程中运行。代理30秒不扩成600秒长连接；验证正常上传/状态/Excel路径均能在代理时限内返回。Q2 CSRF比较固定公开origin，Secure/HttpOnly/SameSite=Strict/Path=/quality/q2；重启后会话失效应要求重新打开表单，已保存对象不丢。

### D4 Q2业务身份与审计

新增纯函数`resolve_principal(remote_addr, userid, auth_method, allowed_userids) -> str | None`，只产生`wecom:<userid>`或None；runner注入actor/access回调。服务层接受明确local/wecom格式，所有get/evidence/export/asset仍核同actor、同scope。原业务操作键/不可变对象/唯一audit不变，不映射旧local对象给真人，不借本件恢复旧作业。AI仍只出建议，professional_signoff始终false。

### D5 正常账户模型通道的有界前置

预检输出当前SID、sys.executable/sys.prefix/base_prefix、库版本/路径、指定CLI绝对路径/版本/hash、必要能力及受控运行回执；不输出环境变量值、认证文件或配置密钥。服务器CLI路径只能来自原运维确认的现有合规通道，不静默找另一个模型/账户。

建议新增授权至多**1次合成Luna/high通道探针**，90秒上限、read-only/ephemeral/结构化JSON、零工具，沿326A的能力收窄/正常hooks与trust。无真实件、无重评分、失败/未知结果不重试。必须由现役Q2正常运行身份（当前SYSTEM）通过其原运维入口执行；Administrator/本机已有成功不得代算。1015不为代测注册新SYSTEM任务或切换身份。没有可用入口或可核回执就明确该前置未解，继续本线模拟构建；CLI安装、登录、凭据复制、账号/权限或任务身份切换不在本次范围。

### D6 私有依赖与可审部署候选

8项依赖固定为§2的已测版本和wheel SHA；禁止在线自由升级或补装平台整套重依赖。预检先确定实际启动环境及Q2独占的私有venv/平台导入路径；只有正常身份回执证明正确才作为部署环境。Q2部署工具只生成/演练“原Q2实例、原账户、原监听＋版本化代码/8库”的方案；不改全局Python、不重装共享editable指针。

产物包含确切Git清单、代码/规则/平台指纹、依赖锁和诊断/冒烟/回滚指令，无真实件/报告/截图/模型响应/.env/凭据。实际应用步骤默认DryRun，-Apply须核另行批准的具体候选与目标基线；本阶段禁止执行。快照原Q2任务/代码/私有依赖/数据审计指纹，保留原实例，失败恢复原版本和实际运行状态；不清数据、不删旧锁、不重建第二服务。缺受控旧部署脚本时生成本线新的明确脚本，不假装旧部署阶段已通过。

### D7 验证分层

先合成失败用例→本机Q2/网关接缝模拟→同件已有响应只读回放/Excel验真→各受影响项目完整回归。Q2完整149基线加新用例；网关完整84基线加新用例由门户承接者执行。QD-A代码/平台/依赖未变时复用56；运行布局或依赖实际变更后补对应完整回归。不能过滤、改断言或随意skip求绿。

本机签名fixture不是现网真人SSO；SSH诊断不是SYSTEM通道证明；wheel标签不是服务器安装成功；完整回放不是浏览器手核；产品测试不是部署或专业验收。本件不新增真实Luna评分调用、不把单件结果当10件校准。

### D8 所有权与持续执行

1015仅认领§4的Q2 17文件，在仓库内独立worktree逐片实现/定向测试/检查点；原树和其他修改保全，不自动跑Guardian或清锁。门户6文件是明确接口请求及候选范围，**1015不写**；建议一次授权后将本件发到现有`[Win]1013V-SC2恢复接力`（01a13466-bde4-77f3-bd68-a996bf9b66f9）请1013协调/确认门户原维护方及模型运维承接，并允许其向本1015会话回传确认/回执。无需新建会话/代理，不对IT/质量外发信件或真实资料。

门户方先按既有队列流程认领不冲突触碰区；不能自动恢复已完成162/197或把240历史blocked字段直接改绿。若对方未接手，1015继续自己的可测试切片，并在原612留清楚外部前置；不把责任分配建议写成已接受。

## 4. 精确文件范围、接口与串行切片

### 1015唯一写入范围：Q2目录内17文件

下表路径均相对`4-数字员工/质量部/Q2-8D报告AI判定/`。开始前逐一核实际HEAD和现时归属；新建不覆盖已有文件。同名文件若已由他人写入即停相应片，不覆盖。

|#|文件|动作及职责|
|---|---|---|
|1|q2_8d_verdict/production_access.py|新增：生产设置、resolve_principal及访问合同；不自建登录|
|2|q2_8d_verdict/webapp.py|修改：消费可信回调、生产Origin及Cookie配置；原页面/评分不重构|
|3|q2_8d_verdict/document_upload.py|修改：明确wecom actor格式，保持逐对象归属、同件范围及审计|
|4|q2_8d_verdict/model_adapter.py|修改：可核的指定CLI绝对路径/版本绑定及探针，不换模型或认证|
|5|scripts/run_q2_web.py|修改：明确local/production profile、保守关闭、正常环境预检及注入|
|6|scripts/q2_production_preflight.py|新增：只读正常身份、实际环境、依赖/模型诊断与有界合成探针|
|7|scripts/build_q2_release.py|新增：只包含批准代码/锁/工具的带hash发布包，不带真实数据/秘密|
|8|scripts/deploy_q2_release.ps1|新增：默认DryRun、具体版本/目标快照/回滚和原实例动作；本轮不Apply|
|9|scripts/smoke_q2_production.py|新增：健康、会话/伪造拒绝、状态/下载及审计检查；真实调用需另绑定|
|10|requirements-production.lock|新增：8项精确wheel与SHA，不升级共享依赖|
|11|tests/test_production_access.py|新增：身份来源、名单、直接LAN/伪造头拒绝|
|12|tests/test_production_runtime.py|新增：启动环境/前置缺口/无模型不冒成功/探针预算|
|13|tests/test_webapp.py|修改：生产Origin/Cookie/CSRF/状态/Excel和旧local/MOCK回归|
|14|tests/test_document_upload.py|修改：wecom对象归属、异用户拒绝、幂等/审计|
|15|tests/test_model_adapter.py|修改：CLI路径/模型/工具/超时错误，无自动重试|
|16|tests/test_release_package.py|新增：精确清单、依赖锁、敏感产物排除和部署DryRun/回滚fixture|
|17|CLAUDE.md|修改：候选/profile/验证分层及真实剩余条件；不宣告生产|

除上述17文件外，1015仅写原包新增本设计/实施记录、原R5和原任务登记。评分规则/engine/ai_advice/excel_report、QD-A、平台、SC2、机制规则与旧任务文件均不动。

### 门户原维护方候选范围：6文件，1015不写

均相对`5-平台底座/unified-portal-gateway/`：`portal_gateway/sso.py`、`portal_gateway/webapp.py`、`portal_gateway/routing.py`、`tests/test_sso.py`、`tests/test_webapp.py`、`tests/test_routing.py`。D2/D3只使用这些文件；不改department_mapping.yaml、permissions.py、网关部署脚本/.env、其他服务或规则。若原维护方核实需扩大范围，先给具体差量，不把本件扩大解释。

### 串行切片与针对性核验

1. **身份/对象切片（1/2/3/11/13/14）**：先RED验证下面最小用例及已有local分支；实现纯resolve_principal和runner注入合同。每片只跑相关tests，GREEN后保存候选检查点。

```python
def test_lan_caller_cannot_assert_gateway_identity():
    from q2_8d_verdict.production_access import resolve_principal
    assert resolve_principal('192.168.100.9', 'ChenChen',
                             'wecom-oauth-q2-v1', ('ChenChen',)) is None

def test_local_gateway_has_explicit_real_oauth_method():
    from q2_8d_verdict.production_access import resolve_principal
    assert resolve_principal('127.0.0.1', 'ChenChen',
                             'wecom-oauth-q2-v1', ('ChenChen',)) == 'wecom:ChenChen'
    assert resolve_principal('127.0.0.1', 'ChenChen',
                             'mock', ('ChenChen',)) is None
```

2. **运行/模型切片（4/5/6/12/15）**：先测试错误CLI、错误账户回执、缺库、能力不能收窄、模型不符、90秒未知结果均不ready且不重试；再实现明确profile及诊断。指定CLI、模型和正常身份回执都可核时才由原运维消费一次合成探针授权。没有通道不阻塞本机测试及发布工具构建。
3. **会话/代理联验（2/11/13及门户方6文件）**：在本机用合成SSO签名fixture验证旧mock/应急/过期/错aud均拒绝；真实用途fixture→Q2表单Cookie→同Origin POST→303→状态→Excel，错误Origin/跨用户/伪造头无作业/audit。Q2测试从本项目根运行；门户回归在其项目根，由承接者绑定实际候选。
4. **依赖/发布切片（7/8/9/10/16/17）**：8wheel逐包SHA和闭包验真；发布ZIP排除`.env`、auth/config秘密、真实源/报告/截图/模型响应；DryRun验证目标只限原Q2私有目录和原实例。实际依赖或布局改变时在该候选环境补完整回归。不开新服务，不执行生产安装/切换。
5. **最终候选收敛**：完整Q2、受影响网关、必要QD-A回归和同件缓存回放/审计验链；保留所有失败/未知状态。记录实际候选HEAD、精确路径/代码/依赖hash、各项目命令与原回显、公开origin及正常账户证据。更新原612/R5；形成实际可审部署件后再集中端出具体发布闸。

## 5. 验收证据、外部前置与停止条件

**Review Focus（五类必须覆盖）：**

1. 原mock签名Cookie尚有效且userid为管理员：Q2仍拒绝，无真实作业/audit；仅有真实OAuth用途凭证才继续。
2. HTTPS:8443经代理后回调变成http/无端口：Q2流程的callback必须精确为`https://aiportal.equalitytec.com:8443/portal/_sso/oauth/callback`，不借信任任意转发头修复。
3. Cookie/Origin不一致或服务重启：保留原门户会话，Q2重新取得自己的CSRF；失败不新建模型作业，已保存对象仍可由原actor核验。
4. Administrator跑通、SYSTEM没证明，或venv路径仅凭进程exe猜测：前置为未解；不伪报ready/新后台运行，不切换账户冒测。
5. 错客户/文件hash/actor、依赖或审计失败：明确拒绝或未确认成功；不变零/不补假分数、不覆盖别人的对象/现场。

真正外部前置为门户承接确认和正常服务账户模型条件；质量部反馈不列前置。服务通道不可用时责任缺口明确交原维护方，1015保全候选及恢复步骤，不额外搭建桌面转发/轮询worker或改凭据绕过。

截至供审：零新模型、零新真实件、零生产安装/重启/配置/角色/凭据变化，未对现网进行真人OAuth登录。当前公开起跳/源码/依赖证据是准备成果；不是新生产入口已经交付。

## 6. 本次一次集中申请与明确排除

**A（推荐）：一次批准本件第1–6节及D1–D8，允许1015按精确17文件串行实现、任务内依赖/打包/本机合成联验和同件已有响应回放；允许门户6文件由1013协调确认的原维护方按本合同实施，本1015不写其文件。** 同时批准向现有1013会话发送本绑定包和原612接口/模型前置请求，并允许该会话回传承接确认/回执；不新建派生会话/代理或修改其现行模型。一次正常服务账户下的合成Luna/high通道探针按D5的前置与上限执行，不传真实件。

应用内2人名单只作为本件限定试评的设计/候选，不更改企微账号角色或门户映射；实际生产真实数据接入仍留至具体候选闸。任务内依赖不代表服务器安装批准。此A不授权新CLI安装、登录、复制/变更凭据、账号或安全设置、Q2任务身份切换、生产上传/实际部署/重启、全网关改造、新ff/push、对质量/IT等外发消息或商务行为。若同身份执行探针需要新特权入口或账户操作，停该步骤，不以探针批准代替权限批准。

**B：保留已推产品和上述只读准备，不开始本件新增代码及协调发送。** 329A/330A已执行事实保持，不重复申请；本次无默认授权。批准后范围内连续推进，不逐片确认、不等质量反馈。
