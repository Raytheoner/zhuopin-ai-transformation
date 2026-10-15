# Q2 真实PPTX → 完整AI建议评分 → Excel导出 · 最小实施方案 v1

> **执行方式：**1015主会话使用`executing-plans`串行切片；不派实现/评审代理，不恢复Guardian。Shao Peishen要求设计、实施和确需新增授权集中一次审；本件与绑定design一并供审，批准后不逐片确认。当前仅准备方案和复用证据，未开始新增产品或模型调用。

**Goal：**在PC选择已授权真实PPTX，动态生成有分数、原文依据、得扣分理由、整改建议的完整AI建议报告，实际下载并打开五表Excel。

**Architecture：**复用原Q2蓝图、既有规则/引擎基线及已批跨页分段；增加独立真实件服务、证据索引、受控业务模型适配与Excel输出。AI建议永不冒称人工裁决；旧正式结论及PENDING不改。

**Tech Stack：**现有Python/Flask、python-pptx、Pillow、openpyxl、XlsxWriter、平台audit/OEMRouter；仅补xls缓存读取依赖xlrd 2.0.2，安装在本任务目录，不写共享全局site-packages。业务推理使用本机既有Codex入口显式gpt-6-luna/high；不复制凭据到Web。

**Spec：**`openspec/changes/q2-real-document-pc-1015/design.md` D1–D8及同包delta spec。原业务#612；旧#652/#656及8文件合同保全。

**Global Constraints：**MOCK/真实/发布/专业验收分记，OEM硬隔离、L2最终人工、ASIL C/D排除。17路径外新代码需先说明具体差量；六片内部不新增批准点；不改变规则权重、标准或全局机制。

**Review Focus：**未读误当缺证归片1/2；文档指令诱导工具归片2；Excel长文本/长编号/公式注入归片4；重启仍显运行归片3/5；同源不同操作者/规则版本错误复用归片3。下文对应片必须包含这些失败用例。

## 1. 已有授权及本次最小范围

已有321A四文件MOCK上传、323跨页两文件修复、324A同件完整离线建议Excel、325A试评发送不重批。组合候选`62e6d71c0b464d73247c8b674e10051ab89833a6`为实现起点，Q2 100+QD-A 56完整测结果及逐文件hash已绑定；不机械重跑未变部分。325A已于20:20北京时间发出并四成功链/九成功回执，构建不等反馈。

首片资料仅OEM-A-01/A0/ASIL B同件PPTX，源SHA256 `c8b52f55e0d2e76686619b7a8017e0a0bb90861393d5be57e9f9031d5842e069`。现有19页、432非空段落、22媒体、2嵌入与1302缓存记录是本件完整性基准。既有84/B是本轮比较样本，**不是新模型必须命中的硬编码答案**；新结果若有差异须逐项列证据，不改断言凑84。

新增范围为该真实件的PC接线、动态业务模型评分、可下载Excel和原资产包；不扩大真实文件/客户/账号或正式验收集。代码接受不同合成件以证明不是静态下载，但其他真实件、Word/PDF/OCR/全部10份校准不在此片。

质量部#11 M11/M12/M13及#12 V1–V5均已给，来源核验在`0-学习与工具/codex-handoff/Q2规则原回件与PENDING失配核验-2026-10-15.md`。不重复问。正式语义上线签认、完整真实校准及专业最终责任仍保留。

## 2. 精确17路径与接口

以下均相对`4-数字员工/质量部/Q2-8D报告AI判定/`，仅从本次隔离树写入：

| # | 路径 | 职责 |
|---|---|---|
| 1 | 新`q2_8d_verdict/document_evidence.py` | PPTX完整取证、位置、资产关系、跨页章节与源覆盖 |
| 2 | 新`q2_8d_verdict/embedded_workbook.py` | xlsx/xls已保存值、类型及行列定位，不执行公式/宏 |
| 3 | 新`q2_8d_verdict/ai_advice.py` | 固定prompt/schema、已答补判条件、逐项校验、建议计算与原基线差异 |
| 4 | 新`q2_8d_verdict/model_adapter.py` | 单件Codex业务推理、限定Luna/high、能力核验/超时/结构化回执 |
| 5 | 新`q2_8d_verdict/document_upload.py` | 原件→证据→模型→验证→导出→audit，单执行线程和不可变对象 |
| 6 | 新`q2_8d_verdict/excel_report.py` | 五表xlsx、缓存公式、内链/图件及原资产ZIP |
| 7 | 改`q2_8d_verdict/webapp.py` | 真实件表单/状态/结果/Excel/ZIP/资产受控路由，复用原门禁 |
| 8 | 改`scripts/run_q2_web.py` | 显式关闭默认、loopback试评配置与真实件allowlist |
| 9 | 改`pyproject.toml` | 声明本模块实际使用的既有库及xlrd固定版本，不改全机指针 |
| 10 | 新`tests/test_document_evidence.py` | 跨页、软换行、表格、图件关系、损坏/超限/源覆盖 |
| 11 | 新`tests/test_embedded_workbook.py` | 缓存类型、长文本编号、加密/损坏/外部链接不执行 |
| 12 | 新`tests/test_ai_advice.py` | 覆盖、引用、得分、扣分、来源和非人工身份 |
| 13 | 新`tests/test_model_adapter.py` | 不调用真实模型的命令/隔离/事件解析/限流/中断用例 |
| 14 | 新`tests/test_document_upload.py` | 单对象编排、幂等、故障与audit门禁 |
| 15 | 新`tests/test_excel_report.py` | 五表、原文/图片/嵌入、公式缓存与文本安全 |
| 16 | 改`tests/test_webapp.py` | multipart→状态→报告→Excel/ZIP、权限/CSRF/OEM及原功能 |
| 17 | 新`tests/test_document_flow.py` | 合成PPTX与受控假模型的端到端业务/audit自动验收 |

不改engine/checks/semantic/config/两PENDING/rules_loader/样本、QD-A产品、平台、机制、门户、旧Workflow/state/claim。原引擎保留原判定，AI建议中有证据的修正单列。

已核旧8文件计划`2026-10-12-q2-semantic-offline-implementation.md`：四模块为semantic_offline_contract/source/calibration/signoff及四对应测试，与本17路径无交集；旧8A仅合成离线实验、无真实模型/Web/上传，不把它当成本片运行授权。新PC建议显示沿324A“单件未签认建议”口径，不把旧离线候选升级为已确认来源/正式等级。

接口冻结如下；实际dataclass字段在对应模块定义，不另造通用框架：

```python
# document_evidence.py
@dataclass(frozen=True)
class DocumentScope:
    oem_label: str
    source_version: str
    asil_level: str
    authorized_sha256: str

# EvidenceBundle包含scope/source_sha256、完整sections、定位records、assets、读取状态。
def read_pptx_evidence(path: Path, scope: DocumentScope) -> EvidenceBundle: ...

# embedded_workbook.py：CachedCell含sheet/row/column/value/value_type及缓存状态。
def read_cached_cells(raw: bytes, name: str) -> tuple[CachedCell, ...]: ...

# ai_advice.py：AiAdviceReport包含每条baseline/proposed/refs/quote/reason/remediation、
# 章分/总分/建议数字等级、红线观察、来源版本和professional_signoff=False。
def make_request(bundle: EvidenceBundle, baseline: Verdict, rules: RuleSet) -> AdviceRequest: ...
def validate_advice(payload: dict, bundle: EvidenceBundle,
                    baseline: Verdict, rules: RuleSet) -> AiAdviceReport: ...

# model_adapter.py：ModelResponse包含payload、requested/observed model、usage(可未知)、
# prompt/schema hash、exit code、原始事件文件hash；不把缺值填成0。
class CodexAdviceClient:
    def request(self, request: AdviceRequest, operation_dir: Path) -> ModelResponse: ...

# excel_report.py：ExportFiles包含xlsx/zip路径及hash，回读未过不得发布。
def build_exports(report: AiAdviceReport, bundle: EvidenceBundle,
                  target_dir: Path) -> ExportFiles: ...

# document_upload.py：JobRef含opaque id/state，root固定到本客户任务存储。
class DocumentUploadService:
    def __init__(self, root: Path, audit: AuditLogger,
                 model: CodexAdviceClient, scope: DocumentScope): ...
    def submit(self, raw: bytes, filename: str, actor: str) -> JobRef: ...
    def get(self, object_id: str, actor: str) -> SavedDocumentReport: ...
    def export(self, object_id: str, actor: str, kind: str) -> Path: ...
```

工厂新增`real_upload_enabled=False`、`real_upload_service=None`、可信`real_upload_access(action, actor)`/`real_upload_actor()`；默认deny，不信任POST身份字段或HTTP身份头。本机操作者标识不等于质量工程师签名。

OEMRouter使用实例级`registered={'OEM-A-01': 'oem_a_01_q2'}`及本客户audit，源/结果/缓存/导出先resolve再guard/guard_write；所有对象携带相同scope并回读对照。没有匿名标签到客户实名的推断，不改平台全局名录，不写通用知识库。

## 3. 模型、数据和依赖的最小新增授权

1. **实现授权：**一次同时批准本计划1–6及design D1–D8，由1015从62e6d71c创建仓库内隔离树`reports/q2-real-document-pc-1015/worktree`、分支`codex/q2-real-document-pc-1015`，只写上述17产品/测试路径与本包/计划/场景笔记/本线证据。旧树/8文件状态不恢复、不覆盖，不派实现/审查代理。
2. **本件业务AI调用：**允许将本件已脱敏正文、必要图件和嵌入缓存，经本机现有Codex账户通道交给显式`gpt-6-luna/high`生成建议。此为新运行用途，不由324A“当前主会话离线分析”自动延伸。每次只一件；不上传整份源PPTX或原始嵌入二进制到第三方新服务，不接其他模型。用现有额度，不购买/付款。CLI正常运行临时文件沿其既有本机目录；不改全局配置、信任、ACL或凭据，不复制token/key。
3. **依赖与本机运行：**仅任务目录补`xlrd==2.0.2`（PyPI标准wheel、无依赖安装，SHA256 `ea762c3d29f4cca48d82df517b6d89fbce4db3107f9d78713e48cd321d5c9aa9`），既有project Python和已安装库复用，不写共享site-packages/editable。本计划明确选用可随产品部署的XlsxWriter运行时生成器，先前Artifact Tool产物不修改；其版本3.2.9已在项目隔离环境可用，openpyxl只读验真。临时服务只绑127.0.0.1；实际URL/PID及服务退出即失效的生命周期交付，不承诺常驻。

模型适配器命令使用argv数组与stdin，不拼shell命令，基准形式：

```text
codex exec --strict-config --model gpt-6-luna
  --config model_reasoning_effort="high" --sandbox read-only --ephemeral
  --config web_search="disabled" --config mcp_servers.node_repl.enabled=false
  --disable shell_tool --disable apps --disable plugins --disable multi_agent
  --disable multi_agent_v2 --disable computer_use --disable browser_use
  --disable browser_use_external --disable in_app_browser --disable image_generation
  --disable view_image --disable skill_search --disable tool_suggest
  --disable workspace_dependencies --disable code_mode_host --disable code_mode
  --disable goals --disable sleep_tool --disable tool_search --disable memories
  --disable agent_message_board --disable remote_plugin
  --cd <本件operation目录> --output-schema <本件schema文件> --json
  --image <仅本件必要PNG/JPEG预览> ... -
```

保持原hooks/rules/trust，不加ignore配置或dangerous选项；不伪造工具能力。启动时核CLI版本、支持项及现时MCP列表，所有MCP都须收窄为disabled（当前只见node_repl），变化则先做同范围合成能力核验。不能证实此限制有效时停止模型步骤，不用API令牌移植、工具开关失效或别的模型替代。实际模型标识可取则记，不可取明确未披露，不声称固定快照/temperature=0或已满足正式V3校准。

首片单调用限600秒，输出超2MiB拒绝，业务并发1；仅结构/schema无效允许一次受控修正，传输超时/访问拒绝/结果不明不自动重放。成功对象重试只读复用。服务重启把本进程未完成作业显示中断，不清未知旧锁或自称仍在跑。

## 4. 六个串行执行片与验收

每片按“行为RED→最小GREEN→必要回归→本地检查点→继续”。以下示例是要落入对应测试模块的真实合同，不在批准前创建产品骨架。

### 片1：真实PPTX证据（路径1/2/10/11）

按OOXML逐页/形状/表格/软换行保全，并与全部非空段落核覆盖；章节正文交既有跨页分段，元数据/图件关系仍保留定位。压缩输入≤20MiB、展开≤128MiB、entry≤4096、页≤64；超限拒绝，不截断。仅本件SHA通过真实运行allowlist，合成测试使用独立scope。xlsx/xls只缓存，无图像或内嵌读取状态不能默认已全读。处理EMF/PNG/JPEG时保留原hash，预览失败明确报错。

```python
def test_continued_d3_is_preserved(tmp_path):
    from pptx import Presentation
    from hashlib import sha256
    from q2_8d_verdict.document_evidence import DocumentScope, read_pptx_evidence
    prs = Presentation()
    for text in ('D3: 第一页临时措施', 'D3: 第二页结果与负责人'):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_textbox(0, 0, 5000000, 500000).text = text
    source = tmp_path / 'continued.pptx'
    prs.save(source)
    scope = DocumentScope('SYNTHETIC-A', 'T1', 'B', sha256(source.read_bytes()).hexdigest())
    bundle = read_pptx_evidence(source, scope)
    assert '第一页临时措施' in bundle.sections['D3']
    assert '第二页结果与负责人' in bundle.sections['D3']
    assert {r.page for r in bundle.records if r.text} == {1, 2}
```

另锁定表格多段/软换行、group shape ID路径、图片关系、空值与读取失败、CFB加密/损坏/外链/公式缓存缺失的拒绝状态；不复制本件xls专用断言冒充通用读取。先跑两个新测试文件，绿后保存检查点。

### 片2：模型与建议合同（路径3/4/12/13）

从load()动态取得适用规则、满分、阈值、M4/M10等签认，补入原#11已答的三条件及原件hash/位置；文件中指令只作原文。向模型提供完整索引及图件，要求每适用项有score/ref/quote/reason/remediation/evidence_state/confidence。仅完整读证据可给建议分；READ_MISSING_REQUIRED按原规则扣分，READ_ERROR/CONFLICT不得当0。未有部分得分口径的语义项仅0/满分，机械规则部分分仅允许原判据明确的档位/扣分步长；D3专项按已签字段/封顶/段内不扣负计算，不接受模型自拟比例。

规则集覆盖动态校验，不将本件20/39写成全系统固定数量。保持原engine输出，建议中的三类非语义修正须有原值/新值/证据解释，不能把已核84设为目标。每条都需质量工程师最终复核；结构性空章先显示结构退回，不强跑/强凑完整总分；红线②③不验收，其他语义红线只疑似。

```python
def test_cli_argv_pins_model_and_keeps_sandbox(tmp_path):
    from q2_8d_verdict.model_adapter import build_argv
    argv = build_argv(tmp_path, tmp_path / 'schema.json', [])
    assert argv[argv.index('--model') + 1] == 'gpt-6-luna'
    assert argv[argv.index('--sandbox') + 1] == 'read-only'
    assert '--ephemeral' in argv and '--strict-config' in argv
    assert 'shell_tool' in argv and 'plugins' in argv
    assert not any('dangerously' in a or a.startswith('--ignore-') for a in argv)
```

用假子进程覆盖缺项、重复ID、越界/NaN、错源/跨OEM、伪引用、引语不存在、模型名不符、缺usage不填0、tool事件、限流、超时、中断。批准后另进行合成隔离探针，成功后才调用本真实件；所有新模型任务显式Luna/high。

### 片3：编排、保存与audit（路径5/14）

单执行线程按scope→源保存→取证→引擎基线→模型→验证→导出→独立回读→唯一audit/验链→发布。操作键含源、scope、规则、prompt/schema及指定模型版本；同键成功复用，不重复付出模型调用。不用新通用任务看板/队列、Guardian或锁清理工具。

对源存储、模型、回读、audit写/查/链、最终发布故障分别注入；任何失败无成功页或完整评分badge。原件/输出不覆盖、状态不可捏造；保留失败现场和恢复步骤。按用户/同OEM检查get/export/asset，不因知道opaque ID可读另一客户/操作者结果。

### 片4：五表Excel（路径6/15）

复用既有报告的格式与字段，不照抄39条评语。分数明细、章/总分/等级公式与缓存同源计算；长编号强制文本，来自原件的`=,+,-,@`文本不执行公式/URL。每单元超过32767字符则分连续记录，保留定位/顺序/内容，不截断；行高≤409.5pt并拆行保证阅读。内部引用可跳页/图/表，图像等比，五表可独立查阅，原资产ZIP保持relative assets。

```python
def test_formula_cache_is_present(tmp_path):
    import openpyxl
    import xlsxwriter
    target = tmp_path / 'cache.xlsx'
    workbook = xlsxwriter.Workbook(target, {'strings_to_formulas': False})
    sheet = workbook.add_worksheet('评审汇总')
    sheet.write_number('A1', 40)
    sheet.write_number('A2', 35)
    sheet.write_formula('A3', '=SUM(A1:A2)', None, 75)
    workbook.close()
    assert openpyxl.load_workbook(target, data_only=True)['评审汇总']['A3'].value == 75
```

该例只钉缓存能力，产品测试还须从build_exports实际输出独立核全部项/章分/100分、引用/原文覆盖、图片/嵌入值、公式无error且缓存非空、无宏/外部执行链接、ZIP每项hash。视觉检查五类表及最长文本处，不以准备JSON正确代替XLSX实际正确。

### 片5：PC操作闭环（路径7/8/16）

只增加D6定义路由，不改MOCK路径/共享门禁。表单列明本件版本/OEM/安全边界和“AI建议，待质量工程师复核”；POST后303进入状态页，阶段与失败原因真实显示。完工页有逐项结果、原文定位、Excel及资产包下载，均same-operation并正确MIME/filename/no-store。默认关闭、可信身份、CSRF、Origin、转义、超限、越权、错误重试全部定向测；原GET/ping/门禁回归保留。临时服务用新核对过的本任务PID，旧四演示进程不覆盖或停止。

### 片6：实际候选验收与交付（路径9/17及本线证据）

先合成输入与受控假模型的Flask multipart端到端，验证原文→动态分数→xlsx→audit，同源不同合成内容必须产生可解释差异，防静态返回。随后在本件真实PPTX进行实际浏览器选择/上传、一次受控模型运行、结果查看、Excel保存并打开；同operation独立回读验证19页/432段、22原媒体、2嵌入/1302缓存、全适用项及原依据/整改建议，语义项不再统一留空。模型实际建议与旧84/B允许有据差异，列比较不强迫一致；不可读则如实交具体阻塞，不宣告完整评分。

最终在实际候选的Q2根运行项目Python `-m pytest -q --tb=short --basetemp <本任务新UUID> --junit-xml <本任务报告>`；Q2全套包含旧100测，不过滤/改断言/skip。QD-A字节/依赖均未变则复用56完整测与必要集成回放；若依赖/实际代码变化则补对应完整回归。独立业务验收核get/export/audit唯一/非空有效链。固定实际HEAD、17路径hash、模型/指令/来源hash、JUnit、实机URL/PID及生命周期，写原612和R5。浏览器因扩展策略不能选文件/下载时，不修改权限，保留该段未验收证据。

## 5. 本次不自动授权的事项及真正停止条件

1. 不批旧任务恢复、清锁、他人文件、机制/安全设置变更、跨客户/新真实件、正式专业验收签认、全部10份校准、产品ff/push、生产部署或新外发。单件AI建议不代正式语义上线验收，旧PENDING不改。
2. 仅具体模型认证/权限/可验证限制不满足、依赖安装被拒、源hash/元数据失配、证据不可读或新写入归属冲突会停止相应依赖片；先保全其余成果及恢复步骤。不无限重试、不切模型、不伪称后台仍跑。
3. 测试、业务真实操作、临时可访问、正式发布、专业验收分项记录。正式发布准备绑定完成后的真实候选HEAD/目标、备份/回滚及冒烟，再一次集中提交具体发布批准；本次无法提前绑定尚未产出的提交。

## 6. 一次审批选项

**A（推荐）**：一次批准本v1第1–6节及绑定design D1–D8，允许上述17路径本机隔离实施、本件PC使用/受控Luna业务评分、任务内xlrd依赖及临时loopback演示。1015串行完成六片，不逐片确认、不等质量反馈；本次不含第5节禁项。

**B**：只保留供审方案；已批MOCK、跨页候选、完整单件Excel及已发试评仍有效，真实PC产品及新模型调用暂不实施。

新增授权只有：**真实件PC接线的实现、该件新业务模型用途、任务目录xls依赖/临时本机服务**。业务规则、同件身份、旧跨页修复和Excel内容要求不重批。源码/包/计划冻结hash后写原队列§四，只有明确A答复才开始新范围。

技术核验来源（2026-10-15）：本机`codex exec --help`/`codex features list`证实现版本支持ephemeral/schema/read-only及相关限制项；未调用新模型。官方[非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)及[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)说明相应选项；[XlsxWriter公式](https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-write-formula)支持显式缓存值；[xlrd](https://xlrd.readthedocs.io/en/latest/)仅读旧xls，不读取宏或公式本体，范围按缓存值处理。模型账户实际可用性及限制生效仍须批准后合成探针，不把文档可用当运行通过。
