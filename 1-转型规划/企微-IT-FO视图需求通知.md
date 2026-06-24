**【需求·IT】正式库新增预测订单视图 ZpViewForecast（外网可取）**

> 提报：Paul（运营/供应链）｜用途：AI 转型「保供预警看板」需要客户预测订单(FO)作为成品生产需求，要求外网无 VPN 可取。

**背景（已实测）**：正式库外网面上，采购单 / 物料 / BOM 视图都能取（`/zp/api/ZpViewPurOrder/Query` 等 HTTP 200），唯独<font color="warning">预测订单没有任何取数接口</font>——U9C 接口文档全集（100+ 接口）无 FO 查询接口，`CommonEntity/Query` 外网 404 且文档无 FO 实体名。所以缺的只是一个 **预测订单视图**。

**请 IT 做的事**：在 **正式库** 新增视图 `ZpViewForecast`，照现有 `ZpViewPurOrder` 同机制挂到 `/zp/api/` 面、复用 OAuth2 token。建好后保供看板即可纯外网运行、零 VPN，我方零代码改动（只改一行配置）。

> 取数 SQL（三表 join：`SM_ForecastOrder` + `_Trl` + `_Line`）、返回字段表、验收标准已写好，可直接抄，见仓库文档：
> `1-转型规划/正式库FO视图需求-给IT（ZpViewForecast）.md`

**关键字段**：DocNo（单号）/ Customer_Name / DocLineNo / ItemInfo_ItemCode（料号）/ ItemInfo_ItemName / Num（数量）/ ShipPlanDate（计划出货日）/ Note。

**验收**：从外网（无 VPN）`POST https://erp.equalitytec.com:4443/zp/api/ZpViewForecast/Query`，body `{}` → 返回 `code=200`，含当月预测订单（如 `FO2026060001` / `FO2026060002`），每行 DocNo / 料号 / 数量 / 计划出货日非空。

---
<font color="comment">注：本项目只要预测订单(FO)，销售订单(SO)不需要，无需为 SO 建视图；此需求针对正式库（erp.equalitytec.com:4443 / 内网 192.168.6.2:5555），请勿复用供应链验证库（192.168.100.49/.51）的旧 FO 服务。</font>