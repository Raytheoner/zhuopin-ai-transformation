# followup-approval-cooldown-5min Tasks

> 🔴 **本文件在 design 审通过前不得开工。** 0.x 是前置闸，逐条过完才进 1.x。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 📌 本包改动量极小（1 个常量 ＋ 1 条 spec Requirement ＋ 1 处文档串 ＋ 2 个用例时间点），**但仍走完整流程**——理由见 proposal「为什么不能就地改」。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 确认 `design.md` 顶部已回填「design 审：✅ 已过 —— Shao Peishen YYYY-MM-DD」，**不凭记忆**
- [ ] 0.2 触碰区复核：`grep` 在途变更包是否有其它包同时改 `aibot_service/approval.py` 或 `openspec/specs/wecom-followup-review-state/spec.md`（design「触碰区核对」）
- [ ] 0.3 建 worktree，确认 `pip show zhuopin_platform` 的 `Editable project location` 指向本 worktree 而非别处（`editable-pth-blindspot-guard` 已记的静默漂移陷阱）

## 1. 实现

- [ ] 1.1 `aibot_service/approval.py`：`DEFAULT_COOLDOWN_MINUTES` 10 → 5，常量上方注释写明——⑴ 改动日期与拍板人；⑵ 为什么可以减半（上下游两道非时长关卡）；⑶ **已知代价不粉饰**（安全边际减半；对"quote 是编的、读回走过场"无效，但 10 分钟同样无效）；⑷ **不再往下调的下限判据**（3 分钟内起草＋批准做得到 ⇒ 5 是下限）
- [ ] 1.2 `scripts/approve_followup_letter.py` 模块文档串「10 分钟」→「5 分钟」，并指向 1.1 的注释处（**不在两处各写一遍理由**——理由只有一个真身）
- [ ] 1.3 `openspec/specs/wecom-followup-review-state/spec.md` 由本包 spec delta 的 `MODIFIED` 承接（`/opsx:sync` 时并入），**本任务不手改 specs/ 本体**

## 2. 测试

- [ ] 2.1 `tests/test_approval.py::test_approve_still_blocked_before_cooldown_elapses`：`minutes=5` → `minutes=3`，注释写明"旧值在新阈值下正好已满、当场变红，**这是正确的失败**"
- [ ] 2.2 `tests/test_approval.py::test_approve_succeeds_after_cooldown_elapsed`：`minutes=11` → `minutes=6`，注释写明"旧值照样通过 ⇒ **不会变红、也就不再钉住任何东西**"
- [ ] 2.3 🔴 **反向验证这一对用例真的夹住了阈值**：临时把 `DEFAULT_COOLDOWN_MINUTES` 改成 4 与 7 各跑一次，**两次都必须有用例变红**；若某次全绿，说明夹持失效、回到 2.1/2.2 重做。改回 5 后再进 2.4。（**这一步是本包唯一的真验证**——不做它，2.1/2.2 只是把数字改了一遍。）
- [ ] 2.4 `python -m pytest tests/test_approval.py tests/test_readme_table.py tests/test_dispatch.py tests/test_delivery.py -q` 全绿
- [ ] 2.5 全量 `python -m pytest tests/ -q` 全绿、零回归

## 3. 端到端实测（不可省）

- [ ] 3.1 用一封**真实待审信**（或临时造一行草稿态测试行）实跑：首跑必被拒并记录时刻 → **第 3 分钟重跑仍被拒** → **第 6 分钟重跑放行**。三次结果与退出码逐一记录进收工报告
- [ ] 3.2 核 `reports/followup_approval_cooldown_state.json` 的行身份键与既有格式一致（未因本包改变）
- [ ] 3.3 核审计里 `followup_approval_rejected` 的 `decision.reason` 仍为 `cooldown_not_elapsed`（语义未漂）

## 4. 收口

- [ ] 4.1 `openspec validate followup-approval-cooldown-5min --strict` 通过
- [ ] 4.2 ff 合入 master（`git rev-list --count master..<分支>` ＝ 0）
- [ ] 4.3 `/opsx:archive followup-approval-cooldown-5min -y`（完工即归档，不跨 session）
- [ ] 4.4 队列回写：本包所在行状态 ＋ §二 批次登记
- [ ] 4.5 🔴 **同步 skill `zhuopin-send-followup` §2 表格里"10 分钟冷却窗口"那句**——它是给下一个会话看的操作说明，**不改就会让人按 10 分钟等**（同族＝该 skill 自己记的「规则落地时间晚于 skill 末次更新，必然错过」）。skill 源码在 `0-学习与工具/skills源码/zhuopin-send-followup/SKILL.md`
- [ ] 4.6 同查 `zhuopin-followup-letter` 源码 §5.3 是否也写了 10 分钟；有则一并改

## 不做什么

- ❌ 不动 `check_cooldown` 算法、状态文件格式、`--cooldown-minutes` 参数
- ❌ 不改 `--quote` 必填与发送侧读回铁律（它们是本包安全性论证的前提）
- ❌ 不把用例写成 `DEFAULT_COOLDOWN_MINUTES ± N` 相对式（design D4）
- ❌ 不顺手调整其它阈值（行长上限、3 天窗口、WIP 上限等）——各有各的判据，一包一事
