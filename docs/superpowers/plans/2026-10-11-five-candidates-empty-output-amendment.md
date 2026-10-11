# 五候选整合空输出与执行身份补充计划

> 执行方法：沿已选 Native，由唯一根按 executing-plans 顺序执行；Luna 独立静审。以下使用编号跟踪，依 Shao Peishen 格式约定不用勾选框。

状态：根正式登记的具体供审补件。尚未取得本版本明确批准，不启动任何新前检、pick 或测试；推荐不等于授权。

**Goal：**修复前检将预期空 Git 输出误传为 null 的错误，在既有 Native 保留已完成的 SC2、SC4，从 SC10 继续原 D5F/5828 批准范围。

**Architecture：**七处 Join 参数数组化，原 clean/dirty 和 EE5 判断不变。旧 E930、原 auth 4D35、after-registration 4F41 保留原字节；旧 E930 是来源身份，新执行副本另由固定执行路径、五件 SHA、本次明确答复及独立补充批准消费件绑定。根继续 Native 执行，Luna 静审；不另建产品设计。

**Tech Stack：**PS7 7.6.5、固定 Git 2.53.0.windows.2、项目隔离 Python 3.14.5 / pytest 9.0.3，均沿原批准路径及 SHA。

**Spec：**原完整计划 `C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-10-five-candidates-alignment.md`（D5F582…CBAADE）和 Windows 补件 `C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-11-five-candidates-windows-path-amendment.md`（5828D0…3DAEC2）。本件只补执行错误与对应批准身份，不改变业务设计。

## 1. 实际停点

唯一 Native：`C:/Users/Paul Shao/.codex/worktrees/five-candidates-align-1010/zhuopin-ai`，分支 `codex/five-candidates-align-1010`。SC2 实际提交 c78b36bf892bba1bead64ee2dbd100e154bd19aa、SC4 实际提交 2d4cd01c5c5557ea2151345e5146fe550efd5b52；两次 pick 均 exit0，各自 after-pick checkpoint 已通过。当前仅这两项已接入，剩余三项和六套整合测试均为0。

SC10 首次 gate：`C:/Dev/zhuopin-ai/reports/candidate-integration-1010/5e363363-847b-4e03-9933-91c72b8e250f/preflight-SC10-cherry-pick-a15eb7c1-6ab8-4d66-836f-717ad14e34ce.json`，success=false/tool exit1。最后 Git 是 Native 全树 status，actual_exit=0、output_line_count=0、空输出 SHA E3B0…B855；随后 Join(values) null 抛错。四次官方 #468/#469 查询成功、EE5 completed/inactive/QA/restored 均有效；不是 EE5 新阻塞。未执行 SC10 cherry-pick，失败证据保留，不复用旧 UUID。

## 2. 精确代码与身份修订

1. `preflight_ee5_and_git-v2.ps1`：复制原 E930，在 source lines291/359/368/374/380/381/382 的 Join 第二参数外增加 `@(...)`。空 success stream 得零元素数组，再 Join 得空字符串；未知/dirty/冲突仍按旧谓词拒绝。内部 line41 已数组化，保持。
2. 旧 `FormalScriptPath` 继续指原正式 E930并核其旧 auth SHA；另建固定 `ExecutionScriptPath` 指已审当前副本。self-path 门改为核新执行路径，新增必填 `SupplementAuthorizationSha256`，实际 Git 前先用常量 SHA 核普通 guard 文件，再读取本次明确批准及五件 SHA。每个 gate 记录补件 SHA；没有新批准则停止，不能把原来源 SHA 冒充新执行 SHA。
3. `supplement-guard.ps1`：固定正式消费路径 `C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选空输出补件批准消费-2026-10-11.json`。外部整体 SHA 必须匹配；approved=true、draft_only=false、scope=sealed_candidate_alignment_verification_only；原 auth/E930/D5F/registration 四 SHA、固定 Native/branch/续行起点、正式补件 SHA、人答与批准 proof 字节、九项剩余 operation、五件执行 SHA 均须闭合。文件及所有祖先目录拒绝 reparse/非普通项；本批 proof/human 只能在固定 reports 下新 UUID 的直系文件。
4. `block0-v2.ps1`：只改 PreflightScript 固定路径及新增参数透传。四次官方查询、门序、记录函数和普通 cherry-pick 逻辑保持。第一版准备字节及其它三件旧候选保全在 snapshot-v1，均不执行。
5. `pick-one-lane-v4.ps1`：沿原 DE84，只保留剩余 SC10/SC11/O4；在点源 guard 前固定其 SHA，再消费本次补件；block0 指新副本且由补件全 SHA 核验。来源提交仍是原三 SHA。
6. `run-one-suite-v2.ps1`：同一 guard 门及新 block0；原 block2 E389B803…7C562E、六套 targets/cwd/command text/campaign 顺序及实际退出码记录保持。SC10/SC11 各传 fresh before-tests checkpoint；其它四套不得传 checkpoint。

## 3. 全局约束与审查重点

固定基线仍 310f54de71149b0cb0281749619ee3cd84f97bca；五来源、41路径、mode/blob、六套测试及两场景精确例外均沿原批准。旧 §三冻结不撤销，EE5 root 记录只证明本根作业状态，不是场景解冻授权。主仓历史 dirty、五来源树/分支、失败件保留。

审查重点：空输出需变为空字符串；非空状态/未知 stderr 不得被吞；原来源与新执行身份分别绑定；guard 必须先核 SHA 再点源；没有本次人答或任何 pin 漂移均不执行；已完成两项不重跑；九项余下 operation 和六套 test 矩阵不得扩大。Native scoped41 仍将 stderr 合并；潜在缺父目录 warning 未获运行观察或豁免，若出现仍停，不全局吞 warning。

## 4. 获批后的顺序与证据

1. 根取得本正式版本明确 A 后，在原锁流程下创建独立补件消费件，以及新 UUID 下原人答字节和批准 proof。消费件 schema=`five-candidates-empty-output-supplement/v1`，原 auth 不改；九项精确顺序为 SC10/SC11/O4:cherry-pick，随后 SC2/PLATFORM/SC4/SC10/SC11/O4:tests。五件绑定字段键 guard/preflight/block0/pick/suite；续行身份字段 continuation.native_root/expected_branch/start_head。plan_path/plan_sha256 与实际本正式件、人批 proof 必须一致。
2. 继续使用原 capture_checkpoint-v4（D56326…370021），从成功 after-SC4 checkpoint `C:/Dev/zhuopin-ai/reports/candidate-integration-1010/auth-preparation-a9cecd4e-74d0-4518-a931-35d59bd3ffb7/execution-checkpoints-1011/789b8cdb-b91e-48df-ac81-c8effa1519a8/checkpoint.json`（AF47AD…691D6）刷新独立 before-pick:SC10，绑定起点 2d4cd01c5c5557ea2151345e5146fe550efd5b52。旧失败 gate/pre-checkpoint 不消费；不重建 Native 或分支。
3. 新 pick-v4 调用 SC10，一次四查询及新 gate；通过后仅 pick 25eb192258fcd6ce51e654ec01c62918486c7736。记录实际 exit/HEAD，再新建 after-pick:SC10。随后独立 before-SC11→四查询+gate→一次 pick6990139aca37e1252684ef051685198bc7e0c9a1→after-SC11，再 before-O4→一次 pick6a11819da67902eaa9ae934e061c607c24fcc624→after-O4。每步证据 CreateNew/字节回读，失败立即停依赖，不 abort/retry/修复现场。
4. final checkpoint 对连续五提交、首父基线、每项来源路径、最终唯一41路径及 mode/blob、Native clean、主仓 controls/runtime/EE5 全核。全五项完成才建六套 campaign；SC10/SC11 各自 before-tests checkpoint 直接消费成功 final，同一最终HEAD，不消费中途 checkpoint。
5. suite-v2 按 SC2→PLATFORM→SC4→SC10→SC11→O4 各一次，原固定 Python `-B -m pytest -q -ra -p no:cacheprovider`，原 targets、独立 UUID basetemp/JUnit/stdout/stderr、同一 campaign。SC10/SC11 每次 tests 前各四查询和新 gate。任何 query/gate/process/JUnit 错误停后续。gate总计最多四次（两pick两test）；未启动的旧失败 gate 不算成功许可，不复用其UUID。
6. 根每套实际 exit0 后、下一套之前只读核 campaign-manifest、末条 readback SHA、run-manifest 和 JUnit 普通文件/有效 XML，报告 tests 计数、failures=errors=0；不重复统计聚合根/子层，不新增测试。不声称冻结 block2 自带 JUnit 门。结果登记路线图/R5/§二，未闭专业与真实源前置保留。

## 5. 副作用与止损边界

本补件批准范围包括上述五件受控准备/执行副本，独立正式补件消费 JSON及新 UUID 人答/proof，原 reports/candidate-integration-1010 范围内新 checkpoint、四查询/preflight/pick证据、原六suite的合成审计/basetemp/JUnit/日志，及已批 Native 三次剩余普通提交与共同 Git 元数据副作用。共享正本文档与队列仍仅根持锁写。

不新增产品文件/测试、不复制新 Native、不重跑 SC2/SC4、无 master 整合/ff/push/生产/真实源/L2/外发/清理。原四个 gate只要任一失败即停依赖，旧冻结及现场全部保留；其它独立泳道继续。推荐 A 不是默认授权。

## 6. 可定夺选项

1. A（推荐）：批准本正式版本及所列执行身份补件与隔离副作用，从 SC10 续行原三提交、六套测试；遇失败停。
2. B：保留两项已接入及失败证据，整合片段停，独立泳道继续。

## 7. 唯一供审执行件与静审范围

固定目录：`C:/Dev/zhuopin-ai/reports/candidate-integration-1010/preflight-empty-output-amendment-1011/`。以下五件是本版本唯一可批准的执行入口；snapshot-v1、旧 proof/README 只作保全，不消费。

| binding | 文件 | SHA256 |
|---|---|---|
| guard | supplement-guard.ps1 | AE4663132E546911E50EDC2D4D3BC9143C09F009094B3F58D450C798D05A14D2 |
| preflight | preflight_ee5_and_git-v2.ps1 | 97C1ABB9824CA7CADABF7853C93355B7F9F7E0CBC0B764B9193220670B5FAE6E |
| block0 | block0-v2.ps1 | 3CB97BB0B3FE00F90A48A9EA32EA2355018F42548640A0B65D8880F8B14C86A6 |
| pick | pick-one-lane-v4.ps1 | 35E489C7FDBC25A470A6CC0DC9776BB1471387CC9E29D683E0902BF52D7DF5F9 |
| suite | run-one-suite-v2.ps1 | 7406B1BA7184ABBC97F01CCC98319C3CB1703E2D8838FC42A1F41C769F7D449A |

根已分别读取五件实际 SHA，PS7 Parser 五件均0。固定 Git no-index diff（ignore-space-at-eol）确认 helper 仅七处数组物化、新参数/执行身份门与两审计字段；block0仅路径及参数透传。diff实际exit1表示存在差异；不当成测试通过或完整字节唯一差异证明。

Luna 静审通过身份/参数链、scope及已完成项不重跑；为选定片段审查，未执行/helper/Git/Parser/test，批量 SHA 调用被 K3 拒绝，未独立重算 SHA。根与独审记录 `root-and-independent-static-review.json` SHA 46CD666EEEC83286123C858F1C390C58F936393E8216A4BCCB941CA2A31B9E64。仍无本次批准消费件、新gate/pick/suite均0；不以静审通过充当执行批准。
