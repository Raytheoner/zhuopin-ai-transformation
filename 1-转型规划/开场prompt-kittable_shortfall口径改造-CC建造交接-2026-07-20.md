---
title: "开场prompt-kittable_shortfall口径改造-CC建造交接-2026-07-20"
created: 2026-07-20
执行方: CC 采购落地（Claude Code Desktop，写代码+commit+push）
来源: 跨桌任务队列 #63（源头 #33/#40，姚祖怡 2026-07-16 企微口径确认）
status: 待执行
---

# `kittable_shortfall` 口径改造 · CC 交接（2026-07-20）

【设置】分支：master ｜ worktree：☑

## 开场词（复制即用）

```
读 1-转型规划/0-全景路线图/跨桌任务队列.md #63 ＋ 本文件 恢复上下文，按【目标实现】改造 sc8/baoguan.py::_kittable_qty 的 shortfall 计算口径，TDD 先写测试再改实现，全量回归零漂移后 commit+push+队列#63销行。
```

## 背景一分钟

C-1/C-2（主料替代料等价合并 + 部分齐套显示）已于 2026-07-15 apply 归档上线（`openspec/changes/archive/2026-07-15-sc8-baoguan-substitute-partial-kit/`）。其中"可齐套 X / 总需求"卡片有个"还差 N 件"提示（`kittable_shortfall`），实现时口径未经专员正式确认，design.md 当时留了 Open Question #3，**推荐**"凑够下一整套还差多少"，但注明需姚祖怡拍板。

姚祖怡 2026-07-16 企微回复（`7-外部文档/采购部/采购部-YaoZuYi-回复-2026-07-16-文本反馈-1b745aed1383667554060ee7db5e5eca.md`）原话：**"凑够客户下的总单量还差多少"即可** —— 与现状实现口径**相反**，两者数值差异大（总单量口径通常大很多）。业务口径已回灌 `1-转型规划/保供看板v2-口径定稿.md` §2 C-2·②+§5 裁决 5、openspec design.md "2026-07-20 补充"段（IATF 可追溯记录均已落位，本次不用再找 Paul/姚祖怡确认，直接按下方口径实现即可）。

## 现状实现（要改的地方）

`4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan.py::_kittable_qty`（约 208-240 行）：

```python
for row in direct:
    ...
    possible = int(avail // row.qty_per_unit)
    if best_qty is None or possible < best_qty:
        best_qty = possible
        best_material = row.component_id
        needed_for_next = (possible + 1) * row.qty_per_unit      # ← 凑下一整套
        best_shortfall = max(int(round(needed_for_next - avail)), 0)
return best_qty, best_material, best_shortfall
```

## 目标实现

**只改 shortfall 一处计算，`best_qty`/`best_material`（可齐套套数 + 瓶颈子件）的判定逻辑不变**——瓶颈子件仍是"全部直接子件里 `floor(avail/qty_per_unit)` 最小的那个"，这个定义没有争议，姚祖怡只是对"还差多少件"的分母有意见。

把 `needed_for_next = (possible + 1) * row.qty_per_unit` 改为**该瓶颈子件为满足整张订单（`so.qty` 套）所需的总量**：

```python
needed_for_order = so.qty * row.qty_per_unit
best_shortfall = max(int(round(needed_for_order - avail)), 0)
```

**边界情况**（务必补测试覆盖）：
- 若该瓶颈子件现货已够撑满整张订单（即 `best_qty >= so.qty`），`needed_for_order - avail` 应 ≤ 0 → `best_shortfall = 0`（不会出现负数展示）。
- `so.qty` 的类型/精度按 `SalesOrder.qty` 现有定义处理（先读一下 `shared_tools/models.py` 或 sc8 内 `SalesOrder` 定义确认是 int 还是 float，避免round出偏差）。
- 保持"数据异常时返回 `(None, None, None)`"的既有 fail-loud 分支不动（`row.qty_per_unit <= 0` 那段）。

## 连带核对（可能不用改，但要看一眼）

- `sc8/baoguan.py::row_to_dict`（`"ksf": r.kittable_shortfall`）与 `_HTML_JS` 卡片文案——字段语义变了，若前端有"还差 N 件"附近的固定说明文字（如 tooltip 里写死"凑够下一套"字样）需同步改文案，避免代码口径已改、页面文字还在说旧口径。
- `BaoguanRow.kittable_shortfall` 字段的 docstring 注释（`# 该瓶颈子件凑够下一整套还差多少件`，约第 77 行）要同步改成新口径描述。

## 测试

- `tests/test_baoguan_partial_kit.py`：现有断言里凡是按"凑下一整套"算 shortfall 的用例，改成按"凑总单量"重算期望值；新增至少一个"瓶颈子件现货已够撑满整单 → shortfall=0"的边界用例。
- 全量回归：SC8 全量 + 平台底座 + SC1 + SC7（黄金基准精确不漂移）+ O2，跑到零回归再 push（参照本场景 CLAUDE.md 历次记录的惯例命令）。

## 收工清单

1. 代码改造 + 测试更新，全量回归零漂移。
2. `openspec/changes/archive/2026-07-15-sc8-baoguan-substitute-partial-kit/design.md`（"2026-07-20 补充"段末尾）补一句"已实现"回填（不新开变更包，直接在归档件里追记即可，参照本文件同一份 design.md 已有的追记先例）。
3. `4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md` 状态时间线新增一行。
4. 跨桌任务队列 `#63` 状态改"完成"+回填结论；`1-转型规划/0-全景路线图/跨桌任务队列.md` §二 登记待 commit 批次（若走独立 worktree，按协议第 5 条完工即推送：push 后同步本地 master 指针）。
5. commit + push + 收工重跑台账（`0-学习与工具/工具-文档台账生成.py`）。

## 权威依据清单

1. `1-转型规划/0-全景路线图/跨桌任务队列.md` `#63`（+源头 `#33`/`#40`）。
2. `1-转型规划/保供看板v2-口径定稿.md` §2 C-2·②、§5 裁决登记 #5。
3. `openspec/changes/archive/2026-07-15-sc8-baoguan-substitute-partial-kit/design.md`（Open Question #3 + "2026-07-15 补充"+"2026-07-20 补充"两段）。
4. `7-外部文档/采购部/采购部-YaoZuYi-回复-2026-07-16-文本反馈-1b745aed1383667554060ee7db5e5eca.md`（口径原文）。
