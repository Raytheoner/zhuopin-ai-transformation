> ✅ **2026-09-06 design 审已过**（Shao Peishen，grill 会话 `OP-0906-V` 会话末当场审，答 `1a`）。design 件 ＝ `openspec/changes/fi10-inventory-writedown-mvp/design.md`（整包件，非局部件），需求收敛产出 ＝ `4-数字员工/财务部/FI10-存货跌价智能分析/intent.md`（`status: 已确认`）。
> 🔴 **审过 ≠ 整包可开工**：按 `design.md` **D1**，本轮**只开工 §3（inventory-intake 采集层）**；**§4／§5 待四条判据实名签认后开工**（各节卷首另有阻断横幅）。§6 收口项不变。
> 📌 下方「本包未过 design 审」的历史横幅原文保留（记 2026-09-03 骨架期的状态），**不追改**——删了会丢成因，改了会留下已被推翻的结论。
>
> ~~🔴 **本包未过 design 审**（🟡 `openspec_design_review`）。§1 已勾选项是本泳道在 🟢 范围内实做的骨架；**§2 起一律不得开工**。~~（2026-09-06 已解除）
> 🔴 **本包是五个财务场景里唯一一个「有一部分被明确判为前置未满足、就地停下」的**：芯片降价超阈值预警**不实现**（`#475`）。
> 📌 **2026-09-03 `OP-0903-D3`（A4 段）**：本包已跑 `/opsx:sync`（delta specs 并入 `openspec/specs/`），并把判据签认迁移到平台底座 `criteria_signoff`——见 §1a。
> 🔴 **`sync` 不是 `apply`**：`sync` 写的是主 specs，`apply` 才是实现 tasks 待办。**design 审仍未过，§2 起照旧不得开工。**

## 1. 工程骨架（🟢，本泳道已完成）

- [x] 1.1 建 `4-数字员工/财务部/FI10-存货跌价智能分析/` 与 `pyproject.toml`
- [x] 1.2 `tests/conftest.py` 用 `bootstrap.ensure_paths` 唯一样板 ＋ `strict=True`
- [x] 1.3 `models.py` 定形七个契约：`InventoryAging` / `InTransitPo` / `BomUsage` / `OemProjectPhase` / `WritedownTest` / `WritedownAlert` / `ProvisionAdvice`
- [x] 1.4 纯派生量落地并测：`book_cost`（数量×单价）、`qty_in_transit`（已订−已收，**刻意与 `kit_engine` 在途口径对齐**）
- [x] 1.5 🔴 `OemProjectPhase.oem_customer` 必填、无默认值 ＋ 用例守（OEM 隔离，§7-3）
- [x] 1.6 🔴 `ProvisionAdvice.disclaimer` 必填、无默认值 ＋ 用例守
- [x] 1.7 `WritedownTest.nrv` 默认 `None` **而非 0**（0 会被读成"可变现净值为零"）＋ 用例守
- [x] 1.8 🔴 缺口⑴ `CHIP_PRICE_API=None` ＋ `CHIP_PRICE_API_BLOCKED`（含「是否同一项未定」原话）＋ 用例守
- [x] 1.9 🔴 缺口⑵ `SLOW_MOVING_CRITERIA=None` ＋ `L9_SOURCE_ABSENT`（SC7 口径尚未落地）＋ 用例守
- [x] 1.10 🔴 缺口⑶ 三项未签认判据落 `None` ＋ 用例守
- [x] 1.11 `OEM_ISOLATION_REQUIRED` 红线落成常量 ＋ 用例守
- [x] 1.12 `data/mock/` 四张合成 CSV ＋ README（🔴 OEM 客户名用占位；**不放芯片价格夹具**、**不打呆滞标注**，理由见 README）
- [x] 1.13 `pytest tests/ -q` 全绿（11 passed）
- [x] 1.14 `git check-ignore -v` 实测四类自动生成物均被忽略

## 1a. 判据签认迁移 ＋ specs sync（A4 段 · `OP-0903-D3` / 看护批 `B-0903_50`，2026-09-03 已完成）

> 本节是 `criteria-signoff-platform` 变更包 §4「A4 段：五场景迁移」在本包这一侧的落点。
> 🔴 **迁移未改变任何行为**：未签认判据的值仍恒为空、读取仍抛、仍无 `default` 旁路；变的只是这条纪律**写在哪**（五份手抄 → 底座一份）。

- [x] 1a.1 `config.py` 的裸 `None` 判据常量改为 `zhuopin_platform.criteria_signoff.CriteriaRegistry` 声明（`CRITERIA`），并在模块级调 `CRITERIA.assert_rule_version(RULE_VERSION)`（**导入期**即双向校验版本号与签认状态）
- [x] 1a.2 删 `test_unsigned_criteria_stay_none` ＋ `test_rule_version_marked_unsigned`（`criteria-signoff-platform` tasks 4.2），改为 `test_criteria_registry_declares_exactly_these` ／ `test_criteria_registry_all_unsigned` ／ `test_rule_version_consistent_with_signoff_state`
  🔴 **§1 里对旧用例名的引用是历史记录，不追改**；现行用例名以本行为准
- [x] 1a.3 🔴 **`G-5` 反向依赖落地**（Shao Peishen 2026-09-03 拍板 `G-5 = (a)` 不接 `AuditLogger`）：本包新增 `config.audit_decision(**fields)`，构造写审计的 `decision` 时**恒带当时生效的 `RULE_VERSION`**；用例 `test_audit_decision_carries_rule_version` 拿真的 `AuditEvent` 断言。**依赖方向 ＝ 审计日志指向判据版本，不是判据模块去写日志**；底座侧净变化为零（`grep -r "audit" criteria_signoff/` 可执行代码 **0 命中**，已实测）
- [x] 1a.4 `/opsx:sync` 跑过 —— 本包 delta specs 已并入 `openspec/specs/`（🔴 **`sync` 不是 `apply`**：`apply` ＝ 实现 tasks 待办，本包 §2 起仍不得开工）
- [x] 1a.5 迁移清点：本包 **4** 条判据（含 `G-3` 归入的第四条），迁移前后均**未签认**
- [x] 1a.6 🔴 **`G-3 = (a)` 落地：`SLOW_MOVING_CRITERIA` 已登记进注册表**，`owner`／`question` 逐字取自 `criteria-signoff-platform` tasks 4.1a、未改写；连带删除裸常量 `SLOW_MOVING_CRITERIA = None`。🔴 **登记 ≠ 填值** —— 它仍未签认、读取仍抛
- [x] 1a.7 🔴 **`EE-4` 落地**（Shao Peishen 2026-09-03 裁 (a) **FI10 先定、SC7 后对齐**）：
  - `L9_SOURCE_ABSENT` **原文保留**（记 `#474` 的来龙去脉），另立 `L9_OWNERSHIP_RULED` 记改判——只留结论会丢成因，只留原文会留下已被推翻的结论
  - ⚠️ **「先定」不等于现在就填**：被定下的只是**口径归属**；判据本身仍未签认。该点已写进 `fi10-nrv-writedown-engine` spec 的「登记不等于填值」场景与队列 `#474` 行
  - 原用例 `test_l9_slow_moving_source_absent` 改为 `test_l9_slow_moving_registered_but_unsigned`（两条 `L9_SOURCE_ABSENT` 文本断言保留，`criteria-signoff-platform` tasks 4.1b）
- [x] 1a.8 🔴 **`G-2 = (a)`：`CHIP_PRICE_API` 原样留在本包、未并入注册表**（**前置未满足**，靠上游 `#475` 落地解除）。新增 `test_chip_price_api_is_not_a_criterion` 守住这个"没有"
- [x] 1a.9 校正一处已被 `EE-3` 推翻的表述：骨架期写的「五个财务场景里**唯一**触及 OEM 隔离的一个」不再成立（`FI9` 亦触及）。`config.OEM_ISOLATION_REQUIRED` 与 `fi10-inventory-intake` spec 两处均已改，**本场景自身的隔离要求不变**

## 2. 🔴 design 收口（未全部关闭不得进 §3）

> ✅ **2026-09-06 design 审（`OP-0906-V`）关闭 2.1／2.4／2.6**；**2.2／2.3 仍开**，但**均已确认不阻断 §3 采集层**（D1）：2.2 只阻断芯片降价预警（本轮本就不实现），2.3 只阻断 §4／§5。

- [x] 2.1 收口-1（**最要紧，口径归属**）：`SC7` 呆滞口径尚未落地 ⇒ L9「同口径」无源可取。等 SC7 落地，还是 FI10 先定、SC7 后对齐？**属 🟡，须 Shao Peishen 拍。本泳道不代判、不代联络姚祖怡**
  ⇒ ✅ **已由 `EE-4` 关闭（Shao Peishen 2026-09-03 裁 (a)：FI10 先定、SC7 后对齐）**。🔴 **本勾是 2026-09-06 补的——裁决 09-03 已下，`config.py`／spec／队列 `#474` 三处当日均已落，只有本复选框滞后了 3 天**（`OP-0906-V` M2 实测出的状态失真，同批修正）。⚠️ 「先定」不等于现在就填：`SLOW_MOVING_CRITERIA` 仍未签认、值恒 `None`、读取仍抛
- [ ] 2.2 收口-2（**须先于选型**）：「芯片供货 API」与「芯片市场价格 API」是否同一项——**判定前不得开始选型，否则可能选错标的**（`#475`）。属规划文档口径 ⇒ 全景路线图线处置，**本泳道不代判**
  ⇒ ⏸️ **2026-09-06 design 审确认仍开，去向不变**（design Open Questions B-2）。**不阻断 §3**：它只阻断芯片降价超阈值预警，而该预警本轮本就不实现（5.1／6.4）
- [ ] 2.3 收口-3：三项判据由**财务 ＋ 供应链联席**主笔实名签认（NRV／库龄门限／项目终止口径）。**分开问会得到两套口径，那正是 L9 要避免的** ⚠️ 需唐燕萍确认者 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得单起一封信**
  ⇒ ⏸️ **2026-09-06 design 审确认仍开，但成信路径已定**（D4／D8／D9）：主笔唐燕萍／会签姚祖怡；先索取近 2–3 年计提底稿、再出判例批改表（🔴 **禁用 mock 造案例**）；姚祖怡闸锁则登记「待前信闭环后发」、不预先起草。**不阻断 §3**，只阻断 §4／§5。🔴 判闸状态一律现取，本行不复述
- [x] 2.4 收口-4：🔴 OEM 隔离落地形态（PLM 如何按客户路由、跨库如何抛错、边界画在哪层）。**本场景是五个财务场景里唯一触及 OEM 隔离的，不可套用其余四个"财务数据不隔离"的结论**（🔴 "唯一"二字已被 `EE-3` 推翻，见 §1a.9；隔离要求本身不变）
  ⇒ ✅ **2026-09-06 design 审关闭**：**D5** 明细硬隔离／脱敏聚合走规范 §2.3 通用层（沿用 FI9 ①(c) 分层）；机械形态借 FI9 —— guard 调在**取数入口**、用 `OEMRouter.resolve()` **而非** `guard()`、`AuditEvent.oem_context` 填法、规范 §3.3 射程不卡关系型取数。**D10** 跨 OEM 汇总只吃脱敏聚合量，**刻意不立第二条豁免款**（与 FI9 ②(c) 的分歧成因见 `design.md` D10 对照表）。**D11** 物料归属 ＝ 关联项目客户的**集合**、多值按最严；🔴 「无关联项目」与「归属未判」**两个哨兵不得合并**
- [x] 2.5 收口-5：**跨五场景** `criteria_signoff` 是否提升进平台底座（rule-of-three 已触发）⇒ ✅ **已裁并已落地**（Shao Peishen 2026-09-03 拍板 `EE-1 = (a)` 收进底座）：平台底座 `zhuopin_platform.criteria_signoff` 已建成并合入 master（变更包 `criteria-signoff-platform`）；本包已于 A4 段迁移完毕，见 §1a。**本条不再需要收口。**
- [x] 2.6 判据持有人 ＋ backup 实名指定（🔴 须跨财务与供应链两侧；呆滞口径持有人按 SC7 记载是姚祖怡，**本泳道不代指派**），登记进前置总表 §一.2（该表**现无 FI10 行**）
  ⇒ ✅ **2026-09-06 design 审关闭「实名指定」这一半**（**D4**）：四条判据全走财务＋供应链联席，**主笔唐燕萍／会签姚祖怡**；注册表域级 `owner`「财务侧」不改。📌 唐燕萍 ＝ **财务总监**（名录正本硬事实）⇒ NRV／库龄／项目终止三条她的圈定即权威签认；姚祖怡的会签只针对呆滞口径的 SC7 对齐，非财务口径的上级审批。
  🔴 **本勾覆盖「实名指定」＋「backup」两半；第三半未做，勿据本勾当整条已闭**：⑴ ✅ **backup ＝ 刻意不设**（Shao Peishen 2026-09-07 答 `1a`，理由见 `design.md` **D4-b**）—— D4 定的是主笔＋会签，与「持有人＋backup」不等价（姚祖怡不能代签财务口径）；⑵ 🔴 **「登记进前置总表 §一.2」仍未做** —— 该表现无 FI10 行，补行属规划文档改动（移交单 `status: 待执行`），已登 `design.md` Open Questions B-3 待派发

## 3. inventory-intake 数据采集（design 审后，先测后实现）

> ✅ **2026-09-06 起可开工**（design 审已过 ＋ `design.md` **D1**：本轮**只做本节**）。本节不读任何判据（账龄／在途／BOM／OEM 项目全是取数），是本轮唯一能端到端真测的部分。
> 🔴 **前置风险（D1 的直接前置，须开工方知悉）**：U9C 库存通道与 PLM 取数通道**两条都未核实、且都无主**（同 `#477` 判词第五次适用），已登 `design.md` Open Questions **B-1** 待总线派发。⇒ `real` 模式一律 fail-loud、**不得回退 mock**（3.1 必测）。
> 📌 3.3／3.4 的隔离接法照 **D5**（`OEMRouter.resolve()`，guard 调在取数入口）与 **D11**（物料归属＝客户集合，多值按最严；两个哨兵不得合并）。

> ✅ **2026-09-07 §3 已实做完毕**（`OP-0907-S`，队列 `#474`；先测后实现，实证：先落 `tests/test_intake.py`、跑出 `ImportError` 红，再落 `fi10_inventory_writedown/intake.py`）。产出 ＝ `4-数字员工/财务部/FI10-存货跌价智能分析/fi10_inventory_writedown/intake.py` ＋ `tests/test_intake.py`（新增 31 条）＋ `config.PLM_PROJECT_CHANNEL_NOT_READY`（新增，B-1 第二条通道的 fail-loud 正本文案）＋ `tests/conftest.py` 两个夹具。**场景 47 passed**（骨架 16 ＋ 采集层 31），**平台底座 528 passed / 1 skipped 零回归**，`openspec validate` 通过。
> 🔴 **§4／§5 仍未开工，本次一字未动**；元测试 `test_intake_layer_reads_no_criteria`／`test_intake_produces_no_writedown_or_alert` 钉死采集层不读判据、不旁路产出跌价结果与预警。

- [x] 3.1 写测试：真实源通道未核实时 fail-loud —— 4 条用例：抛 `ChannelNotVerifiedError`；🔴 **在读任何夹具之前就抛**（把 `_read_csv` 换成"被调用即失败"仍须抛，否则「fail-loud」与「先读了 mock 再报错」会被混为一谈）；文案取 `config` 正本非改写；未知模式（拼错 `real`）不兜底成 mock
- [x] 3.2 写测试：在途量 ＝ 已订 − 已收（与 `kit_engine` 口径一致）—— 🔴 **不是重抄一遍公式**：把同一批单据喂给 `kit_engine.calc_shortage`（库存与安全库存置 0），反解它眼里的在途量做交叉核对；两边各写一遍公式则一起写错也照样通过
- [x] 3.3 🔴 写测试：OEM 跨库访问抛 `CrossOEMAccessError`（**须实测**）—— `read_phase_as()` 以某客户身份读另一客户项目即抛 ＋ 平台侧留痕断言（`decision.reason == "跨客户专属库访问"`）；未注册／拼写变体客户名在取数入口 fail-closed ＋ 留痕
- [x] 3.4 实现采集层，OEM 侧走 `OEMRouter` —— `D5-1` guard 只调在 `collect()` 取数入口一处；`D5-2` 归属校验用 `resolve()`；⚠️ `read_phase_as()`／`isolated_view()` **用 `guard()`，与 `D5-2` 不矛盾**：那里的第二根轴是真的（**视图属主 ≠ 数据属主**），已写进模块 docstring。`D11` 三态 ＋ 两个哨兵不合并 ＋ 多值按最严（含「一个料同时挂已判与未判项目 ⇒ 整体算未判」）；`D5-3` `audit_oem_context()` 字典序去重逗号连接，空集填通用料哨兵而非空串
- [x] 3.5 单测全绿 —— 47 passed；另做**一次性变异实测**（同 FI9 D2.4 的两层做法之第一层，证明守卫不是碰巧通过）：拆掉跨库 guard／合并两个哨兵／real 静默回退 mock／在途量算成已订量／归属未判静默放行，**五处变异逐一被用例逮住**（1/2/3/2/3 failed），脚本用完即弃、不入库
- [x] 3.6 🆕 **apply 期一处判断，须知悉**：新增 `intake.MOCK_OEM_REGISTRY`（三个占位客户）。成因 ＝ 两条硬要求在 mock 模式下相撞 —— spec 场景「夹具不得含真实客户名」要求占位名，而 `D5` 要求归属校验必过 `OEMRouter.resolve()`，占位名在平台 `REGISTERED_OEMS` 里必然未注册、一 resolve 就被拒。**另两条路都更坏**：把占位名塞进平台注册表 ＝ 在生产注册表里凭空多出两个"客户"；mock 模式绕开 router ＝ `D5`／`3.3` 在唯一能真跑的模式里失去覆盖。🔴 **它不是口径**（不是待签认的业务口径，是夹具的注册形态），故不进注册表；用例守「与平台注册表零交集」＋「real 模式的 router 只用平台注册表」

## 4. nrv-writedown-engine 跌价测试引擎（design 审后，先测后实现）

> 🔴 **本节仍不得开工（2026-09-06 design 审 D1）**：design 审已过 ≠ 本节可开工。四条判据全未签认时，本节每条读值路径都抛，「实现完」等于只有 fail-loud 分支能测；且判据回来若与假设形状不符（如库龄门限要分物料类别），本节须返工。
> **解除条件** ＝ `tasks 2.3` 关闭（四条判据经主笔唐燕萍签认、呆滞口径另经姚祖怡会签）。

- [ ] 4.0 🆕 **新增第 5 条 `Criterion`：`SLOW_MOVING_ALLOCATION_BASIS`（共用料跌价额在多个 OEM 项目间的分摊口径）** —— 2026-09-06 design 审 **D11** 点破：「多值按最严」只解决数据可见性，**不解决分摊**。🔴 **登记 ≠ 填值**：新增即未签认、值恒 `None`、读取即抛，`RULE_VERSION` 保持 `unsigned` 标记。口径点 ID ＝ `FI10-G-05`（回件后与 `Criterion.key` 同名对齐），随 `tasks 2.3` 同批问主笔唐燕萍。⚠️ 本条**不在 grill 会话内做**（`OP-0906-V` 明令不改 `config.py`）
- [ ] 4.1 写测试：`NRV_ESTIMATION_BASIS` 为空时 fail-loud，`nrv` 保持 `None` **而非 0**
- [ ] 4.2 写测试：呆滞口径无源时 fail-loud，不采用任何自拟口径
- [ ] 4.3 写测试：成本 > NRV／成本 ≤ NRV 两支，及边界相等
- [ ] 4.4 实现 NRV vs Cost 引擎（纯函数，口径全从 config 读）＋ `RULE_VERSION` 登记
- [ ] 4.5 单测全绿

## 5. alerting-and-provision 预警 ＋ 计提建议 ＋ what-if（design 审后，先测后实现）

> 🔴 **本节仍不得开工（2026-09-06 design 审 D1）**，解除条件同 §4（`tasks 2.3` 关闭）。
> 📌 开工时另有三条已定形态：**D2** what-if **本轮不实现、推晋档 2**（处置形态同 5.1 芯片降价预警，不新造第二种「留而不做」写法）；**D6** 计提建议确认 ＝ **双签**（财务侧＋供应链侧各一名，全部计提行适用、**无金额分档**）；**D13** 双签用**角色制**，`confirmed_by` **不得写自然人姓名**（具体岗位待 `FI10-G-06` 回件）。
> **D7** 本轮输出 ＝ 结构化数据 ＋ 门户页，**不做 Excel 导出**（列的排布属专员使用习惯，待判例包回件后按真实底稿格式补）。

- [ ] 5.1 🔴 **芯片降价超阈值预警：前置未满足，本轮不实现**；并写一条用例锁住"不存在生成该类预警的代码路径"，且**不得以历史采购价推算等替代价格源顶替**
- [ ] 5.2 写测试：库龄／项目终止两类预警在门限为空时各自 fail-loud
- [ ] 5.3 写测试：项目终止后**在途部分**须显式覆盖，不得只看已入库存量
- [ ] 5.4 写测试：`confirmed_by` 为空的计提建议不得进入入账流程
- [ ] 5.5 实现两类可做的预警 ＋ 计提建议表（🔴 **what-if 本轮不实现，另包补** —— 2026-09-06 design 审 **D2**：what-if 叠在基线测算之上，而基线依赖 `NRV_ESTIMATION_BASIS`，未签认前无处可叠。spec 要求保留、不删）
- [ ] 5.5a 🔴 写一条用例锁住「本轮不存在 what-if 代码路径」（**处置形态与 5.1 一致**，D2）
- [ ] 5.6 每次判定/预警/建议写平台 `audit`
- [ ] 5.7 单测全绿

## 6. 收口（不在本包，登记以免遗漏）

- [ ] 6.1 场景 `CLAUDE.md` 六段式（根 `CLAUDE.md` §5 第 6 步）
- [ ] 6.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi10` ＋ 预留网关 auth 接入点
- [ ] 6.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
- [ ] 6.4 芯片降价预警：待 `#475` 前置满足后，另起变更包补做（**不在本包内追加**）
- [ ] 6.5 🆕 what-if 模拟：待四条判据签认、基线测算可运行后，另起变更包补做（**不在本包内追加**）——2026-09-06 design 审 **D2**
- [ ] 6.6 🆕 Excel 导出：待判例包回件、拿到真实计提底稿格式后补（**不先猜列再改**）——2026-09-06 design 审 **D7**
