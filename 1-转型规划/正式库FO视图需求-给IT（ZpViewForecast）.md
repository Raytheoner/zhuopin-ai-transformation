# 需求：正式库新增「预测订单」卓品视图 `ZpViewForecast`（外网可取）

> 提报：Paul（运营/供应链 VP）　｜　受理：IT　｜　日期：2026-06-24
> 用途：AI 转型「保供预警看板」需要**客户预测订单（FO）**作为成品生产需求输入，要求 off-LAN（外网无 VPN）可取。
> 一句话：**照现有 `ZpViewPurOrder` 同机制，在正式库再建一个预测订单视图 `ZpViewForecast`，挂到 `/zp/api/` 面即可。** SQL 和字段我们已写好，见下。

---

## 1. 为什么必须建视图（不能走现有接口）

我们已实测正式库（`https://erp.equalitytec.com:4443/U9C`）外网面，确认**预测订单当前外网取不到，且不是网络问题**：

| 取数路径 | 实测结果 |
|---|---|
| `/zp/api/ZpViewPurOrder/Query`（采购单视图，对照组） | ✅ 外网 HTTP 200，真实数据 |
| `/zp/api/ZpViewItemMaster/Query`（物料视图，对照组） | ✅ 外网 HTTP 200，真实数据 |
| `/U9C/webapi/BOM/Query`（BOM） | ✅ 外网 HTTP 200 |
| **预测订单 webapi 标准接口** | ❌ **U9C 接口文档全集（100+ 接口）里没有"查询预测订单"接口** |
| `/U9C/webapi/CommonEntity/Query` 查 FO 实体 | ❌ 外网 404（通道未对外开放）+ 预测订单实体名文档亦无 |

**结论**：`/zp/api/` 这条卓品自建面外网是通的（采购单/物料/BOM 都能取），唯独缺一个**预测订单视图**。只要补上这一个视图，保供看板即可纯外网运行、零 VPN、我方零代码改动（只改一行配置）。

---

## 2. 请 IT 做的事

在**正式库**新增视图 `ZpViewForecast`，并按 `ZpViewPurOrder` 的相同方式暴露到卓品 REST 面：

- 调用方式：`POST https://erp.equalitytec.com:4443/zp/api/ZpViewForecast/Query`，body `{}`（与 ZpViewPurOrder 一致）
- 鉴权：复用现有 OAuth2 token（与 ZpViewPurOrder 同）
- 返回结构：`{"code":200, "msg":"...", "data":[ {行}, ... ]}`（与 ZpViewPurOrder 一致）

---

## 3. 视图取数 SQL（已写好，可直接用）

> 来源：供应链项目已验证的预测订单取数逻辑（三表 join）。`<正式库 Org Id>` 请 IT 用正式库实际组织号替换；`Status` 过滤按贵方口径调整（建议只取已审核单）。

```sql
SELECT
    h.[DocNo]                AS DocNo,              -- 预测订单单号（FO...）
    t.[Customer_Name]        AS Customer_Name,      -- 客户名称
    l.[DocLineNo]            AS DocLineNo,          -- 行号
    l.[ItemInfo_ItemCode]    AS ItemInfo_ItemCode,  -- 料号（成品）
    l.[ItemInfo_ItemName]    AS ItemInfo_ItemName,  -- 品名
    l.[Num]                  AS Num,                -- 数量
    l.[ShipPlanDate]         AS ShipPlanDate,       -- 计划出货日（= 需求日）
    t.[Note]                 AS Note                -- 备注
FROM [dbo].[SM_ForecastOrder]      h
INNER JOIN [dbo].[SM_ForecastOrder_Trl]  t ON h.[ID] = t.[ID]
INNER JOIN [dbo].[SM_ForecastOrderLine]  l ON h.[ID] = l.[ForecastOrder]
WHERE h.[Org] = <正式库 Org Id>
  AND h.[Status] = 2          -- 2 = 已审核（按贵方口径调整）
ORDER BY h.[DocNo], l.[DocLineNo];
```

---

## 4. 返回字段（视图列定义）

| 视图字段 | 源表.列 | 含义 | 必填 |
|---|---|---|---|
| `DocNo` | SM_ForecastOrder.DocNo | 预测订单单号 | ✅ |
| `Customer_Name` | SM_ForecastOrder_Trl.Customer_Name | 客户名称 | |
| `DocLineNo` | SM_ForecastOrderLine.DocLineNo | 行号 | ✅ |
| `ItemInfo_ItemCode` | SM_ForecastOrderLine.ItemInfo_ItemCode | 料号（成品/半成品） | ✅ |
| `ItemInfo_ItemName` | SM_ForecastOrderLine.ItemInfo_ItemName | 品名 | |
| `Num` | SM_ForecastOrderLine.Num | 需求数量 | ✅ |
| `ShipPlanDate` | SM_ForecastOrderLine.ShipPlanDate | 计划出货日（= 我方齐套基准日） | ✅ |
| `Note` | SM_ForecastOrder_Trl.Note | 备注 | |

---

## 5. 验收标准

视图建成后，我方从**外网（无 VPN）**执行：

```
POST https://erp.equalitytec.com:4443/zp/api/ZpViewForecast/Query   body: {}
```

应满足：
1. 返回 `code=200`，`data` 为非空数组；
2. 含当前正式库的**当月预测订单**（如 `FO2026060001` / `FO2026060002` 等 6 月新单），而非历史陈旧单；
3. 每行含 `DocNo / ItemInfo_ItemCode / Num / ShipPlanDate` 四个关键字段非空。

---

## 6. 备注（避免混淆）

- 我们**只要预测订单（FO）**作为生产需求；**销售订单（SO）本项目不需要**，IT 无需为 SO 建视图。
- 此视图针对**正式库**（外网 `erp.equalitytec.com:4443` / 内网 `192.168.6.2:5555`）。供应链验证库（`192.168.100.49/.51`）的旧 FO 服务与本需求无关，请勿复用。
- 视图为**只读查询**，不涉及任何写操作。
