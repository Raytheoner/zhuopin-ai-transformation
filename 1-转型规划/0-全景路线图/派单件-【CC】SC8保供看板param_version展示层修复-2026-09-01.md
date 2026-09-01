---
title: "派单件 · 【CC】SC8 保供看板 param_version 展示层修复"
created: 2026-09-01
编号: OP-0901-F
执行方: Claude Code Desktop（建造车间）
派出线: Cowork 业务总线
来源: Cowork 业务总线 OP-0901-E（其派出线 = 环境保障线 OP-0901-D）
承接队列行: 跨桌任务队列-业务场景 §一 #445
status: 待执行
---

# 派单件 ·【CC】SC8 保供看板 `param_version` 展示层修复（队列 §一 #445）

> 🔴 **引用版**：本件只给路径与判据指针，**不复制队列行与代码正文**。所有实测数字标注取值时刻，**开工须自行复核**。

---

## 开场词（复制即用）

```
[OP-0901-F]【CC】SC8看板param_version
【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op0901f-sc8-445-param-version`）｜ worktree：☑（sc8-445，新 worktree，收工自删）｜ 工作区：触碰 `.51` 已部署保供看板 8091 —— 须 `sync-to-server.ps1` 推送 ＋ 重启对应计划任务 ＋ 冒烟三件套（`/api/ping`·关键页 200·一次全量重算）＋ 回滚 SOP 在位；🔴 推送范围仅限 `C:\baoguan`，不得触碰 `C:\fi2` ｜ session：新开 ｜ 派出线：Cowork 业务总线
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]0901F-SC8看板param_version。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① `1-转型规划/0-全景路线图/派单件-【CC】SC8保供看板param_version展示层修复-2026-09-01.md` → ② CLAUDE.md §5／§7 恢复上下文，按派单件执行。本件为 A 类（口径已定、判据已写死），无需再问澄清，直接开工。
```

---

## 一、这是什么缺陷（一分钟）

保供看板构造快照时，`param_version` 取的是**模块级常量**而非**按开关求值的函数**，于是 `SC8_KIT_DATE_RULE1` 翻到 `on` 之后，**算法确实换了、标签没换**。

- 缺陷点：`sc8/baoguan_service.py:212`（写 `config.PARAM_VERSION`，恒为 `sc8-params-v1`）
- 正确实现参照：`sc8/config.py:266` `active_param_version()`（按 `kit_date_rule1_enabled()` 追加 `+rule1` 后缀）
- 对客链路的正确用法参照：`sc8/config.py:280` `default_params()`

🔑 **为什么必须修**：`active_param_version()` 自己的 docstring 已把后果写死——同一个 `sc8-params-v1` 会对应两套不同的齐料日算法，**审计记录再也无法还原当时是按哪一支算的**。这是可追溯性缺口，IATF 语境下站不住。

**已排查范围（不是全链路失真，别扩大）**：`forecast.py`／`commitment.py`／`pipeline.py` 均经 `default_params()` 取值，**对客承诺主链路不受影响**；受影响面**仅限**保供看板自身的快照／页面／JSON 展示字段（`baoguan.py` 多处渲染点、`/api/baoguan` 响应体）。

**现网状态（`OP-0831-L` 2026-08-31 15:32 实测，开工请自行复核）**：`.51` 上 `SC8_KIT_DATE_RULE1=on`，颜色分布已按规则1 正确变化，但 `/api/baoguan` 与页面显示的 `param_version` 仍无 `+rule1` 后缀。

## 二、做什么

1. **修**：`baoguan_service.py:212` 改调 `config.active_param_version()`，或直接改用已含正确取值的 `ForecastParams.param_version`。**二选一由你评估后定**，在收工报告里写一句为什么选它。
2. **反例单测（硬要求）**：翻开关前后 `param_version` 必须出现／消失 `+rule1` 后缀——**关掉修复即失败**的退化守卫，不是只测 happy path。
3. **openspec 门槛自评**：按 CLAUDE.md §5 三条门槛（改跨场景口径／涉鉴权／改对外语义）逐条对照并写一句结论。立行方初判**很可能不命中、不必走 openspec**，🔴 **但复核责任在你**，不得直接引用这句了事。

## 三、验收（发布四关，缺一不算收口）

| 关 | 判据 |
|---|---|
| ① 功能 | 全量测试绿＋零回归＋黄金基准不漂移；反例单测已锁死；openspec 门槛结论已写 |
| ② 部署 | `.51` 部署（SC8 服务）＋冒烟：`/api/ping`、保供看板页 200、一次全量重算 |
| ③ 真机复验 | 🔴 **`.51` 当前即 ON 态，可直接验**：`GET /api/baoguan` 与页面 `param_version` **须显示 `sc8-params-v1+rule1`**。**无需翻开关**——见 §四 红线 ⑵ |
| ④ 留痕 | 队列 §一 #445 回写（✅ 写在状态列开头）＋ §二 待 commit 批次登记 |

⚠️ **若开工时 off-LAN**：第 ② ③ 关**留步并标 LAN 留步**，队列行写明「代码已合入、部署与真机复验待回内网」，**不得跳过后直接销号**。

## 四、红线（本件专有，除 CLAUDE.md §5／§7 通则外）

1. 🔴 **部署范围仅限 SC8（`.51` 的 `C:\baoguan`）**，**不得触碰 `C:\fi2`**——FI2 侧有留步待批的重摄取代码（§一 #418 ⑸②），且 `Fi2TaxExportDailyScan` 已被人为停用、**恢复权在 Shao Peishen**。任何把 FI2 一并带上生产的「顺手同步」都踩本项目已实证过的那个坑（#418 ⑻／⒀：整包同步会把别人留步的改动带上去，且不出声）。
2. 🔴 **不得翻任何环境开关**。`SC8_KIT_DATE_RULE1` 现为 `on`，本件是**让标签跟上算法**，不是改算法。翻开关属口径变更、须另走签认。
3. 🔴 **不修改／停用／删除任何计划任务**。
4. **不新起端口**——本件不新增对外入口，如涉路由一律挂统一门户 `/procurement/sc8` 既有路径下。
5. **不改对客承诺主链路**（`forecast.py`／`commitment.py`／`pipeline.py`）。若修复过程中发现它们也有问题：**登记新行，不就地改**。

## 五、触碰区与并行

**本件触碰区**：`sc8/baoguan_service.py`（唯一改动点）＋其单测。

🔴 **软序（触碰区重叠，不得与本件同时在办）**：
- §一 `#334`（`[S:partial]`，物料维度缺料视图，触 `baoguan_service.py` 的 `Snapshot.materials`／`materials_meta`）——现为**待业务总线定级派发**，未在办。
- §一 `#344`（`[S:partial]`，齐料日期口径改判，触 `baoguan_service.py`／`models.py`）——现为**待排期派单**，且硬前置是姚祖怡签认，未在办。

⇒ **开工第一件事仍须自行 grep 两份队列真身＋归档件复核这两行是否已被人认领**（本件落档时刻为 2026-09-01 13:38 本地，之后的变化本件不知道）。**有重叠不得抢领，报总线裁决。**

**可并行**：与 §一 `#379`（年度节假日提醒首触发，Shao Peishen 本人执行、载体在 aibot 服务）**零重叠，可完全并行**。

## 六、收工段

1. 队列 §一 `#445` 回写：状态列**开头**写 ✅（四关全过）或 🟡（任一子项未完成，含 LAN 留步）。
2. 登记 §二「待 commit 批次」——**文件清单写完整路径，不用「同上」**。
3. 🔴 **commit message 整条用一对反引号包起来，内部不得再出现反引号**（`工具-落库sweep.py::_extract_commit_message` 取第一段反引号内容，写成裸文本会让 commit 主题只剩碎片）。建议：

   `fix(sc8): 保供看板 param_version 改用 active_param_version 使其跟随 SC8_KIT_DATE_RULE1 开关，补退化守卫单测（#445，OP-0901-F）`

4. commit + push + 收工重跑台账。
5. **零孤儿脏文件自检**——工作区不得留下不属于任何待处理 §二 批次的脏文件（`#416 ⑶` 一旦命中，下一封专员回件到达时机器人 release 被拒、**队列锁死 30 分钟**）。
