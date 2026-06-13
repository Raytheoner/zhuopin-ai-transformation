# Tasks — 变更包 B（数据正确性与审计强制化 P1）

> 先写/改测试再实现。每段跑相关测试。全包绿 + 黄金值不漂移后 commit + push。
> 顺序：B5/B2（独立小）→ B6（底座，含黄金值）→ B1（BOM 签名）→ B4（审计接入）→ B3（审批分级）。

## B5 · OEM 隔离违规留痕（`data_isolation_layer/router.py`）
- [ ] 1.1 测试：注入 audit，`resolve(未注册)` 与 `guard(跨库)` 抛错前各写一条 `cross_oem_access_denied`；无 audit 时仅抛错。
- [ ] 1.2 `OEMRouter.__init__` 加 `audit`；resolve/guard 抛 `CrossOEMAccessError` 前写 `AuditEvent`。

## B2 · SRM 承诺交期失败/未答交区分（`srm_connector/connector.py`）
- [ ] 2.1 测试：3 个 PO 中 1 个抛异常、1 个未答交(None)、1 个有交期 → 返回 (confirmed={有交期}, failed=[异常PO])；audit 记 `confirmed_date_query_failed`。
- [ ] 2.2 `get_confirmed_dates` 返回 `(dict, failed_pos)`；异常计入 failed + audit；None 不计失败。更新其测试。

## B6 · kit_engine 在途盲区 + SC5 黄金值
- [ ] 3.1 测试（平台 test_kit_engine）：物料不在库存快照但有在途 → 缺口=need-在途（非 need）；缺快照物料进 missing_snapshot 告警清单。
- [ ] 3.2 `calc_shortage` 缺快照时 `available=在途`，返回 `(shortages, missing_snapshot)`（依 Paul B6 决定）。
- [ ] 3.3 更新 O2/SC5 调用方解包；跑 O2(20)/SC5(41) 全绿。
- [ ] 3.4 SC5 黄金值 `approx(rel=0.01)` → 精确相等（auto_total=35850/review_total=640000/grand_total=675850）。无法精确则**停下报告原因**，不放宽。

## B1 · BOM 拉取静默吞错（`erp_connector/connector.py`）
- [ ] 4.1 测试（test_erp_connector_validation / 新建）：注入假 `_u9c_bom_post` 部分抛错 → 返回 (rows, failed_ids) + audit `bom_partial_failure`；全失败抛 RuntimeError；get_bom 真实空 + real 未 opt-in → RealEndpointNotReadyError。
- [ ] 4.2 `get_bom_for_products` 失败集合 + 返回 `(rows, failed_ids)`；全失败抛错。
- [ ] 4.3 `get_bom()` 回退走 `_fallback_or_failloud`。
- [ ] 4.4 更新调用方：`get_bom` 解包；`sources.load_real_bom` 解包 + 对 failed_ids 告警；4 处测试解包。

## B4 · 审计强制化（`from_env` + SC8 接入）
- [ ] 5.1 测试：`ZpConnector.from_env()`/`XkySrmConnector.from_env()` 无 audit → `UserWarning`；注入则不 warn。
- [ ] 5.2 两个 `from_env`：`audit is None` → `warnings.warn`。
- [ ] 5.3 SC8 `sources.py`：构造连接器注入 `ConnectorAudit`；`loaders.load_forecast_orders_from_api` 加 `audit` 参数 + FO 访问 trace。
- [ ] 5.4 跑平台连接器测试 + SC8 全绿（注意既有无参 from_env 测试现会 warn，用 `pytest.warns` 或 filterwarnings 适配）。

## B3 · 审批授权分级（`pending_queue.py` + SC8 config）
- [ ] 6.1 SC8 `config.py` 加 `VP_APPROVERS` / `KEY_CUSTOMERS`（依 Paul B3-b）。
- [ ] 6.2 测试：重点客户/首次承诺项 required_level=vp；非 VP 确认人 approve → 拒绝(False, pending, audit approval_denied)；VP 确认人 → 放行（需总开关开）。
- [ ] 6.3 入队计算并记录 `required_level`；`approve` 校验确认人级别（依 Paul B3-a 范围）。

## 收尾
- [ ] 7.1 全仓回归全绿；黄金值 auto_total=35850 / review_total=640000 不漂移。
- [ ] 7.2 `openspec validate fix-b-data-integrity-audit --strict`。
- [ ] 7.3 commit（引用 B1–B6 编号）+ push + PR（base = A 分支，stacked）。
