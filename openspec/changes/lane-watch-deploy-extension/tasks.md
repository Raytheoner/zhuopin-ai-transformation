# lane-watch-deploy-extension Tasks

> 队列 §一 `#478` 四项期望产出缺一不算完；本清单逐条对应，完工后回写 `#478`。
> 🔴 **第一轮（`OP-0907-G`，2026-09-07）＝ propose ＋ design 起草**（§0）。
> ✅ **design 审 2026-09-07 已过**（Shao Peishen 合审 §2 答 (a)，全部决策点按起草方推荐）。
> 🔴 **第二轮（`OP-0907-AF`，2026-09-07）＝ apply**：§1–§5 ＋ §6.1 已完成，见各条行内实测记录；§6.2–§6.5 的停点与理由写在 §6 各条。

## 0. 本轮范围（propose ＋ design 起草）

- [x] 0.1 读 `#478` 行内四条 MUST 判据与核心约束原文（`工具-队列查询.py --row 478 --field all`）
- [x] 0.2 只读核对四份输入指针：`工具-泳道看护状态机.py:126` 起 `TRANSFER_ACTIONS`／`zhuopin-lane-watch/SKILL.md` ⏭️ 段与分工表／`lane-watch-mode/design.md` D1 与「为什么单独设一档」节／`zhuopin-lan-closeout/SKILL.md`（被指向方）
- [x] 0.3 `proposal.md`：含两条 MANDATORY 节（守卫退休问答、`.gitignore` 覆盖问答，后者附 `git check-ignore -v` 实测输出）＋ 知识资产三问 ＋ 验收与晋档条件
- [x] 0.4 `design.md`：七个决策点各带 (a)/(b)/(c)、各自代价、推荐项与默认项；🔴 核心约束「指向而非复制」落在决策点 2 与决策点 6
- [x] 0.5 delta spec 两份：`specs/lane-watch/spec.md`（MODIFIED 两条既有 requirement）＋ `specs/lane-watch-deploy-authorization/spec.md`（ADDED 五条）
- [x] 0.6 🔴 自检：本包全部产出中，`zhuopin-lan-closeout` 执行纪律的可执行文本出现次数 ＝ 0（本轮人工核；机器判据待 §4 落地后接管）
- [x] 0.7 🔴 自检：`工具-泳道看护状态机.py`／`zhuopin-lane-watch/SKILL.md`／`lane-watch-mode/design.md` 三处载体本轮零改动（`git status` 核）
- [x] 0.8 **design 审**（🟡 档 ③）：✅ 2026-09-07 已过——Shao Peishen 答合审材料 §2 (a)「全部决策点按起草方推荐（含无默认点）」，`design.md` 顶部已回填审过行；材料件＝`1-转型规划/0-全景路线图/合审材料-八包design与三项决策-2026-09-07.md`

## 1. 主体改动（`0-学习与工具/工具-泳道看护状态机.py`）

- [x] 1.1 `TRANSFER_ACTIONS` 处注释扩写：分类不变（决策点 1a），补条件放行分支说明与指针；**不写纪律正文**（`TRANSFER_ACTIONS` 上方注释扩写：分类不变＋条件放行分支说明＋指向被指向方的指针常量，未写任何纪律正文）
- [x] 1.2 新增 `authorize_deploy()` ＋ `deploy-authorize` 子命令：前置三查（LAN `effective == "on"`／该项已有 `transfers` 记录／授权文本非空），任一不过即拒绝 ＋ 非零退出（`authorize_deploy()` ＋ `deploy-authorize`；三查次序 ⑶→⑵→⑴，前两项零副作用先跑，LAN 探针放最后。拒绝 ⇒ `DeployAuthorizationRejected` ⇒ CLI 退出 1）
- [x] 1.3 放行输出只打印指针（被指向方路径 ＋ 小节 ＋ 一句 MUST 现读），**不打印任何步骤内容**（决策点 2a）（`deploy_discipline_pointer()` 只回路径＋小节＋条目＋一句 MUST 现读；单测 `test_deploy_authorize_output_points_at_source_of_truth_only` 钉死）
- [x] 1.4 新增 append-only 字段 `deploy_authorizations`／`deploy_attempts`（schema 见 design §二），逐项粒度、无批量形态、无撤销机制（决策点 4a）（两个 append-only 字段落地；逐项粒度由「转出记录一旦被某条授权 `transfer_index` 绑定即不可再被绑定」实现——无批量形态、无时间窗、无撤销机制）
- [x] 1.5 `summary` 新增一行现取（本批授权 N 次／执行 N 项及结果分类），同 `count_lock_hits` 模式；🔴 会话不得自算（`summary` 多打一行「本批 ⏭️ 档授权放行 N 次｜执行 N 项（done/rolled_back/stopped）」，`count_deploy_authorizations`／`build_deploy_attempt_summary` 现取）
- [x] 1.6 🔴 不动 `classify()`／`_ALL_TIERS`／`transfer_out_lane()` 的既有语义（实测：既有 70 例一条未改、全绿；`classify("deploy_51")` 在有无授权两种情形下均返回 ⏭️）

## 2. `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`

- [x] 2.1 顶部分工表：根边界那一格不动，「遇到需要判断的动作」列补时序说明（他在环且 on-LAN 可同 session 续做，纪律仍取自收口正本）（分工表本包行「遇到需要判断的动作」列补时序说明；「管什么」那一格一字未动）
- [x] 2.2 ⏭️ 档段（步骤 3 与步骤 5）：转出仍先发生这条不改，其后追加条件放行分支，**写成指针**（步骤 3 ⏭️ 段追加条件放行分支＋步骤 5 看护段一行＋步骤 6 收工汇总一行，全部写成指针）
- [x] 2.3 红线节「D1 ⏭️ 档本包永不执行」改判为一行指针；🔴 旧版原文原样保留、标注取代关系（同「推送目标」节 2026-09-06 手法）（红线节改判为「不自行执行、一律先转出，唯一例外见分工表时序放宽一段」；旧版原文 `<details>` 原样保留并标注取代关系）
- [x] 2.4 版本节追加一条沿革；同目录 `CHANGELOG.md` 同步（SKILL.md 版本节新增 v2.1；同目录 `CHANGELOG.md` 新增 2026-09-07 一节）

## 3. `openspec/changes/lane-watch-mode/design.md`

- [x] 3.1 D1 表 ⏭️ 档「处置」格追加条件分支（分类仍为 ⏭️）（D1 表 ⏭️ 档「处置」格追加条件分支，并明写「分类仍是 ⏭️，不因此改判」）
- [x] 3.2 「为什么 `.51` 部署要单独设一档」节追加一段：该节论证在放宽后为何仍成立（论证落点是纪律归属，不是执行地点）（新增「放宽之后本节论证为什么仍然成立」小节：落点是纪律归属，不是执行地点）
- [x] 3.3 D7 上限 6 的论证按 0.8 审定结论处置（决策点 7 推荐 (a)：补说明、不改上限）（按决策点 7(a)：D7 论证 ② 补一段说明、**上限维持 6 不改**，并如实标明「这是判断不是事实」）

## 4. 反例守卫（`#478` 期望产出 ③）

- [x] 4.1 新建 lint 工具（落点与命名按决策点 6⑴(a) 的既有范式 `工具-引导样板lint.py`）：判据词**运行时从 `zhuopin-lan-closeout` 正本提取**，工具内不写死词表（新建 `0-学习与工具/工具-泳道纪律复制lint.py`，命名与落点沿 `工具-引导样板lint.py` 既有范式；判据词运行时从收口正本「执行步骤」小节的「固定N步＝A→B→C→D」＋「不过即X」现取，工具内零词表）
- [x] 4.2 提取失败 ⇒ fail-closed 报错（🔴 绝不"抽不到词就当没违规"）（抽不到小节／抽不到序列／抽到少于 4 个词，三种情形一律退出码 2 报错；单测 `test_fail_closed_when_*` 三例钉死）
- [x] 4.3 覆盖四类载体：`skills源码/zhuopin-lane-watch/**`／`工具-泳道看护状态机.py`／`openspec/changes/lane-watch-mode/**`／**本变更包自身**（归档后 specs 路径一并纳入）（实测覆盖 12 个受守护载体：`zhuopin-lane-watch/**` 2 个、状态机 1 个、`lane-watch-mode/**` 4 个、**本变更包自身 5 个**；归档后 specs 路径已写进 `GUARDED_GLOBS`）
- [x] 4.4 序列门槛与指针句豁免：apply 期实测校准后回填 lint docstring（决策点 6⑶(a)，本 design 刻意不预设数字）（**实测校准值 ＝ 4**，已回填 lint docstring：正本序列共 5 个词，看护侧现存那句警示性缩略引用只带得动 3 个，真副本会把 5 个都带过来；指针句豁免收窄为「同行既有指向动词、又真的指着 `zhuopin-lan-closeout` 正本」）
- [x] 4.5 🔴 **负例验证**：人为注入一段复制文本，确认被拦下——只跑绿不算数（🔴 **负例实测**：向 `zhuopin-lane-watch/SKILL.md` 注入一段照抄文本 ⇒ 退出码 1，报 `SKILL.md:161 命中 5 个判据词`（🔴 具体是哪五个词**此处刻意不复述**——把它们按序抄进本文件，本文件自己就会被这道守卫拦下，实测已如此；要看现取值跑 `--json`）；还原后重跑退出码 0、`git diff` 为空）
- [x] 4.6 挂 CI job（CI 新增 job `lane-discipline-copy-lint`，直接上硬门禁不走告警过渡——上线前正例已实跑清零、负例已实跑拦下）

## 5. 单测（`0-学习与工具/test_工具-泳道看护状态机.py`）

- [x] 5.1 三项前置各自不满足时均拒绝 ＋ 非零退出（LAN off／LAN unknown／未先转出／授权为空，逐个用例）（四个用例：LAN off ／ LAN unknown ／ 未先转出 ／ 转出属别的批次 ／ 授权文本为空，均拒绝且不落任何留痕）
- [x] 5.2 三项全过时放行并落 `deploy_authorizations` 一条，含探针原值（`test_deploy_authorize_records_authorization_with_raw_probe_value`：落一条留痕，含探针**原值** `{status: on, effective: on}` 与绑定的 `transfer_index`）
- [x] 5.3 `classify("deploy_51")` 在有无授权两种情形下均返回 ⏭️（决策点 1a 的机器钉死）（`test_classify_deploy_51_stays_transfer_with_and_without_authorization`）
- [x] 5.4 授权逐项粒度：第二项不复用第一项授权（`test_second_item_does_not_reuse_first_authorization`：第二项在自己转出前被拒，转出后拿到的是绑定另一条转出记录的第 2 条授权）
- [x] 5.5 `summary` 现取报出授权与执行统计（`test_summary_reports_deploy_authorizations_and_outcomes` ＋ `test_cli_deploy_authorize_then_summary`）
- [x] 5.6 探针一律注入替身、状态文件指向临时夹具；🔴 **不连 `.51`、不发真实请求**（全部用例注入 `_prober` 替身、`REPO_ROOT` 指向临时夹具；CLI 用例用 `mock.patch.object(module, "_load_lan_prober", …)`——**零真实网络请求**）
- [x] 5.7 既有 70 例回归全绿（新增前基线：70 passed）（实测 `70 passed` → `87 passed`，既有 70 例一条未改；另有 `test_工具-泳道纪律复制lint.py` 13 例全绿）

## 6. 收口

- [x] 6.1 `openspec validate lane-watch-deploy-extension --strict` 全绿（实测输出 `Change 'lane-watch-deploy-extension' is valid`）
- [ ] 6.2 回写队列 `#478`：状态、产出路径、四项期望产出逐项对账 —— ⏸ **本泳道不写队列**（子任务泳道纪律：不碰主仓工作区、不抢编辑锁），已在收工报告里把四项对账交回看护者代登记
- [ ] 6.3 解除过渡期口径：三处载体同改合入 master 后，opener 方可改写；**合入前一律维持「🔴 不部署」** —— ⏸ **未解除**：本轮只 push 分支，ff 入 master 属 🟡 档，须他一个字母。**在 ff 之前，各批 opener 一律仍写「🔴 不部署」**
- [ ] 6.4 `/opsx:archive lane-watch-deploy-extension -y`（全部 [x] 后执行）—— ⏸ 6.2／6.3／6.5 未闭合，按本条自身的前提不执行
- [ ] 6.5 ⏸ **未做，如实登记不假装闭合**——**真实链路验证（晋档 2 前提）**——须等到某批泳道产出**确实需要上 `.51`** 时才做；🔴 **不得拿 FI9 那批当样例**（无部署对象，`#478` 行内点名）。如实登记不假装闭合。
