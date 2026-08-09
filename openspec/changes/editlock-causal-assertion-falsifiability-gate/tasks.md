## 0. design 审前置

- [x] 0.1 三选一已由 Shao Peishen 2026-08-07 拍板选 (a)，本变更不重开审议（见 design.md 顶部说明）。

## 1. 单测先行

- [x] 1.1 正例：P0/P1 定级 + 无反引号命令片段 → 拒绝release，提示含"证伪"字样。
- [x] 1.2 反例：P0/P1 定级 + 含反引号命令片段 → 正常通过（不因本项拒绝）。
- [x] 1.3 回归：状态列含被「」/『』引号包裹的 P0/P1 定级引用文本（复述判据本身），引号外无真实 P0/P1 断言 → 不因本项误拦。
- [x] 1.4 与既有④（未核实字样）校验的独立性：一行同时缺证伪命令又含"未核"字样 → violations 含两条独立提示。
- [x] 1.5 既有 ①-⑨ 校验全量回归零漂移（另修正两处既有用例——`test_p0_p1_row_without_unverified_phrase_passes`／`test_quoted_unverified_phrase_alongside_unquoted_p1_does_not_block`——原状态列缺证伪命令片段，⑩落地后需各补一条反引号命令以维持其"应通过"的原始测试意图）。

## 2. 实现

- [x] 2.1 `_validate_release_structure` 新增校验（沿用 `_strip_quoted_spans`/`P0_P1_TOKEN_RE`/`BACKTICK_SPAN_RE`，不新增扫描面，只查 §一 状态列 cells[5]）。
- [x] 2.2 docstring 补充说明第⑩项校验及其边界（"只判有没有、判不了对不对，覆盖2/3；防不住『想过但用了错的证据』"，不得表述为质量保证）。

## 3. 文档降级

- [x] 3.1 实测发现"opener 模板库 §六防线4"字面路径与稳定文件不符（`专线opener模板库.md` §六实为"变量速查"，与"防线"无关；"防线"清单历史上活在环境保障线自己的滚动接力文件里，已滚动更新且未留痕迹消失）——按 design.md 决策点3 落地：在 `专线opener模板库.md` 新增 §〇.12，一行指针说明该人守条目已机制化、正文不再复述，指向本变更与编辑锁④延伸校验。

## 4. 验证

- [x] 4.1 全量回归：`0-学习与工具/test_工具-共享文档编辑锁.py` 128 passed，零漂移。
- [x] 4.2 `openspec validate editlock-causal-assertion-falsifiability-gate --strict` 通过；`openspec validate --all --strict` 75/75 通过。

## 5. 收工

- [ ] 5.1 队列 #285 行回填完工状态（含实现说明的 2/3 覆盖率边界原样保留）。
- [ ] 5.2 `/opsx:archive editlock-causal-assertion-falsifiability-gate -y`。
