# SC2 / FI14 具体实施供审集合 v1

## 1 已批准设计及本次请求

4A已批准首批实际设计供审集合v1（SHA256 a3012a4eb20ba9c908223dcdf3ede6f1d3ffa468fce534caadffd1ddfd12a592），仅允许编写计划；已登记§四291，不能代本次实现/测试批准。

本集合请求批准下表两份**具体实施计划**及第2–5节限定文件/隔离树/证据/验证范围。先SC2与FI14合成PC闭环，独立双泳道；所有派生模型显式gpt-6-luna。FI5/QD-A离线恢复可在资源空闲后继续，不把其它场景材料作为这两个合成切片停笔前置。正式实现前需第6项恢复v2中的PC双设计保全批次接续成功；若其未获批，保留本项实施批准，先停正式调度，不能裸手或直接advance绕过Guardian。

| 场景 | 具体计划 | 计划SHA256 | 已批准design HEAD / SHA256 |
|---|---|---|---|
| SC2 | docs/superpowers/plans/2026-10-12-sc2-three-metric-mvp-implementation.md | a1439d01589ef5f6704705a99364a103759544e602fc45c90c8d3f5982a683bd | b2933132b733756b30b94e309e2066bbd50d6e43 / 9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e |
| FI14 | docs/superpowers/plans/2026-10-12-fi14-pc-mvp-implementation.md | 7cb1fe70ac82ecb7dd247410a6447e78b9762b13c8eb0becc808ef19eb00a383 | cd1c154800945f6fe6c756bd60474bb8fe082783 / 73a79dae37c75e8d09f862655212deae645fff4715cd2c72b109b554bcc47e37 |

FI14继续绑定已批准技术附录SHA256 `5f022c8ad5fbd00603e4996b70ab88c7425a0f30f2e0546c3c3c199d99959c63`，不修改其原件。具体计划与本集合供审后冻结；需要实质改变则另审新版本。

## 2 SC2 精确12文件

唯一执行树：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-sc2/zhuopin-ai`；仅下列workspace-relative产品/测试文件可改：

1. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`
2. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py`
3. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/windows.py`
4. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py`
5. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py`
6. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py`
7. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py`
8. `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`
9. `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`
10. `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/legacy_snapshot.json`
11. `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/new_snapshot.json`
12. `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/workday_calendar.json`

六/五工作日是已有签认事实，起算/归属完整公式未签不能猜。G01–G04全部保留未签；可绑定到货事实采用已签正分母、两端含、单项率算术平均。技术切片须展示value/unknown/pending、固定来源能力、权威日历、UUID/hash不可变快照及audit屏障。明确opt-in默认关闭、只读按ID查询，不新增live取数或采购动作。旧report/dataset/316/明细/旧golden回归保持。

## 3 FI14 精确17文件

唯一执行树：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai`；仅下列workspace-relative产品/测试文件可改：

1. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/pyproject.toml`
2. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/__init__.py`
3. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/models.py`
4. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/config.py`
5. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/sources.py`
6. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/engine.py`
7. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/storage.py`
8. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/access.py`
9. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/webapp.py`
10. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/templates/index.html`
11. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/data/mock/fi14_bundle.json`
12. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/conftest.py`
13. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_sources.py`
14. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_engine.py`
15. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_storage.py`
16. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_access.py`
17. `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_webapp.py`

首期仅版本化MOCK JSON，不接受MASKED/CSV/XLSX/真实来源；独立比较源的截止/组织/币种/覆盖一致才勾稽，Decimal不用float、unknown不补零；标准报表桶只读。草稿保留每行与FI3风险/来源，资金和规则未知不排序或称最优。仅合成身份显式注入演示，默认deny。人工演示版本有理由/父版本/操作幂等；金额/原件/未脱敏理由只在受控结果对象，audit只投影非敏感引用/hash。先journal与audit回读验链，再no-replace发布`fi14_result/v1`业务版本。G01–G06全部PENDING，不做支付/审批/记账。

## 4 仓库外证据及副作用限定范围（待本项批准）

根AGENTS要求仓库外修改先确认，正式实现授权须在repo/全部worktree之外。请求批准：

- `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1012-sc2-fi14-implementation/`内两个task专属approval JSON；标准字段task_id/design_head/design_sha256/allowed_paths/text，绑定本集合及两计划精确SHA，text嵌入经批准计划全正文。整个approval文件SHA由Workflow封存。不是仅放一条路径就假设模型已读计划。
- 已有Guardian/Workflow runtime的两个task与PC双设计保全批次状态、CI、审查、commit封存证据，正常lane恢复需使用既有受控入口；不改工具、hook、其它task或凭证。
- 第2/3节两个原树：精确29代码/测试路径，Git元数据及正式外层commit；各树`reports/pc-mvp-input/`中的同字节只读实施计划、批准设计与附录输入；两个场景各自ignored `reports/`下的MOCK快照/版本/audit/保留pending与reservation，以及既有CI/JUnit输出。不得写其它场景或共享平台。
- 测试临时输出可通过进程级TEMP/TMP指定到主仓新UUID `reports/pc-mvp-1012/implementation-verification/`，不改系统全局设置；不安装/升级依赖或全局editable指针，不注册新的常驻服务/端口。失败资产保留，无清理/删除数据授权。

## 5 执行、验证与停点

前置现场核两个worktree身份/HEAD/design SHA、source row/task binding及不busy；四件/附录/计划SHA任一变化停止对应执行。按根场景规则先mock、OEM隔离、完整audit，不自动L2代签或改ASIL C/D。

批准后通过正式Guardian的SC2/FI14原task、原树、对应外部authorization按具体计划实施；子模型不commit/push，外层封存实现。每任务按未来计划TDD及定向测试运行；CI只在各自隔离树的场景根，用隔离解释器执行`python -m pytest -q --tb=short --junit-xml=pytest-result.xml`，不在主仓产品目录或仓库根跑。SC2旧回归只读；FI14五个目标测试及全包CI留原文退出码。

新实现HEAD接受独立Luna审查，发现问题只在白名单内修，留CI/审查/文件SHA/范围证据；CI与review通过后停review/release准备。新文件需求、权限/日历/审计接口变更或专业规则需求超界则重新供审，不能用本项扩范围。

本轮仅写计划和静态检查Markdown示例，两个文档29个Python代码块语法解析、测试名定义、dataclass构造字段及路径检查无所列问题；这不是执行示例或产品测试。父级逐要求覆盖、字段/日历、审计真实接口及隔离/恢复/不可覆盖合同已复核。记录`reports/pc-mvp-1012/implementation-plan-document-check.json`。

**本集合不授权ff、发布上线、生产.51、真实财务/采购取数、付款、通知、对外发送或专业阈值签认。**

## 6 可直接答复

第7项：7A（推荐）批准本实施供审集合v1第1–5节绑定的两计划及29文件、限定外部证据/原隔离树/验证范围，继续合成PC实现、定向测试/项目CI及独立Luna审查；7B只批准SC2，FI14保持计划待批；7C保留成果暂不实现。无默认，未答不执行产品或测试。
