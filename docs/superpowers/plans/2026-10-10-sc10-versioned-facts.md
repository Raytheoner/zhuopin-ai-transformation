# 供审执行边界（根会话收敛）

本计划供审，不授权立即执行。已批准 design SHA 06DA737EF7C8BC647AD456047A265071501759059EEAED7FB687CE333B9C36DC 不变；本件新增的是精确实现/测试和隔离副作用审。

1. 起点固定主仓当前 HEAD `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。本聊天无可复用的合适托管树；历史 O3/门户树保留，不扩写。
2. 获批后用 app 原生 `create_worktree(allowAsync=true, name=sc10-versioned-facts-1010, ref=28337c0ebb52afdbf61e955ecdbc22d151bcd185)` 创建并附着新候选。批准范围包括原生工具返回的仓库外新 checkout/必要 Git 元数据；创建后将实际绝对 workspace 路径留证，只修改正文四个产品/测试路径。Native 执行及显式 gpt-6-luna 沿用。没有复制旧 dirty、删除目录、重置分支或改全局依赖的动作。
3. 计划/已批准 OpenSpec 在主仓读取。候选产品修改、定向测试和独立审查均在该新树；主仓产品不覆盖。正式 tasks/队列与批准/证据记录由根按共享锁落库。候选 diff/最终 SHA 留证，CommitSweep 的实际候选提交/ff 另按既有治理闭合，不在候选裸跑主仓 sweep 或手动 commit。
4. 逐项目测试只包括本文四个 SC10 文件：test_evidence.py、test_review_facts.py、test_agent_audit.py、test_pending_gates.py。baseline 用其中三个已存在文件；实现后只运行同一清单。每次新 UUID 的主仓 ignored `reports/sc10-versioned-facts-1010/run-<uuid>/` 保存独立 basetemp（含 synthetic JSONL/lock）、JUnit、stdout/stderr、退出码；不覆盖/删除旧证据，不安装依赖，不做根混跑。
5. 下面的唯一测试命令要求显式 `CandidateRoot`（原生工具的真实返回路径）。没有真实 ERP/行情、专业建议或业务签认；ff/push、生产、真实源及外发均不在本次实现批准范围。

---

# SC10 版本化事实包实施计划（供审）

## Goal

交付 SC10 首项可复核的 synthetic facts：fixture_id=SC10-MOCK-B01、revision=r1，含 2 个成品、3 个物料，计算毛需求 80/10/20 与完备度 3/1/2/0；输入冻结、三个输入源分别哈希、manifest 与结果哈希可复算；成功结果写入真实持久 JSONL 审计并可重新打开读取。版本化入口明确委托既有 collect_facts 与平台 explode_bom，不改旧入口语义，不生成任何建议、真实性结论或专业签认。

本文件只是计划，不代表实现已批准或发生。本轮没有改产品/测试/正式 OpenSpec/队列，没有运行测试、连接真实数据源或写入运行审计。

## Architecture

1. 新建独立 evidence.py，定义 immutable frozen snapshots、canonical serializers、三源 hash manifest 与 versioned result envelope；不改 MaterialRecord、BomRow、ProductionPlan 等共享模型，不改 kit_engine。
2. 新入口 run_versioned_review_facts 接收当前 BomRow、ProductionPlan、MaterialRecord 数据，先冻结输入；从冻结副本恢复底座输入，再委托既有 collect_facts；对冻结输入、输出事实与 schema/version 作哈希和审计。
3. 保留 run_review_facts 作为 legacy 入口，不在其中增加版本化校验、改变默认行为或改变其旧审计事件。旧事件没有本版本 evidence_contract/run_mode 字段，不能被下游当作版本化结果。
4. 完全匹配已批准 design：scenario=SC10、action=bom_review_facts、evidence_contract=sc10-versioned-facts-v1、run_mode=synthetic_versioned。manifest 同时记录 fixture_id=SC10-MOCK-B01、revision=r1、source_kind=synthetic、固定 as_of、facts_contract_version 和 professional_rule_version=not_applied；缺少任何身份/版本/hash 字段的事件不能按本包 versioned facts 消费。
5. 采购普通物料数据的 oem_context 保持空；三个 suggest_* 仍 PendingPrerequisiteError。价格为 0 是有效数值，None 才是缺价；零价合理性与真实源有效性由专业/业务流程另行判断。

## Tech Stack

- 项目现有 Python runtime 与 SC10 包；数据展开沿用 zhuopin_platform.agents.kit_engine.explode_bom。
- Decimal 用于输入边界冻结与 canonical numeric form；JSON canonicalization 使用 UTF-8、sorted keys、无 NaN/Infinity、紧凑分隔符。
- 审计使用平台 AuditLogger.jsonl(path) 与真实 JsonlSink，事件经 AuditLogger.record 持久追加。
- pytest 与 tmp_path 用于之后的隔离验证；本轮不运行测试。

## Spec

- 正式 change：openspec/changes/sc10-bom-review-material-governance。
- 已批准设计：openspec/changes/sc10-bom-review-material-governance/design.md；D1–D9 与 canonical/audit 条款；SHA-256 06DA737EF7C8BC647AD456047A265071501759059EEAED7FB687CE333B9C36DC。版本字段逐字遵循设计固定值：scenario=SC10、action=bom_review_facts、evidence_contract=sc10-versioned-facts-v1、run_mode=synthetic_versioned。
- OpenSpec apply instructions 当前显示 10/36 项完成；3M.1 要求本具体实施计划及产品/测试白名单经供审并获批。根已将正式 delta/tasks 调整为 3M dependency 与 MODIFIED old/ADDED new，三个 strict valid；正式文件由根维护，本计划不修改它们。
- 3M 实施只覆盖可重复的 mock facts。真实 ERP/API、采购经理专业判断、建议实现、晋档、发布、归档都不在范围内。

## Global Constraints

- 本计划仅供批准，不授权实施或测试。
- 保护既有 run_review_facts、collect_facts、MaterialRecord 类型、shared models、kit_engine、sources、三个建议闸和旧测试口径。
- 不引入 ERP/外部行情 API，不查询现网，不写正式运行 audit，不创建新的运行服务，不改变 OEM 隔离策略。
- 不凭技术校验替代人对生命周期、零价、选用级别或淘汰规则的专业认定。
- canonical 输入保留每一个 BOM 行，包括完全重复行；规范排序仅消除输入排列对 hash 的影响，不使用 set 去重。
- 数值先严格转换成 Decimal；None、Decimal(0)、枚举 UNKNOWN 与主数据缺失必须保持语义差别。拒绝 bool、NaN、正负 Infinity、负毛用量、越界/无效输入及无法明确序列化的值。
- Decimal 的 canonical 形式使用普通十进制字符串，去除无意义尾零、零统一为 0；不得通过 binary float JSON 输出。
- 本计划中的测试和命令都只在未来实施获批后执行；日志、夹具均置于 pytest tmp_path。
- 保留所有已有 dirty/untracked 变更。白名单之外若确有依赖改动，先停止并重新审阅，不扩大本任务所有权。
- 不手动 commit；不创建 worktree。将来若进入实现，使用 Native 隔离执行，遵循仓库既有 dirty 状态，不清理历史工作。

## Review Focus

1. frozen 输入是否与调用方后续 mutation 隔离，hash 是否不受原始 list/dict 改写影响。
2. BOM、计划、物料三个来源是否各自有 schema version、完整字段集与独立 SHA；manifest 与最终事实结果是否可独立复算。
3. 排列变化是否保持 canonical hashes；同计数不同值是否改变来源 hash 和 result hash；重复 BOM 行是否仍参与展开。
4. None、0、UNKNOWN、not-in-master 是否分别保留，不将未知回填为默认值。
5. 新入口是否只委托 collect_facts/底座展开；旧入口、旧事件和 suggest_* 闸是否不变。
6. 成功是否必须具有真实 JSONL 持久化事件；无 audit 或写入失败是否绝不返回成功 result。
7. 是否没有 OEM context、真实数据、建议、专业签认、ERP/API、发布或档位结论。

## File Structure and Ownership

本轮未来实施的最小白名单：

- 新建：4-数字员工/采购部/SC10-BOM评审与物料库管控/sc10_bom_review/evidence.py
- 修改：4-数字员工/采购部/SC10-BOM评审与物料库管控/sc10_bom_review/agent.py
- 新建：4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_evidence.py
- 修改：4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_agent_audit.py

必须保持不变：sc10_bom_review/models.py、review.py、sources.py、pending.py，平台 shared models、kit_engine、AuditLogger/JsonlSink、正式 OpenSpec proposal/spec/design/tasks、场景 CLAUDE/README、队列、运行配置与真实连接器。报告自身位于 reports/sc10-versioned-facts-1010/implementation-plan.md；本路径的 ignore 证据为 .gitignore:59:**/reports/，git check-ignore -v 已返回该规则命中。

## Canonical Data Contract

Canonical JSON 顶层字段固定为 schema_id、schema_version、records。输入源各有独立 schema_id/version；canonical object 的键名和值型显式固定，拒绝未识别的字段或类型漂移。SHA-256 作用于 UTF-8 编码的 canonical JSON，不含时间戳、随机 UUID、路径、Python repr 或 list 输入排列顺序。

| 输入源 | Canonical 字段与语义 |
|---|---|
| BOM 行 | 完整编码 product_id、component_id、component_name、level、qty_per_unit、loss_rate、unit、sequence、is_substitute 共 9 字段。数值用量/损耗为 Decimal 字符串；is_substitute 为 JSON boolean；其余字段保留原始字符串。即便旧 fixture 使用默认值，sequence 与 is_substitute 也必须进入 hash。完全相同的多行均保留。 |
| ProductionPlan | plan_id、product_id、product_name、planned_qty、planned_date；数量按底座声明保留 int 并在 canonical JSON 用整数表示；planned_date 按底座字段保留字符串原值。该字段不是来源版本或 as_of 时间。 |
| MaterialRecord | material_id、material_name、category、lifecycle、package、unit_price。lifecycle 用 Enum.value；unit_price 的 null 对应 None，数值 0 编码为字符串 0，正数为稳定十进制字符串。未入库物料由事实结果的 not_in_master 表示，不创建猜测的主数据行。 |

BOM 字段名依据当前平台 BomRow 声明：product_id:str、component_id:str、component_name:str、level:int、qty_per_unit:float、loss_rate:float、unit:str、sequence:str=''、is_substitute:bool=False。ProductionPlan 字段为 plan_id:str、product_id:str、product_name:str、planned_qty:int、planned_date:str；planned_date 不充当来源版本/as_of。实现前将两组确切字段集合固定进各自 schema v1 和测试；实际声明若有差异，停止并重新审阅，不根据构造位置猜字段或静默忽略字段。

Canonical 排序规则：BOM、计划、物料分别按 canonical row 的完整 UTF-8 JSON 字节序排序；排序不删行，不合并完全重复记录。物料事实按 material_id 排序；每个 BomUsage 的 product_ids 是去重后的产品标识集合，以 UTF-8 字节序排序，符合现有共享料事实语义。所有输出数组依各自规则稳定排序。

Manifest 固定字段：scenario=SC10、action=bom_review_facts、evidence_contract=sc10-versioned-facts-v1、run_mode=synthetic_versioned、fixture_id=SC10-MOCK-B01、revision=r1、source_kind=synthetic、as_of=not-applicable/synthetic、facts_contract_version=sc10-bom-review-facts-v1、professional_rule_version=not_applied、input_schema_versions、bom_sha256、plans_sha256、materials_sha256、manifest_sha256。mock 的 `as_of` 固定字面值 `not-applicable/synthetic`，不使用当前日期或计划日期冒充提取时刻。manifest_sha256 对除自身字段外的 manifest canonical JSON 计算。Versioned result 固定字段：manifest_sha256、facts、facts_contract_version、result_sha256。facts 的完整 canonical 字段为 usages[{material_id,gross_qty,product_ids}]、unknown_lifecycle、missing_price、not_in_master、data_readiness{materials_in_bom,lifecycle_unknown,price_missing,not_in_master}；result_sha256 对除自身字段外的完整 result canonical JSON 计算。

## Implementation Steps

### 0. 批准与执行准备

1. 重新核对 design.md SHA-256 必须仍为 06DA737EF7C8BC647AD456047A265071501759059EEAED7FB687CE333B9C36DC。若不一致，停止并重新审阅。
2. 确认具体实施计划获得批准，正式 spec/tasks 3M dependency 已生效。OpenSpec 设计齐全不等同于 3M.1 计划审批。
3. 核对四个白名单文件及仓库既有 dirty 状态；不覆盖任何他人改动。未来实际实施必须在 Native 隔离运行并保留现场状态。
4. 锁定当前平台 BomRow 的 9 字段 schema 与 ProductionPlan 的 5 字段 schema。若实际声明与表中字段不同，停止并重新审阅，不能根据构造位置猜字段语义。

### 1. 新增不可变输入证据模块

1. evidence.py 定义 frozen dataclasses：FrozenInputs、SourceManifest、VersionedFactsResult。所有集合用 tuple；嵌套字典不暴露可变引用，使用冻结键值 tuple 或只读映射。
2. freeze_inputs 接收 BOM、plans、materials 三个来源。每个来源在进入函数时立即复制为只含不可变标量的快照；对外部 dataclass/list 后续修改不影响快照。
3. 分别实现 canonicalize_bom_row、canonicalize_plan、canonicalize_material；每一项显式处理 null、Decimal、Enum 和字符串，不使用 dataclasses.asdict 后任意接收字段。
4. 固定数值入口：int/Decimal/finite float 接受，bool 明确拒绝；float 仅用 Decimal(str(value)) 转换；不接受 NaN/Infinity。毛需求、计划量及单价不得小于零。None 保持 null，不得变成 0；枚举必须是 LifecycleStatus 成员并序列化 value。
5. 规范化后按本文件 Canonical Data Contract 的规则排序。保留完全重复 BOM 行；材料以 material_id 作为主数据键，重复物料 master id 拒绝，避免 dict 覆盖造成来源歧义；计划重复 id/冲突字段也拒绝。
6. 通过确定性 JSON 计算 bom_sha256、plans_sha256、materials_sha256；添加输入 schema 与 evidence contract 计算 manifest_sha256。所有 hash 为小写 64 位十六进制。
7. 提供从 frozen tuple 重建新的 BomRow、ProductionPlan、MaterialRecord 实例的内部函数，供 collect_facts 消费；禁止将调用方原对象直接传下去。MaterialRecord 是 frozen dataclass，测试只通过替换调用方 list 元素验证脱离，不尝试原地改其字段。

### 2. 增加版本化事实入口并保持 legacy 兼容

1. 在 agent.py 新增 run_versioned_review_facts，要求显式 evaluator 与 audit；签名允许测试传 audit=None 以验证立即拒绝，但运行时不得以无审计方式返回 facts。evaluator 空白、audit 缺失或 contract/mode 不匹配时，在事实计算前拒绝。
2. 固定 scenario=SC10、action=bom_review_facts、evidence_contract=sc10-versioned-facts-v1、run_mode=synthetic_versioned；fixture_id、revision、source_kind、as_of、facts_contract_version 与 professional_rule_version 作为 manifest 和审计事件身份字段。旧事件没有这些字段，仍识别为 legacy。
3. 调用顺序：校验闸 → freeze_inputs → 从 frozen 输入重建共享模型 → 调用既有 collect_facts → 对事实字段 canonicalize → 生成 result hash → 构造 AuditEvent → audit.record → 返回 VersionedFactsResult。audit.record 成功前不返回结果。
4. 不直接复制 BOM 展开或主数据对齐逻辑；collect_facts 继续委托既有 kit_engine.explode_bom。新入口必须和 legacy collect_facts 对相同 frozen 输入产出相同事实内容。
5. 保留 run_review_facts 原函数、旧 ACTION、audit 可选行为、旧 data_sources/content_hash 结构，不把旧入口自动改造成版本化验收；legacy 事件没有本版本 evidence_contract/run_mode 时保持可识别为 legacy。
6. 新版本化 AuditEvent 仍使用固定 SCENARIO 与 ACTION，并在 decision/data_sources 写入全部 manifest 身份字段、三个 source hash、manifest_sha256、facts_contract_version、result_sha256、professional_rule_version=not_applied；保留 readiness counts、shared_materials、review_status=待前置到位、blocked_by 三项原标记。content_hash 使用 result_sha256。data_sources 值遵循平台字符串约束。legacy 与 versioned 的判别依据为完整 evidence_contract/run_mode/manifest 字段齐全与否，而不是更换 action。
7. 保持 oem_context 空；不要将材料普通采购数据送入 OEM 隔离路由。
8. audit 缺失或 AuditLogger.record/JsonlSink.write 异常均无成功返回。不要捕获审计错误并返回先算好的事实；失败状态通过异常交给调用者，不伪造持久审计行。
9. 三个 suggest_* 仍调用 pending.require 并 fail-loud；不实现任何建议、排序、淘汰判定或默认策略。

### 3. 构造冻结 mock 输入与边界矩阵

1. 在 tests/test_evidence.py 中用 pytest tmp_path 纯内存/临时对象构造 fixture_id=SC10-MOCK-B01、revision=r1：产品 F01 计划 10、F02 计划 20；BOM 中 F01→M-A 用量 2、F01→M-B 用量 1、F02→M-A 用量 3、F02→M-C 用量 1。每行明确包含全部九个字段；基线 sequence=''、is_substitute=False。预期毛需求 M-A=80、M-B=10、M-C=20，共用料 M-A 的 product_ids 为 F01/F02。
2. 主数据设置 M-A 生命周期 Active 且单价非空；M-B 生命周期 UNKNOWN 且单价 None；M-C 生命周期 NRND 且单价 None。预期完备度按现有四指标顺序为 materials_in_bom=3、lifecycle_unknown=1、price_missing=2、not_in_master=0。普通采购事实 oem_context 为空。
3. 同值换序：反转 BOM 行、计划和物料列表，三个 source hashes、manifest hash 与 result hash 必须不变。
4. 同计数换值：保持 3/1/2/0 各数量不变，只把 M-A 有效正单价改为另一正数；materials source hash、manifest hash、result hash 必须变化，而 readiness counts 保持不变。
5. 重复 BOM：在同一产品中追加一条完全重复 M-A 行；canonical BOM hash 必须反映额外行，不能去重；collect_facts 毛需求按底座计算增加，product_ids 仍是唯一产品集合。
6. 区分 null/zero/UNKNOWN/not-in-master：M-C 单价 0 不算 missing_price；None 算 missing_price；UNKNOWN 进入 unknown_lifecycle；不存在的 M-X 只进入 not_in_master，不能伪造 MaterialRecord。各 case 的 source/result hash 与计数按事实变化。
7. 冻结性：freeze_inputs 后通过替换调用方列表中的 BomRow（含 sequence）、ProductionPlan 与 frozen MaterialRecord 元素，验证已冻结快照、hash 与重建输入不变；直接尝试修改 frozen snapshot 字段应失败。
8. 数值边界：接受十进制等价值并得到相同 canonical number；拒绝负数量/单价、bool、NaN、正负 Infinity、不规范日期、未知 lifecycle 值、空 ID、重复主数据 ID；非法输入不得生成 manifest/result/audit 成功事件。
9. 计划 fixture 仅为 synthetic 数据，不在仓库留入出料文件，不调用 ERP/API，也不生成采购或产品建议。

### 4. 验证真实持久 JSONL 与 legacy 隔离

1. 修改 tests/test_agent_audit.py 添加 versioned success 测试：用 AuditLogger.jsonl(tmp_path / audit.jsonl) 调用新入口；检查文件真实存在且至少有一行合法 JSON。
2. 关闭第一次 logger 后，以相同 audit.jsonl 路径新建 AuditLogger，断言返回的 ChainVerifyResult 满足 `ok is True` 且 `total == 1`，再 query_by(scenario=SCENARIO, action=ACTION)，按 evidence_contract/run_mode/fixture/revision/source_kind/as_of/facts_contract_version 区分 versioned 行，逐一断言三个源 hash、manifest/result hashes、L2、synthetic-test-operator、professional_rule_version=not_applied、readiness、shared_materials、review_status 与 blocked_by。
3. 使用平台审计的实际验证接口核验 JSONL 链；不以 mock sink、内存事件列表或仅检查调用次数作为持久化证据。
4. audit=None 必须抛出清晰错误，不返回 VersionedFactsResult；构造受控写入失败时，新入口传播异常且调用方拿不到成功结果。
5. 并排调用旧 run_review_facts 与新 run_versioned_review_facts，两个事件都保持 scenario=SC10/action=bom_review_facts；旧事件不含 versioned manifest 身份字段，新事件含完整字段、hash 与链；旧 API/audit=None 合同行为不变。
6. 仍验证采购普通物料审计 oem_context 留空、三个 suggest_* 必须抛 PendingPrerequisiteError。

### 5. 获批后运行定向测试与交付审查

未来实施获批后，从 SC10 子项目 cwd 使用本文档后部的唯一 UUID/JUnit/stdout-stderr 定向命令；本轮没有运行测试。

通过后逐项复核：diff 不超白名单；共同底座和旧函数未改；M-A/B/C 预期值正确；列表换序 hash 稳定、同计数换值 hash 改变；重复 BOM 未丢；错误输入不产成功审计；重启 logger 后 JSONL 可读且链验证；三个建议闸仍拒绝；oem_context 空。未全部成立不得宣称本计划范围完成。

## Side Effects and Isolation

- 预期产品副作用限于新 evidence.py 与 agent.py 的版本化入口；测试仅新增/修改两个 SC10 定向测试文件，生成物只在 pytest tmp_path。
- 不写 reports 外的本地快照、不创建产品运行 audit、不访问服务端数据，不修改其他场景的共享模型或算法。
- 将来执行须用 Native 隔离工作环境；本轮不创建 worktree、不手动 commit、不清理或覆盖他人的工作。
- 计划批准也不批准合并、push、部署、真实 ERP/API、业务审核、知识签认、专业判定、建议功能、升档或归档。

## Concrete Implementation Listing

以下是计划中的完整新模块与关键入口/测试代码，供评审锁定接口和失败行为。实现时照此拆成白名单文件；若批准 design 与下列合同冲突，先修订计划，不得直接改变批准 design。平台共享类型字段已核为 BomRow 九字段和 ProductionPlan 五字段；这两个共享类及 kit_engine 均不修改。

### evidence.py

~~~python
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .models import BomReviewFacts, LifecycleStatus, MaterialRecord
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

SCENARIO = "SC10"
ACTION = "bom_review_facts"
EVIDENCE_CONTRACT = "sc10-versioned-facts-v1"
RUN_MODE = "synthetic_versioned"
FIXTURE_ID = "SC10-MOCK-B01"
FIXTURE_REVISION = "r1"
SOURCE_KIND = "synthetic"
AS_OF = "not-applicable/synthetic"
FACTS_CONTRACT_VERSION = "sc10-bom-review-facts-v1"
PROFESSIONAL_RULE_VERSION = "not_applied"
INPUT_SCHEMA_VERSIONS = (
    ("bom", "sc10-bom-row/v1"),
    ("plans", "sc10-production-plan/v1"),
    ("materials", "sc10-material-record/v1"),
)
RESULT_SCHEMA_VERSION = FACTS_CONTRACT_VERSION
BOM_FIELDS = (
    "product_id", "component_id", "component_name", "level", "qty_per_unit",
    "loss_rate", "unit", "sequence", "is_substitute",
)
PLAN_FIELDS = ("plan_id", "product_id", "product_name", "planned_qty", "planned_date")
MATERIAL_FIELDS = (
    "material_id", "material_name", "category", "lifecycle", "package", "unit_price",
)


def _assert_source_schema() -> None:
    expected = (
        (BomRow, BOM_FIELDS),
        (ProductionPlan, PLAN_FIELDS),
        (MaterialRecord, MATERIAL_FIELDS),
    )
    for model, names in expected:
        actual = tuple(field.name for field in fields(model))
        if actual != names:
            raise TypeError(
                f"{model.__name__} schema changed: expected {names}, got {actual}"
            )


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _decimal_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError(f"{field_name} 必须是有限数值")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} 不是有效十进制数") from exc
    if not number.is_finite():
        raise ValueError(f"{field_name} 不可为 NaN 或 Infinity")
    if number < 0:
        raise ValueError(f"{field_name} 不可为负数")
    if number == 0:
        return "0"
    text = format(number, "f")
    if "." in text:
        integer, fraction = text.split(".", 1)
        fraction = fraction.rstrip("0")
        text = integer if not fraction else f"{integer}.{fraction}"
    return text


def _float_from_decimal_text(value: str, field_name: str) -> float:
    decimal_value = Decimal(value)
    result = float(decimal_value)
    if not math.isfinite(result) or Decimal(str(result)) != decimal_value:
        raise ValueError(
            f"{field_name} 超出共享 float 的有限且无精度损失范围"
        )
    return result


def _text(value: object, field_name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} 必须为 str")
    if required and not value.strip():
        raise ValueError(f"{field_name} 不可为空")
    return value


@dataclass(frozen=True, slots=True)
class FrozenBomRow:
    product_id: str
    component_id: str
    component_name: str
    level: int
    qty_per_unit: str
    loss_rate: str
    unit: str
    sequence: str
    is_substitute: bool

    def canonical(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "component_id": self.component_id,
            "component_name": self.component_name,
            "level": self.level,
            "qty_per_unit": self.qty_per_unit,
            "loss_rate": self.loss_rate,
            "unit": self.unit,
            "sequence": self.sequence,
            "is_substitute": self.is_substitute,
        }

    def thaw(self) -> BomRow:
        return BomRow(
            self.product_id, self.component_id, self.component_name, self.level,
            _float_from_decimal_text(self.qty_per_unit, "qty_per_unit"),
            _float_from_decimal_text(self.loss_rate, "loss_rate"), self.unit,
            self.sequence, self.is_substitute,
        )


@dataclass(frozen=True, slots=True)
class FrozenPlan:
    plan_id: str
    product_id: str
    product_name: str
    planned_qty: int
    planned_date: str

    def canonical(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "planned_qty": self.planned_qty,
            "planned_date": self.planned_date,
        }

    def thaw(self) -> ProductionPlan:
        return ProductionPlan(
            self.plan_id, self.product_id, self.product_name,
            self.planned_qty, self.planned_date,
        )


@dataclass(frozen=True, slots=True)
class FrozenMaterial:
    material_id: str
    material_name: str
    category: str
    lifecycle: str
    package: str
    unit_price: str | None

    def canonical(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "material_name": self.material_name,
            "category": self.category,
            "lifecycle": self.lifecycle,
            "package": self.package,
            "unit_price": self.unit_price,
        }

    def thaw(self) -> MaterialRecord:
        return MaterialRecord(
            material_id=self.material_id,
            material_name=self.material_name,
            category=self.category,
            lifecycle=LifecycleStatus(self.lifecycle),
            package=self.package,
            unit_price=None if self.unit_price is None else _float_from_decimal_text(
                self.unit_price, "unit_price"
            ),
        )


@dataclass(frozen=True, slots=True)
class FrozenInputs:
    bom: tuple[FrozenBomRow, ...]
    plans: tuple[FrozenPlan, ...]
    materials: tuple[FrozenMaterial, ...]
    bom_sha256: str
    plans_sha256: str
    materials_sha256: str
    manifest_sha256: str

    def thaw(self) -> tuple[list[BomRow], list[ProductionPlan], list[MaterialRecord]]:
        return (
            [row.thaw() for row in self.bom],
            [plan.thaw() for plan in self.plans],
            [material.thaw() for material in self.materials],
        )


@dataclass(frozen=True, slots=True)
class FrozenUsage:
    material_id: str
    gross_qty: str
    product_ids: tuple[str, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "gross_qty": self.gross_qty,
            "product_ids": list(self.product_ids),
        }


@dataclass(frozen=True, slots=True)
class FrozenFacts:
    usages: tuple[FrozenUsage, ...]
    unknown_lifecycle: tuple[str, ...]
    missing_price: tuple[str, ...]
    not_in_master: tuple[str, ...]
    materials_in_bom: int
    lifecycle_unknown_count: int
    price_missing_count: int
    not_in_master_count: int

    def canonical(self) -> dict[str, object]:
        return {
            "usages": [usage.canonical() for usage in self.usages],
            "unknown_lifecycle": list(self.unknown_lifecycle),
            "missing_price": list(self.missing_price),
            "not_in_master": list(self.not_in_master),
            "data_readiness": {
                "materials_in_bom": self.materials_in_bom,
                "lifecycle_unknown": self.lifecycle_unknown_count,
                "price_missing": self.price_missing_count,
                "not_in_master": self.not_in_master_count,
            },
        }


@dataclass(frozen=True, slots=True)
class SourceManifest:
    scenario: str
    action: str
    evidence_contract: str
    run_mode: str
    fixture_id: str
    revision: str
    source_kind: str
    as_of: str
    facts_contract_version: str
    professional_rule_version: str
    input_schema_versions: tuple[tuple[str, str], ...]
    bom_sha256: str
    plans_sha256: str
    materials_sha256: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class VersionedFactsResult:
    manifest: SourceManifest
    facts: FrozenFacts
    result_schema_version: str
    result_sha256: str


def freeze_inputs(
    bom: Iterable[BomRow],
    plans: Iterable[ProductionPlan],
    materials: Iterable[MaterialRecord],
) -> FrozenInputs:
    _assert_source_schema()
    frozen_bom: list[FrozenBomRow] = []
    for row in bom:
        if type(row) is not BomRow:
            raise TypeError("BOM 输入必须为平台 BomRow")
        if isinstance(row.level, bool) or not isinstance(row.level, int) or row.level < 0:
            raise ValueError("BOM level 必须为非负 int")
        if not isinstance(row.is_substitute, bool):
            raise TypeError("BOM is_substitute 必须为 bool")
        if not isinstance(row.sequence, str):
            raise TypeError("BOM sequence 必须为 str")
        qty_text = _decimal_text(row.qty_per_unit, "qty_per_unit")
        loss_text = _decimal_text(row.loss_rate, "loss_rate")
        _float_from_decimal_text(qty_text, "qty_per_unit")
        _float_from_decimal_text(loss_text, "loss_rate")
        frozen_bom.append(FrozenBomRow(
            _text(row.product_id, "product_id", required=True),
            _text(row.component_id, "component_id", required=True),
            _text(row.component_name, "component_name"),
            row.level,
            qty_text,
            loss_text,
            _text(row.unit, "unit"),
            _text(row.sequence, "sequence"),
            row.is_substitute,
        ))
    frozen_bom.sort(key=lambda item: _json_bytes(item.canonical()))

    frozen_plans: list[FrozenPlan] = []
    for plan in plans:
        if type(plan) is not ProductionPlan:
            raise TypeError("计划输入必须为平台 ProductionPlan")
        if isinstance(plan.planned_qty, bool) or not isinstance(plan.planned_qty, int):
            raise TypeError("planned_qty 必须为 int")
        if plan.planned_qty < 0:
            raise ValueError("planned_qty 不可为负数")
        if not isinstance(plan.planned_date, str):
            raise TypeError("planned_date 必须为 str")
        if date.fromisoformat(plan.planned_date).isoformat() != plan.planned_date:
            raise ValueError("planned_date 必须是规范 YYYY-MM-DD ISO 日期")
        frozen_plans.append(FrozenPlan(
            _text(plan.plan_id, "plan_id", required=True),
            _text(plan.product_id, "product_id", required=True),
            _text(plan.product_name, "product_name"),
            plan.planned_qty,
            _text(plan.planned_date, "planned_date"),
        ))
    plan_ids = [plan.plan_id for plan in frozen_plans]
    if len(plan_ids) != len(set(plan_ids)):
        raise ValueError("ProductionPlan plan_id 重复，不能冻结为唯一输入集")
    frozen_plans.sort(key=lambda item: _json_bytes(item.canonical()))

    frozen_materials: list[FrozenMaterial] = []
    for material in materials:
        if type(material) is not MaterialRecord:
            raise TypeError("物料输入必须为 SC10 MaterialRecord")
        if not isinstance(material.lifecycle, LifecycleStatus):
            raise TypeError("lifecycle 必须为 LifecycleStatus")
        if not isinstance(material.category, str) or not isinstance(material.package, str):
            raise TypeError("category 与 package 必须为 str")
        price = None if material.unit_price is None else _decimal_text(
            material.unit_price, "unit_price"
        )
        if price is not None:
            _float_from_decimal_text(price, "unit_price")
        frozen_materials.append(FrozenMaterial(
            _text(material.material_id, "material_id", required=True),
            _text(material.material_name, "material_name"),
            material.category,
            material.lifecycle.value,
            material.package,
            price,
        ))
    material_ids = [material.material_id for material in frozen_materials]
    if len(material_ids) != len(set(material_ids)):
        raise ValueError("MaterialRecord material_id 重复，不能冻结为唯一主数据集")
    frozen_materials.sort(key=lambda item: _json_bytes(item.canonical()))

    bom_rows = [item.canonical() for item in frozen_bom]
    plan_rows = [item.canonical() for item in frozen_plans]
    material_rows = [item.canonical() for item in frozen_materials]
    bom_hash = _sha256({"schema_id": "sc10-bom-row", "schema_version": 1, "records": bom_rows})
    plans_hash = _sha256({
        "schema_id": "sc10-production-plan", "schema_version": 1, "records": plan_rows,
    })
    materials_hash = _sha256({
        "schema_id": "sc10-material-record", "schema_version": 1, "records": material_rows,
    })
    manifest_body = {
        "scenario": SCENARIO,
        "action": ACTION,
        "evidence_contract": EVIDENCE_CONTRACT,
        "run_mode": RUN_MODE,
        "fixture_id": FIXTURE_ID,
        "revision": FIXTURE_REVISION,
        "source_kind": SOURCE_KIND,
        "as_of": AS_OF,
        "facts_contract_version": FACTS_CONTRACT_VERSION,
        "professional_rule_version": PROFESSIONAL_RULE_VERSION,
        "input_schema_versions": dict(INPUT_SCHEMA_VERSIONS),
        "bom_sha256": bom_hash,
        "plans_sha256": plans_hash,
        "materials_sha256": materials_hash,
    }
    return FrozenInputs(
        tuple(frozen_bom), tuple(frozen_plans), tuple(frozen_materials),
        bom_hash, plans_hash, materials_hash, _sha256(manifest_body),
    )


def freeze_facts(facts: BomReviewFacts) -> FrozenFacts:
    usages = tuple(
        FrozenUsage(
            usage.material_id,
            _decimal_text(usage.gross_qty, "gross_qty"),
            tuple(sorted(set(usage.product_ids))),
        )
        for usage in sorted(facts.usages, key=lambda item: item.material_id)
    )
    return FrozenFacts(
        usages=usages,
        unknown_lifecycle=tuple(sorted(facts.unknown_lifecycle)),
        missing_price=tuple(sorted(facts.missing_price)),
        not_in_master=tuple(sorted(facts.not_in_master)),
        materials_in_bom=len(facts.usages),
        lifecycle_unknown_count=len(facts.unknown_lifecycle),
        price_missing_count=len(facts.missing_price),
        not_in_master_count=len(facts.not_in_master),
    )


def build_result(inputs: FrozenInputs, facts: BomReviewFacts) -> VersionedFactsResult:
    frozen_facts = freeze_facts(facts)
    manifest = SourceManifest(
        SCENARIO, ACTION, EVIDENCE_CONTRACT, RUN_MODE, FIXTURE_ID, FIXTURE_REVISION, SOURCE_KIND,
        AS_OF, FACTS_CONTRACT_VERSION, PROFESSIONAL_RULE_VERSION, INPUT_SCHEMA_VERSIONS,
        inputs.bom_sha256, inputs.plans_sha256, inputs.materials_sha256,
        inputs.manifest_sha256,
    )
    body = {
        "scenario": manifest.scenario,
        "action": manifest.action,
        "evidence_contract": manifest.evidence_contract,
        "run_mode": manifest.run_mode,
        "fixture_id": manifest.fixture_id,
        "revision": manifest.revision,
        "source_kind": manifest.source_kind,
        "as_of": manifest.as_of,
        "facts_contract_version": manifest.facts_contract_version,
        "professional_rule_version": manifest.professional_rule_version,
        "manifest_sha256": manifest.manifest_sha256,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "facts": frozen_facts.canonical(),
    }
    return VersionedFactsResult(manifest, frozen_facts, RESULT_SCHEMA_VERSION, _sha256(body))

~~~

### agent.py 新入口

在现有 agent.py 添加下面函数，保留固定 SCENARIO=SC10、ACTION=bom_review_facts，及 run_review_facts 原函数、默认参数与旧审计结构不变：

~~~python
from .evidence import VersionedFactsResult, build_result, freeze_inputs


def run_versioned_review_facts(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    materials: Iterable[MaterialRecord],
    *,
    evaluator: str,
    audit: AuditLogger,
) -> VersionedFactsResult:
    if not evaluator.strip():
        raise ValueError("evaluator 不可为空：L2 场景须留可归责人")
    if audit is None:
        raise ValueError("版本化事实必须使用真实持久 AuditLogger")

    frozen = freeze_inputs(bom, plans, materials)
    frozen_bom, frozen_plans, frozen_materials = frozen.thaw()
    facts = collect_facts(frozen_bom, frozen_plans, frozen_materials)
    result = build_result(frozen, facts)
    manifest = result.manifest
    audit.record(
        AuditEvent(
            scenario=SCENARIO,
            action=ACTION,
            evaluator=evaluator,
            automation_level="L2",
            decision={
                **facts.data_readiness,
                "shared_materials": sum(1 for usage in facts.usages if usage.is_shared),
                "review_status": "待前置到位",
                "blocked_by": [
                    "external_price_api",
                    "material_attribute_data",
                    "selection_ranking_criteria",
                ],
                "evidence_contract": manifest.evidence_contract,
                "run_mode": manifest.run_mode,
                "fixture_id": manifest.fixture_id,
                "revision": manifest.revision,
                "source_kind": manifest.source_kind,
                "as_of": manifest.as_of,
                "facts_contract_version": manifest.facts_contract_version,
                "professional_rule_version": manifest.professional_rule_version,
                "input_schema_versions": dict(manifest.input_schema_versions),
                "bom_sha256": manifest.bom_sha256,
                "plans_sha256": manifest.plans_sha256,
                "materials_sha256": manifest.materials_sha256,
                "manifest_sha256": manifest.manifest_sha256,
                "result_schema_version": result.result_schema_version,
                "result_sha256": result.result_sha256,
            },
            data_sources={
                "bom": f"sha256:{manifest.bom_sha256}",
                "plans": f"sha256:{manifest.plans_sha256}",
                "materials": f"sha256:{manifest.materials_sha256}",
            },
            content_hash=result.result_sha256,
        )
    )
    return result
~~~

evaluator 缺失或空白、audit 缺参或显式 None 时不能返回任何结果。record/write 失败异常直接传播；在审计持久化成功前不返回 result。固定 evidence_contract/run_mode 在 evidence.py，调用者不可任选版本以伪造合规事件。

### tests/test_agent_audit.py 完整持久化/失败测试

~~~python
import json

import pytest
from zhuopin_platform.audit import AuditLogger

from sc10_bom_review.agent import ACTION, SCENARIO, run_review_facts, run_versioned_review_facts
from sc10_bom_review.models import LifecycleStatus, MaterialRecord
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan


def _inputs():
    bom = [
        BomRow("F01", "M-A", "电阻A", 1, 2.0, 0.0, "PCS", "001", False),
        BomRow("F01", "M-B", "电容B", 1, 1.0, 0.0, "PCS", "002", False),
        BomRow("F02", "M-A", "电阻A", 1, 3.0, 0.0, "PCS", "001", False),
        BomRow("F02", "M-C", "芯片C", 1, 1.0, 0.0, "PCS", "002", False),
    ]
    plans = [
        ProductionPlan("P1", "F01", "成品一", 10, "2026-09-10"),
        ProductionPlan("P2", "F02", "成品二", 20, "2026-09-11"),
    ]
    materials = [
        MaterialRecord("M-A", "电阻A", lifecycle=LifecycleStatus.ACTIVE, unit_price=0.1),
        MaterialRecord("M-B", "电容B", lifecycle=LifecycleStatus.UNKNOWN, unit_price=None),
        MaterialRecord("M-C", "芯片C", lifecycle=LifecycleStatus.NRND, unit_price=None),
    ]
    return bom, plans, materials


def test_versioned_success_is_persisted_and_reopenable(tmp_path):
    bom, plans, materials = _inputs()
    path = tmp_path / "sc10-versioned.jsonl"
    result = run_versioned_review_facts(
        bom, plans, materials, evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(path)
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    decision = event["decision"]
    assert event["scenario"] == SCENARIO
    assert event["action"] == ACTION == "bom_review_facts"
    assert event["evaluator"] == "synthetic-test-operator"
    assert event["automation_level"] == "L2"
    assert decision["evidence_contract"] == "sc10-versioned-facts-v1"
    assert decision["run_mode"] == "synthetic_versioned"
    assert decision["fixture_id"] == "SC10-MOCK-B01"
    assert decision["revision"] == "r1"
    assert decision["source_kind"] == "synthetic"
    assert decision["as_of"] == "not-applicable/synthetic"
    assert decision["facts_contract_version"] == "sc10-bom-review-facts-v1"
    assert decision["professional_rule_version"] == "not_applied"
    assert all(type(value) is str for value in event["data_sources"].values())
    assert decision["bom_sha256"] == result.manifest.bom_sha256
    assert decision["plans_sha256"] == result.manifest.plans_sha256
    assert decision["materials_sha256"] == result.manifest.materials_sha256
    assert decision["manifest_sha256"] == result.manifest.manifest_sha256
    assert decision["result_sha256"] == result.result_sha256
    assert event["content_hash"] == result.result_sha256
    reopened_logger = AuditLogger.jsonl(path)
    chain = reopened_logger.verify_chain()
    assert chain.ok is True
    assert chain.total == 1
    reopened = reopened_logger.query_by(scenario=SCENARIO, action=ACTION)
    assert len(reopened) == 1
    assert reopened[0]["decision"]["result_sha256"] == result.result_sha256
    assert reopened[0]["decision"]["review_status"] == "待前置到位"
    assert reopened[0]["decision"]["blocked_by"] == [
        "external_price_api", "material_attribute_data", "selection_ranking_criteria",
    ]
    assert reopened[0].get("oem_context", "") == ""


def test_missing_audit_never_returns_result():
    bom, plans, materials = _inputs()
    with pytest.raises(ValueError, match="真实持久"):
        run_versioned_review_facts(
            bom, plans, materials, evaluator="synthetic-test-operator", audit=None,
        )


def test_real_jsonl_sink_write_failure_never_returns_result(tmp_path):
    bom, plans, materials = _inputs()
    blocked_path = tmp_path / "audit-is-a-directory.jsonl"
    blocked_path.mkdir()
    real_logger = AuditLogger.jsonl(blocked_path)
    with pytest.raises(OSError):
        run_versioned_review_facts(
            bom, plans, materials, evaluator="synthetic-test-operator", audit=real_logger,
        )


def test_legacy_entry_keeps_legacy_event_shape(tmp_path):
    bom, plans, materials = _inputs()
    path = tmp_path / "legacy.jsonl"
    run_review_facts(
        bom, plans, materials, evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(path)
    )
    event = AuditLogger.jsonl(path).query_by(scenario=SCENARIO, action=ACTION)[0]
    assert "evidence_contract" not in event["decision"]
    assert "run_mode" not in event["decision"]
    assert event.get("oem_context", "") == ""


def test_legacy_audit_none_compatibility_is_preserved():
    bom, plans, materials = _inputs()
    facts = run_review_facts(
        bom, plans, materials, evaluator="synthetic-test-operator", audit=None,
    )
    assert facts.data_readiness == {
        "materials_in_bom": 3,
        "lifecycle_unknown": 1,
        "price_missing": 2,
        "not_in_master": 0,
    }
~~~

此代码段只计划未来的真实 JSONL 成功与受控 sink 写失败覆盖；失败用真实 AuditLogger.jsonl 指向测试目录对象验证，不以替身 sink 代替成功审计证据。

### tests/test_evidence.py fixtures and failure matrix

~~~python
from dataclasses import replace
from decimal import Decimal

import pytest
from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from sc10_bom_review.evidence import (
    BOM_FIELDS, MATERIAL_FIELDS, PLAN_FIELDS, _decimal_text, build_result, freeze_inputs,
)
from sc10_bom_review.models import LifecycleStatus, MaterialRecord
from sc10_bom_review.review import collect_facts


def inputs_b01():
    bom = [
        BomRow("F01", "M-A", "电阻A", 1, 2.0, 0.0, "PCS", "001", False),
        BomRow("F01", "M-B", "电容B", 1, 1.0, 0.0, "PCS", "002", False),
        BomRow("F02", "M-A", "电阻A", 1, 3.0, 0.0, "PCS", "001", False),
        BomRow("F02", "M-C", "芯片C", 1, 1.0, 0.0, "PCS", "002", False),
    ]
    plans = [
        ProductionPlan("P1", "F01", "成品一", 10, "2026-09-10"),
        ProductionPlan("P2", "F02", "成品二", 20, "2026-09-11"),
    ]
    materials = [
        MaterialRecord("M-A", "电阻A", lifecycle=LifecycleStatus.ACTIVE, unit_price=0.1),
        MaterialRecord("M-B", "电容B", lifecycle=LifecycleStatus.UNKNOWN, unit_price=None),
        MaterialRecord("M-C", "芯片C", lifecycle=LifecycleStatus.NRND, unit_price=None),
    ]
    return bom, plans, materials


def test_b01_gross_demand_and_readiness():
    bom, plans, materials = inputs_b01()
    frozen = freeze_inputs(bom, plans, materials)
    facts = collect_facts(*frozen.thaw())
    assert {u.material_id: u.gross_qty for u in facts.usages} == {
        "M-A": 80.0, "M-B": 10.0, "M-C": 20.0,
    }
    assert facts.data_readiness == {
        "materials_in_bom": 3,
        "lifecycle_unknown": 1,
        "price_missing": 2,
        "not_in_master": 0,
    }
    shared = next(u for u in facts.usages if u.material_id == "M-A")
    assert shared.product_ids == ("F01", "F02")
    assert shared.is_shared


def test_canonical_source_field_sets_are_explicit():
    assert BOM_FIELDS == (
        "product_id", "component_id", "component_name", "level", "qty_per_unit",
        "loss_rate", "unit", "sequence", "is_substitute",
    )
    assert PLAN_FIELDS == (
        "plan_id", "product_id", "product_name", "planned_qty", "planned_date",
    )
    assert MATERIAL_FIELDS == (
        "material_id", "material_name", "category", "lifecycle", "package", "unit_price",
    )


def test_decimal_format_is_context_independent_and_keeps_integer_zeroes():
    assert _decimal_text(
        Decimal("1234567890123456789012345678900.1234500"), "golden"
    ) == "1234567890123456789012345678900.12345"
    assert _decimal_text(
        Decimal("1000000000000000000000000000000000000000"), "golden"
    ) == "1000000000000000000000000000000000000000"
    assert _decimal_text(Decimal("-0.000000"), "golden") == "0"


def test_permutation_does_not_change_source_manifest_or_result_hash():
    bom, plans, materials = inputs_b01()
    left = freeze_inputs(bom, plans, materials)
    right = freeze_inputs(list(reversed(bom)), list(reversed(plans)), list(reversed(materials)))
    assert (left.bom_sha256, left.plans_sha256, left.materials_sha256) == (
        right.bom_sha256, right.plans_sha256, right.materials_sha256,
    )
    assert left.manifest_sha256 == right.manifest_sha256
    left_result = build_result(left, collect_facts(*left.thaw()))
    right_result = build_result(right, collect_facts(*right.thaw()))
    assert left_result.result_sha256 == right_result.result_sha256


def test_same_counts_different_material_value_changes_hashes():
    bom, plans, materials = inputs_b01()
    first = freeze_inputs(bom, plans, materials)
    materials[0] = replace(materials[0], unit_price=0.2)
    second = freeze_inputs(bom, plans, materials)
    assert first.materials_sha256 != second.materials_sha256
    assert first.manifest_sha256 != second.manifest_sha256
    first_result = build_result(first, collect_facts(*first.thaw()))
    second_result = build_result(second, collect_facts(*second.thaw()))
    assert first_result.facts.canonical()["data_readiness"] == second_result.facts.canonical()["data_readiness"]
    assert first_result.result_sha256 != second_result.result_sha256


def test_duplicate_bom_line_is_hashed_and_not_deduplicated():
    bom, plans, materials = inputs_b01()
    first = freeze_inputs(bom, plans, materials)
    bom.append(bom[0])
    second = freeze_inputs(bom, plans, materials)
    assert len(second.bom) == len(first.bom) + 1
    assert second.bom_sha256 != first.bom_sha256
    facts = collect_facts(*second.thaw())
    shared = next(u for u in facts.usages if u.material_id == "M-A")
    assert shared.gross_qty == 100.0
    assert shared.product_ids == ("F01", "F02")


def test_frozen_snapshot_is_detached_from_caller_lists():
    bom, plans, materials = inputs_b01()
    frozen = freeze_inputs(bom, plans, materials)
    hashes = (frozen.bom_sha256, frozen.plans_sha256, frozen.materials_sha256)
    bom[0] = replace(bom[0], sequence="999")
    plans[0] = ProductionPlan("P1", "F01", "成品一", 99, "2026-09-10")
    materials[0] = replace(materials[0], unit_price=0.9)
    assert hashes == (frozen.bom_sha256, frozen.plans_sha256, frozen.materials_sha256)
    with pytest.raises((AttributeError, TypeError)):
        frozen.bom[0].sequence = "changed"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0, True])
def test_invalid_bom_numbers_fail_closed(bad):
    bom, plans, materials = inputs_b01()
    with pytest.raises((TypeError, ValueError)):
        invalid_row = replace(bom[0], qty_per_unit=bad)
        freeze_inputs([invalid_row, *bom[1:]], plans, materials)


def test_zero_null_unknown_and_missing_master_are_distinct():
    bom, plans, materials = inputs_b01()
    materials[2] = replace(materials[2], unit_price=0.0)
    materials = [*materials, MaterialRecord(
        "M-D", "零价已知物料", lifecycle=LifecycleStatus.ACTIVE, unit_price=0.0,
    )]
    extra = BomRow("F01", "M-D", "零价已知物料", 1, 0.5, 0.0, "PCS", "003", False)
    facts = collect_facts(*freeze_inputs([*bom, extra], plans, materials).thaw())
    assert {usage.material_id: usage.gross_qty for usage in facts.usages}["M-D"] == 5.0
    assert facts.missing_price == ["M-B"]
    assert facts.unknown_lifecycle == ["M-B"]
    assert facts.not_in_master == []
    assert facts.data_readiness == {
        "materials_in_bom": 4,
        "lifecycle_unknown": 1,
        "price_missing": 1,
        "not_in_master": 0,
    }


def test_missing_master_is_not_conflated_with_unknown_attributes():
    bom, plans, materials = inputs_b01()
    absent = BomRow("F01", "M-Z", "未入库物料", 1, 0.25, 0.0, "PCS", "004", False)
    facts = collect_facts(*freeze_inputs([*bom, absent], plans, materials).thaw())
    assert facts.not_in_master == ["M-Z"]
    assert "M-Z" not in facts.missing_price
    assert "M-Z" not in facts.unknown_lifecycle


def test_bad_lifecycle_and_negative_price_are_rejected():
    bom, plans, materials = inputs_b01()
    invalid_lifecycle = replace(materials[0], lifecycle="ACTIVE")
    with pytest.raises(TypeError, match="LifecycleStatus"):
        freeze_inputs(bom, plans, [invalid_lifecycle, *materials[1:]])
    with pytest.raises(ValueError, match="单价不可为负"):
        replace(materials[0], unit_price=-0.01)


def test_duplicate_plan_or_material_identity_is_rejected():
    bom, plans, materials = inputs_b01()
    with pytest.raises(ValueError, match="plan_id 重复"):
        freeze_inputs(bom, [*plans, plans[0]], materials)
    with pytest.raises(ValueError, match="material_id 重复"):
        freeze_inputs(bom, plans, [*materials, materials[0]])


def test_planned_date_requires_canonical_iso_date():
    bom, plans, materials = inputs_b01()
    invalid = replace(plans[0], planned_date="2026/09/10")
    with pytest.raises(ValueError):
        freeze_inputs(bom, [invalid, *plans[1:]], materials)


@pytest.mark.parametrize(
    "unrepresentable",
    [Decimal("0.12345678901234567890123456789"), Decimal("1e10000")],
)
def test_shared_float_range_or_precision_loss_is_rejected_before_manifest(unrepresentable):
    bom, plans, materials = inputs_b01()
    invalid_row = replace(bom[0], qty_per_unit=unrepresentable)
    with pytest.raises(ValueError, match="float"):
        freeze_inputs([invalid_row, *bom[1:]], plans, materials)
~~~

零价 case 中 M-C 和新增 M-D 均为已知生命周期、零价且不计入 missing_price；M-B 保持 UNKNOWN/None。未入库 M-Z 独立断言只进入 not_in_master。

未来定向命令只从 SC10 子项目工作目录运行，并将 junit、stdout/stderr 留在新的 ignored UUID 证据目录。以下命令只列入计划，本轮未运行：

~~~powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc10ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc10CandidateHead = (& git -C $sc10ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc10CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') {
    throw 'SC10 candidate HEAD differs from the approved starting point'
}
$sc10RunId = [guid]::NewGuid().ToString('N')
$sc10RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc10-versioned-facts-1010' "run-$sc10RunId"
New-Item -ItemType Directory -Path $sc10RunDir -ErrorAction Stop | Out-Null
$sc10ProjectDir = Join-Path $sc10ResolvedRoot '4-数字员工/采购部/SC10-BOM评审与物料库管控'
Push-Location $sc10ProjectDir
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_evidence.py' 'tests/test_review_facts.py' 'tests/test_agent_audit.py' 'tests/test_pending_gates.py' --basetemp (Join-Path $sc10RunDir 'basetemp') --junitxml (Join-Path $sc10RunDir 'junit.xml') 1> (Join-Path $sc10RunDir 'stdout.log') 2> (Join-Path $sc10RunDir 'stderr.log')
    $sc10TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc10RunDir 'exit-code.txt'), [string]$sc10TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc10TestExit -ne 0) {
    throw "SC10 targeted pytest failed with exit code $sc10TestExit; preserve $sc10RunDir"
}
~~~

## Exit Criteria

- 计划与正式 3M.1 依赖审批齐全后，才可进入实现。
- 三源 canonical hashes 与 manifest/result hashes 可确定性复算，冻结输入不可被调用方 mutation 改写。
- fixture_id=SC10-MOCK-B01、revision=r1 得到毛需求 80/10/20、完备度 3/1/2/0；换序稳定、同计数换值变化、重复行保留。
- 真正 JSONL sink 写入后可经新 logger 实例读回并验证链；缺审计或写失败不返回成功。
- legacy 入口保持原样；oem_context 空；三个建议继续 fail-loud；没有真实数据或专业结论。
- 本计划和 mock facts 均不等于业务签认、数据真实性结论或更高交付档位。
