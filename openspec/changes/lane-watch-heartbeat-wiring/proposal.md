# lane-watch-heartbeat-wiring Proposal

> 归属：队列 §一 `#565`（2026-09-12 立行，Cowork 环境总线 `OP-0910-H`）；本轮由派单件 `OP-0912-B` 起草（诊断＋设计＋调用侧最小落地，触发批 `B-0911_W`）。
> 类别：**机制/工具类变更包**（守护本仓库 opener 生成器与泳道看护心跳约定自身），受 `openspec/config.yaml` 两条 MANDATORY 约束，见下文。
> 🔴 **本轮范围＝propose ＋ design ＋「调用侧」最小修复已落地**：`工具-opener生成.py`／`opener骨架.md`／`工具-opener块lint.py`／`zhuopin-lane-watch/SKILL.md`（示例命令与缺陷登记）已在本轮改完并过全部单测；**心跳工具本身 `工具-泳道看护状态机.py` 与看护状态机读侧一行未动**——方案 B（见 design 决策点 5）**只设计、不落地**，apply 留给 Shao Peishen 过审后另开泳道。

## Why（为什么做）

**一句话**：看护批 `B-0911_机制收口` 5 条泳道全部做完、五条分支全部 ff 进 master，但 `工具-泳道看护状态机.py summary --batch B-0911_机制收口` 报「本批终态泳道 0 条」、`reports/lane-heartbeat/` 两小时窗口零新文件——**看护者用 Task/Agent 扇出的子任务泳道，其 opener 正文里从未出现过心跳约定**，心跳机制形同虚设，全靠人工事后逐份读 5 份收工通知重建状态（队列 `#565` 行内原文：「这正是心跳机制本该提供的那种守，现在靠的是人工」）。

### 成因：两处约定都不在子任务能读到的地方（实测坐实，非推断）

**成因半 ⑴ · 心跳约定只写给「看护者自己」看**

| 载体 | 内容 | 是否进子任务 prompt |
|---|---|---|
| `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md` 步骤 4 | 「心跳一律跑命令写……」完整约定 | **否**——这是看护者读的规则正本，子任务不读 SKILL.md |
| 看护件 `看护件-泳道看护批B-0911_机制收口-2026-09-11.md` §一「硬边界继承」 | 「🔴 心跳跑命令写 `... heartbeat --lane <泳道> --text "..."`（收工带 `--done`）」 | **否**——本泳道现取该件全文核实：§一 是看护者读给自己的四条提醒，§三 各 `### A<N>` 泳道 opener 的代码块正文（真正被当 Task/Agent 子任务 prompt 使用的那部分）逐字比对 `工具-opener生成.py` 的 `subtask_lane` 输出，**只有三条机器口径**（并行上限／push分支/收工哨兵），**一个字没提心跳** |

`opener骨架.md`【CC · 子任务泳道】骨架节明写「正文三行之后固定追加三条机器口径……由 `工具-opener生成.py` 自动写入」——**心跳压根不在这三条清单里**，`工具-opener生成.py` 的 `generate_opener()` 在 `variant == "subtask_lane"` 分支里也确实只拼了 `SUBTASK_PARALLEL_NOTE`／`SUBTASK_PUSH_NOTE`／`SUBTASK_SENTINEL_NOTE` 三个常量（本泳道现取源码坐实，2026-09-12）。**这与 `#550` 收工哨兵那次是同一个失效形态**：正文里没写的东西，子任务无从知道要做。

**成因半 ⑵ · 即便调用了心跳，`--done` 不带 `--batch` 也会白写（同批复核发现的第二个坑）**

本泳道在隔离 worktree 内现取一次 `heartbeat --done --batch <测试批次>`，随后跑 `summary --batch <该批次>`，输出多打了一行：

```
⚠ 另有终态泳道 8 条批次归属未知（未计入任何批；成因＝`heartbeat --done` 未带 `--batch`）
｜逐条：419-ops-webhook；459-sweep-pth；519-scanner-test；530-evidence-guard；
532-bot-domain；533-editlock-deadlock；535-fixture-date；537-anchor-count
```

即：**历史上确实有泳道调用过心跳**（说明工具本身能用），但 `SKILL.md` 步骤 4 给的示例命令（`heartbeat --lane <泳道> --done --text "..."`）本身就没带 `--batch`，8 条历史泳道因此全部落进「批次归属未知」、从未被任何一次 `summary --batch <某批次>` 统计到过。**这不是本次实撞的直接根因（`B-0911_机制收口` 是压根没调用），但会让"调用了却算不进批次"的现象在下一次复发**，故本包把 `--batch` 一并写死进提醒，不能只补心跳这一半。

### 心跳工具本身是否有问题？（question ①③④ 的实测结论——不是推断）

- **真实完整命令**（`heartbeat --help` 现取）：
  ```
  python 0-学习与工具/工具-泳道看护状态机.py heartbeat --lane LANE --text TEXT [--done] [--batch BATCH] [--json]
  ```
  `SKILL.md` 与看护件里写的 `... --lane <泳道>` 是缩写，实际参数名与顺序如上；`--batch` 是可选项、**不传不报错**（这正是坑的来源——静默丢弃同族，同 `#487` 子项「一个参数没传却仍产出内容」的反面：这里是"一个可选参数不传，行为悄悄退化成不可用状态却不报错"）。
- **worktree 隔离下心跳工具本身正常**：本泳道在隔离 worktree（`C:\Dev\zhuopin-ai\.claude\worktrees\agent-a1ba3d09237312495`）内现取一次 `git rev-parse --path-format=absolute --git-common-dir` → `C:/Dev/zhuopin-ai/.git`，随即跑 `heartbeat --lane test-op0912b-verify-565 --text "..."`，回显 `💓 泳道 test-op0912b-verify-565 心跳已写入：C:\Dev\zhuopin-ai\reports\lane-heartbeat\test-op0912b-verify-565.md`——**写入落在主 checkout，不是本 worktree**。`工具-泳道看护状态机.py::REPO_ROOT` 直接复用 `工具-共享文档编辑锁.py::REPO_ROOT`（按 `git rev-parse --git-common-dir` 解析），与 `lane-watch-heartbeat-visibility`（`#504`）已修复的读写同锚结论一致。**⇒ 方案 B（改看护状态机读子任务收工报告的哨兵字段）不是紧急必需**，心跳工具本身可用；本次的缺口纯粹是"调用侧没把约定传给执行者"。验证后已清理测试用心跳文件与状态文件条目，不留痕（`reports/` 不入库，清理只为不干扰其他会话读 `summary`）。

### 为什么必须走 openspec（门槛判定）

命中 `.claude/rules/场景建造与合规.md` §二 **③ 改变既有模块对外语义**——`工具-opener生成.py --variant subtask_lane` 的输出契约（此前"恒为三行 ＋ 三条机器口径"）本次改为"恒为三行 ＋ 四条机器口径"，且新增 `工具-opener块lint.py` 形态⑩ 这一道新判据（改变"子任务泳道 opener 怎样算合格"这个全项目口径）。两条命中任一即必走，本件命中两条。

### 守卫退休问答（MANDATORY · 协议〇.9 措施 B / one-in-one-out）

**本次不退休任何既有守卫，是新增一道**——如实说明为何不能对等退休一条：

- 本包新增的形态⑩守卫的对象（"子任务泳道 opener 正文缺心跳约定"）此前**没有任何守卫**（无论人守还是机器守）——看护者读 SKILL.md／看护件时会"看到"心跳约定，但那不构成对**子任务泳道 opener 正文**的守卫，两者是不同的对象。故本包不是"用机器守替换人守"（`#550`／`#504` 那种 one-in-one-out 场景），而是**填补一个此前完全没有守卫覆盖的对象**。
- 类比 `#550`（收工哨兵）先例：那次同样是"新增一道生成器强制注入 ＋ 一条 lint 形态"，proposal 里同样未退休既有守卫（哨兵此前也没有任何守卫），项目已接受这种"新对象、新守卫、不硬凑退休"的处置方式，本包沿用同一判据。

### 伴生文件的 .gitignore 覆盖问答（MANDATORY · 队列 #328 子项②）

**不适用（不新增文件名形态）**：本包不新增任何自动生成的文件——心跳文件形态 `reports/lane-heartbeat/<泳道>.md` 沿用 `lane-watch-heartbeat-visibility`（`#504`）已确认覆盖的既有形态（`.gitignore:50:**/reports/`），本包只改**谁在什么时候被提醒去调用**它，不改它的产出位置或命名。opener骨架.md／工具-opener生成.py／工具-opener块lint.py 三个改动对象都是仓库内**已跟踪的源码/文档文件**，非自动生成物。

## What Changes（改什么）

**① `0-学习与工具/工具-opener生成.py`**（本轮已改，🟢 起草范围内的调用侧修复）

- 新增常量 `SUBTASK_HEARTBEAT_NOTE`：含心跳完整命令模板（`--lane`／`--text`／`--done --batch <批次>`）、`--repo-root`／`--heartbeat-file` 不存在的提醒、长等待补写规则。
- `variant == "subtask_lane"` 分支的强制注入列表由 `[PARALLEL, PUSH, SENTINEL]` 三条扩为 `[PARALLEL, HEARTBEAT, PUSH, SENTINEL]` 四条（心跳排在并行上限之后、push 规则之前）。
- 🔴 **不新增必填字段**：`--lane` 取值不由生成器预先算好塞入，沿用 SKILL.md 既有的 `<泳道标识>` 字面占位约定（同 `<批次>`／`<波次>`／`<泳道名>` 一样，是留给执行者按上下文——通常是队列行号——自行填的模板占位，不是本工具的必填参数）——设计理由见 design 决策点 2。

**② `1-转型规划/0-全景路线图/opener骨架.md`**（本轮已改）

- 【CC · 子任务泳道】骨架节：「三条机器口径」改为「四条机器口径」，新增心跳约定说明段（仿 `#550` 收工哨兵段的"有意扩入，不是漏删"写法，注明 `#565`），示例代码块插入心跳行。

**③ `0-学习与工具/工具-opener块lint.py`**（本轮已改）

- 新增形态⑩：子任务泳道 opener 块缺心跳约定行（须同现 `heartbeat` 与 `--lane`）⇒ 报警。判据文档表新增一行，`RULE_EFFECTIVE_BY_FORM`／`FORM_TITLE` 同步登记生效日 2026-09-12。
- 🔴 **不改 `工具-opener批处理执行v2.ps1`**——沿用派单件硬边界，该脚本只读引用未动一行。

**④ 单测**（本轮已改，`test_工具-opener生成.py`／`test_工具-opener块lint.py`）

- `骨架与生成器契约`：三条改四条逐字比对，新增「正本写明心跳行是有意扩入」断言。
- 新增 `心跳强制注入` 类（镜像既有 `收工哨兵强制注入`）：含成品行、排序、其它变体不注入、变异检验删行后 lint 转红四类用例。
- 新增 `形态十_子任务泳道块缺心跳约定` 类（镜像既有 `形态九_子任务泳道块缺收工哨兵`）：正反例、非子任务块豁免、看护者开场词豁免、格式正本自身不命中、生效日登记、骨架自带心跳行七类用例。
- 既有涉 `SENTINEL_LINE` 的"干净样本"共享夹具补齐 `HEARTBEAT_LINE`，保持"共享夹具须满足全部现行判据"既有纪律（同 2026-09-04 扩形态时把 `SETTINGS_CC` 改六字段齐的手法）。
- 全量回归：`test_工具-opener块lint.py`／`test_工具-opener生成.py` 共 210 例 ＋ 40 subtests 全绿。

**⑤ `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`**（本轮已改，示例命令与缺陷登记，非规则本身）

- 步骤 4 心跳命令示例补 `--batch <批次>`（`--done` 分支），并加一句 `--batch` 不能漏的提醒（对应成因半 ⑵）。
- 「已知缺陷与其状态」新增缺陷四：本缺陷的成因、已修状态、指向本变更包；注明方案 B 已记入本包 design、非紧急、未落地。
- 版本历史追加 v2.3 条目。

**⑥ `openspec/changes/lane-watch-heartbeat-wiring/specs/lane-watch-heartbeat-wiring/spec.md`**（本轮新增，ADDED）

- 新增 capability spec：规范"子任务泳道 opener 正文 MUST 内嵌心跳约定"这条此前从未被任何 spec 承载的要求（见下文 Impact）。

**⑦ 方案 B（design 决策点 5）——只设计，不落地**

- 让 `工具-泳道看护状态机.py summary` 改为能从子任务收工报告的结构化哨兵字段（`OPENER_DONE`/`OPENER_PARTIAL`）自动回填终态，作为心跳缺失时的反向兜底。**本轮不实现**：涉及看护状态机工具本身（`check_heartbeat`／`summary` 读侧逻辑），改动面更大，且本次实测心跳工具在 worktree 隔离下已能正常工作（见 Why 节），非紧急缺口。apply 留待 Shao Peishen 过 design 审后另开泳道。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - **「子任务泳道 opener 正文该含哪些机器口径」**：此前完全靠起草人／生成器维护者记得同步骨架与生成器——`#550` 已撞过一次（哨兵漏注入），本次心跳是第二次同类撞车。这条经验此前**没有任何清单化载体**，"三条"这个数字本身就是历史事故堆出来的，下一条新增的机器口径大概率还会重演同一个失效模式（正文里写一句 vs 生成器强制注入，是这条经验里最容易被跳过的一步）。
   - **「`--lane` 该填什么值」**：SKILL.md 全文用字面占位符 `<泳道标识>`，从未显性规定"没有更明确约定时用队列行号"——本包在心跳提醒行里首次把这条隐含默契写成文字，但仍留作提示而非强制参数（决策点 2 的取舍）。
   - **「`--batch` 该不该带」**：`heartbeat --help` 里已标注"🔴 收工强烈建议带上"，但 SKILL.md 步骤 4 的示例命令此前没有——即工具作者知道这条尺度，却没有传导进执行指引，这条差距本包一并补齐。
2. **由谁显性化？** 持有人 **Shao Peishen**（看护机制自身的判据，归他；`#565` 立行依据＝其对该批实测异常的关注）；backup **孙涛**（其缺席时的代理人，范围见 `.claude/rules/场景建造与合规.md`）。
3. **用什么方法提取？** **历史案例反推**——反推依据＝本 proposal「成因」节两组实测（看护件 §三 opener 正文逐字比对生成器输出、`summary` 现取暴露的 8 条历史"批次归属未知"泳道），以及 `#550` 记录的同族坑（正文写一句拦不住，须生成器强制注入）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：**档 1（mock 验证）→ 部分档 2**。`工具-opener生成.py`／`工具-opener块lint.py` 的改动已过全部单测（210 例 ＋ 40 subtests，含新增的心跳专项用例），且已用真实 `工具-泳道看护状态机.py heartbeat` 命令在隔离 worktree 内做过一次真实调用验证（非 mock）；**尚未经过一次真实看护批的端到端验证**（即：用新生成器产出的 opener 真正派发给 Task/Agent 子任务、子任务真的调用了心跳、`summary --batch` 真的报出非零终态泳道）。
- **晋下一档的条件**：
  1. 下一个用 `工具-opener生成.py --variant subtask_lane` 生成 opener 的看护批（≥1 条泳道即可，不要求并行）跑完后，`summary --batch <该批次>` 报出的「本批终态泳道」计数 > 0——判据取自该命令现取输出，不许会话自算。
  2. `工具-opener块lint.py --enforce` 对该批产出的看护件 §三 泳道 opener 零形态⑩告警。
  3. `openspec validate --strict` 全绿（本包自身）。
- **价值指标**（**风险型**指标）：
  - **基线**：`B-0911_机制收口` 批 5/5 泳道零心跳、`summary` 报终态泳道 0 条，看门狗对该批的信号覆盖率**结构上等于 0%**；额外实测 8 条历史泳道因 `--batch` 缺失而"批次归属未知"。
  - **目标值**：新产出的子任务泳道 opener 心跳约定覆盖率 100%（生成器强制注入，非人工记忆）；`--done` 均带 `--batch`。
  - **基线确认人**：Shao Peishen。
- **LLM 判据黄金集**：**不适用**。本包不含任何 LLM 运行时判断，全部为确定性的字符串拼装、正则匹配与文件读写。

## Impact（影响面）

**受影响 specs**：**新增** `lane-watch-heartbeat-wiring`（ADDED，本包 `specs/` 内）。**不修改** `lane-watch`（`lane-watch-mode`／`lane-watch-heartbeat-visibility` 两包的 delta）——那两包管的是心跳工具**读侧**的语义（读写同锚、终态豁免），本包管的是**调用侧**（opener 生成器该不该把心跳约定塞进子任务能读到的正文），是不同的 capability 边界，故新开一个 capability spec 而非对既有 spec 做 MODIFIED，避免把"生成器输出契约"与"状态机运行时语义"混进同一份 requirement。

**受影响代码/文档**（本轮已全部改完）：`0-学习与工具/工具-opener生成.py`、`1-转型规划/0-全景路线图/opener骨架.md`、`0-学习与工具/工具-opener块lint.py`、`0-学习与工具/test_工具-opener生成.py`、`0-学习与工具/test_工具-opener块lint.py`、`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`（示例命令与缺陷登记两处）。

**明确不受影响、且刻意不动的**（本轮）：

- 🔴 `0-学习与工具/工具-泳道看护状态机.py` —— **不动**。心跳工具本身（写侧 `write_heartbeat`／读侧 `check_heartbeat`／`summary`）一行未改；实测已证明其在 worktree 隔离下工作正常。
- 🔴 `0-学习与工具/工具-opener批处理执行v2.ps1` —— **不动**（派单件硬边界，只读引用）。
- 🔴 看护件 `看护件-泳道看护批B-0911_机制收口-2026-09-11.md` —— **不追改**（历史记录不追改，带日期的历史快照件）。
- `HEARTBEAT_STALE_MINUTES_DEFAULT`／终态豁免逻辑（`#504` 已定）—— 不涉及，本包不改"什么算失联"，只改"约定有没有传达给执行者"。

**红线核对**：

- **mock 先行**：opener 生成器与 lint 的改动全部经单测覆盖（临时字符串/临时目录），心跳工具真实调用仅在隔离 worktree 内做过一次只读验证性质的写入（已清理，不留痕）；不触碰 `.51`、不发真实请求、不推企微。
- **audit 留痕**：本包不改变任何 AI 自动决策路径，无需新增 audit 字段。
- **OEM 隔离**：不涉及——不含任何 OEM 技术数据。
- **L2 门禁 / ISO 26262 / ASIL**：不涉及——非安全相关代码，🔴 档四项本包一项不放宽。
- **凭据纪律**：本包全部产出**不含任何口令、URL 值或凭据**。
