# audit-retention-archive Tasks

> 🛑 **design 审通过前不得开工任何一项**（队列 §一 `#358` 领取方栏原文：「design 审通过前不得直接实现」）。
> 起草 `OP-0907-X`【CC】2026-09-07｜**机制/环境类变更包**｜design ＝ `design.md`（status: 待审）
> 🔴 §0 两条是 **design 审的前置**，不是实现的前置——它们的输出会改 D5／D6 的数值。

## 0. design 审前置（⏭️ `.51` 只读取证，属收口批，本线不自跑）

- [ ] 0.1 ⏭️ 取 `.51` 上 `baoguan_access_trace.jsonl` 与同目录其余审计类文件的**真实大小与行数**（`Get-ChildItem`／`Measure-Object -Line` 输出原样贴回）【收口批 `zhuopin-lan-closeout`】
  - 🔴 **判的是「那 309 MB 到底落在哪个文件上」**：若在 `*_access_trace.jsonl` ⇒ `TRACE` 类，D5 阈值就着它定；若在 `baoguan_audit.jsonl` ⇒ `COMPLIANCE` 类，**D5 默认值与 D7 优先级都要重排**。
  - ⚠️ 队列行转述的 309 MB **本包未核实**，不得直接采信（队列行自己写明「不得直接采信本行转述」）。
- [ ] 0.2 ⏭️ 取 `.51` 该盘**剩余磁盘空间**（`Get-PSDrive`／`Get-Volume` 输出原样贴回）【收口批】
  - 决定 D6「封存即压缩 vs 保持未压缩」。
- [ ] 0.3 把 0.1／0.2 的真实输出补进 `design.md`《审前置》节，**再交审**【CC】

## 1. 留存类别与 fail-closed（D1）

- [ ] 1.1 新建 `5-平台底座/zhuopin_platform/zhuopin_platform/audit/retention.py`：`RetentionClass` 枚举（`COMPLIANCE`／`TRACE`／`OPS`）＋ 每类默认阈值【CC】
- [ ] 1.2 `JsonlSink.__init__` 增 `retention_class` 参数；`AuditLogger.jsonl()` 默认 `COMPLIANCE`，`ConnectorAudit` 默认 `TRACE`【CC】
  - 🔴 **42 个既有构造点零改动**（`AuditLogger` 26 ＋ `ConnectorAudit` 16，实测计数）——靠默认值兜住。改动量超出这两处即说明设计跑偏。
- [ ] 1.3 🔴 **断言测试：fail-closed** —— 对未声明类别的文件，封存／删除接口 MUST 拒绝并抛，MUST NOT 从文件名、路径或内容推断【CC】
  - 反向对照组：给一个名叫 `xxx_audit.jsonl` 但未声明类别的文件，**必须照样拒绝**（证明它没在偷偷看名字）。
- [ ] 1.4 🔴 **断言测试：`COMPLIANCE` 类不存在删除路径** —— AST 扫全模块，`COMPLIANCE` 分支下无任何 `unlink`／`remove`／`truncate`／`write_text`／`"w"` 模式打开【CC】
  - 口径同 `coverage_point_ledger.LedgerStore` 无 `delete()`：**append-only 不是纪律，是没有那个函数。**

## 2. 滚动封存与封条（D2／D3／D4／D7／D9）

- [ ] 2.1 封存实现：**锁内**「算上段末行 sha256 → 写续接记录到临时新文件 → 原子 rename 旧文件为段 → 原子 rename 临时件为热文件 → 写封条」【CC】
  - 🔴 顺序不得颠倒（design《三条容易做错》⑵）：先 rename 再新建，中途被杀会留下"热文件不存在、续接记录未写"，下次启动当 genesis 重开链，**段间断链且事后无法与篡改区分**。
  - 🔴 任何一步失败整体回退，**MUST NOT 留下半封存状态**。
- [ ] 2.2 🔴 **断言测试：封存不改一个字节**（D3）—— 封存前后对原热文件内容做 sha256 逐字节比对，段文件必须全等；且断言实现里**没有任何重算 `prev_hash` 的代码路径**【CC】
  - 成因：**2026-07-28 本项目已重算过一次链，且 `verify_chain()` 通过**（CHANGELOG 第 43 行）。⇒ 重算过的链验证永远是 ✅，哈希链对整理动作零防御力。**这是本包唯一一条已经出过事的约束。**
- [ ] 2.3 🔴 **断言测试：封存不跨文件合并**（D9）—— 两个不同场景的热文件各自封存后，段文件数 ＝ 2，MUST NOT 出现任何合并产物【CC】
  - 成因：2026-07-28 那次做的**恰恰是"把两份归并成一份"**；实现者照先例走就会在 OEM 隔离（红线 3）上开洞。
- [ ] 2.4 🔴 **断言测试：封存 MUST NOT 由外部进程执行**（D7）—— 封存入口不得暴露为可对任意路径调用的独立 CLI；对不属于本进程 sink 的路径调用 MUST 拒绝【CC】
  - 成因：2026-06-13 审计报告 P1 实测——锁与 `prev_hash` 缓存**仅进程内有效**，跨进程写同一 JSONL 产生的断链**无法与真篡改区分**。
- [ ] 2.5 封条格式落地：`{segment, line_count, first_line_sha256, last_line_sha256, first_ts, last_ts, sealed_at, sealed_by, prev_segment_seal_sha256}`，封条自身成链【CC】
  - 🔴 `sealed_at` 用本机 `Get-Date` 当场取并显式标基准（UTC vs 本地），不估算。

## 3. 跨段校验与跨段检索（改 `audit-hash-chain`）

- [ ] 3.1 `verify_chain()` 升级为可跨段：沿封条链回溯，逐段重算【CC】
- [ ] 3.2 🔴 **genesis 豁免不得放宽**：只有第 1 段第 1 行可为 genesis；**第 2 段起首行 MUST 是续接记录且 `prev_hash` 非空**，缺则判断链【CC】
  - 🔴 成因：续接记录**看起来很像 genesis**，顺手改成"每段首行都豁免"，就把 2026-08-04 `fix-a-security-compliance-p0` 堵上的绕过原样打开（删光全文件 `prev_hash` 字段重写即整链通过）。**须落正反两组断言。**
- [ ] 3.3 🔴 **四条反向对照组必须全部 `ok=False`**（本包真正的验收，不是陪衬）【CC】
  - [ ] a. 从已封存段删掉一行 ⇒ `ok=False`，且报出**段名 ＋ 行号**
  - [ ] b. 把已封存段整段重算 prev_hash 后重写 ⇒ `ok=False`（封条的段首/末行 sha256 对不上）
  - [ ] c. 直接删掉一整个段文件 ⇒ `ok=False`（封条链断）
  - [ ] d. 篡改封条本身 ⇒ `ok=False`（`prev_segment_seal_sha256` 对不上）
- [ ] 3.4 `read_all()`／`query_by()` 增 `scope` 参数，**默认跨全段**【CC】
  - 🔴 成因：默认只读热文件的话，封存那一刻起「**查不到**」与「**没发生过**」不可区分——本项目最危险的一类静默失败。
  - 断言：封存后 `query_by()` 返回记录数 **≥** 封存前（不减少）。
- [ ] 3.5 `TRACE`／`OPS` 删除动作 MUST 写一条 `COMPLIANCE` 记录（删了哪个文件、几行、时间跨度、谁执行）【CC】

## 4. 退休既有守卫（协议〇.9 措施 B）

- [ ] 4.1 `0-学习与工具/工具-落库sweep.py::_rotate_hooks_audit_log` **降为调用方**：策略取平台层 `OPS` 类默认值，删除 sweep 私有常量 `LOG_ROTATION_KEEP_WEEKS`（当前 ＝ 4）【CC】
  - **退的是"它自己拍板什么该删、删多久"，不是它的行为**——`hooks-audit.jsonl` 是 hook 拦截遥测、非 AI 决策，属 `OPS` 类，删 4 周前的行在新口径下合法且不变。
- [ ] 4.2 🔴 **必须沿用 sweep 既有的软依赖形态**（`工具-落库sweep.py:401-413`，队列 #306 起的兜底桩写法）：import 平台包失败时回落当前行为，**MUST NOT 让 sweep 硬依赖 `zhuopin_platform`**【CC】
- [ ] 4.3 **不动 `_rotate_sweep_commit_log`**（管的是 `reports/sweep-commit.log`，非审计文件，不在射程内）【CC】
- [ ] 4.4 回归：sweep 全量测试绿、零回归（`0-学习与工具/test_工具-落库sweep.py`）【CC】

## 5. 真实文件验证与现网落地

- [ ] 5.1 **只读**比对：对本机 `5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl`（实测 2.58 MB／5,170 行）跑跨段 `verify_chain()`，**不执行封存**【CC】
  - 🔴 **先确认动的是哪一份**：本仓库已知同名多份问题——主工作区那份是活的，`ops/wecom-service-home` worktree 里那份是**停在 08-04 的诱饵**，2026-08-28 环境体检自己先撞了进去并已写下错误结论。
  - ⚠️ 该文件历史上被 2026-07-28 重算过链（原件另存 `-split-archive-2026-07-28.jsonl`，41 行仍在）；跨段校验结果**如实记录，不得为了"好看"调整判据**。
- [ ] 5.2 在 tmp 复制件上跑一次完整封存并逐字节比对（**不动真身**）【CC】
- [ ] 5.3 ⏭️ `.51` 四服务（8091 保供看板／8093 QD-B／8094 FI2／8096 SC2）落地 ＋ 冒烟三件套 ＋ 回滚 SOP【收口批 `zhuopin-lan-closeout`，不在本包合入 master 的验收内】
- [ ] 5.4 ⏭️ 各服务审计文件在重启后继续追加且跨段校验通过【收口批】

## 6. O2 落地（🔴 仅在 Shao Peishen 答 O2 = (a) 时执行）

- [ ] 6.1 锚点台账落 `3-治理与合规/审计链锚点/`，格式取 `.md` 或 `.json`（随 O2 一并拍）【CC】
  - 🔴 **绝不放 `reports/` 下、绝不用 `.jsonl`** —— 实测：`reports/audit-anchor.json` 命中 `.gitignore:41 **/reports/`；`3-治理与合规/审计链锚点/audit-anchor-2026-09.jsonl` 命中 `.gitignore:32 **/*.jsonl`；而同目录 `.md`／`.json` **不被忽略**。放错的后果是**静默的**：文件正常生成、`git status` 永远看不见、锚定形同虚设、不报错。
- [ ] 6.2 落库后**在真仓库原样复跑** proposal §「伴生文件」那 12 条 `git check-ignore -v --no-index` 并逐条贴出真实输出【CC】
  - 🔴 其中第 8 条是**反向对照组**（口径点台账 `采购域.jsonl` 必须仍不被忽略）——本包 MUST NOT 影响 #439 那条例外。
- [ ] 6.3 断言：锚点台账内容**只有哈希／行数／时刻**，MUST NOT 含 `decision`／`evaluator`／`payload`／任何业务字段【CC】

## 7. 收口

- [ ] 7.1 更新 `5-平台底座/CLAUDE.md` 审计段（留存类别与封存语义）【CC】
- [ ] 7.2 `openspec validate audit-retention-archive --strict` 通过【CC】
- [ ] 7.3 全量回归零漂移（平台包 ＋ 各场景包）【CC】
- [ ] 7.4 回写队列 §一 `#358` ＋ 登 §二 批次【CC】
- [ ] 7.5 tasks 全 [x] 后当场 `/opsx:archive audit-retention-archive -y`（「完工即归档」，不得跨 1 个 session）【CC】
  - ⚠️ §0 与 §5.3／§5.4 属 ⏭️ 收口批，若仍未闭合，归档前须按 `暂不归档`／`预期观察窗口：N 天`／`--ack-stale-change` 三选一写明理由。
