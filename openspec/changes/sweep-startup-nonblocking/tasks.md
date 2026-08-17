# sweep-startup-nonblocking Tasks

> apply 前须 Shao Peishen 批准 design.md（四个决策点）。下列任务按**决策点全部取默认项**（1a／2a／3a／4a）编排；若拍板不同，受影响任务在开工时同步调整并在本文件注明。

## 1. `_fetch()` 去异常化（守卫退休，one-out）

- [ ] 1.1 `_fetch(repo_root, log, phase) -> bool`：失败时 `log.append` 一行含阶段名（起跑段/收尾段）与 git stderr 的记录，返回 `False`；成功返回 `True`。函数体内 MUST 无任何 `raise`。
- [ ] 1.2 更新 `_fetch` docstring：写明"本函数不再中止整轮，中止与否由调用方按起跑段通则判定"，并指向队列 #328 与本变更包。

## 2. 起跑段两处降级（决策点 1＝(a)）

- [ ] 2.1 `_push_any_unpushed_commits`：fetch 返回 `False` 时记录后 `return`，**跳过 ahead 计算与推送**（不依据可能陈旧的 `origin/master` 引用做判断），继续本轮。
- [ ] 2.2 同函数补推失败分支（原 `SweepAbort(exit_code=2)`）改为记录后 `return`：日志写明本地提交完整保留、推送交收尾段重试。
- [ ] 2.3 更新该函数 docstring，补记本次两处降级及其理由（沿 #194→#309-F→#328 的记法惯例）。

## 3. 收尾段降级（决策点 2＝(a)）

- [ ] 3.1 `_reconcile_with_origin_and_push`：fetch 返回 `False` 时记录后 `return`，不抛错；日志在 `origin/master..HEAD` 可读时点名未推送提交数（读不到则明写"未推送提交数不可知"，不猜）。
- [ ] 3.2 确认 `main()` 中该函数返回后其余步骤（#198(c) 部署提示、#229 部署留痕、#298 openspec 覆盖与滞留检测）照常执行。

## 4. 通则一：spec ＋ 可扫描判据

- [ ] 4.1 新增单测 `test_起跑段中止位点须与冻结清单一致`：`ast.parse` 源码，遍历起跑段六函数，收集全部 `raise SweepAbort` 节点（含行号与所在函数名），与测试内冻结清单逐项比对；清单每项附一行判定理由。
- [ ] 4.2 断言该测试**对真实生产源码**（`0-学习与工具/工具-落库sweep.py`，非夹具副本）运行通过。
- [ ] 4.3 反向用例：临时构造含多一处 `raise SweepAbort` 的源码文本，断言检查失败（证明它真能拦住第四例，而非恒真）。
- [ ] 4.4 反向用例：注释/docstring/字符串内出现 `raise SweepAbort` 字样时不计为位点（AST 免疫性验证）。

## 5. 通则二：`openspec/config.yaml` 撰写期问询（决策点 3＝(a)）

- [ ] 5.1 在 `rules.proposal` 追加一条 MANDATORY：凡新增或修改"工具会自动生成的伴生文件"（锁文件、快照、暂存、状态、日志、重命名退路产物等），proposal MUST 写明该文件名形态是否已被 `.gitignore` 覆盖及核实方式（`git check-ignore` 结果）；不适用时须写明为何不适用。
- [ ] 5.2 条文内注明成因＝队列 #328 子项②（#322 的 rename-away 退路凭空造出 `.editlock.mutex.stale` 这一新文件名形态，无人回头看忽略规则，企微群连响 17.1 小时）。
- [ ] 5.3 本变更包自身 dogfooding：本包不新增任何伴生文件，在 proposal 或本文件明确作答。**已答：本包不新增伴生文件，仅改既有函数控制流与测试，不适用。**

## 6. 回归测试

- [ ] 6.1 复现场景（队列 #328 交付条件⑶）：构造"fetch 失败但 §二 有待处理批次"，断言**批次仍被本地提交、销行完成**，仅 push 推迟。
- [ ] 6.2 构造"fetch 失败且 §二 无待处理批次"，断言 flush 暂存、孤儿告警、openspec 检测**仍执行**。
- [ ] 6.3 构造"起跑段补推 push 失败"，断言本轮继续、本地提交未被撤销、退出码不再为 2。
- [ ] 6.4 构造"收尾段 fetch 失败"，断言跳过对齐与推送但其后本地检测执行、退出码 0、日志点名未推送提交数。
- [ ] 6.5 断言既有七处"维持拦截"位点行为**逐一未变**（分支非 master／未完成 git 操作／未合并冲突／新鲜 index.lock／linked worktree／repo_root 不符／编辑锁占用）。
- [ ] 6.6 `python -m pytest 0-学习与工具/test_工具-落库sweep.py -v` 全绿、零漂移。
- [ ] 6.7 `0-学习与工具/` 全量回归（编辑锁／队列查询／队列结构 lint／台账／仓库外载体／孤儿 worktree／定时任务源码备份）零漂移。
- [ ] 6.8 `openspec validate --all --strict` 全部通过。
- [ ] 6.9 `python 0-学习与工具/工具-落库sweep.py --dry-run --repo-root <本 worktree>` 真实跑一次，确认不触碰主工作区、无副作用。

## 7. 子项② 验收复核（不改动，只核）

- [ ] 7.1 复核 `.gitignore` 现为单条 `*.editlock*`，`git check-ignore -q <任一 .editlock.mutex.stale>` 退出码 0（已于 design §4 记录当前通过）；**本包不修改 `.gitignore`**。

## 8. 收口

- [ ] 8.1 队列 §一 #328 回写：✅ 写在状态列开头，写明九个位点的逐一判定结论（交付条件⑵）、20/715 实测更正、子项②已完工核实、子项③④⑤ 未做。
- [ ] 8.2 队列 §二 登记本次批次。
- [ ] 8.3 commit + push；重跑文档台账。
- [ ] 8.4 `/opsx:archive`——**仅当本文件全部任务真实勾选后才执行**；有未完成项则如实留置，不假装完工（§5 已登记两项预期无法在本次闭合的观察项，若届时仍未闭合则不归档）。
