# FI14 PC端MVP · 技术供审附录 v1

本件补齐已确认intent第2节第5项。绑定原实际设计HEAD `cd1c154800945f6fe6c756bd60474bb8fe082783`、design SHA256 `73a79dae37c75e8d09f862655212deae645fff4715cd2c72b109b554bcc47e37`；原四件和正式Workflow封存均不改。**原设计与本附录须一起审；本附录未批准，不实施。** 以下确定工程接缝，不签财务C1六项，不扩到真实付款、ERP、真实取数或生产。

## 1 技术选择与现有资产实证

Python独立场景包`fi14_payment_plan`，Flask app factory及Blueprint `/finance/fi14`，与仓内FI3已有Flask/Blueprint工厂一致；不新起监听端口、不改网关、SSO或共享平台。金额用stdlib Decimal的字符串编码，离线输入和结果为版本化UTF-8 JSON，首期不接CSV/XLSX或OCR。原设计所说未来适配在获准样本确认后另审，不阻止本期mock闭环。

现取源码：FI3 `fi3_payment_validation/webapp.py::create_app`、`pyproject.toml`；平台`audit/events.py::AuditEvent`、`audit/logger.py::AuditLogger.jsonl/record/verify_chain`。FI3当前默认身份接入点仅读`X-Zp-Identity`，为过渡只读mock页；**不能把该空壳/裸请求头当FI14真实组织权限**。平台audit明确只存决策结果、来源、hash，不存原始财务红色数据。

## 2 最小闭环与文件职责

首期PC流程：上传合成JSON包→校验来源/截止/币种与覆盖→账龄/标准报表勾稽或unknown→只读草稿及缺口→人工调整演示/新版本/理由→历史比较/受控导出/审计。全部结果标`MOCK`或`DRAFT`，没有付款、审批、记账、通知或ERP写回按钮/API。

场景根`4-数字员工/财务部/FI14-应付账龄与付款计划分析/`，未来候选逐文件白名单如下（仅待批准的新建文件，不含现存intent和共享源码）：

| 文件 | 责任 |
|---|---|
| `pyproject.toml` | 场景Python包及仓内既有Flask依赖声明，跟随隔离运行时，不全局editable安装 |
| `fi14_payment_plan/__init__.py` | 包定位与版本 |
| `fi14_payment_plan/models.py` | manifest、来源记录、AgingRun、PlanVersion、差异/缺口类型 |
| `fi14_payment_plan/config.py` | 模式、schema版本、场景结果目录和audit路径；无专业默认阈值 |
| `fi14_payment_plan/sources.py` | 只接versioned mock JSON；字段、来源、截止、币种、覆盖校验 |
| `fi14_payment_plan/engine.py` | 同截止勾稽、unknown/PENDING、合成规则演示；不访问真实连接器 |
| `fi14_payment_plan/storage.py` | 不可变版本JSON codec、内容hash、幂等、原子发布、失败留证据 |
| `fi14_payment_plan/access.py` | 场景内权限适配协议与显式合成身份fixture；不建真实角色体系 |
| `fi14_payment_plan/webapp.py` | app factory、PC页面/只读结果/人工演示/授权导出及既有auth预留接缝 |
| `fi14_payment_plan/templates/index.html` | 导入与来源、缺数/账龄、草稿、人工调整/历史的PC视图 |
| `data/mock/fi14_bundle.json` | 全合成AP/标准账龄/资金/约束、来源版本及明确演示规则 |
| `tests/conftest.py` | 现有bootstrap唯一stub，strict=True，不复制旧引导算法 |
| `tests/test_sources.py` | manifest/截止/范围/币种/覆盖/恶意字段的未来合成验证 |
| `tests/test_engine.py` | unknown不补零、勾稽差异、C1锁定与mock演示 |
| `tests/test_storage.py` | 幂等、不可变版本、冲突/失败、audit提交屏障 |
| `tests/test_access.py` | 身份/范围未知和拒绝、合成权限边界 |
| `tests/test_webapp.py` | 上传→结果→调整→历史/导出及拒绝的未来PC合成验证 |

未来实施如需新增任何其它文件、改平台/FI2/FI3/网关/原规则，先另审。没有部署脚本、常驻服务或新端口。计划中测试仅供未来获准阶段，本轮不新增或运行产品测试。

## 3 来源与snapshot codec

`fi14_mock_bundle/v1`包带`mode=MOCK`、source_id/version/hash、extracted_at_utc、org_scope、as_of_date、currencies、coverage、AP/standard_aging/funds/constraints引用。MVP只接受严格白名单字段；上传作为字节数据读取，不执行内容，不接受路径/SQL/宏/可运行附件。mode未明确或不是MOCK则拒绝；获准脱敏模式需在真实来源授权、字段合同和可信权限接缝齐备后另开。

所有金额字符串→Decimal，不经float；跨币种不合并。来源日期和截止日原样保存，不用机器今天代替；缺时区/截止或覆盖不明为缺口。人工调整保留父plan_version、actor、UTC时刻、理由及字段差异；C1未签的真实金额/排序/拆付/日期决定全部锁定，首期只有标为合成的演示可调整。

结果schema `fi14_result/v1`。canonical UTF-8 JSON固定键序，Decimal为字符串、日期ISO表示，hash不含自身hash字段。存储位置仅场景结果根`reports/fi14_pc_mvp/<run_id>/<plan_version>.json`，不读写其它场景快照；通过ID解析路径，禁止用户提交任意文件路径。

## 4 去重、并发与持久化

导入幂等键绑定mode、组织/截止/币种、schema版本及源内容hash，范围不同不能因同文件名合并。同一key重复导入返回同一run引用；来源/规则版本变化生成新run。调整采用父版本检查和每plan排他锁，过期父版本返回冲突，不覆盖别人调整；重试带operation_id，不重复创建版本。

同卷唯一临时对象写入/flush/回读/hash核验→记录对应audit→回读核唯一operation_id及hash、verify_chain通过→不覆盖原子发布可见manifest。审计前写入的对象是未提交对象，查询/导出不能读取；audit或发布失败不显示成功。重试查operation_id并继续原提交，不复制财务动作；失败文件保留，不能静默删除或自动支付。真实档案保留沿已有财务策略，未核策略不自行定TTL；audit沿现行append-only/3年。

## 5 权限与审计接缝

app factory注入可信`AccessDecisionProvider`，输入actor与组织/对象/操作，输出允许或拒绝及来源版本。默认未注入/来源未知即拒绝上传、计算、调整、结果下钻和导出。不得仅信任客户端header或通过共享口令推断组织/财务角色。首期只可显式注入合成fixture身份/权限，界面标演示身份；不把它注册成真实员工/角色。权限实现不满足时停该动作，未获批准不新增平台权限。

平台审计复用`AuditLogger.jsonl`、`record(AuditEvent(...))`、`verify_chain`。事件只含scenario=FI14、action、actor（可信/合成）、automation_level、operation/run/plan IDs、结果态、规则/来源版本、内容hash、拒绝原因码。**金额、资金余额、原单细节、发票/附件原文、before/after金额值及未脱敏人工理由不进audit负载**；它们留在受同等权限控制的场景结果对象，audit只持对象版本引用/hash和差异字段名。调用端投影：`decision`只放状态/opaque IDs/hash，`override_reason`留空或非敏感reason code，`data_sources/report_path/error/oem_context`均不载原始敏感值；平台接口不会自动脱敏。拒绝不泄露受限对象是否存在或行级数据。

此项隐私合同同样适用于FI5供审：原始金额/员工发票/差额/未脱敏理由不得因“人工采纳留audit”原值进入通用审计，使用受控结果对象引用与hash。该条不修改FI5现有代码或正式Workflow状态。

## 6 专业与未来验证边界

G01–G06全保持PENDING；synthetic fixture的演示规则不是CriteriaRegistry签认。真实无标准报表且未签规则不分桶；资金/排序/必付/拆付缺依据不排行或称最优。mock端到端可演示工作流和拒绝/缺数状态，不能解除C1或成为付款依据。

未来获准后只从FI14项目根用隔离Python执行项目CI，沿`.github/workflows/ci.yml`矩阵规则及本包五个目标测试文件留原文/退出码；本次未跑。实施HEAD独立review通过才进入发布准备，ff/真实取数/生产/外发继续逐项授权。设计批准只允许写详细实施计划，产品实现与测试仍按后续具体授权。
