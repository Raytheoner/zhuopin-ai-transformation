# tasks-zombie-item-detect Tasks

> **✅ design 审已签认（Shao Peishen 2026-09-12 回 `P2：4a`），apply 已完成（`OP-0912-AA`，2026-09-12，CC worktree `op0912aa-p2-zombie-lint-apply`，分支 `claude/op0912aa-p2-zombie-lint-apply`）。** 未归档：0.2／0.3 他未明答、2.8 目标行已归档不得改、2.10 依前三项。下段为 propose 期原文，不追改：
> ~~本包止于 design，未 apply。下方 §0 是待定夺项，§1 是已完成的回测取证，§2 起是 apply 阶段待办、在 design 审通过前一律不得开工。~~
>
> 🔴 **apply 硬前置**：`OP-0821-J` 第 1 步对 `fi2-recon-mvp` 的 7 项勾除必须已在 `master`。否则 J-A 存量为 4 而非 0，门禁上线即红（design 决策点 3）。

## 0. 待定夺（design 审，本包不得 apply 亦不得归档）

**三项动手的都不是本 session（本 session 收工后不再执行），按根 `CLAUDE.md` §5「答完之后由谁动手」判据：不给选项、只登记待总线派发。**

- [x] 0.1 **decision 决策点 4：J-C 的强度取 (a)/(b)/(c)** —— 已登记，待总线派发。design 推荐 (a)（强判据直接 enforce，存量为 0）。**这是本包唯一一处会给他人增加书写负担的判据，不擅自定。** —— ✅ Shao Peishen 2026-09-12 回 `P2：4a`（经 Cowork 环境总线 `OP-0912-E`，签认段在 design §决策点 节首）。
- [ ] 0.2 **decision Open Question 2：J-B 清单是否设陈化门槛** —— 已登记，待总线派发。**无实测数据支持任一侧**（fi2 的 5 个 B 类命中末次触碰均 > 30 天，设与不设当下结果相同），故不预设。 —— ⏳ 2026-09-12 签认轮他**未答**，按起草方原意「不预设」实现（脚本无任何陈化阈值、无默认开着的开关）；**未答≠已答**，本项留 `[ ]`，噪音真起来时再端给他。
- [ ] 0.3 **decision Open Question 3：队列 §四 `#91` 那条人守规则的退休是否成立** —— 已登记，待总线派发。proposal 已按"成立"撰写，须确认；若不成立，proposal 的「本次退休哪一个既有守卫」一节须重写（协议〇.9 措施 B 为机制类包强制项）。 —— ⏳ 2026-09-12 签认轮他**未明答**；退休声明已按 design 现取更正 6 落 proposal ＋ CHANGELOG 附录 L（记「机制已上线」这一事实，不替他答）。本项留 `[ ]`。

## 1. 回测取证（已完成，本 session 内实跑）

- [x] 1.1 逐项核实 `fi2-recon-mvp` 全部 13 个未勾项，分为「已交付但漏勾 5／被后续决策作废 2／真未决 6」三类，逐项写勾除依据（产出＝该包 `tasks.md`，OP-0821-J 第 1 步）
- [x] 1.2 `git log -S'1.5 前置登记' -- openspec/changes/fi2-recon-mvp/tasks.md` 实跑 —— 只返回建档 commit `0d19918`（2026-07-07），证实该行 45 天零触碰、同期同文件被改 13 次
- [x] 1.3 `git show b04503f --stat` ＋ 该 commit 的 `tasks.md`／`CLAUDE.md` diff 实跑 —— 证实同一 commit 的 message 写「真实部署.51:8094冒烟通过」而其写入的 `15.10` 是 `[ ]`（形态 B 的硬证据）
- [x] 1.4 首轮候选判据（未勾项正文含完成态标记）全库实跑 —— 召回 0/7、误报 3/3，**当场否决**
- [x] 1.5 J-A／J-B 在**勾除前**快照（`git show HEAD:…`）上实跑 —— J-A 命中 `1.5`／`1.6`（精度 2/2），J-B 命中 5（精度 4/5）
- [x] 1.6 J-A／J-B 在全库 14 个活跃变更包上实跑 —— J-A 其余 13 包命中 0，J-B 其余 13 包命中 6
- [x] 1.7 J-C 基线实跑 —— 全库「前置登记」项 3 个、「前置 N.M」引用 3 处，**当前 100% 覆盖，存量违规 0**
- [x] 1.8 核实 `工具-落库sweep.py` 不承载 lint（全文「lint」命中 0），确认本项目 lint 一律在 CI —— 据此推翻派单件的「加进 sweep」建议

## 2. apply 阶段（🔴 design 审通过前不得开工）

- [x] 2.1 先写测试：J-A／J-B／J-C／J-D 四条判据各自的正反例夹具（含「节标题声明前置」与「条目正文声明前置」两种来源、含 `10.11b` 这类"真未决却被 J-B 命中"的样本，锁死其输出措辞为「请复核」） —— ✅ 2026-09-12 `OP-0912-AA`：`0-学习与工具/test_工具-僵尸未勾项lint.py` 29 条（`pytest -q` 29 passed）：J-A 节标题来源／正文来源各一正例、三反例；J-B 含 `10.11b` 样本、断言输出含「请复核」且不含「疑似已完成」；三种分隔形态各一条（斜杠 `1.5/1.6`、斜杠 `0.1/0.4`、顿号 `2.3、0.3`）＋ spec 明列的 `,`／`，`。
- [x] 2.2 反例单测锁死 R1：J-B **MUST NOT** 返回非零退出码，无论命中多少条 —— ✅ `test_jb_never_nonzero_exit_even_with_enforce`：29 条 J-B 命中 ＋ `--enforce` ⇒ 退出码 0。
- [x] 2.3 反例单测锁死已知边界 5：`openspec/changes/archive/**` 不进扫描面 —— ✅ `test_archive_dir_excluded_but_archive_named_pkg_included`：`archive/**` 内的违规不出现在任何输出；名含 archive 的活跃包（`audit-retention-archive`）照扫。
- [x] 2.4 实现 `0-学习与工具/工具-僵尸未勾项lint.py`（纯只读，零写盘；`--enforce` 只对 J-A／J-C 生效） —— ✅ 已实现（`test_read_only` 锁死运行前后文件集合与 mtime 不变；退出码只看 J-A／J-C）。
- [x] 2.5 对全库 14 个包实跑，核实命中数与 design §判据实测表逐格一致（J-A=0、J-C=0、J-B=7）；不一致即停手查因，不得改判据去迁就 —— ✅ 按签认段改为对现取活跃包重跑（2026-09-12 `python 0-学习与工具/工具-僵尸未勾项lint.py --enforce --jd-summary`）：**79 个包**（design 写 75 是 `grep -v archive` 把 `audit-retention-archive`／`opener-batch-archive-precheck` 两个活跃包也滤掉了）；前置声明 11 处、前置登记项 6 个（与 design 现取更正 2 一致）；**J-A 首跑 3、非 0——停手查因**：全部来自 `status-triage-resident-round` §7 标题级前置声明（指向 6.3）过宽，7.1–7.3 已 `[x]` 且实际不依赖 6.3（只有 7.4 归档依赖它，7.4 正文自己写着「待 6.3 留痕后」），是该包 09-06 写入、晚于 08-22 基线的真命中、非解析错；**未改判据**，把该声明从 §7 标题下移到 7.4 正文（不动任何勾选）⇒ J-A 0；J-C 0；J-B 47（14 包时 7）。design 表旧值不覆盖。
- [x] 2.6 新增 CI job `zombie-task-lint`（不加 `continue-on-error`——分档已在脚本内实现，见 design 决策点 3；job 注释须写明为何与 `claude-progress-lint` 取法不同） —— ✅ `.github/workflows/ci.yml` 末尾新增 `zombie-task-lint`（`--enforce`、无 `continue-on-error`、`fetch-depth: 0` 供 J-D blame）；注释三点写明与 `claude-progress-lint` 取法不同：档位分在判据不分在时间／J-B 永不切 enforce 而非二期再切／强判据侧沿「先清零再关门」。
- [x] 2.7 R2 自检：脚本须打印「本次扫描共发现 N 个前置声明」，使 N→0 这一失效信号可见 —— ✅ 输出固定含「本次扫描共发现 N 个前置声明（「前置 N.M」引用 N 处；「前置登记」项 M 个）」；N=0 时追加 🔴 失效提示（`test_prereq_count_line_and_zero_flag`）。
- [ ] 2.8 队列 §四 `#91` 正文降级为一行指针（0.3 确认成立后才做） —— ⛔ **不做、如实登记**：`#91` 已清扫入队列归档件，归档行按「历史记录不追改」不得改（design 现取更正 6）；且 0.3 未答。退休声明改落 proposal ＋ CHANGELOG 附录 L。
- [x] 2.9 场景/工具侧文档更新 ＋ 队列回写 —— ✅ 文档：proposal 状态行、CHANGELOG 附录 L、`0-学习与工具/门禁判据族清单.json` 登记本工具四族（`工具-取证件回显lint.py` 自洽校验对本条目无报错）；队列：§一 `#561` 追段 ＋ §二 批次。
- [ ] 2.10 tasks 全 `[x]` 后当场 `/opsx:archive`；未全 `[x]` 则**不 archive、如实登记** —— ⛔ 0.2／0.3／2.8 留 `[ ]`，**不 archive**。

## 3. 明确不做（写出来免得下一个读者以为漏了）

- [x] 3.1 **不改 `工具-落库sweep.py`** —— 决策点 1，推翻派单件建议，理由已留痕
- [x] 3.2 **不改编辑锁、不改任何既有 lint** —— 本包零"改变既有模块对外语义"的动作
- [x] 3.3 **不清理其余 13 个包的 J-B 命中项** —— 那 6 条各归各包，逐条核实需要各自的上下文；本包只交付检出能力，不代做他包的核实（同 `claude-progress-section-lint` 一期不做存量清理的取法）
