## Purpose

把生产计划与 BOM 展开成物料级用量事实，与公司物料主数据对齐，产出一张**数据完备度体检表**，
并把「BOM 评审建议、物料优先选用级别建议、优先选用与淘汰建议」三项依赖外部数据与采购口径的
能力挡在前置闸之后。本能力只回答「物料库和 BOM 里有什么、还差什么数据」，不回答「该选哪个」。

## MODIFIED Requirements

### Requirement: BOM 展开复用平台底座
系统 SHALL 通过平台底座的 BOM 展开能力计算物料毛需求，MUST NOT 自建第二份展开实现。
系统 SHALL 逐个成品单独展开后再合并，以保留「某物料的需求来自哪些成品」这一底座合计口径
丢弃的信息。

#### Scenario: 毛需求与底座一致
- **WHEN** 给定 BOM 与生产计划
- **THEN** 各物料毛需求等于按底座展开口径逐计划累加的结果

#### Scenario: 跨机型共用料被识别
- **WHEN** 某物料同时出现在两个成品的 BOM 中
- **THEN** 该物料的用量记录列出全部相关成品，并被标记为共用料

#### Scenario: 共用只陈述事实
- **WHEN** 系统标记某物料为共用料
- **THEN** 系统 MUST NOT 因此给出任何选用优先级结论

### Requirement: 物料主数据对齐与缺省语义
系统 SHALL 把展开结果与物料主数据对齐。生命周期属性未知时 SHALL 取「未知」，
MUST NOT 缺省为任何具体生命周期状态；单价缺失时 SHALL 以「无值」表示，MUST NOT 以 0 表示。

#### Scenario: 生命周期缺省为未知
- **WHEN** 主数据未提供某物料的生命周期属性
- **THEN** 该物料的生命周期为「未知」，且计入生命周期未知计数

#### Scenario: 无价与零价可区分
- **WHEN** 某物料在价格库中无记录
- **THEN** 其单价为无值而非 0，且负单价 MUST 被拒绝

#### Scenario: BOM 中的物料不在主数据里
- **WHEN** 某物料出现在 BOM 中但主数据中没有它
- **THEN** 系统将其单列进「主数据缺失」，MUST NOT 静默丢弃，且不重复计入其他缺口计数

### Requirement: 数据完备度体检
系统 SHALL 产出一张体检表，包含 BOM 内物料总数、生命周期未知数、无价数与主数据缺失数，
用以回答「离能做评审还差多少数据」。

#### Scenario: 体检表如实计数
- **WHEN** BOM 含 3 个物料，其中 1 个生命周期未知、2 个无价
- **THEN** 体检表相应计数分别为 3、1、2

### Requirement: 生命周期属性不承载优先级
生命周期属性的定义 MUST NOT 使其成员之间可比较大小。任何依赖成员定义顺序进行排序的行为
均视为违规。

#### Scenario: 成员不可比较
- **WHEN** 比较两个生命周期属性成员的大小或对其排序
- **THEN** 操作失败，而不是按字母序或定义序静默给出结果

### Requirement: 建议层前置闸
在「外部行情 API 选型与接入」「物料属性数据整备」「物料优先选用级别口径」三项前置到位前，
系统 MUST NOT 提供三项建议能力的任何默认实现。调用时系统 SHALL 失败，且错误信息
MUST 指明卡在哪一项前置、其 Owner、前置类型与判据源。

#### Scenario: 建议能力被调用
- **WHEN** 调用方请求 BOM 评审建议、选用级别建议或淘汰建议中的任意一项
- **THEN** 系统抛出前置未到位错误，并点名对应前置

#### Scenario: 外部行情源占位实现
- **WHEN** 调用方通过尚未选型的外部行情源取数
- **THEN** 系统抛出前置未到位错误，指明选型尚未完成

#### Scenario: 前置登记区分数据型与知识型
- **WHEN** 查看前置登记
- **THEN** 每项前置标明其类型，使按 6 周／8 周倒排启动日时不致混算

#### Scenario: 窗口未到与已逾期可区分
- **WHEN** 查看数据型两项前置的状态
- **THEN** 状态明确写出「窗口未到、非逾期」，而不是笼统的「未完成」

### Requirement: L2 留痕与隔离边界
每次事实层计算 SHALL 写入平台审计，记录场景、动作、可归责人、自动化等级 L2 与体检结果。
可归责人为空时系统 MUST 拒绝执行。采购物料数据不适用 OEM 隔离，系统 MUST NOT 对其施加
OEM 路由。

#### Scenario: 缺可归责人
- **WHEN** 调用方未提供可归责人
- **THEN** 系统拒绝执行并说明 L2 场景须留可归责人

#### Scenario: 审计不带 OEM 上下文
- **WHEN** 系统写入一条事实层审计记录
- **THEN** 该记录的 OEM 上下文为空，体现「刻意不施加隔离」而非遗漏

## ADDED Requirements

### Requirement: 版本化合成事实封套
首项SC10-MOCK-B01/r1 SHALL 使用冻结BOM/plans/materials值与显式schema/facts-contract；分别生成三源hash，
再生成绑定输入身份及三源hash的manifest hash和绑定完整事实的result hash。旧未版本化入口保持兼容，
无manifest的旧结果MUST NOT 被计作3M验收。计算MUST复用collect_facts及平台展开，不产专业建议。

#### Scenario: 两成品三物料事实对照
- **WHEN** 合成F01=10/F02=20，M-A分别用2/3，M-B仅F01用1，M-C仅F02用1
- **THEN** 毛需求80/10/20，M-A共用且两产品来源可追溯；给定首项主数据完备度3/1/2/0，不推导BOM合格或选用优先级

#### Scenario: 冻结后调用方改变原对象
- **WHEN** 调用方在封套建立后修改原输入
- **THEN** 本次计算/证据只依冻结值，不重新读取可变原对象

### Requirement: Canonical hash和缺数证据
规范化SHALL使用UTF-8 canonical JSON（ensure_ascii=False、sort_keys=True、separators逗号/冒号、allow_nan=False）。
有限数按Decimal(str(value))无指数文本，去小数末零但保留整数位，负零归0；None为null、enum取value。
逐源行按完整canonical JSON字节排序，重复BOM行MUST保留；计划日期不得冒充as-of。

#### Scenario: 同计数不同内容
- **WHEN** 物料值或BOM用量改变但四项完备度计数不变
- **THEN** 相应输入/manifest/result hash改变，不能只以计数证明版本

#### Scenario: 换序与重复BOM
- **WHEN** 内容仅换排列或含重复BOM行
- **THEN** 换序hash稳定；重复行保留其重复次数和毛需求，不去重

#### Scenario: 非法数与缺数
- **WHEN** 输入含NaN/Inf或None、0、UNKNOWN、缺主数据
- **THEN** 非有限数拒绝；四种缺数/值语义保持可区分，不自动判断零价有效或淘汰

### Requirement: 版本化事实审计有效性
新run_versioned_review_facts SHALL 非空evaluator和可写audit，事件SHALL含
evidence_contract=sc10-versioned-facts-v1、run_mode=synthetic_versioned及输入/manifest/result完整hash链。
audit缺失或持久化失败MUST传播失败；摘要/引用不带原BOM/物料行，ordinary采购oem_context保持空。

#### Scenario: 真实合成JSONL读回
- **WHEN** 版本化合成事实run完成
- **THEN** 可从实际JSONL读回匹配contract/mode/hash链事件，仅构造AuditEvent/no-op sink不算成功

#### Scenario: Legacy事件与专业规则
- **WHEN** 查询缺contract/hash链旧事件或请求任一专业suggest
- **THEN** 旧事件不能算3M验收；专业suggest仍按原前置fail-loud，规则未应用显式not_applied

