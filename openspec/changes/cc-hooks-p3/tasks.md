# Tasks — cc-hooks-p3

> 建造授权已由 §四 `#155`（2026-09-04，Shao Peishen 答 (a)(a)）与 §一 `#381` 子项⑸原文给出，本包 propose/design 与 apply 同批进行（不再单独等待一轮 design 回合）。
> 顺序＝opener 指定的建造顺序：**ⓐ → ⓒ → ⓔ → ⓕ → ⓑ → ⓓ**，一枚一批次、先本地单测过再进下一枚。
> 🔴 **§8 降指针不在本次范围**——前置条件（每枚在真实 session 里真实验活）依赖 Shao Peishen／Cowork 瘦身线完成 `.claude/settings.json` 人工注册，超出本 CC session 的可控范围。

## 0. 前置

- [x] 0.1 grep 两份队列 + 归档确认触碰区无重叠（`0-学习与工具/工具-共享文档编辑锁.py`、`工具-落库sweep.py`、`0-学习与工具/hooks/`、根 `CLAUDE.md`）
- [x] 0.2 §二 预登记批次行 `B-0904_CC-P3H001_预登记_381子项5建造`
- [x] 0.3 与 Shao Peishen 澄清两处分歧（#398 合并、ⓓ 半覆盖风险），已获答复
- [x] 0.4 openspec propose：proposal.md／design.md／tasks.md／六份 spec delta

## 0a. ⓖ opener 块 lint 扩三形态＋单文件自检（2026-09-04 00:48 会话中途插入，✅ 已完成，先于 ⓐ 建造）

- [x] 0a.1 `check_block` 新增形态③④⑤（`工具-opener块lint.py`）
- [x] 0a.2 `--file <路径>` 单文件自检模式（不查 git、不分当前/历史、恒以命中数决定退出码）
- [x] 0a.3 单测：新三形态各自正例/反例 + 两侧都能关掉 + `--file` 模式 3 例 + `_settings_field_order_problems` 直测（`test_工具-opener块lint.py` 41 passed，含既有 F1/F2 回归零漂移）
- [x] 0a.4 全库真实扫描验证（非 mock）：`python 0-学习与工具/工具-opener块lint.py` 与 `--show-historical`，F1/F2/F3/F4/F5 命中 75/57/81/221/247，规则生效日前存量全部归历史件、`--enforce` 不阻断
- [x] 0a.5 确认 release 侧 `_opener_guard_violations` 零改动即感知新判据（读码确认其 `for form, detail in lint.check_block(block)` 无形态白名单）
- [ ] 0a.6 §一 `#381` 状态列回写 ⓖ 完成情况（随 §7 收口一并做）

## 1. ⓐ SessionStart 会话开场上下文

- [ ] 1.1 写 `0-学习与工具/hooks/hooks-sessionstart-context.ps1`
- [ ] 1.2 双标时刻 + `git fsck --connectivity-only` 摘要 + ahead/behind 计数
- [ ] 1.3 队列待领行摘要（§一 `[S:open]` 非 🛑 前 5 条）
- [ ] 1.4 fail-open + `reports/hooks-audit.jsonl` 留痕（含正常与异常路径）
- [ ] 1.5 单测：spec 全部 Scenario（含 git 不可用、队列不可读两条反例）
- [ ] 1.6 交付：`.claude/settings.json` 的 `SessionStart` 挂接片段 + 验活命令

## 2. ⓒ PreToolUse 编辑锁门禁

- [ ] 2.1 写 `0-学习与工具/hooks/hooks-pretooluse-editlock-guard.ps1`
- [ ] 2.2 受保护清单五份文件路径判定（含相对/绝对路径归一化）
- [ ] 2.3 有效锁检查（复用 `STALE_MINUTES` 语义，不做身份匹配）
- [ ] 2.4 fail-open + 审计留痕
- [ ] 2.5 单测：spec 全部 Scenario（无锁拦截、陈旧锁视为无效、有效锁放行、非受保护文件放行、锁文件损坏时放行四类）
- [ ] 2.6 交付：`.claude/settings.json` 的 `PreToolUse` 挂接片段（matcher `Edit|Write|MultiEdit`）+ 验活命令

## 3. ⓔ acquire 路由提示

- [ ] 3.1 在 `工具-共享文档编辑锁.py` 新增关键词→规则文件映射表常量（design 决策点 4）
- [ ] 3.2 在 `_acquire_locked`（含 `--reserve` 分支与非 reserve 分支）占锁成功回显后追加路由提示打印
- [ ] 3.3 单测：spec 全部 Scenario + 既有 `test_工具-共享文档编辑锁.py` 全量回归零漂移
- [ ] 3.4 交付：验活命令（`acquire --note "起草跟进信" ...` 实跑一次贴输出）

## 4. ⓕ sweep rules 尺寸巡检

- [ ] 4.1 `CLAUDE_MD_ROOT_BYTE_CAP` 48KB → 12KB
- [ ] 4.2 `_claude_md_targets` 新增 `.claude/rules/*.md` glob，阈值 8KB
- [ ] 4.3 新增 rules 合计 30KB 判据（`.claude/rules/__total__` 告警 key）
- [ ] 4.4 单测：spec 全部 Scenario + 既有 `test_工具-落库sweep.py` 全量回归零漂移
- [ ] 4.5 交付：验活命令（`python 0-学习与工具/工具-落库sweep.py --dry-run` 或等效只读调用，贴当轮回显）

## 5. ⓑ UserPromptSubmit 常驻五条

- [ ] 5.1 根 `CLAUDE.md` 五处目标行追加 `<!-- UPS5:1 -->` … `<!-- UPS5:5 -->` 锚点（零语义改动）
- [ ] 5.2 写 `0-学习与工具/hooks/hooks-userpromptsubmit-standing-five.ps1`
- [ ] 5.3 锚点提取 + 数量断言（≠5 时可见不静默）+ 截断规则
- [ ] 5.4 fail-open + 审计留痕
- [ ] 5.5 单测：spec 全部 Scenario（锚点齐全、缺失、重复、截断、读取失败五类）
- [ ] 5.6 交付：`.claude/settings.json` 的 `UserPromptSubmit` 挂接片段 + 验活命令

## 6. ⓓ Stop 需你定夺格式检查

- [ ] 6.1 写 `0-学习与工具/hooks/hooks-stop-decision-check.ps1`
- [ ] 6.2 transcript 末条 assistant 文本提取（jsonl 解析，版本探测/解析失败 fail-loud 进审计但仍 fail-open 放行）
- [ ] 6.3 「需你定夺」字样 + 选项标签判据；`stop_hook_active` 防循环
- [ ] 6.4 fail-open + 审计留痕
- [ ] 6.5 单测：spec 全部 Scenario（缺标签拦截、格式完整放行、无小节放行、"本次无需你决策"放行、`stop_hook_active` 放行、transcript 不可读五类）
- [ ] 6.6 交付：`.claude/settings.json` 的 `Stop` 挂接片段 + 验活命令

## 7. 收口（本 session 内可完成的部分）

- [ ] 7.1 `openspec validate --strict` 绿
- [ ] 7.2 六份交付物（脚本/改动/单测结果/注册片段/验活命令）汇总进收工报告
- [ ] 7.3 §二 批次行 `B-0904_CC-P3H001` 精确化（实际文件清单、真实 commit message、状态改"待处理"）
- [ ] 7.4 §一 `#381` 状态列追记：⑸ 六项建造完成到"可注册＋有单测"状态，等 Shao Peishen／Cowork 瘦身线注册后进入生产验活
- [ ] 7.5 push 分支，供 ff 入 master

## 8. 生产验活与降指针（🔴 不在本 session 范围，前置条件未满足）

- [ ] 8.1 Shao Peishen／Cowork 瘦身线完成 `.claude/settings.json` 四段挂接注册
- [ ] 8.2 六枚钩子各自在真实 session 里真实触发一次，`reports/hooks-audit.jsonl` 贴对应行进验收记录
- [ ] 8.3 ⓐⓒⓑⓓ 对应根 `CLAUDE.md`／`.claude/rules/队列与落库.md` 文本降为一行指针（逐条对照「本次退休哪一个既有守卫」的范围，只降已验活对应的那一半）
- [ ] 8.4 队列 §一 `#284`「规则退休制阈值计数台账」登记本次机制守 +5、扩展 +1
- [ ] 8.5 `/opsx:archive cc-hooks-p3 -y`
