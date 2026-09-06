# followup-decision-point-gate Tasks

> 🔴 **1／2 已在分支 `claude/op0906r-decision-field-guard` 完成（worktree 内建造，未合入 master）；3 起全部卡在 design 审之后。**

## 0. design 审（🟡 档，须 Shao Peishen 拍板）

- [ ] 0.1 D1 逃生阀留不留（推荐 (a) 不留）
- [ ] 0.2 D2 是否比对「信件 vs 命令行参数」一致性（推荐 (a) 维持不校验，或 (c) 登记追行）
- [ ] 0.3 D3 存量豁免期（推荐 (a) 确认无需）
- [ ] 0.4 D4 与 `followup-readme-phase2` 的排序（推荐 (a) 先收尾那一包）
- [ ] 0.5 复核 D5–D7 三项已落定取舍

## 1. 实现（已完成，待 design 审后方可合入）

- [x] 1.1 importlib 复用 `工具-跟进信frontmatter校验.py`（`parse_frontmatter`／`RE_DECISION`），不新造第二份解析器与正则。
- [x] 1.2 `DECISION_FIELD`／`DECISION_HINT` 常量：四种拒绝形态共用同一句出路文案，措辞只有一处可改。
- [x] 1.3 `_assert_decision_points(letter_path) -> str`：四种拒绝形态（读不到／无 frontmatter／缺或空／形态不合），返回取值供成功路径回显。
- [x] 1.4 `cmd_append` 首段调用本闸，排在读 README 之前；`[PLAN]` 行追加 `｜ 决策点=<取值>`。
- [x] 1.5 `--letter-path` 必填参数 ＋ 模块 docstring 两节（「复用而非重造」补一条、新增「`append` 的 `决策点:` 前置校验」节，含口径来源 P1–P4 指针与「为什么必填」）。

## 2. 单测与回归（已完成）

- [x] 2.1 任务书要求的三例：缺字段拒／`0 项（…）` 放行／`3 项（a / b / c）` 放行。
- [x] 2.2 其余拒绝形态：取值为空／形态不合（`唯一 1 项`）／文件不存在／无 frontmatter（正文里的「决策点」不算数）。
- [x] 2.3 边界与不变量：括号外后缀不被误杀（`IT部#5` 真实语料）／绝对路径可用／`--dry-run` 同样过闸／本闸不改 `set-status` 行为。
- [x] 2.4 argparse 层：缺 `--letter-path` 直接报错（证明"可省略即绕过"这条路已封死）。
- [x] 2.5 `test_工具-跟进信README登记.py` 全绿：**30 passed**（改前 18）。
- [x] 2.6 邻接零回归：`test_工具-跟进信README归档.py`／`test_工具-跟进信README查询.py`／`test_工具-跟进信README行长外置.py`／`test_工具-跟进信frontmatter校验.py`／`test_工具-跟进闸查询.py`／`test_hooks-pretooluse-queue-read-guard.py` 合计 **132 passed**。
- [x] 2.7 真实语料只读冒烟（`--dry-run`，未取锁未写盘）三例：真实信件缺字段 ⇒ 拒；`IT部#5` 带括号外后缀 ⇒ 放行并回显；路径写错 ⇒ 拒。

## 3. 合入（🟡 档，design 审通过后）

- [ ] 3.1 `git merge-base --is-ancestor` 核可快进后 ff 合入 master。
- [ ] 3.2 `git status --porcelain` 核实无任何新形态未跟踪文件（proposal「伴生文件」节的核实方式）。
- [ ] 3.3 `openspec validate followup-decision-point-gate --strict` 通过。

## 4. 文档落字（🔴 前置条件：先真实验活，后改文字）

- [ ] 4.1 `.claude/rules/跟进信与专员.md` 的登记命令示例句补 `--letter-path`（**这一步不依赖验活，可随 3 一起做**——它只是把新的正确用法写对，不是把人守降成机器守）。
- [ ] 4.2 🔴 **前置条件：本闸已在真实起草流程里至少拒绝过一次并留痕。** 满足后才改 `skills源码/zhuopin-followup-letter/SKILL.md` §5 步骤 1bis 末句「（登记 CLI `append` 校验为机器守，建成前人守）」——删「建成前人守」半句，改为指向机器守。
- [ ] 4.3 同上改文字时 MUST 写明「机器守的只是**登记**这一条路径」，转 docx 与发送两条路径仍是人守（proposal 残余风险 3）。
- [ ] 4.4 🔴 **1bis 主体不退休**（怎么按 P1 拆点、类型怎么标、判据类永不默认生效），不得借本包名义整条降掉。

## 5. 收尾

- [ ] 5.1 队列 §一 `#436` 状态列**只追加一段**（本件编号 `OP-0906-R` ＋ 结论 ＋ commit 哈希）。
- [ ] 5.2 登记 §二 待 commit 批次（路径反引号包裹、只列本批脏改动）。
- [ ] 5.3 覆盖率观察窗口：交付后至少 3 封新信逐封核 `决策点:` 非空，且**逐封判定是否为"为过闸而编"的假数据**（proposal 验收条第 3 项）。
