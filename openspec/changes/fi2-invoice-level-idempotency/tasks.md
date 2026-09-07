# fi2-invoice-level-idempotency Tasks

> 🔴 **本包零代码改动、无 apply 阶段**——建造侧已于 2026-08-24 落地并在 `.51` 生产运行（队列 §一 `#371`）。本文件只有「转写核对」与「收口」两段。
> 🔴 **design 审通过前不得开工 1.x 之后的任何一步。** 0.x 是前置闸。
> ✅ **design 审已过 —— Shao Peishen 2026-09-07**（合审材料 §7，答 (a)＝全部决策点按起草方推荐）。闸已开。
> 执行环境：**CC**（纯库内文档，不触碰 `.51`／企微机器人／定时任务）。
> **执行记录**：CC `OP-0907-Z`（2026-09-07，分支 `claude/op0907f-openspec-483`，rebase 到 master `2c03a66` 后施工）。逐条销账见本包 `转写对照表.md`。

## 0. 前置闸（design 审后、动手前）

- [x] 0.1 确认 design 决策点 **6**（`known_invoice_nos` 半开状态收不收紧）与 **7**（门槛张力沉不沉淀成判据）的拍板结果已白纸黑字回填队列 §四 `#106`，不凭记忆
  - 📌 **实际取证路径**：拍板结论的白纸黑字载体 ＝ `1-转型规划/0-全景路线图/合审材料-八包design与三项决策-2026-09-07.md` §7（他答 (a)），并已由队列 §一 `#483` 行状态段记明「design 审已过（合审 §6）」。🔴 **§四 `#106` 行本身的回填属 §3.1，本泳道未做**（见 §3 说明），故本条按「结论已有权威载体、不凭记忆」销账，**不冒充 §四 已回填**。
  - [x] 0.1.1 6 答 **(a)**（非 (b)/(c)）：⇒ 本包**照旧只补 spec**，未改 `ingest_directory` 签名、未新增源码结构用例，范围未扩
  - [x] 0.1.2 7 答 **(a)**：**本包不执行沉淀**。⇒ 须在 §四 `#106` 登记一行「待总线另行派单落地（触碰区＝`.claude/rules/场景建造与合规.md` openspec 门槛段）」——**该登记动作已随 §3.1 一并挂起，登记稿见 §3 说明**
- [x] 0.2 复核 `openspec/changes/fi2-source-inversion` 仍**未 apply** 且其 delta 目标仍**不含 `fi2-tax-export-ingest`**
  - 实测：该包仍在 `openspec/changes/` 下（未进 `archive/`）；`ls openspec/changes/fi2-source-inversion/specs/` ＝ `fi2-ap-driven-intake`／`fi2-daily-workbook`／`fi2-feed-source`／`fi2-recon-notify`／`fi2-recon-report`／`fi2-result-classify` 六个，**不含 `fi2-tax-export-ingest`** ⇒ 零重叠，**无须停手回报**。明细见 `转写对照表.md` §四。

## 1. 转写核对（🔴 事后补包的核心工序：证明 spec 没写超过代码）

- [x] 1.1 白盒重读 `fi2/tax_export_ingest.py` 的模块 docstring「发票级幂等」段（`:38-59`）、`IngestResult` 的两个重复计数字段（`:214-215`）、`load_ingested_invoice_nos()`（`:253-269`）、`ingest_directory()` 的 `known_invoice_nos` 参数（`:1035`／`:1069`）与**两处** `seen_before_this_file` 快照（常规 pass `:1096`、重试 pass `:986`），确认 spec 各条 Requirement 与实现逐条对得上
- [x] 1.2 🔴 **逐条销账**：对照表已落 `openspec/changes/fi2-invoice-level-idempotency/转写对照表.md`
  - [x] 1.2.1 **凡指不出背书的条目删掉** —— 逐条过后**无一条需删**。三条子项（A3-S2「重建后闸随之重建」／A3-容错「表头缺失返空集」／A5-S2「调用方将其打印」）标 ⚠️ **仅代码结构背书、无专属用例**（背书形态 C），已如实登记而非删除；两条表述类子项（A4-缺口／A5-限定／A6-S3）背书形态 ＝ 源码反向证据（背书形态 A）
  - [x] 1.2.2 反向核对已做，6 条如实登记。其中 **④ 一条判为「spec 遗漏项」**：`ingest_directory` **不修改**传入集合（复制一份用）是调用方可依赖的真实契约、docstring 已声明但 spec 未写——**不在本包补**（补条 ＝ 扩范围），登记供下次动本 capability 时一并收
- [x] 1.3 🔴 **MODIFIED 那条逐字比对** —— 已用 Python `difflib.unified_diff` 比对本包 delta 与 `openspec/specs/fi2-tax-export-ingest/spec.md` 现行版本的同名 Requirement 段：**diff 输出只有 1 个 `+` 内容行（那段「本次新增的作用域限定」）＋ 1 个 `+` 空行，零 `-` 行** ⇒ 首段原文与三个 Scenario **一字未改** ✅
- [x] 1.4 🔴 **补做 propose 期标为「未做穷尽推演」的那项**（proposal 残余风险 4）：`invoice.csv` 被误删／截断 × ledger 仍记得源文件 SHA × 重试 pass 的交互面
  - **结论：未发现重复入库路径**，四种形态逐一推演见 `转写对照表.md` §三·1.4。根因 ＝ **闸的状态就是产出物自己**，CSV 变成什么样闸就变成什么样，不存在「CSV 里已有、闸却不知道」的窗口（正是 design 决策点 3 (a) 的设计意图兑现）。
  - ⇒ 按本条判据「**若确有重复路径**，才须登记队列行」：**无重复路径 ⇒ 本次不新立队列行**。
  - 另如实登记两条**非重复**的观察项：① CSV 被删／截断后 `rebuild_invoice_csv.py` 闸① 将永久不过、存量清理工具即不可用（fail-closed，安全但会卡住）；② 写盘中途崩溃留下的半行会一直留在 CSV 里，摄取侧无任何完整性校验。**本包不修**（零代码）。
- [x] 1.5 销 propose 期标为「未核」的两项：
  - [x] 1.5.1 `scripts/rebuild_invoice_csv.py` **确写备份副本**：`invoice.csv.bak-<UTC 戳>`（`:263-265`）与 `.processed_exports.json.bak-<UTC 戳>`（`:285-286`）。**`git check-ignore -v` 实测**（非推断）：两种形态**均被覆盖**，命中 `4-数字员工/财务部/FI2-三单匹配自动对账/.gitignore:21` 的整目录规则 `data/tax_export/`。📌 口径提示：覆盖来自**目录规则**，备份若日后改落别处须重核。
  - [x] 1.5.2 摄取通道**确写** `zhuopin_platform.audit`：`scripts/ingest_tax_export.py:76` 引入 `JsonlSink`，`:84-85` 构造 `ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl"))` 注入 `ZpConnector`。⚠️ **如实限定**：写 audit 的是**连接器访问层**，被幂等闸跳过的重复行**不进 audit**（与 A5-限定 一致）⇒ **不得据此表述为「重复跳过有审计轨迹」**。该痕迹文件亦已被 `.gitignore:2 reports/` 覆盖（实测）。
- [x] 1.6 跑针对性单测（在 `4-数字员工/财务部/FI2-三单匹配自动对账/` 下）：
  - 🔴 **原命令 `-k "duplicate or invoice_nos or ONE_file"` 有漏网，已按实测订正**——它**捞不到主用例** `test_same_invoice_in_two_byte_different_files_is_ingested_only_once`（名中三个关键词一个不含），照抄只会跑到 6 条。**订正后的命令**：
    `python -m pytest tests/test_tax_export_ingest.py -k "duplicate or invoice_nos or ONE_file or same_invoice_in_two_byte" -v`
  - 实测：6 passed（6.91s）＋ 1 passed（3.82s）＋ 2 passed（3.23s，含 `test_retry_does_not_re_add_an_invoice_another_file_already_contributed`）＋ `tests/test_rebuild_invoice_csv.py` **14 passed**（3.31s）
  - ⇒ proposal §Impact 列的 **7 个用例全部存在且全绿、名称无漂移** ⇒ **proposal 无错引用需更正**；另 2 条同族用例未列入 proposal 清单，已在对照表 §二·⑥ 补记（proposal 原文不追改）

## 2. 验证

- [x] 2.1 `openspec validate fi2-invoice-level-idempotency --strict` ⇒ `Change 'fi2-invoice-level-idempotency' is valid`
- [x] 2.2 `openspec validate --all --strict` ⇒ **173 passed / 0 failed**。基线（本包 propose 当次）＝ 172 passed / 0 failed；差额 +1 item ＝ 期间合入 master 的 `followup-approval-cooldown-5min`（commit `d0d5f04`）。**零新增失败** ✅
- [x] 2.3 本包零代码改动，**未跑 FI2 全量回归**；1.6 那几次针对性跑已足够。另附跑 `工具-场景包intent闸lint.py --enforce` ⇒ 退出码 0、无违规（本包判为深化类·永久豁免）

## 3. 收口

> 🔴 **本节 3.1–3.4 四项本泳道未做，原因写死于此**：本泳道为 worktree 隔离的 CC 泳道，看护者（批 `B-0907_Y`）下的硬口径为「**只 push 自己那条分支，不碰主仓工作区、不 ff master、不在主仓 commit**」。两份队列真身与 §二 批次登记均在主仓工作区，`§四 #106`／`§一 #371` 亦属他人触碰区（关他人队列行 ＝ 🟡 档）。⇒ **按既有「队列回写待补」机制挂起，登记稿已随本分支落 `1-转型规划/0-全景路线图/队列回写待补/B-0907_Z-*.json`**，待总线在 ff 合入 master 后回灌。

- [ ] 3.1 队列 §四 `#106` 回填：变更包路径、design 审结论（决策点 6 ＝ (a) 半开状态维持靠 spec 守；7 ＝ (a) 沉淀门槛判据，**须总线另行派单落 `.claude/rules/场景建造与合规.md`**）、转写对照表要点；该行原题自 2026-09-03 起已由 (b) 结案，本次补包完成即可整体销号 —— **登记稿已备（`队列回写待补/B-0907_Z-106.json`）**
- [ ] 3.2 队列 §一 `#371` 回填一行指针（本包 ＝ 该行修法的 spec 载体），便于 `fi2-source-inversion` 的硬前置 **F3** 追溯 —— **登记稿已备（`队列回写待补/B-0907_Z-371.json`）**
- [ ] 3.3 队列 §一 `#483` ⑵ 回填并标已完成（⑴ 另见 `sweep-manifest-coverage-guard` 包；**两子项都完才销 `#483` 整行**）—— **登记稿已备（`队列回写待补/B-0907_Z-483.json`，⑴⑵ 合并一稿）**
- [ ] 3.4 §二 批次登记 ＋ 触发一次 sweep，**看一眼 `reports/sweep-commit.log` 末几行确认真落库** —— **登记稿已备（`队列回写待补/B-0907_Z-sec2-待ff合入master后再登.json`，与 ⑴ 包合为同一批次）**
- [x] 3.5 `openspec archive fi2-invoice-level-idempotency -y` —— 已在本分支执行（详见收工报告）。🔴 **archive ≠ 合入 master**：本包 spec 此刻只存在于分支 `claude/op0907f-openspec-483`，**ff 属 🟡 档，本泳道不自行合**
  - [x] 3.5.1 archive 后已复核 `openspec/specs/fi2-tax-export-ingest/spec.md` 里 MODIFIED 那条**只多了那一段**，既有三个 Scenario 未被合并工具改写（复核手段 ＝ `git diff` 该文件，结果见收工报告）
