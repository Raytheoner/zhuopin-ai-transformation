---
title: "口径点台账 · schema（coverage-point-ledger tasks §1.1）"
created: 2026-09-06
status: 生效（D1–D9 已审；与 `criteria_signoff` 同 ID 一条待两包合审，见 §四）
来源: openspec/changes/coverage-point-ledger/{proposal,design}.md；design审前置-口径点台账三开放点收敛-2026-09-01.md §2.3 P1–P4、§4.5；端到端构建workflow优化-方案-2026-09-06.md §四 W2
---

# 口径点台账 · schema v1

> **信是视图、点是真身**（D6）。本目录五份域文件平铺（D2／D8：🔴 不得建子目录，`.gitignore` 例外不递归，子目录内 `.jsonl` 会被静默吞掉且不报错）。格式 JSONL（D7）。
> 🔴 **每行＝一次事件（append-only）**，同一 `id` 的**最后一行**是当前态；历史行永不改写——这就是 proposal「每次状态转换写 append-only 记录」与 spec「事实日期一经写入不得被补记覆盖」的落点，不另建审计文件。

## 一、文件

| 文件 | 域 | ID 前缀（隐含域，不设 `域` 字段，D2） |
|---|---|---|
| `采购域.jsonl` | 采购 | `SC*` |
| `财务域.jsonl` | 财务 | `FI*` |
| `质量域.jsonl` | 质量（OEM 隔离边界内，物理独立） | `QD-*`／`Q*` |
| `销售域.jsonl` | 销售 | `S*`（销售域场景码） |
| `IT域.jsonl` | IT | `IT*`／`D-IT*` |

跨域度量只读逐份聚合，🔴 禁止任何合并落盘产物含缓存（D3，断言测试＝tasks 1.4）。

## 二、字段（每行一个 JSON 对象，UTF-8，无 BOM，`\n` 结尾）

| 键 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 稳定标识，**不随队列行号漂移**。两种形态：⑴ 代码侧已有判据 ⇒ `<场景码>-<Criterion.key>`（如 `FI10-NRV_ESTIMATION_BASIS`，与 `zhuopin_platform.criteria_signoff` 注册表同名，**不建第二本账**）；⑵ 无代码判据的专员判例点 ⇒ `<场景码>-<判例批次>-<序号>`（如 `FI2-D19-03`）。同一 `id` 只能出现在其域文件里 |
| `event` | enum | ✅ | `建点`／`转态`／`补记`／`作废`。`补记`＝迟到登记，**只能加行、不得改前行** |
| `status` | enum | ✅ | `待问`→`在途`→`已签认`→`已回灌`→`已落码`（单向；`已作废` 另计；回退须 `note` 留因）。🔴 `已签认` **只能由真实回件驱动**（D5）：该事件行必须带 `evidence`，无任何超期自动签认路径 |
| `type` | enum | ✅（建点行） | `判据类`／`试用反馈`／`材料索取`（P4）。`判据类` 永不默认生效；`试用反馈`／`材料索取` 可标 `default_after_h`（如 48） |
| `scene` | string | ✅（建点行） | 场景码（`FI2`／`SC8`／`QD-B`…） |
| `proposer` | string | ✅（建点行） | 提出人，**取自 `6-人才与组织/人员名录-称谓与性别-正本.md`，不推断** |
| `fact_date` | date | ✅ | **事实发生日**（建点＝提出日；转态＝该状态实际发生日）。不可考时写字面量 `"事实日未知"`，🔴 不得用补记日顶替；度量脚本把 `事实日未知` 单列、不混入中位数 |
| `recorded_on` | datetime | ✅ | 本行写入时刻（本机 `Get-Date`，带 `+08:00`）。与 `fact_date` 并存——两者之差就是「补记滞后」 |
| `by` | string | ✅ | 写入者（会话编号 `OP-…` 或人名） |
| `case_text` | string | ✅（建点行） | 判例原文（判例批改法左栏，原样） |
| `proposed_ruling` | string | ✅（建点行） | 拟改判定（右栏，原样） |
| `carrier` | string[] | ≥1（**仅建点行**） | 承接载体：`openspec:<change>`／`queue:§一#N`／`commit:<sha>`／`criterion:<key>`。队列行号引用在行号漂移时标 `需复核`。🔴 **`转态` 行可空、写入期不强制**（Shao Peishen 2026-09-06 经 `OP-0906-X` 拍板 (a)，定死本表与 §二 最小示例此前的自相矛盾）——成因：若转态行也强制，则 ⑴ `coverage-point-ledger` tasks §6.3 的质量型指标「承接载体缺失数量」**结构性恒为 0**（自己度量自己永远合格），⑵ 会逼 §2 回溯拆点为历史转态行**编造**载体，与「历史记录不追改」相抵。⇒ 载体缺失改走度量（`Snapshot.missing_carrier`），不走写入期硬拦 |
| `letters` | string[] | 可空 | 该点由哪封信投影出去，`部门#N`，可多封 |
| `due` | date | 可空 | 非空则进超期扫描（超期只生成催办草稿，状态保持 `在途`） |
| `evidence` | string | `已签认`／`已回灌` 行必填 | 回件落档件路径（`7-外部文档/<部门>/…`）；`已回灌` 另可指 commit |
| `note` | string | 可空 | 回退原因／补记说明 |

**最小示例（三行＝一个点的建点→在途→已签认）：**

```jsonl
{"id":"FI10-NRV_ESTIMATION_BASIS","event":"建点","status":"待问","type":"判据类","scene":"FI10","proposer":"Shao Peishen","fact_date":"2026-09-06","recorded_on":"2026-09-06T21:30:00+08:00","by":"OP-0906-W","case_text":"…","proposed_ruling":"…","carrier":["criterion:NRV_ESTIMATION_BASIS","openspec:fi10-inventory-writedown-mvp"],"letters":[],"due":null}
{"id":"FI10-NRV_ESTIMATION_BASIS","event":"转态","status":"在途","fact_date":"2026-09-10","recorded_on":"2026-09-10T09:35:00+08:00","by":"ZhuopinFollowupDispatchDaily","letters":["财务部#17"]}
{"id":"FI10-NRV_ESTIMATION_BASIS","event":"转态","status":"已签认","fact_date":"2026-09-12","recorded_on":"2026-09-12T14:02:00+08:00","by":"OP-0912-B","evidence":"7-外部文档/财务部/财务部-tangyanping-回复-财务部#17-2026-09-12-….md"}
```

## 三、约束（落成断言测试／lint，不只写在这里）

1. 同一 `id` 的行按文件顺序即时间顺序；`status` 单向，回退行必须带 `note`（tasks 1.3）。
2. `已签认` 行缺 `evidence` ⇒ 写入拒绝（tasks 1.5，D5）。
3. `fact_date` 一经写入不得被后续行改写；`补记` 事件只能新增行（tasks 3.3）。
4. 目录下出现子目录 ⇒ lint 失败（tasks 1.6，D8）。
5. 跨域聚合不得写出任何含跨域数据的文件（tasks 1.4，D3）。
6. 跨域 `id` 前缀与文件不符 ⇒ 写入拒绝（D2 派生）。

## 四、待两包合审的一条（不阻塞 §1.3）

**`id` 形态⑴ 与 `criteria_signoff` 注册表同名、状态单向由台账驱动注册表**（专员签认回件 ⇒ 台账 `已签认` ⇒ 同一动作写 `Signoff(signed_by, evidence)`）——依据方案件 §四 W2；`criteria-signoff-platform` design 审未过，与本包 design 合并一次审时定死。定前，形态⑴ 只作 `id` 命名约定使用，不写注册表。
