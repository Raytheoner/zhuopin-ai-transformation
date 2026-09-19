# CLAUDE.md — Q2 8D 报告 AI 自动判定（场景级进度笔记）

> 本文件是 Q2 的本地记忆/进度笔记。项目级上下文见仓库根 `CLAUDE.md`；规划权威见全景规划 §2.1.3 Q2 块；档位正本＝陈忱 V3.2（`data/rules/8D评审规则库V3.2-结构化清单.json` 为搬运件）；签认追溯＝`1-转型规划/8D报告AI评审规则库.md`（台账，不是档位来源）。本场景 ＝ CC 建造车间产物；**不改规划文档**。

## 1. 定位
- 质量域旗舰①，排期 2026-10。输入＝已有 8D 的 D1–D8 段落文本（QD-A 为前置抽取层）→ 输出 七维评审结论＋百分制评分＋A/B/C/D 分级＋处置**建议**。
- 自动化等级 **L2**（AI 评审并输出评分报告，质量工程师最终确认）：退回决定由质量工程师签发，引擎不执行流程动作。
- 当前档位：**档 1（mock 验证）**，`pytest -q --tb=short --maxfail=5` **19 passed**（2026-09-19，`OP-0919-C`，含门户页测试）。

## 2. 决策
- 业务判据全部来自陈忱签认：08-25 判例 1/3/4/5/6、08-28 判例 2、09-01 `质量部#11`（两档／M1–M18／P1–P3）、09-14 `质量部#14`（判例 7–11、验收集标签）——逐条以 `Signoff(陈忱, 日期, 凭据)` 登记 `config.CRITERIA`（24 条），`RULE_VERSION=q2-v3.2-chenchen-2026-08-28+signoff-2026-09-14`。
- 判定顺序（不得颠倒）：模板映射（判例 10）→ D0/D8 豁免（判例 2）→ **结构闸（判例 9）** → 红线（P1/P2/判例 7/11）→ 51 条评分（M4/M6/M10/M15/M16）→ 分级（M5 左闭右开）→ **安全分流（判例 6，评分后、退回建议前）** → audit。
- 语义层（25 条语义规则＋红线①②③⑤）**档 1 无 LLM 实现**：`PendingSemantic` 一律待人工，等级只出区间 `[下界, 上界]`；`HumanVerdictSource` 承接质量工程师逐条裁决后才出单一等级。红线①⑤有关键词预筛（判例 8 表面原因词／验证词）只出「疑似」。
- 工程决策 D1–D8 见 `openspec/changes/q2-8d-review-verdict-mvp/design.md`，✅ **2026-09-19 Shao Peishen 追认通过**（答复原文 `1a 2a`；D3-M10 六组取 a、D4-D3-03 并入 D3-06 均按已签认口径引用）。
- 两项未签认在 `config.PENDING`（措施可验证性标准／语义层上线签认），读即抛，本包不代填。

## 3. 底座
- `zhuopin_platform.criteria_signoff`、`audit`（每份一条 `AuditEvent`，`decision` 恒带 `rule_version`＋`automation_level`＋规则表 sha256）、`bootstrap.ensure_paths`（唯一样板）。
- 上游：QD-A `doc_reader.DocumentSections.sections`（D 段全文）＋ `EightDRecord.safety_related`（置信度原样带入）。
- OEM 隔离：含 OEM 信息的 8D 按客户隔离（`5-平台底座/CLAUDE.md` 质量域扩展）；档 1 合成样本客户名一律令牌 `【客户A】`；`AuditEvent.oem_context` 预留，档 2 接 `data_isolation_layer`。

## 4. 红线
- 🔴 真实 8D 原文一律不入 git（`data/golden/`、`results/`、`reports/` 已 ignore，`git check-ignore -v` 实测）。
- 🔴 ASIL C/D ＝ AI 绝对禁区：`AsilExcludedError` 直接抛，不出评分。安全相关＝是／未确认 ⇒ 一律转人工。
- 🔴 判据不写死：引擎所有数字来自 `CRITERIA.value_of(...)`；缺签认一律 `PENDING` 读即抛。
- 🔴 QD-A 命中率 37.9% 低于门槛：`feed_source.from_qda` 不把 LOW/MED 当已确认输入（P2）；红线④只在 HIGH＋确认为空时触发。
- 不碰 `.51`、不发信、不代指派持有人、不代联络陈忱。

## 5. 时间线
- 2026-08-22 v8 定位改为「AI 自动判定」、QD-A 降为前置抽取层；08-25/08-28/09-01/09-14 四轮签认；09-02 规则库降为台账；09-14 验收集 10 份到件。
- 2026-09-17 `OP-0917-Q` 无头泳道从零建到档 1（分支 `claude/op0917q-q2-verdict`，commit `0a52378` 起），红线②③（判例 11）已随本次建造一并落地——`config.J11_REDLINES_2_3_NOT_ACCEPTED_THIS_BATCH` ＋ `redlines.evaluate_redlines` 命中即出 `NOT_ACCEPTED`／转人工、不代填默认判定，`test_all_mock_samples_match_expected` 逐样本断言。
- 2026-09-18 design 审 D1–D8 通过（Shao Peishen 答 `1a`）；`intent.md` 转 `已确认`（答 `2a`）。
- 2026-09-19（队列 §一 `#592`，`OP-0919-B`）：核对 ⑵ 红线②③引擎配置——**已在 09-17 建成，本次复核无需改动**；建 ⑷ PPT D2 页场景勾选行解析器（`QD-A/qda_prefill/doc_reader.extract_scene_checkbox`，详见该场景 CLAUDE.md 时间线），本包 `feed_source.from_qda(scene=...)` 接口原样接受、未改代码。
- 2026-09-19 `OP-0919-C`（队列 §一 `#612`）：tasks 5.1 门户页 `/quality/q2` 落地——`q2_8d_verdict/webapp.py`（Flask 蓝图，首屏显著标注「mock 数据」，网关 `X-Zp-Identity` 接入点已挂但只预留不实现，`install_flask_gate` 用共享 `ZP_GATE_PASSWORD`）＋ `dashboard.py`（七维 D1–D7 得分／满分聚合、A/B/C/D 分级分布含语义层待人工区间桶、处置建议分布、结构性退回与红线命中清单）＋ `scripts/run_q2_web.py`（默认只绑 `127.0.0.1:8098`）。回归 19 passed（原 12＋新增 7）。**5.2 `.51` 部署未做**（本批不碰 `.51`、不新起对外端口，设计上仍走 `.51:8090` 网关反代，`#612` 明令不做）。
- 下一步：语义层（V3 固定模型＋prompt 版本、V4 二级置信）＋ 用验收集 10 份跑校准（排除红线②③、样本 3 单列）→ 档 2 接 QD-A 真实解析（含把 `SceneCheckbox.scene` 接进 `from_qda` 调用，LAN 留步）→ 5.2 `.51` 部署／5.3 第 8 步跟进信（design 审已通过，两项余 §5 待做）。

## 6. 依赖
- 输入：陈忱团队 8D（pptx/docx/pdf，QD-A 解析）；PPT 模板 D2 页场景勾选行（J7，模板改版由质量部做）。
- 下游：历史案例入库／相似案例检索（判例 5 分类标签）；Q4 PPAP 同域复用红线流。
- 开放点：`Q2-G-01` 措施可验证性标准（陈忱）／`Q2-G-02` 语义层上线签认／`Q2-G-03` 样本 3 ※／`Q2-G-04` 持有人 backup（人事）。

**Last Updated**: 2026-09-19
