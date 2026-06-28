"""FI1 供应链自动仓库对账（内部对账 MVP）。

范围（Paul 2026-06-28 定）：SMT 实际投料 vs BOM 理论用量的差异分析与对账。
  · BOM 理论用量：复用平台 ZpConnector（SC8 已验证的 U9C BOM/Query 真实路径）。
  · 投料/产出：U9C 直读（MO `UFIDA.U9.MO.MO.MO` 完工 + 领料）——CommonEntity/Query
    外网当前 404，real 模式 fail-loud，开发期走 mock 夹具（无 CSV 旁路，Paul 选直读）。
  · 差异分类（损耗溢短/来料短缺/管理差异）+ L2 异常门禁 + 平台 audit 全链留痕。
委外库存对账 = 二期（卡 8/15 商务条款，留接口位）；损耗基线趋势模型 = 二期。
"""
