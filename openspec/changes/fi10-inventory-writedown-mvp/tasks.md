> 🔴 **本包未过 design 审**（🟡 `openspec_design_review`）。§1 已勾选项是本泳道在 🟢 范围内实做的骨架；**§2 起一律不得开工**。
> 🔴 **本包是五个财务场景里唯一一个「有一部分被明确判为前置未满足、就地停下」的**：芯片降价超阈值预警**不实现**（`#475`）。

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

## 2. 🔴 design 收口（未全部关闭不得进 §3）

- [ ] 2.1 收口-1（**最要紧，口径归属**）：`SC7` 呆滞口径尚未落地 ⇒ L9「同口径」无源可取。等 SC7 落地，还是 FI10 先定、SC7 后对齐？**属 🟡，须 Shao Peishen 拍。本泳道不代判、不代联络姚祖怡**
- [ ] 2.2 收口-2（**须先于选型**）：「芯片供货 API」与「芯片市场价格 API」是否同一项——**判定前不得开始选型，否则可能选错标的**（`#475`）。属规划文档口径 ⇒ 全景路线图线处置，**本泳道不代判**
- [ ] 2.3 收口-3：三项判据由**财务 ＋ 供应链联席**主笔实名签认（NRV／库龄门限／项目终止口径）。**分开问会得到两套口径，那正是 L9 要避免的** ⚠️ 需唐燕萍确认者 ⇒ 串行闸在途 —— 🔴 **状态勿在此复述**（会过时），现取 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，登记「待闸开后并进下一封」，**不得单起一封信**
- [ ] 2.4 收口-4：🔴 OEM 隔离落地形态（PLM 如何按客户路由、跨库如何抛错、边界画在哪层）。**本场景是五个财务场景里唯一触及 OEM 隔离的，不可套用其余四个"财务数据不隔离"的结论**
- [ ] 2.5 收口-5：**跨五场景** `criteria_signoff` 是否提升进平台底座（rule-of-three 已触发）
- [ ] 2.6 判据持有人 ＋ backup 实名指定（🔴 须跨财务与供应链两侧；呆滞口径持有人按 SC7 记载是姚祖怡，**本泳道不代指派**），登记进前置总表 §一.2（该表**现无 FI10 行**）

## 3. inventory-intake 数据采集（design 审后，先测后实现）

- [ ] 3.1 写测试：真实源通道未核实时 fail-loud
- [ ] 3.2 写测试：在途量 ＝ 已订 − 已收（与 `kit_engine` 口径一致）
- [ ] 3.3 🔴 写测试：OEM 跨库访问抛 `CrossOEMAccessError`（**须实测，不得只写文档**）
- [ ] 3.4 实现采集层，OEM 侧走 `OEMRouter`
- [ ] 3.5 单测全绿

## 4. nrv-writedown-engine 跌价测试引擎（design 审后，先测后实现）

- [ ] 4.1 写测试：`NRV_ESTIMATION_BASIS` 为空时 fail-loud，`nrv` 保持 `None` **而非 0**
- [ ] 4.2 写测试：呆滞口径无源时 fail-loud，不采用任何自拟口径
- [ ] 4.3 写测试：成本 > NRV／成本 ≤ NRV 两支，及边界相等
- [ ] 4.4 实现 NRV vs Cost 引擎（纯函数，口径全从 config 读）＋ `RULE_VERSION` 登记
- [ ] 4.5 单测全绿

## 5. alerting-and-provision 预警 ＋ 计提建议 ＋ what-if（design 审后，先测后实现）

- [ ] 5.1 🔴 **芯片降价超阈值预警：前置未满足，本轮不实现**；并写一条用例锁住"不存在生成该类预警的代码路径"，且**不得以历史采购价推算等替代价格源顶替**
- [ ] 5.2 写测试：库龄／项目终止两类预警在门限为空时各自 fail-loud
- [ ] 5.3 写测试：项目终止后**在途部分**须显式覆盖，不得只看已入库存量
- [ ] 5.4 写测试：`confirmed_by` 为空的计提建议不得进入入账流程
- [ ] 5.5 实现两类可做的预警 ＋ 计提建议表 ＋ what-if
- [ ] 5.6 每次判定/预警/建议写平台 `audit`
- [ ] 5.7 单测全绿

## 6. 收口（不在本包，登记以免遗漏）

- [ ] 6.1 场景 `CLAUDE.md` 六段式（根 `CLAUDE.md` §5 第 6 步）
- [ ] 6.2 🔴 **不新起端口**：注册到统一门户路由 `/finance/fi10` ＋ 预留网关 auth 接入点
- [ ] 6.3 `.51` 部署 ＋ 部署段基本测试 ＋ 回滚 SOP（⏭️ `deploy_51`，泳道无权，且本机 off-LAN）
- [ ] 6.4 芯片降价预警：待 `#475` 前置满足后，另起变更包补做（**不在本包内追加**）
