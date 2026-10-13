# FI5 PC初审MOCK兼容切片实施包 v1

状态：具体实施供审，未批准产品实现。§四307的2A已批准actual design并允许准备本包；不重新审已批业务目标。

**Goal:** 可打开的`/finance/fi5`合成初审工作面：选择申请版本→来源/OCR/验真/预算/政策缺口→附件授权→记录人工初审处置→同版本audit。正式报销审批、付款、记账仍由原流程负责。

**Architecture:** 保留旧FI5实体/判据注册表，新增独立带来源版本的review sidecar及只读Blueprint，不把上传材料自述当实现。不构造真实WeCom/U9C/OCR/验真连接器；actor/权限由注入provider提供，默认deny；处置只有audit回读/验链成功才呈现完成。

**Tech Stack:** 现有Python/dataclasses、Decimal、Flask、pytest、平台AuditLogger；不安装依赖或修改全局editable指针。

**Spec:** 原task `fi5-wecom-pc-review-alignment-1013v5`，actual design HEAD`23c7e794c4186fd48711721ca4b2260ab748eb8f`，SHA`d74b3870da9298058d0c8e1abc5641fb543016fc6a1f2e857fcb7a1591b76e2f`。§四307的2A仅design批准，实施须以后绑定本包真实SHA/路径的明确授权。

## 1 现时代码兼容核对及前置分类

已读主仓FI5 `models.py/config.py/pyproject.toml`，现实体ExpenseClaim/ExpenseLine/BudgetBalance/AuditFinding存在；`BudgetBalance.remaining`是预算额减used的旧派生量，不能偷换成C2已确认可用额。实体金额为float，旧接口保持；新来源金额独立保存规范Decimal文本，不改旧金额语义。注册表四项仍未签，RULE_VERSION带unsigned；引擎不得默认给风险等级或把新v3材料自述静默装入注册表。

FI5包仅models/config/init骨架，未有PC webapp；门户Python源未检索到`/finance/fi5`已运行挂载证据。该路由是已定目标，**不是已实现事实**。本切片提供可导入Blueprint与隔离create_app供MOCK演示；不修改共享门户注册或现网。实际门户挂载列发布前置，不能以本包单测代替真实入口。

平台已核API：AuditLogger.jsonl/record/query_by/verify_chain/verify_integrity，AuditEvent字段decision/data_sources/content_hash/evaluator/automation_level等存在；record不返回事件ID。新operation_id放decision并查询相关action后精确匹配该ID和版本/hash，verify_chain通过才报告处置完成，不能假设有不存在的get_event方法。

必要工程前置：原tree/common-dir/design四件/批次claim/当前CI根/输入可读/hash/Flask已在隔离环境可import；不存在的目录CLAUDE先Test-Path，不能盲读。可选业务前置：真实C2、三例、政策效力冲突、预算定义、权限职责、独立验真；它们只阻真实/专业路径，MOCK页面与unknown/pending可独立完成。

## 2 固定未来白名单（14路径）

前缀`4-数字员工/财务部/FI5-费用报销智能审核/`，只在现有`pc-mvp-1012-v4-fi5-admission/zhuopin-ai`树内：

1. `fi5_expense_audit/review_contract.py`（新）：来源/版本/证据/权限/处置typed合同；旧实体保持。
2. `fi5_expense_audit/review_sources.py`（新）：只读MOCK输入、字段和来源能力，拒绝real。
3. `fi5_expense_audit/review_storage.py`（新）：不可变review版本/hash、来源事件幂等与前版链、隔离存储。
4. `fi5_expense_audit/review_access.py`（新）：默认deny注入权限，所有申请/附件/查询/导出访问校验。
5. `fi5_expense_audit/review_service.py`（新）：PC视图和audit处置屏障；不支付/记账/正式审批。
6. `fi5_expense_audit/webapp.py`（新）：`create_blueprint`与隔离`create_app`，无自动监听/连接器。
7. `fi5_expense_audit/templates/review.html`（新）：版本与差异/来源/as-of/pending/unknown/人工操作。
8. `tests/test_review_contract.py`（新）。
9. `tests/test_review_storage.py`（新）。
10. `tests/test_review_access.py`（新）。
11. `tests/test_review_service.py`（新）。
12. `tests/test_review_webapp.py`（新）。
13. `tests/fixtures/fi5_review_mock.json`（新）：仅固定MOCK案例及身份/授权假设。
14. `pyproject.toml`：声明已在环境中核实的Flask依赖/模板打包；不安装或升级。

旧models/config/init/scaffold测试、共享门户/平台、专业注册表、旧包、上传材料/SQL只读。发现必须扩路径则记录具体差量；不先改后问。数据/audit/临时文件限该树ignored reports的新UUID；不得清理历史tmp/改ACL。

## 3 接口与数据合同

| 接口 | 输入／结果／必须约束 |
|---|---|
| read_mock_bundle(path) | 固定MOCK JSON；versioned来源合同，非MOCK/real模式直接拒绝；不load真实.env或联网 |
| ingest_confirmed_event(bundle, store) | 仅输入显式confirmed stable application_id/version/event_id。相同key同内容返回同version；同key异内容冲突待人工；缺标识保留未核证据，不猜去重键 |
| load_review_version(id, actor, permissions) | 先权限再视图；保留source/version/as-of/previous_version、canonical hash；非法ID/路径/hash拒读，不寻找latest |
| resolve_attachment(id, actor, permissions) | 授权通过才返回当前MOCK附件内容/引用；无任意本地路径/file://、公开URL回退或按姓名推权限 |
| build_review_view(version) | OCR候选及置信与独立验真分开；原OCR和人工纠正链都保留；预算来源值/定义/period/as-of分开，不用BudgetBalance.remaining推已签available |
| append_disposition(actor, version, action, reason, expected_hash) | 仅采纳/改判/待补件初审动作。先权限/hash/version核对，再append-only平台audit、精确operation_id回读、verify_chain；完成后才提交结果索引。故障/幂等重试不重复业务结果，不正式approve/reject/pay/account/send |
| create_blueprint(service, identity_resolver, permission_source) | `/finance/fi5` GET列表、GET显式版本、GET附件/导出、POST版本初审处置。身份/权限默认不可确认即deny；只有明确MOCK配置才注入MOCK actor |

金额输入为Decimal规范文本，NaN/Infinity/负值/空串按字段合同拒绝或unknown，不通过float近似比较。预算可用额只展示来源明确给出的字段；unknown不转0，source-provided0保留0。政策材料的v3已明确变更及原出处可展示，未核效力/冲突影响的确定性规则保持pending，不修改旧CRITERIA。

版本原子发布采用不覆盖写入，ID碰撞拒绝；作用域含来源组织/申请/version；前版必须同申请且hash存在，乱序/循环/跨申请链接拒绝。MOCK初版authority限定单进程并对操作串行；不声称已解决分布式多实例写入。

## 4 可运行小段、定向测试、回归及独审

1. **合同/版本链**：先RED再实现合同/source/storage；只用fixture的正常、缺事件ID、重复、补件v2/旧版本保全、同key异内容、非法前版/hash/金额案例。首里程碑输出确定来源版本和未核状态，保持所有原件。
2. **权限/处置/audit**：先RED锁定默认deny、角色不可用、跨申请/组织、附件列表/预览/下载/搜索/导出泄漏、并发旧expected_hash、audit append失败/回读缺operation_id/验链失败、重试幂等。实现权限与service；旧AuditFinding风险字段不填，旧unsigned注册表不改。
3. **页面闭环**：先RED锁定申请选择/显式版本、来源链接/差异、OCR与验真、预算as-of、missing/pending、人工理由和audit结果。实现模板/Blueprint/create_app；测试全部GET无刷新/真实源副作用，POST不触发正式流程或通知。非授权响应统一最小错误，模板转义用户输入。
4. **回归/CI**：原`tests/test_scaffold.py`及新五测试文件在FI5子项目根运行。定向用完整node-id，不把ImportError或工具拒绝当功能RED。outer正式CI命令以当次CI矩阵核实，按现合同为隔离Python `-m pytest -q --tb=short --junit-xml=pytest-result.xml`，保留stdout/stderr/JUnit/hash；不从仓库根混跑。
5. **独立Luna审查**：14路径/原实体兼容、权限/审计故障负例、unknown与0、原政策来源与待签、无真实源/正式业务动作，绑定actual implementation HEAD。缺陷仅原范围内修复、定向与必要回归重跑；不把fixture业务期望当专业签认。

## 5 演示与发布准备分层

合成版本目标FI5-PC-review-mock-v1，版本以实际HEAD与review_version/hash为准。入口`/finance/fi5`沿统一门户路由合同；先由隔离app/Flask test_client导出实际HTML/API/audit响应用于演示，不新开对外端口，不称已挂现役门户。用MOCK身份展示版本链、资料缺口和人工初审；固定fixture中的“正常/超标/补件”仅技术类别，没有真实专业通过声明。

合成验收：页面可打开；显式版本与来源、权限拒绝、预算时点、OCR/验真分离、人工理由/audit屏障实际贯通。真实可用验收：C2完整源职责/版本/预算/权限合同及三笔脱敏真实案例，另获读取授权后逐例对照。生产发布：实际门户mount文件和目标环境、候选HEAD、指定使用人、数据范围、default-off开关、部署前完整备份/原PID/配置、关闭开关及恢复文件/自有进程回滚、鉴权/关键页/初审/audit冒烟、反馈入口齐备后单独申请。当前无真实候选HEAD/上线日期，不编造。

## 6 后续一次实施批准需要覆盖的完整范围

本计划14路径、原FI5 task/原树、原design SHA、MOCK实现/定向测试/必要回归/独立审查/缺陷修复/成果保全，以及标准工作树外实施JSON和正常runtime阶段记录。原SC2优先，不新增同类FI5任务，不因本计划完成自动开工。真实源、专业代签、ff、生产、付款、记账和外发均不在本包。

本次2A准备任务完成只表示具体方案可审；不是FI5业务完成。
