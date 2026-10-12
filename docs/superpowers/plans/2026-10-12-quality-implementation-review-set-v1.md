# Q2 / Q9 具体实施供审集合 v1

## 1 已批准设计及本次范围

5A已经批准质量实际设计集合v1（SHA256 `5649280b4fedf389235ef13188bea5d168eee4fabbeaf9595c61485b75226500`），只允许写计划，§四292已答。6A-v2两个双设计保全批正式完成，原Q2/Q9任务与原树停design闸；没有重做成功提案。

本集合第1–5节请求具体实施、合成测试/项目CI及独立Luna审查；不是只批设计，也不包含Q2上传闭环、线上语义启用或真实专业校准。

| 场景 | 具体计划 | 计划SHA256 | 已批design HEAD / SHA256 |
|---|---|---|---|
| Q2 | docs/superpowers/plans/2026-10-12-q2-semantic-offline-implementation.md | ee353d9d1dcc0a9b17aa38126e81ac8df2b4ddc7e9578372ee6accf3cad21089 | 31270c3dc9ff165eec85553f0e26df6ca8b26b5b / 8fbb2dcc1094f58886c47b7fce12f77b0af0a83cfb1b9638a2450ae1ab86c909 |
| Q9 | docs/superpowers/plans/2026-10-12-q9-apqp-evidence-implementation.md | b4438c22b1dfb4396bda5ef5c5f4ee3f9ec43e6963977f79dde727fccc26e075 | 1df48365385cf3a2e1c436fbe77466caaae80cd2 / fce1a7c85a7c5414985c36b21fd3b38178c319524084fcfa32f9db2a7f7da3c5 |

两计划及本集合冻结，实质改变另审。父级修齐审计类型/回读、fixture、typed红线、显式实验grade（不推新阈值）、逐case摘要、样本3追溯、Q9安全输入/默认deny与精确文件表；Markdown Python块只AST解析，未运行实现/产品测试。证据`reports/pc-mvp-1012/v3/quality-plan-document-check.json`。

## 2 Q2 精确8文件

原任务`q2-semantic-offline-source-1012v2`，原树`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai`。

1. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_contract.py`
2. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_source.py`
3. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_calibration.py`
4. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_signoff.py`
5. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_contract.py`
6. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_source.py`
7. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_calibration.py`
8. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_signoff.py`

只新增离线候选合同、固定MOCK来源、合成校准与审计/显式人工override接口；None≠0，数字置信与输入显式实验等级分别保留，不从未签阈值计算grade。typed规则/红线分离、②③不入验收；真实RuleSet只读投影。每case绑定来源摘要与单tenant/版本。审计record→指定事件回读→verify链后才返回结果，失败关闭；PENDING读取原样抛。无engine/UI/上传/专业库/平台改动，无真实校准或线上source启用。

## 3 Q9 精确24文件

原任务`q9-apqp-evidence-pilot-1012v2`，原树`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai`。

1. `4-数字员工/质量部/Q9-APQP阶段审查/pyproject.toml`
2. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/__init__.py`
3. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/models.py`
4. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/identity.py`
5. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/ingest.py`
6. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/extraction.py`
7. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/candidate_graph.py`
8. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/comparison.py`
9. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/criteria.py`
10. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/review.py`
11. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/audit.py`
12. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/service.py`
13. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/report.py`
14. `4-数字员工/质量部/Q9-APQP阶段审查/q9_apqp_evidence/webapp.py`
15. `4-数字员工/质量部/Q9-APQP阶段审查/tests/conftest.py`
16. `4-数字员工/质量部/Q9-APQP阶段审查/tests/fixtures/q9_mock_manifest.json`
17. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_identity_contract.py`
18. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_candidate_graph.py`
19. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_extraction_status.py`
20. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_criteria_pending.py`
21. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_decision_audit.py`
22. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_q4_result_isolation.py`
23. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_mock_case_contract.py`
24. `4-数字员工/质量部/Q9-APQP阶段审查/tests/test_report_contract.py`

单客户/项目、显式版本和locator；not_provided≠provided_not_extracted。G01–G06全PENDING，不作APQP/阶段裁决。只用显式启用的synthetic demo actor，默认deny；更正追加事件，审计屏障失败不得报成功。Q4仅共享输入identity，review/decision/audit分开。安全属性显式输入，未知转人工，ASIL C/D在抽取前退出。Blueprint仅importable mock入口，不改共享门户注册/CI/平台或开监听。pyproject与init只承担新场景子包导入/CI scaffold。

## 4 外部证据、原树及验证副作用（本项待批）

根AGENTS要求仓库外修改先确认，标准implementation授权必须仓库/全部模型树外。请求：

1. `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1012-q2-q9-implementation/`仅两task标准JSON（task_id/design_head/design_sha256/精确allowed_paths/text），绑定本集合及两冻结计划全文。
2. 既有runtime仅两task和`B-1012_v3质量双设计保全`的授权/正常lane resume/实现/CI/审查/封存状态与日志；两原树精确32文件及outer Git commit。不得改工具、hook、其它task或凭证。
3. 两原树`reports/pc-mvp-input/`同字节批准计划/四件/现有规则副本及明确可选路径索引；先Test-Path bool，再只读已存在文件。不存在的部门或新场景CLAUDE不是缺必需规则，不盲读缺路径；适用根/场景建造规则仍完整执行。
4. 两场景ignored reports下MOCK审计/结果及项目CI/JUnit，测试TEMP/TMP/basetemp限定进程级主仓新UUID `reports/pc-mvp-1012/quality-implementation-verification/`；保留失败资产，不删除/改ACL、不安装依赖、不改全局editable指针。

## 5 调度、验证与停点

先核原tree/common-dir、原design HEAD/SHA、未busy及live row锚；标准证据附到现有质量双设计保全manifest，既有resume只解除暂停，实施权仍由标准JSON核验。两任务独立按空闲槽错峰90秒、全局≤4，所有派生显式gpt-6-luna。不得裸advance或手写成功。

两计划按行为TDD RED→最小GREEN；ImportError不算功能RED。定向测试在各自场景根，outer项目CI精确`python -m pytest -q --tb=short --junit-xml=pytest-result.xml`，解释器固定`C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`；不在根混跑。新HEAD接受独立Luna审查，留原退出/CI/JUnit/hash/白名单证据，CI/review齐再停发布准备。

未批新路径、真实权限/专业签认、共享整合/取数需求停对应项。无ff、生产、真实OEM/财务/采购取数、付款、外发或线上语义启用。

## 6 可答复

8A（推荐）：批准本集合v1第1–5节，两个冻结计划/32文件/限定外部证据/原树/验证范围，执行合成实现与项目CI/独审。8B仅批准Q2；8C保留计划暂不实现。本项无默认。
