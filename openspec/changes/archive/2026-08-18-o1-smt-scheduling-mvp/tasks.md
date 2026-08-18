# o1-smt-scheduling-mvp Tasks

> 🔴 **前置：本清单不得在 Shao Peishen 放行 apply 前开工**（§5 场景固定流程第 3 步）。**2026-08-18 状态：七个决策点已全部拍板（见 `design.md` §拍板记录，Shao Peishen 答「全部默认」），但 apply 尚未获放行**——「放行 apply」一项的默认项是「不答则不 apply」，故本清单仍全部未开工。
> 下列任务即按已拍板结论拟定（D1 场景本地／D2 复制不改签名／D3 记 L1／D4 随表声明／D5 复用底座闸／D6 CSV+inline 混合／D7 原测试迁入+新增边界）。**条目内「若 D3/D4 改选…」一类的分支注记已失效，保留仅为说明当初取舍，apply 时按已拍板结论执行、不得再改判。**

## 1. 场景工程骨架

- [x] 1.1 建 `4-数字员工/运营部/O1-生产排程智能优化/` 目录树：`o1_smt_scheduling/`（含 `__init__.py`）、`tests/`（含 `__init__.py`）
- [x] 1.2 写 `pyproject.toml`，照 O2 同款（name=`o1-smt-scheduling`，依赖 `zhuopin_platform`，`[tool.pytest.ini_options] testpaths=["tests"]`）
- [x] 1.3 写 `tests/conftest.py`，**逐字照抄 O2 同款 worktree 路径引导**（队列 #300；从 `__file__` 向上找 `5-平台底座/zhuopin_platform` 插 `sys.path` 最前）——不得自行改写该片段
- [x] 1.4 验证骨架：在场景目录跑 `python -m pytest --collect-only`，确认 collection 阶段无 `ModuleNotFoundError`（队列 #313 已实证 O2/SC1/SC7 曾因缺此步长期隐式依赖全局 editable 指针）

## 2. 收割引擎（D2：复制＋改 import，签名不变）

- [x] 2.1 复制 `supplychain/src/agents/smt_scheduling.py` → `o1_smt_scheduling/schedule_engine.py`，保持 `schedule_smt()` / `load_smt_lead_time()` 两个签名逐字不变
- [x] 2.2 改 CSV 默认路径常量：由 supplychain 的 `data/mock/` 改指场景内 `fixtures/smt_lead_time.csv`
- [x] 2.3 补 docstring：注明收割来源（`supplychain/src/agents/smt_scheduling.py`，2026-08-18 收割）与「自然日、不跳周末节假日」口径的待复核状态
- [x] 2.4 实现 spec「工时表格式非法」场景：工时天数为空或非整数时**跳过该行**而非静默视为 0（原实现已有 `if product_id and lead_days` 判空，但非整数会抛 `ValueError`——须确认取哪种行为并与 spec 对齐）

## 3. 工时夹具与占位声明（D4(a)）

- [x] 3.1 复制 `supplychain/data/mock/smt_lead_time.csv` → `o1_smt_scheduling/fixtures/smt_lead_time.csv`（46 行真实料号）
- [x] 3.2 在 CSV 头部加显式声明块：「本表 46 行工时值全为占位常数 7，非真实工时，禁止用于任何对外承诺或产能测算」+ 待由运营部 PMC 实名确认替换
- [x] 3.3 🔴 **验证声明块不被读成数据行**——跑 `load_smt_lead_time()` 确认仍返回 46 项（design D7 已预警：原测试 `test_all_products_loaded` 断言 `len == 46`，声明块若被 `csv.DictReader` 吃进去会以看似无关的方式让该断言失败）
- [x] 3.4 `load_smt_lead_time()` 增加返回占位标记的途径（供任务 4.3 透传），不改动既有返回值形状——**若 D4 改选 (b)/(c)，本组任务全部重写**

## 4. 场景入口 agent（D3 默认 L1／D5 复用底座闸）

- [x] 4.1 写 `o1_smt_scheduling/agent.py::run_smt_schedule()`，薄包装，形状照 O2 `run_kit_alert()`（dataclass 返回值 + `audit_logger: AuditLogger | None = None`）
- [x] 4.2 接平台审计：`AuditEvent(scenario="O1", action="smt_schedule", automation_level="L1", ...)`，含产品清单、推算时刻、各输入 `data_sources` 标记——**若 D3 改选 (b)，`automation_level` 改 L2 并加空门禁壳**
- [x] 4.3 返回值携带 `lead_time_is_placeholder` 标记（spec「推算结果须标明其可信边界」）
- [x] 4.4 实现「部分产品无法排产时分项返回」：返回可排产产品的完工日 ＋ 单独列出无法排产的产品及原因，不整批失败、不静默丢弃
- [x] 4.5 接底座档位闸：`real` 模式取生产计划时由 `ZpConnector._fallback_or_failloud` 抛 `RealEndpointNotReadyError`——**场景侧只传递档位与 opt-in 标志，不自建等价判断**（D5）

## 5. 测试（D7）

- [x] 5.1 迁入 supplychain `tests/test_smt_scheduling.py` 全部用例，仅改 import 路径，其余逐字不变（收割保真回归网）。**⚠️ 如实更正：当初写作「8 个」，实为 10 个**（TestLoadSmtLeadTime 4 ＋ TestScheduleSmt 6），已全部迁入
- [x] 5.2 新增边界用例 —— **跨周末不顺延**（spec 场景，原测试只在 docstring 提及、无断言）
- [x] 5.3 新增边界用例 —— 工时表非法行跳过（2.4 对齐后的行为）
- [x] 5.4 新增边界用例 —— 占位标记透传至返回值
- [x] 5.5 新增边界用例 —— `real` 档位且未 opt-in 时 fail-loud，且**不返回任何完工日**
- [x] 5.6 新增边界用例 —— 部分产品无法排产时的分项返回
- [x] 5.7 新增用例 —— 未传 `audit_logger` 时正常返回且不抛异常（单测不依赖 sink）
- [x] 5.8 跑全量 `python -m pytest -v`，确认全绿 —— **32 passed**（10 迁入 ＋ 22 新增；新增数超出当初拟定的 6 条，因 spec 反推出的边界比预估多）

## 6. 回归与零漂移核实

- [x] 6.1 跑 O2 场景全量测试，确认零漂移（本变更不改底座，预期无影响，但须实测而非推断）
- [x] 6.2 跑 `5-平台底座/zhuopin_platform` 全量测试，确认零漂移
- [x] 6.3 `openspec validate o1-smt-scheduling-mvp --strict` 通过
- [x] 6.4 `openspec validate --all --strict` 通过（确认未破坏其余变更包）

## 7. 收口

- [x] 7.1 写场景 `CLAUDE.md`（六段式：定位/决策/底座/红线/时间线/依赖），照 O2 同款结构；**红线段须含「首版是完工日估算器而非优化器」与「工时为占位值」两条**
- [x] 7.2 CLAUDE.md「依赖」段登记晋档 2 的四条解锁条件（U9C MO 外网开放／PMC 确认工时表／自然日口径复核／知识资产持有人点名）
- [x] 7.3 输出《跨场景前置数据与知识库任务总表》§一.2 的 O1 待登记行内容——已随队列 #343 回写落地（**CC 不改规划文档，只输出内容交 Cowork 落档**）
- [x] 7.4 `/opsx:archive o1-smt-scheduling-mvp -y`（完工即归档纪律，不拖到下次 session）
- [x] 7.5 git commit + push；队列回写完工行；收工重跑文档台账
- [x] 7.6 **（apply 期间新增）** `plans` 与 `connector` 互斥守卫 —— 初版实现两者同时传入时会静默丢弃 `plans`，会让审计里「这批工单哪来的」说不清；改为直接 `ValueError` 并补 2 个用例

## 8. 明确不做（首版边界，写在此处以防范围蔓延）

- [x] 8.1 确认交付物**不含**：设备状态接入、人员排班、最优化求解、紧急插单重排、策略模拟、Web 呈现——逐项在场景 CLAUDE.md 中列为「首版排除」
- [x] 8.2 ✅ 已确认**未部署 `.51`**：档 1 无真实数据、无对外呈现，不触发 §5「发布即收口纪律」的部署段；**故本变更亦不起草跟进信**（§5 第 8 步的前置「发布收口完成」未成立）——此项须在收工报告中显式声明，不得静默略过
