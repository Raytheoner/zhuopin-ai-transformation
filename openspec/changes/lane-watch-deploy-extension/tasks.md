# lane-watch-deploy-extension Tasks

> 队列 §一 `#478` 四项期望产出缺一不算完；本清单逐条对应，完工后回写 `#478`。
> 🔴 **本轮（`OP-0907-G`，2026-09-07）只做 §0**：propose ＋ design 起草。§1–§5 全部**未开工**，须待 design 审通过（🟡 档 ③）后方可 apply——**未审即改三处载体，等于绕过本包自己要求的门禁。**

## 0. 本轮范围（propose ＋ design 起草）

- [x] 0.1 读 `#478` 行内四条 MUST 判据与核心约束原文（`工具-队列查询.py --row 478 --field all`）
- [x] 0.2 只读核对四份输入指针：`工具-泳道看护状态机.py:126` 起 `TRANSFER_ACTIONS`／`zhuopin-lane-watch/SKILL.md` ⏭️ 段与分工表／`lane-watch-mode/design.md` D1 与「为什么单独设一档」节／`zhuopin-lan-closeout/SKILL.md`（被指向方）
- [x] 0.3 `proposal.md`：含两条 MANDATORY 节（守卫退休问答、`.gitignore` 覆盖问答，后者附 `git check-ignore -v` 实测输出）＋ 知识资产三问 ＋ 验收与晋档条件
- [x] 0.4 `design.md`：七个决策点各带 (a)/(b)/(c)、各自代价、推荐项与默认项；🔴 核心约束「指向而非复制」落在决策点 2 与决策点 6
- [x] 0.5 delta spec 两份：`specs/lane-watch/spec.md`（MODIFIED 两条既有 requirement）＋ `specs/lane-watch-deploy-authorization/spec.md`（ADDED 五条）
- [x] 0.6 🔴 自检：本包全部产出中，`zhuopin-lan-closeout` 执行纪律的可执行文本出现次数 ＝ 0（本轮人工核；机器判据待 §4 落地后接管）
- [x] 0.7 🔴 自检：`工具-泳道看护状态机.py`／`zhuopin-lane-watch/SKILL.md`／`lane-watch-mode/design.md` 三处载体本轮零改动（`git status` 核）
- [ ] 0.8 **design 审**（🟡 档 ③）：Shao Peishen 逐条批改七个决策点 ＋ 裁定 design §五「未决」三项；**未过不得进 §1**

## 1. 主体改动（`0-学习与工具/工具-泳道看护状态机.py`）

- [ ] 1.1 `TRANSFER_ACTIONS` 处注释扩写：分类不变（决策点 1a），补条件放行分支说明与指针；**不写纪律正文**
- [ ] 1.2 新增 `authorize_deploy()` ＋ `deploy-authorize` 子命令：前置三查（LAN `effective == "on"`／该项已有 `transfers` 记录／授权文本非空），任一不过即拒绝 ＋ 非零退出
- [ ] 1.3 放行输出只打印指针（被指向方路径 ＋ 小节 ＋ 一句 MUST 现读），**不打印任何步骤内容**（决策点 2a）
- [ ] 1.4 新增 append-only 字段 `deploy_authorizations`／`deploy_attempts`（schema 见 design §二），逐项粒度、无批量形态、无撤销机制（决策点 4a）
- [ ] 1.5 `summary` 新增一行现取（本批授权 N 次／执行 N 项及结果分类），同 `count_lock_hits` 模式；🔴 会话不得自算
- [ ] 1.6 🔴 不动 `classify()`／`_ALL_TIERS`／`transfer_out_lane()` 的既有语义

## 2. `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`

- [ ] 2.1 顶部分工表：根边界那一格不动，「遇到需要判断的动作」列补时序说明（他在环且 on-LAN 可同 session 续做，纪律仍取自收口正本）
- [ ] 2.2 ⏭️ 档段（步骤 3 与步骤 5）：转出仍先发生这条不改，其后追加条件放行分支，**写成指针**
- [ ] 2.3 红线节「D1 ⏭️ 档本包永不执行」改判为一行指针；🔴 旧版原文原样保留、标注取代关系（同「推送目标」节 2026-09-06 手法）
- [ ] 2.4 版本节追加一条沿革；同目录 `CHANGELOG.md` 同步

## 3. `openspec/changes/lane-watch-mode/design.md`

- [ ] 3.1 D1 表 ⏭️ 档「处置」格追加条件分支（分类仍为 ⏭️）
- [ ] 3.2 「为什么 `.51` 部署要单独设一档」节追加一段：该节论证在放宽后为何仍成立（论证落点是纪律归属，不是执行地点）
- [ ] 3.3 D7 上限 6 的论证按 0.8 审定结论处置（决策点 7 推荐 (a)：补说明、不改上限）

## 4. 反例守卫（`#478` 期望产出 ③）

- [ ] 4.1 新建 lint 工具（落点与命名按决策点 6⑴(a) 的既有范式 `工具-引导样板lint.py`）：判据词**运行时从 `zhuopin-lan-closeout` 正本提取**，工具内不写死词表
- [ ] 4.2 提取失败 ⇒ fail-closed 报错（🔴 绝不"抽不到词就当没违规"）
- [ ] 4.3 覆盖四类载体：`skills源码/zhuopin-lane-watch/**`／`工具-泳道看护状态机.py`／`openspec/changes/lane-watch-mode/**`／**本变更包自身**（归档后 specs 路径一并纳入）
- [ ] 4.4 序列门槛与指针句豁免：apply 期实测校准后回填 lint docstring（决策点 6⑶(a)，本 design 刻意不预设数字）
- [ ] 4.5 🔴 **负例验证**：人为注入一段复制文本，确认被拦下——只跑绿不算数
- [ ] 4.6 挂 CI job

## 5. 单测（`0-学习与工具/test_工具-泳道看护状态机.py`）

- [ ] 5.1 三项前置各自不满足时均拒绝 ＋ 非零退出（LAN off／LAN unknown／未先转出／授权为空，逐个用例）
- [ ] 5.2 三项全过时放行并落 `deploy_authorizations` 一条，含探针原值
- [ ] 5.3 `classify("deploy_51")` 在有无授权两种情形下均返回 ⏭️（决策点 1a 的机器钉死）
- [ ] 5.4 授权逐项粒度：第二项不复用第一项授权
- [ ] 5.5 `summary` 现取报出授权与执行统计
- [ ] 5.6 探针一律注入替身、状态文件指向临时夹具；🔴 **不连 `.51`、不发真实请求**
- [ ] 5.7 既有 70 例回归全绿（新增前基线：70 passed）

## 6. 收口

- [ ] 6.1 `openspec validate lane-watch-deploy-extension --strict` 全绿
- [ ] 6.2 回写队列 `#478`：状态、产出路径、四项期望产出逐项对账
- [ ] 6.3 解除过渡期口径：三处载体同改合入 master 后，opener 方可改写；**合入前一律维持「🔴 不部署」**
- [ ] 6.4 `/opsx:archive lane-watch-deploy-extension -y`（全部 [x] 后执行）
- [ ] 6.5 **真实链路验证（晋档 2 前提）**——须等到某批泳道产出**确实需要上 `.51`** 时才做；🔴 **不得拿 FI9 那批当样例**（无部署对象，`#478` 行内点名）。如实登记不假装闭合。
