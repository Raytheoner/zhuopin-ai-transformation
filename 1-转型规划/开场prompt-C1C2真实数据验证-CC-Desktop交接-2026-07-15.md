---
title: "开场prompt-C1C2真实数据验证-CC Desktop交接-2026-07-15"
created: 2026-07-15
执行方: CC 建造车间（Paul 的 CC Desktop 长期环境，非本次沙箱 worktree）
来源: 采购专线 2026-07-15 session 收口交接（C-1/C-2 apply+归档后，Paul 已回公司确认在 LAN，但本次施工的沙箱
      worktree 缺 `.env` 凭证无法真调 U9C，Paul 拍板"换到 CC Desktop 长期环境做"）
status: 待执行
---

# C-1/C-2 真实数据验证 · CC Desktop 交接（2026-07-15）

> **用法**：Paul 在 Claude Code Desktop（长期 clone，已配好 `.env`）新开 session，粘贴下方开场词即可。

## 开场词（复制即用）

```
读 1-转型规划/0-全景路线图/跨桌任务队列.md #33 ＋ 本文件 ＋ openspec/changes/archive/2026-07-15-sc8-baoguan-substitute-partial-kit/design.md 恢复上下文，执行 C-1/C-2 真实数据验证；开干前确认 .env 里 U9C_API_BASE/U9C_CLIENT_ID/U9C_CLIENT_SECRET 等凭证齐全。
```

## 背景一分钟

- 2026-07-15 当天早些时候，采购专线在一个**沙箱 worktree**（`.claude/worktrees/upbeat-diffie-6972f9`，非 Paul 平时用的 CC Desktop 长期 clone）里完成了 C-1（主料/替代料等价合并判缺料）+ C-2（部分齐套显示）的 openspec 批2全流程：propose → design（Paul 审通过）→ apply（TDD 实现）→ 全量回归零漂移（SC8 188 passed+3 skip，平台/O2/SC7/SC1 全绿，SC7 黄金基准精确不漂移）→ 归档 → commit+push（已在 master）。
- **但该 worktree 是临时环境，没有 `.env`（U9C_API_BASE/U9C_CLIENT_ID/U9C_CLIENT_SECRET 等凭证），也一度连不上内网**，所以实现是**完全按 mock/脱敏数据 + design.md 里的一个技术假设**做的，**没有做真实数据验证**。
- Paul 回公司确认在 LAN 后，沙箱环境测了一下：`192.168.6.2`（U9C 数据库服务器）能 ping 通了，但 `192.168.100.51`（保供看板部署服务器）仍 ping 不通（**建议顺手确认一下这台服务器是不是关机/离线了**，与 #32 sync-to-server.ps1 修复的真实部署验证也相关）；且沙箱工作区始终没有 `.env`，即便网络通也调不了真实 U9C 接口。Paul 拍板：真实验证换到 CC Desktop 长期环境（已配好凭证）来做。

## 需要验证的三件事（跨桌任务队列 #33）

### ① 替代料 DTO 真实字段结构验证（最关键，design.md Open Question #1，未验证）

**背景**：2026-07-08 那次生产只读实测（`保供看板v2-口径定稿.md` §2 C-1·①）**只确认了**：
- 替代料嵌套在主件行的 `m_bOMCompSubstituteDTO4CreateSv` 子列表里（不是同级平铺重复序号）；
- 替代料与主件行共享同一 `m_sequence`（项次）语义。

**但没确认**：替代料 DTO 内部的每个元素，是否自带独立的 `m_usageQty`（用量）/`m_scrap`（损耗率）/`m_itemMaster`（料号/名称），还是完全不带这些字段、需要继承主件行的值。

`get_bom_for_products`（`5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py`，替代料提取那一段代码有清楚的注释标注这是"design.md D2 假设"）目前的实现是：**替代料自带 `m_usageQty`/`m_scrap` 就优先用自己的，没有就继承主件行的值**——这是本次实现时给自己留的一个"两头都接得住"的保守假设，但从未拿真实 API 响应验证过究竟走的是哪个分支。

**验证方法**（复用 2026-07-08 那次的方法论，只读、不改任何 ERP 数据）：
1. 用 `保供看板v2-口径定稿.md` §2 已确认存在替代料的样本母件（15 母件/56 组替代料那批，或重新用今天真实 FO 订单抽样），只读调用 `ZpConnector.get_bom_for_products`（或直接看 `_u9c_bom_post` 原始响应），打印/落一份诊断脚本输出（一次性、不入库，参考 `保供看板v2-口径定稿.md` 里"样例数据/脚本为一次性诊断，未入库"的做法）。
2. 检查真实响应里 `m_bOMCompSubstituteDTO4CreateSv` 列表内每个元素，是否含 `m_usageQty`/`m_scrap`/`m_itemMaster` 字段，值是多少。
3. 顺带验证 `m_subSeq` 字段是否被真实数据用上（同一料位是否存在多条替代料，即"一组多替代"场景是否真实存在）——design.md/tasks.md 里也留了这个待验证点。
4. **如果验证结果与"优先用自己的、没有则继承主件行"这个假设不符**（比如替代料根本不带这些字段、或字段含义不一样），回来改 `get_bom_for_products` 里替代料提取那段代码（`connector.py` 里有明显注释标注位置），并同步更新：
   - `5-平台底座/zhuopin_platform/tests/test_bom_substitute_extraction.py`（现有 mock 测试的假设前提要跟着改）
   - `openspec/specs/platform-data-connectors/spec.md`（该 Requirement 的 Scenario 描述如涉及字段假设需要更新）
   - 本文件登记的验证结论

### ② 姚祖怡真实数据抽验

用真实数据跑一遍保供看板（`python scripts/run_baoguan_web.py` 或直接调 `compute_snapshot`），挑几个确认存在替代料的成品行 + 几个部分齐套的场景，让姚祖怡对照线上/真实数据核实：
- 替代料合并后的判齐结果是否符合她的预期（参考 `保供看板v2-口径定稿.md` 的 15 母件/56 组替代料样本）；
- "可齐套 X / 总需求"的数字和"卡在子件 Rxx、还差 N 件"的提示是否可读、不引起误解。

### ③ `kittable_shortfall`（还差 N 件）口径一句话确认

`design.md` Open Question #3：目前"还差 N 件"算的是**"凑够下一整套（kittable_qty+1）所需的缺口"**，不是"凑够客户下单总量所需的缺口"（两者数值差很多）。这是实现时自己选的一个推荐口径，没有跟姚祖怡正式确认过。随②真实数据抽验一起顺口问一句就行，不用单独开会。

## 权威依据清单（只给指针，不抄内容）

1. `openspec/changes/archive/2026-07-15-sc8-baoguan-substitute-partial-kit/`（proposal/design/tasks 全套，design.md 的 Decisions/Open Questions 段是本次交接的核心依据）。
2. `1-转型规划/保供看板v2-口径定稿.md` §2（C-1/C-2 业务口径权威，含 2026-07-08 那次字段验证的完整记录，可作方法论参考）。
3. `4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md`（"3. 复用底座资产"新增的 C-1/C2 行 + "5. 状态时间线" 2026-07-15 两行 + "6. 关键依赖"新增一行）。
4. `1-转型规划/0-全景路线图/跨桌任务队列.md` `#33`（本任务的正式登记行）。

## 收工纪律提醒

- 本次沙箱环境的实现代码（commit `e6bf6a2`）已在 master，**不需要重新实现**，本次只是补真实数据验证，验证通过就在队列 `#33` 和 SC8 CLAUDE.md 里销行；验证不通过才需要改代码。
- 若顺带确认了 `192.168.100.51` 服务器状态，一并回填队列 `#32`（sync-to-server.ps1 重启可靠性修复的真实部署验证）。
- 验证完收工：队列 `#33` 状态改"完成"+回填结论，SC8 CLAUDE.md 状态时间线补一行，commit+push+收工重跑台账。
