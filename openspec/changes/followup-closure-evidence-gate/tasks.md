# Tasks — 闸的开合系统性根治（`OP-0828-X`）

> 🔴 **本包当前只完成 propose ＋ design 阶段**（队列 §一 `#366` 派单明写「只出 propose ＋ design，不实现、不改任何生产代码」）。
> 下方第 1–6 节为**实现期任务清单**，全部未开工；实现须另派单件（属 CC 建造，触碰生产代码）。

## 0. 🔴 归档前置与开工前置（未决）

- [ ] 0.1 **与两个未归档前序包对齐**：`editlock-followup-reply-state-sync` 这项能力目前只存在于 `followup-letter-state-single-source` 与 `followup-reply-pairing-latest-letter` 两包的 delta 里，尚未 sync 进主 specs。本包因此只能用 `ADDED`。**归档任一包之前须按 design.md D7 一次对齐**；🔴 **本包不得先于那两个包归档。**
- [ ] 0.2 **需 Shao Peishen 定夺：`IT部#9`／`IT部#10` 降回第九态会重新锁上陈承的串行闸。** 这是正确的后果（回件确实没人拆），但会立刻影响 IT 线。见 design D3 B 类。
- [ ] 0.3 **需 Shao Peishen 定夺：截止日期取 `2026-08-28`（本包实撞当日）还是 `2026-08-23`（桥二上线日）。** 本 design 建议前者，理由见 D3。
- [ ] 0.4 **design 审**：D1 主动改判（不引入 `🤖 已归档待拆件`、改用既有第九态）与 opener 原文不同，须被明确同意或推翻。

## 1. 权威判据模块（`zhuopin_platform/shared_tools/followup_gate.py`）

- [ ] 1.1 新增 `parse_closure_references()`：从 `📥` 状态单元格解析队列行引用与归档件标识
- [ ] 1.2 新增 `parse_reflow_targets()`：解析入信行状态列的 `[R:…]` 机器字段（单值/多值）
- [ ] 1.3 新增 `status_cell_has_human_content()`：剥掉全部机器字段与空白后判非空（D2 第 4 条判据）
- [ ] 1.4 新增 `closure_has_evidence()`：四条合格判据合一，**不改 `is_closed_status` 语义**
- [ ] 1.5 新增 `classify_gate_state()`：返回四态之一，含历史豁免分支与「机器代写不豁免」分支
- [ ] 1.6 新增 `CLOSURE_EVIDENCE_CUTOFF_DATE` 常量（取值待 0.3 定夺）与 `MACHINE_WRITTEN_MARKER = "未经人工逐字确认"`
- [ ] 1.7 `工具-队列结构lint.py` 的符号断言名单同批加入 1.1–1.5 的新符号（既有四个符号一个都不改名）

## 2. 闸查询工具四态输出（`0-学习与工具/工具-跟进闸查询.py`）

- [ ] 2.1 `GateReport` 增 `gate_state`；`gate_open` 改为 `gate_state == "✅ 开"` 的派生字段（既有 JSON 消费方零改动）
- [ ] 2.2 人读渲染显示四态标签；`🔴 待拆件` 与 `🔒 在途` 的催办对象分别写清
- [ ] 2.3 走历史豁免时，输出中**显式标注**「旧口径（无回灌引用）」——🔴 只写在文档里不算
- [ ] 2.4 退出码语义不变：四态全部 0

## 3. 桥二天花板下调与 `[R:…]` 校验（`0-学习与工具/工具-共享文档编辑锁.py`）

- [ ] 3.1 `_build_reply_closed_status` → 改为构造第九态；移除此处对 `FOLLOWUP_SERIAL_CLOSED_PREFIX` 的引用
- [ ] 3.2 `_auto_sync_followup_reply_state`：已是第九态则空操作（幂等）
- [ ] 3.3 `[R:…]` 缺失 → 低噪 note 不拦；`[R:…]` 引用落空 → 违规拦截并指名
- [ ] 3.4 🔴 **新状态文件的 `git check-ignore -v` 实测输出原样贴进本行**（proposal 强制项，不得以「应该被覆盖」代替）

## 4. 串行闸切换（`_validate_followup_readme_release`）

- [ ] 4.1 `_followup_status_is_closed` → 改走 `classify_gate_state`，只有 `✅ 开` 放行
- [ ] 4.2 拦截文案区分三种不放行原因（在途／待拆件／终态无引用），各给不同的下一步动作
- [ ] 4.3 `串行豁免：` 逃生阀保持不变

## 5. sweep 常驻告警（`0-学习与工具/工具-落库sweep.py`）

- [ ] 5.1 新增 `_check_followup_unverified_closure`，复用 `_track_and_alert_standing_state`
- [ ] 5.2 key ＝ 信编号，不含任何会变的量
- [ ] 5.3 两条解除出路（补齐引用／降回第九态）各一条测试
- [ ] 5.4 每轮回显四项统计；读取失败写「不据此判为合规」
- [ ] 5.5 抑制窗口 N ＝ 6 小时（首月只告警不调参）
- [ ] 5.6 退休条款：连续 30 天零命中触发退休评估提示，指向承接队列行

## 6. 存量处置与文档同批

- [ ] 6.1 `质量部#10`／`采购部#19`：Cowork 2026-08-28 已实拆，补写合格引用转正
- [ ] 6.2 `IT部#9`／`IT部#10`：降回第九态（待 0.2 定夺后执行）
- [ ] 6.3 README 状态语义正本：加「谁有资格写哪一态」一张表 ＋ 四态闸语义 ＋ 截止日期
- [ ] 6.4 `定时任务源码/huijian-chaijian-patrol.SKILL.md` §三.4：拆件回灌须写 `[R:…]`
- [ ] 6.5 skills `zhuopin-followup-letter`／`zhuopin-send-followup`／`zhuopin-queue-audit` 中的闭环判据措辞同批改
- [ ] 6.6 根 `CLAUDE.md` §5 相关指针行同批改（只改指针，不搬正文）

## 7. 验收（proposal「实现落地后真实生效」五条）

- [ ] 7.1 新函数全量单测绿，含「机器无法在不写内容的情况下让终态通过」反例断言
- [ ] 7.2 `--all` 在**生产真身**跑通，四态各出现过一次真实取值（`⏸ 暂缓` 可用构造样本）
- [ ] 7.3 一次真实 release 上观测到桥二**没有**再写 `📥`
- [ ] 7.4 存量 4 行处置完毕，sweep 该类告警从有到无并**播报过一次解除**
- [ ] 7.5 🔴 **一次真实完整往返**：回件到达 → 第九态 → 拆件写 `[R:…]` → release → `📥` 带引用 → `--to` 显示 `✅ 开`。**这一条不发生，前四条全绿也不算生效。**
- [ ] 7.6 回归零漂移：`0-学习与工具` ／ `zhuopin_platform` ／ `wecom-aibot-service` 全量 ＋ `openspec validate --all --strict`

## 8. 收工回写

- [ ] 8.1 队列 §一 `#366` 回填实现结论
- [ ] 8.2 §二 批次登记 ＋ sweep ＋ 台账
