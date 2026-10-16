# Q2原612 · 发布准备与一次整合审批 v1（§四329）

记录时刻：2026-10-16T07:30:20+08:00（北京时间）。唯一执行：1015 / 01a13d5b-aa79-7fd3-b17b-1637315fa3c2。状态：已准备、未获ff/push批准；暂不归档，浏览器实机及正式发布未闭。326A冻结包不改。

## 1. 具体候选与范围

发布候选HEAD `c8a31b049e27f5db3bedbbec09c6ef945b5ce36d`，分支`codex/q2-release-prep-1015`，工作树`reports/q2-real-document-pc-1015/release-worktree`，干净；父提交为主仓快照`740f5bb97e775df1ad39630f31a3671092937d44`。原业务候选eae205cc及其工作树、真实运行和旧状态原样保全。

只取原321A/323和326A已批准的Q2/QD-A 22个差异路径（21产品/测试＋场景说明）；没有重新设计功能或带入财务、Q9、SC2、平台、机制及旧8文件。22路径清单指纹SHA256 `24d320df364260849e22a1a7efa7c0ac6a4c58e65dd79e64d44f5645b6621a09`，算法为清单路径→原始文件SHA字典的UTF-8排序紧凑JSON再SHA256。

独立代码差量包`reports/q2-real-document-pc-1015/q2-approved-code-delta-2026-10-16.zip`，SHA256 `76916bdfbb40bd375a91acedbcd9f11a35f6cab9687b8122c0b216ecf4c668c9`，100597 bytes，含22份after、已有文件before和manifest；无真实原文、报告、截图、凭据或模型响应。包是供审代码快照，**不能直接当生产部署脚本执行**。

## 2. 验收证据与复用边界

- 整合树按项目根完整回归：Q2 149 passed，QD-A 56 passed；均零失败、零错误、零skip。JUnit及命令/环境/日志见release-candidate-receipt.json和release-pytest-*-01.log；只任务目录deps补xlrd，不写共享Python指针。
- 整合树独立业务回放：用同客户成功对象的本机副本及禁止模型调用客户端，Flask test_client选择提交→303同对象→结果200→Excel/ZIP200；39项含20语义项全填，导出字节hash与已交件相同；审计唯一1条、链有效、前后字节不变。它是整合运行时回放，不冒称新浏览器验收。
- 原候选实际HTTP、原文/资产全量回读、模型来源审计继续引用final-candidate-receipt.json、real-delivery-receipt.json；没有重新运行模型。桌面Excel五表实机证据见ui-acceptance-2026-10-16/receipt.json及4图，无修复提示，未修改保存文件。
- 浏览器真实选文件及下载由Shao Peishen明确稍后手工核验；保持未核，不阻断准备/代码整合，但上线验收不得当作已通过。质量部反馈和专业签认是独立层，不作为继续已批构建的依赖；84/B仍仅建议、专业签认false。

复现命令（本机隔离Python，cwd分别为发布工作树内Q2、QD-A根）：
```text
PYTHONPATH=<本任务>/deps
<项目Python> -m pytest -q --tb=short --basetemp <本任务>/release-pytest-q2-01 --junit-xml <本任务>/release-junit-q2-01.xml
<项目Python> -m pytest -q --tb=short --basetemp <本任务>/release-pytest-qda-01 --junit-xml <本任务>/release-junit-qda-01.xml
```
上面为已运行命令的路径缩写；实际绝对路径、cwd和时间见报告，不因文档登记重复跑不变代码。

## 3. 本次集中申请的新增授权（仅此一项）

**329A（推荐）：批准本件第1–6节绑定的22路径候选，授权1015在前置满足后ff-only合入本地主仓master，并正常push至既有origin/master（https://github.com/Raytheoner/zhuopin-ai-transformation.git）。** 只合入已审代码，不部署、不开放真实上传、不外发。329B为保留候选，均不执行。

当前master快照是候选祖先，但主仓有其他会话未提交/未跟踪修改，所以当前不能执行ff。不得清理、自动提交、stash、覆盖、reset这些现场；等待所属会话按既有流程提交后重查。批准不替代该前置。

本批登记文档可能由既有CommitSweep提交而使master前进：若差量**仅为本线R5、implementation、本审批件及相应队列/登记记录**，可在本任务隔离树重新构造相同22路径提交，保持清单每个文件SHA及完整产品树不变，重新记录实际HEAD/父提交、验真并执行ff。此项是329A明确申请的有限执行差量；无泛化rebase/合并授权。若出现其他产品/依赖变更、冲突、测试回归或清单漂移，停止ff/push并报告具体差量，不能用旧205测强行覆盖。

## 4. 执行与回退检查点

批准后依次核：原批准文本和本件SHA；目标全仓干净；目标祖先关系；22路径清单hash及真实候选状态；Q2/QD-A代码/依赖与绑定测试相同。然后只运行`git merge --ff-only <实际已绑定候选HEAD>`，保存ff前/后HEAD；核变更清单及版本。push前只读核origin/master，正常快进push；远端已前进或保护规则拒绝则停止，不强推/绕限制，不擅自pull融合新产品。

代码差量包保存已有7文件before及15新增路径清单。若整合后发现回归，保留候选和证据，停止push/发布并准备前向修复或反向提交供审；不以reset/强推/删文件回退共享历史。生产没有本轮改动，因此目前无生产回滚动作。

后续生产更新必须先快照原Q2WebServer/目标文件/依赖/audit及监听，只重启原实例，失败恢复同一已核版本并核门禁/健康/审计，不重建第二服务、不清原数据；本段为准备边界，不是生产执行授权。

## 5. 生产真实入口还缺什么

候选运行器在`Q2_REAL_UPLOAD=1`时只允许127.0.0.1，操作者固定`local:1015`，是326A批准的本机试评。现有共享口令及客户端可伪造的身份头都不能据此当质量同事可信身份。**缺口一：生产可信操作者及本客户访问边界的实际接线。** 不能通过删loopback检查或改actor字样放行；不改1013所属机制。1015先在Q2本线准备适配方案，涉及门户/身份的实际改动归原维护方，承接确认前不越界。

**缺口二：服务器现有模型执行环境/正常账户通道尚未核验。** 本轮未访问或配置该账户；不能写成服务器没有账号，也不能复制本机凭据。最小后续路径是只读核验既有条件，具备后再绑定同件/同OEM/相同Luna边界的部署方案；若无合规可用通道，保留本机试评入口并列责任缺口。该核验与设计准备不需要等待质量反馈。

**缺口三：浏览器上传/下载实机待本人手核；专业签认/全10件校准仍属原612后续范围。** 本次不扩大真实件、客户或受众，不把单件完整报告当成全部指标达成。

因此本次只集中申请已经具体可审的ff＋产品push；生产、账号/权限/安全设置、新真实数据和新外发均不包含在329A。待生产接线形成实际候选后再按既有逐项生产闸办理，不能对尚未构建/核验的部署泛批。

## 6. 精确22路径与保存点

| # | 仓库路径 | SHA256 |
|---|---|---|
| 1 | `4-数字员工/质量部/Q2-8D报告AI判定/CLAUDE.md` | `ea7e2293a78908c1e1c2c3d858e442eeedd48d33d268a898a2732bc0b379278b` |
| 2 | `4-数字员工/质量部/Q2-8D报告AI判定/pyproject.toml` | `76d74496e8ee4e54fe906a57241911d30d4b68e6fdcc9502598f83bd9f42410d` |
| 3 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/ai_advice.py` | `2e490d005967d46ff17a75d95bb524871a012266ae137a5cd5fde92d67d41e52` |
| 4 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/document_evidence.py` | `1ea214e90c31a0ac2c0a9645df11590e16a07706a1a6a5edbdd6939020450118` |
| 5 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/document_upload.py` | `333e34fa51cc4345dc0509db56951911c7e3baff2609cffff2358a995474bae6` |
| 6 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/embedded_workbook.py` | `39d64aa90ac397ca12365b7068fafd13a100e74eab0aa406770462deeb0fb28d` |
| 7 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/excel_report.py` | `21d3c1b95d68a43b54ebf8c45bf8fcb4b207d646e87ad7fa771e2edec0802cb4` |
| 8 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/mock_upload.py` | `7017de2bbe8feeca1f42cdfba0f03cbcdf40f369d0319f2a26c4b8f781a78e8f` |
| 9 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/model_adapter.py` | `5bb383cae1d60001831588920d0135012d54be38fa02f14a7a7d9473d50d3ce8` |
| 10 | `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/webapp.py` | `7b4b3b2c36e678ad9628686196d8d4cd6b8f063b7001338b84f937a4102beb6c` |
| 11 | `4-数字员工/质量部/Q2-8D报告AI判定/scripts/run_q2_web.py` | `f4c19932ce58510a4a1c7502cccfcd9e66d4481e3e2bdf4c625979002560e695` |
| 12 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_ai_advice.py` | `a7047661e25132c8fc3e8145c24599c874e60b88c064e38471cd99ec51ab4126` |
| 13 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_document_evidence.py` | `447cc920b807cffbc705538b3eab97c7850ceb078c51010a613c02584bbe04e3` |
| 14 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_document_flow.py` | `ddf42c7ad7282bb4d7b2d2cd9c777a3448eb9540bb458f271f947e6cfb711a4f` |
| 15 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_document_upload.py` | `52ee50bc1026f6b935924c8579799b872a47e957dbdb5c060f935c5a2eb909fe` |
| 16 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_embedded_workbook.py` | `aa49a790a3d5ff893a08b774ce526ccc8244e05467d0ff59c8140e0e6a097582` |
| 17 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_excel_report.py` | `126943527f9a9aed484b8e845fd6e7ab2756420b3757b0b518a3198668266bf4` |
| 18 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_mock_upload.py` | `a067f1a052f8c4bb6f30e606c2feb731b5a539defade6d672fec3c0b52f566af` |
| 19 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_model_adapter.py` | `5a48d749f011c97ce778a05a710805b50242b7f3039edf8dbd439bb7e6c0174d` |
| 20 | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_webapp.py` | `a7da2c28013bd24d96c8759555c61125fa8d9106f44a274cea3e806c8e868e64` |
| 21 | `4-数字员工/质量部/QD-A-8D不良分析/qda_prefill/doc_reader.py` | `9816f03a5a0ed5831ba1af7e9842d227e547840253944b9ff57b12267e79458b` |
| 22 | `4-数字员工/质量部/QD-A-8D不良分析/tests/test_doc_reader.py` | `bf4db77939786bbb0005ed7fb49d9dc809062a083a6043c7a9e7e1c7a88ffd86` |

机器证据正本：`reports/q2-real-document-pc-1015/release-candidate-receipt.json`。本审批正文SHA另登记§四329及release-approval-binding.json，避免自引用。本件和R5在原包/原任务登记，不另建任务系统。
