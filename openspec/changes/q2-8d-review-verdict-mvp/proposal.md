# q2-8d-review-verdict-mvp Proposal

> 🔴 **状态：档 1 mock 已全绿（12 passed），design 审 🟡 待 Shao Peishen。** 由无头泳道 `B-0917_波1bis / op0917q-q2-verdict`（件号 `OP-0917-Q`，队列 §一 `#612`）起草并建造。**本包类别 ＝ 业务场景变更包**（非机制/环境类）⇒ `openspec/config.yaml`「本次退休哪一个既有守卫」按其括注不适用。
> 🔴 **`intent.md` 现为 `status: 待确认`**（转写版，非 grill；`#612` 明令不跑 grill）⇒ CI `scene-intent-gate-lint` 对本包报违规属**如实状态**，转 `已确认` 由 Shao Peishen 定。

## Why（为什么做）

陈忱 08-25／08-28／09-01／09-14 四轮回件攒出的全部判据（51 条规则、6 条红线、11 条判例、10 份验收样本、7 条退回理由）**现取全仓零个 `.py` 引用**——没有任何东西消费它们。Q2 排 2026-10、零工程实体，与 FI3 09-17 早间处境相同。Shao Peishen 2026-09-17 答 `a`（「新场景发布能提高团队工作积极性」）立行 `#612`。本包让引擎把签认判据吃进来、在合成样本上跑通档 1，并把「哪些能自动判、哪些必须转人工」按 P1/P2/判例 11 如实分开。

## What Changes（改什么）

- 新建 `4-数字员工/质量部/Q2-8D报告AI判定/`：`q2_8d_verdict/{config,models,rules_loader,vocab,checks,semantic,redlines,engine,feed_source,run}.py` ＋ `tests/`（12 passed）＋ `data/rules/`（V3.2 JSON 搬运件，sha256 用例守与正本一致）＋ `data/mock/samples.json`（11 份合成样本，按验收集形态仿写、零真实文字）。
- **陈忱签认逐条以 `Signoff(陈忱, 08-25/08-28/09-01/09-14, 凭据)` 登记进底座 `criteria_signoff`（24 条覆盖层）**；引擎无一处写死数字。
- **两项未签认落 `PENDING`（读即抛）**：措施可验证性标准（判例台账 §3 开放点 1）、语义层上线签认。
- 判定流：模板映射（判例 10）→ D0/D8 豁免（判例 2）→ 结构闸（判例 9）→ 六红线（P1 语义只出疑似／P2 抽取未命中转人工核／判例 7 填 N＝未固化／判例 11 ②③本批不验收）→ 26 条确定性规则评分（M4/M6/M10/M15/M16/M18）→ M5 分级（语义待人工时只出区间）→ 判例 6 安全分流 → audit。

### New Capabilities
- `q2-verdict-engine`：结构闸＋红线流＋评分分级＋分流＋审计（档 1）。

### Modified Capabilities
无。平台 `audit`／`criteria_signoff`／`bootstrap` 为消费复用，不改其契约。QD-A 只读其解析结果，不改 QD-A。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

**1. 本流程哪些判断是人脑默会经验？** 已显性化：51 条规则的判定方式与分值（V3.2）、两档结构、六红线的自动/转人工边界（P1/P2）、D3 子字段扣分步长与封顶（M4）、D7「填 N＝未固化」（判例 7）、结构性退回先于语义（判例 9）、模板映射（判例 10）、场景标签来源（J7）。仍在人脑里：**措施可验证性的判定标准**（`Q2-G-01`）、25 条语义规则与红线①②③⑤的实际裁决（档 1 由质量工程师经 `HumanVerdictSource` 逐条给出、`audit` 留痕）。

**2. 由谁显性化？** 持有人 ＝ **陈忱**（质量部，实名签认人，四轮回件）。🔴 backup 与前置总表 Q2 行的持有人登记**未指派，本包不代指派**（`Q2-G-04`）。

**3. 用什么方法提取？** **AI 起草·专家批改**（判例批改法：我方拟判 → 她 w14:checkbox 勾选／文本逐字确认 → 回灌台账）＋ **历史案例反推**（10 份验收集、7 条退回理由为 ground truth）＋ 上线后 **L2 改判判例累积**（`HumanVerdictSource` 即采集入口）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位 ＝ 档 1（mock 验证）**：11 份合成样本覆盖 合格/边界/客户模板/七步法/结构性退回/供应商编制/红线④⑥触发/研发/场景未标注，`pytest -q --tb=short --maxfail=5` **12 passed**；`openspec validate --strict` 通过；CLI 出清单＋审计 JSONL。
- **晋档 2（真实数据跑通）条件**：① design 审通过（🟡）；② 语义层实现（V3 固定模型＋temperature=0＋prompt 版本入 audit；V4 二级置信）；③ 用验收集 10 份跑校准，**红线②③排除在指标外、样本 3 单列**，语义规则一致率≥80%、红线假阳≤2%（V2）；④ `PENDING.SEMANTIC_LAYER_ACCEPTANCE` 签认落档；⑤ `feed_source.from_qda` 接 QD-A 真实解析（LAN 留步）。
- **晋档 3（内部服务）**：门户页 `/quality/q2`（不新起端口）、`.51` 部署＋冒烟＋回滚 SOP、跟进信（串行闸三分支）。
- **价值指标（质量型为主）**：8D 首次评审通过率↑、退回轮次↓、评审工时↓（基线由陈忱确认）；红线误判＝0 为硬指标（宁可漏报不可误报）。
- **LLM 判据黄金集**：档 1 不含 LLM 运行时判断；语义层上线前须以验收集为黄金集（V5 漂移闸）。

## Impact（影响面）

- **新增**：上述场景目录；`openspec/changes/q2-8d-review-verdict-mvp/`。
- **底座依赖（消费，不改）**：`criteria_signoff`、`audit`、`bootstrap.ensure_paths`。
- **OEM 隔离**：含 OEM 信息的 8D 按客户隔离（质量域扩展口径）；档 1 合成样本客户名全令牌化，`AuditEvent.oem_context` 预留，档 2 接 `data_isolation_layer`。
- **不修改**：QD-A 任何文件；V3.2 JSON 正本；判例台账；任何规划文档。

### 红线核对
| 红线 | 本包状态 |
|---|---|
| mock 先行 | ✅ 只有合成样本；`qda` 通道须逐份传入、不落盘 |
| audit 留痕 | ✅ 每份一条 `AuditEvent`，`decision` 恒带 `rule_version`＋`automation_level`＋规则表 sha256 |
| OEM 隔离 | ✅ 客户名令牌化；`oem_context` 预留 |
| L2 门禁 | ✅ `needs_manual_review` 恒 `True`；处置一律「建议」；退回由质量工程师签发 |
| ISO 26262 | ✅ ASIL C/D `AsilExcludedError`；安全相关一律转人工 |

### 伴生文件的 .gitignore 覆盖（强制项，队列 #328 子项②）
本变更新增自动生成物：`reports/q2_verdicts.md`／`reports/q2_audit.jsonl`（CLI 产出）。`git check-ignore -v` 实测：`4-数字员工/质量部/Q2-8D报告AI判定/.gitignore:2:reports/` 命中 `reports/x.md`；`:11:data/golden/` 命中 `data/golden/a.pptx`；`data/rules/*.json`、`data/mock/*.json` 实测**不**命中，刻意不整体忽略 json（评估件 §5.6 的 QD-A 地雷不复制）。

## design 停审点（🟡 Shao Peishen）

见 `design.md` D1–D8。**本包停在档 1**：design 审通过前不接真实解析、不上语义层、不部署、不发信。
