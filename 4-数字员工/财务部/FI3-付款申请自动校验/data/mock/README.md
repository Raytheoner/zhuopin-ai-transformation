# FI3 mock 夹具（档 1）

🔴 **全部为合成数据**：供应商名称、银行账号、合同号、发票号均为占位，不对应任何真实往来单位；金额为整数示意。

六表对应 U9C 侧六个数据面（就绪清单 §一 #1–#5 ＋ FI2 结果）：

| 文件 | 对应 | 备注 |
|---|---|---|
| `payment_requests.csv` | 付款申请单（乙方案旁路导出形态） | `invoices` 列格式 `INV:金额;INV:金额`；`po_nos` 以 `;` 分隔 |
| `supplier_accounts.csv` | U9C 供应商主数据收款账户（含变更历史） | `first_use_confirmed_by` 空＝新账户首用未经财务主管确认 |
| `contracts.csv` | U9C 采购合同（框架／暂估价／账期条款） | 子订单 `parent_contract_no` 指向框架父合同，上限记在父合同 |
| `paid_vouchers.csv` | U9C 已付款凭证（近 12 个月） | |
| `prepayments.csv` | U9C 预付款台账 | |
| `fi2_match_results.csv` | FI2 三单匹配结果（上游 `.51:8094`） | 类别字面沿用 FI2 五类 |

十二张申请刻意覆盖四态与六个子场景的每一条分支（对照见 `tests/test_engine_mock.py`），
**基准日固定 2026-09-17**（引擎 `today` 由调用方传入，测试不依赖机器时钟）。
