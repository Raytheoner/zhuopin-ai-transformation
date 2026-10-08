# Q2 门户展示技术设计

> 状态：Shao Peishen 本会话已答“Q2设计：A”及“Q2计划：A；执行：Native；”，技术D1–D7和具体计划均已批；2026-10-08；#661，执行会话01a118fc-82a7-7aa3-8c51-986a2de1a1ed。按批准计划进入隔离实施，实际进度见实施批准与开工.md及后续检查证据。暂不归档：实现及发布尚未完成。批准前设计字节SHA保留approval_baseline，具体计划f2cc原文不追改。

## Context

动机见 `proposal.md`。本次读取主仓 HEAD `557429e2ed10afdfee35a63fa79e72520b9be88f` 的 Q2 页面、模型和聚合代码，未执行引擎、调用业务 GET 或读取真实 8D。页面只有 `/quality/q2/` 汇总入口；原 GET 加载合成输入、evaluate 每份并写原审计。`_render_page(verdicts)` 和 `dashboard.summarize/render_markdown` 可直接消费现成结果。

批准来源：`docs/superpowers/plans/2026-10-08-portal-ui-rollout.md` 阶段3；`1-转型规划/AI运营指挥中心/UI设计评审-2026-10-07/设计变量.json`、`需求页面映射.json`、`审核说明与统一UI规范.md`；Q2 已确认 `intent.md` 与原 `q2-8d-review-verdict-mvp/design.md` D1–D8。原引擎包 tasks 的语义、校准和发布闸独立有效。

`Verdict` 包含结论和规则依据，未包含原 8D 全文/地址、业务取数时间、单份 audit_id、安全输入或 OEM 身份。`Verdict.to_dict()` 的规则项还省略 step/dimension/judge_method。展示从既有对象读取需要的字段，不能从简化 dict 推断这些内容。

## Goals / Non-Goals

**Goals:** 为质量工程师提供汇总 P16、逐报告依据 P17、原 Markdown 清单和明确的人工责任；纯展示输入足以完成离线契约检查；维持既有数据值及语义。

**Non-Goals:** 本件不接真实报告，不设计签发/退回写接口，不扩网关或权限，不改判据、audit 流程、聚合函数或 #612 部署整合。无自动化晋档。

## Decisions

### D1：复用单一路由，渲染现成结果

保留原 `_render_page(verdicts)` 调用入口，在 `webapp.py` 内用小型纯展示助手构建页面。助手只能读取输入、调用已有 summarize/render_markdown 和转义文本，不创建 engine、load_mock、audit logger 或文件。`create_app`、ping、身份接入点、门禁及 `_index` 流程保持。

备选：独立 SPA/详情 API 会增加状态同步与权限面；在 dashboard 改聚合会扩大业务边界。本方案继续服务端 HTML，无运行依赖新增。注意原页面 GET 的 evaluate/audit 仍存在，“纯展示”仅指渲染函数，不宣称页面访问零业务执行或零审计。

### D2：P16 聚合值逐项绑定，零与缺失分开

七维使用 `summarize` 的全部 D1–D7 项；标题标“已自动判定部分”，维度满分是当前报告集合适用规则满分之和，不标成每维100或单份平均分。分级分布保留 A/B/C/D 和“区间（待人工）”五桶；处置建议按原字符串显示。结构性退回和红线列表保留原记录，不按颜色再次推断业务结果。

全局没有报告时，显示“暂无报告结果”，保留规则/责任/来源说明；可同时显示总数0，但不展示仿真记录或“全部通过”。有记录但某维满分0时显示原数值0并说明本批无可计分项；不造百分比、不标该维通过。列表无项明确“本批无此类记录”，不等于整个报告已经审核通过。

备选：换算百分比或合并五桶会改变观察口径。使用原聚合字典可以逐项对照。

### D3：P17 为同页逐报告依据，原报告能力缺口可见

在汇总之后展示报告列表，每条用本页顺序号建立安全且唯一的 DOM 锚点，显示转义后的 report_id；锚点不直接拼 report_id。使用原生 `details/summary` 展开已有 Verdict，不增加路由、弹窗或远程请求。展开包括分级/区间、分数上下界、处置建议、结构缺段、scene_flags、notes、红线原状态、逐规则 score/max/status/evidence、step/dimension/judge_method。D6 依据属于逐规则表的现有 evidence，不冒充原报告页码或附件。

页面明确“原报告入口未接入，请沿既有质量流程核对原件”；未获正式入口前不生成文件链接、审核人、签认时间、audit_id或按钮。显示“人工复核责任：质量工程师；此页不提交退回/签发”。原型意见至少6字只属模拟设计，不加入正式规则。

备选：复制原型复核表单会产生正式提交错觉；读取原文会进入真实资料接线和 OEM 权限范围。同页 native details 保留键盘及无 JavaScript 可用性。

### D4：规则、红线与人工状态原样表达

`grade is None` 才显示 `grade_range` 的原下界→上界和待人工标签；单一 grade 存在时显示该 grade。分数使用 `score_auto/score_upper/score_max` 原值，单独显示 `score_pending_max`，不将上界展示为最终评分。

红线按照原 status 文字区分“触发（自动判D）”“疑似”“抽取未命中”“本批不验收”和“未触发”。聚合 redline_hits 包含所有非 CLEAR 状态，标题用“需关注的红线记录”，不能统一叫“确定触发数”。L2、needs_manual_review 和处置建议就近展示；即使 grade=A 或有确定性红线也保留质量工程师最终责任。ASIL C/D 由原引擎拒绝，不增加 UI 重新评分路径或展示安全合格承诺。

备选：颜色归并或取等级上界会吞掉专业待办；采用原 enum.value。

### D5：来源与时间只显示已有事实

页头固定标“档1 · mock 合成数据；非真实8D评审结论”，规则版本读取 config.RULE_VERSION，automation_level 读原 config/逐报告字段。来源显示既有合成输入，不把 config.DATA_SOURCE_DEFAULT 环境字符串当本页真实加载来源，因为原 `_index` 明确用 load_mock。

当前无可信业务更新时间、审计标识或原报告引用，分别写“源数据更新时间未提供”“单份审计标识未接入”“原报告入口未接入”。不使用当前时间、文件mtime或规则签认日期替代取数时间；不增加刷新、重算或伪实时提示。未来真实接线由 #612 另审。

### D6：继承公共视觉与原生交互

使用已批变量：canvas #f5f8fc、surface #ffffff、brand #1677ff、text #18253b、secondary #63738b、border #e7edf5；风险/关注/覆盖颜色配文字。页头包括“返回智能门户”的既有入口链接（公共门户 `http://192.168.100.51:8092/`），不猜另一反代路径。1440视口双栏概览、390/320单栏；表格放独立可横向滚动的命名区域，页面主体不横向溢出。长ID、规则版本和依据可换行。

原生展开项/链接可 Tab、Enter/Space 操作，焦点可见；不设计模态层或侧栏，因此本模块没有 Escape 关闭需求。区域标题、表格caption/th scope、触控区域≥44px；按 prefers-reduced-motion 减少运动。备用“原 Markdown 清单”转义后保留。

备选：新建复制门户侧栏会形成两套导航与移动焦点责任。页面只继承公共视觉和来源返回。

### D7：检查直接进入渲染层

批准实施后新增 `tests/test_dashboard_ui_contract.py`，用人工构造的合成 Verdict/RuleFinding/RedlineFinding 直接调用 `_render_page`；不调用 create_app、Flask客户端、load_mock、evaluate或真实 fixture。验证输入快照前后相同；engine.evaluate、feed_source.load_mock、AuditLogger.jsonl 被禁调用，确认页面助手没有越界。既有 test_webapp.py 的客户端检查会 evaluate/audit，若后续需要跑它须说明该原流程，不能冒称纯渲染验证。

展示检查用临时目录保存纯 HTML，由本机临时静态预览做1440/390/320与键盘；无需本轮连接.51或任何业务请求。后续按 rollout 要求一次明确 Luna 独审，保留用户模型约定。当前只完成文档，不加/跑测试。

## 字段展示契约

| 原字段/来源 | 页面位置和含义 | 缺失/特殊情况 |
|---|---|---|
| summarize.total | P16报告数 | 空集合0；无伪造样本 |
| summarize.by_step[D1…D7].auto/max | P16七维聚合表 | 保留七项；max0说明无可计分项，不算比例 |
| summarize.by_grade[A/B/C/D/区间（待人工）] | P16五桶分布 | 0份仍显示；未知等级不由UI改判 |
| summarize.by_disposition | P16处置建议分布 | 原建议字符串；空字典无记录 |
| summarize.structural_returns[].report_id/empty_sections | P16结构性退回清单 | 原缺段标签；不补跑评分 |
| summarize.redline_hits[].report_id/redline_no/status | P16需关注红线记录 | 包含疑似/未验收/抽取未命中，不能全计确定触发 |
| Verdict.report_id/scene/scene_flags | P17报告识别与场景 | 原文字转义；不猜客户/编制人 |
| grade / grade_range | P17单一等级或原区间 | None才用区间；不排序或取上界判通过 |
| score_auto/score_upper/score_max/score_pending_max | P17已判定分、可能上界、适用满分和待人工分 | 原值显示；结构闸等无评分需同时显示原notes/缺段 |
| disposition / needs_manual_review / automation_level | P17 AI建议、待复核与L2 | 保留原值、最终责任说明；无执行接口 |
| structural_return / structural_empty_sections | P17结构缺段 | True时显著显示，原规则/红线为空不能说“全部合格” |
| redlines[].redline_no/step/description/status/evidence | P17逐红线依据 | 空evidence“依据未提供”；CLEAR只是该条未触发 |
| rules[].rule_id/step/dimension/judge_method/status/score/max_score/evidence | P17逐规则依据表 | PENDING/NA原样显示；空依据不造坐标，零分不等于缺字段 |
| notes / config.RULE_VERSION / config.AUTOMATION_LEVEL | P17说明与页头版本责任 | 原备注逐条显示；版本缺失必须显式缺失 |
| 原报告地址/原文、源更新时间、单份audit_id、复核人/签认时间 | 页头和P17能力边界 | 当前模型无字段，明确未接入/未提供；无占位人物或时间 |

## Risks / Trade-offs

- [model包含结果但不含原报告/审计引用] → 明示缺口，逐条依据只能证明已有发现来源文字，不能证明完整原件复核。
- [某些mock单份语义待人工或结构闸未评分] → 等级区间、原 notes、缺段、pending/NA原样呈现，不生成最终结论。
- [原 GET 每次运行mock引擎并写审计] → 保留原行为，纯展示验证绕过 GET；生产冒烟范围另说明并取得批准。
- [真实报告数量扩大后同页较长] → 当前档1合成规模内逐项展开；真实接线前另审分页和 OEM 权限，不提前增加查询接口。
- [主仓与历史部署分支尚未整合] → 上线申请先核精确服务器文件与源版本，仅UI包不能宣称历史整合完成。

## Migration Plan

1. proposal/design/spec/tasks 的技术设计已由“Q2设计：A”批准；详细计划见 `docs/superpowers/plans/2026-10-08-portal-q2-ui.md`，待本人审核计划并选择执行方式。纯文档可 off-LAN 审阅。
2. 计划及执行方式批准后检查已有适用工作树，按原技能选择隔离树；仅两件代码/展示测试及对应证据，先完成定向检查和1440/390/320可用性检查。
3. 一次 Luna review、修复与复验，形成精确commit和文件清单；ff及.51上线逐项申请，不因旧QD-B授权跳过。
4. 发布前核现有Q2服务、主仓/历史分支/服务器版本差异，准备只替批准文件的备份和哈希；回滚恢复此次文件。原服务重启、业务GET审计及任何真实样本另在发布范围审批。

## Open Questions

Q2-G-01/G-02/G-04仍由原业务线承接，当前设计使用原待人工和责任表达即可实施；其回件不作为UI代签。正式原报告入口、业务时间和单份审计标识若未来接入，另有数据契约审查。以上均不阻断本包当前档1纯展示设计，不能提前标已闭。
