"""FI3 付款申请自动校验 —— **档 1（mock 验证）**，L3 旁路校验清单（乙方案）。

七个子场景（全景规划 §2.1.4 FI3 块，v10 起同批开工）：
  FI3-1 三单匹配状态前置校验（消费 FI2 结果）   → `checks.check_three_way_match`
  FI3-2 收款账户与合同比对                       → `checks.check_account`
  FI3-3 重复付款检测                             → `checks.check_duplicate`
  FI3-4 累计付款超合同/订单拦截                  → `checks.check_contract_cap`
  FI3-5 预付款管控与核销校验                     → `checks.check_prepayment` ＋ `prepay_ageing`
  FI3-6 付款日期自动计算                         → `checks.compute_due_date` ＋ `holiday_calendar`
  FI3-7 综合校验仪表盘                           → `dashboard`

判据 R1–R8 已由唐燕萍 2026-07-10 圈改定稿，逐条实名登记在 `config.CRITERIA`（底座 `criteria_signoff`）。
🔴 **AI 不碰钱**：只出校验结果与拦截建议；付款执行永远人工。
🔴 **停在档 1**：L3→L4 晋级须 Shao Peishen ＋ CFO 会签（`config.PENDING.L4_PROMOTION_COSIGN` 未签认即抛）。
"""
