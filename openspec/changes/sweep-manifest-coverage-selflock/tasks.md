# sweep-manifest-coverage-selflock Tasks

> 🔴 **design 审通过前不得开工 1.x 之后的任何一步。** §0 是前置闸。
> 🔴 本包**含代码改动**（与 `2026-09-07-sweep-manifest-coverage-guard` 那份零代码的事后补包不同），apply 阶段须实机跑测试。
> 执行环境：**CC**（纯库内，不触碰 `.51` ／企微机器人常驻／定时任务）。
> propose 出件：CC `OP-0910-E`，泳道 `507-sweep-selflock`，分支 `claude/op0910e-507-sweep-selflock`。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 确认 design 决策点 **D1–D5** 的拍板结果已白纸黑字回填队列 §一 `#507`，不凭记忆；**D4 是阈值项、按根 `CLAUDE.md` §5 属「本项无默认」**，未见明确答复即不得开工 ④
- [ ] 0.2 与在途包 `sweep-manifest-scoped-stage`（队列 §一 `#479`）**再核一次触碰区**：两包都要改 `_process_normal_batch`（前者改 `git add` pathspec、后者＝本包 ② 改提交信息正文），语义不冲突但文本同段 ⇒ 由总线定谁先 apply、谁后 rebase。**本包不自行裁定**
- [ ] 0.3 **复现本包全部实测数字**（propose 期的现取表会过期，同队列 §一 `#522`）：
  - 解析 `reports/sweep-commit.log` 全量跳过记录 → 去重缺项路径 → 逐条跑 `git ls-tree -r --name-only HEAD` 与 `git check-ignore -q --no-index --` 归类
  - 直接 import `工具-落库sweep.py` 调 `_parse_section_two` / `_classify_section_two_rows` / `_resolve_batch_files` / `_manifest_coverage_gap`，对**当前** §二 待处理批次复算「现行判据跳过数 vs 新判据跳过数」
  - propose 期基线（2026-09-10）：日志 760 条 / 48 批次；缺项路径 113 条 ＝ A16(gitignore) / B89(HEAD) / C8；当前 §二 待处理 36 个批次，现行判据跳过 2、新判据跳过 0
  - 🔴 **数字变了不追改 propose 原文**，把新值与判读写进本节，并说明定性结论是否被推翻

## 1. 实现（`0-学习与工具/工具-落库sweep.py`）

- [ ] 1.1 ①**判据换锚**：`_manifest_coverage_gap()` 增两条排除
  - [ ] 1.1.1 `HEAD` 存在性：新增只读辅助（一次 `git ls-tree -r --name-only HEAD`，本轮内缓存），匹配规则**复用** `_resolve_batch_files` 的「精确相等 或 `/` 后缀」，🔴 **不另起一套**
  - [ ] 1.1.2 `.gitignore` 命中：`git check-ignore -q --no-index --  <片段>`，🔴 **`--no-index` 不得省**（省了已跟踪路径不被报告，判定会漏）
  - [ ] 1.1.3 🔴 两处新增的 git 子进程调用**必须留在既有 fail-open 的 try 覆盖范围内**（design D6）——`ManifestCoverageFailOpenSourceTests` **一行不改**，靠它转不转红来验
- [ ] 1.2 ③**形状判据补三条 reject**：含反斜杠即拒 ／ `^[A-Za-z]:` 盘符绝对路径即拒 ／ 不含 `/` **且不在 `HEAD` 仓库根层级**即拒（🔴 `CLAUDE.md` 例外，实测反例）
- [ ] 1.3 ②**部分装入自陈**：`_process_normal_batch()` 在 N<M 时给提交信息正文追加自陈段（清单 M 条 / 实际装入 N 条 / 未装入逐条列举＋归类）；**标题一字不改**；N==M 时**不加任何东西**
- [ ] 1.4 ④**连续跳过计数与升格 §四**
  - [ ] 1.4.1 状态文件 `reports/sweep-manifest-skip-state.json`（已实测被 `.gitignore:50` 的 `**/reports/` 覆盖，复核命令见 proposal §伴生文件）
  - [ ] 1.4.2 计数：本轮被跳过 +1；本轮成功落库归零
  - [ ] 1.4.3 达 K 轮升格：**整套范式复用** `_escalate_long_lived_orphans_to_section_four()`（编辑锁 `acquire --reserve 1 --section 四` → `append-row` 位置式 `--cell`（🔴 不用 `--set`，兜底桩无 `SECTION_COLUMN_NAMES`）→ 当日同批次去重 → 失败只留日志、不改退出码），🔴 **不改那个函数的签名与判据**
  - [ ] 1.4.4 跳过日志降频：同一批次由每轮一条改为「首轮一条 ＋ 每次升格一条」
- [ ] 1.5 全段 docstring 按本项目惯例写清「判据 ＋ 成因 ＋ 实测数字 ＋ 两个方向的失手」，🔴 **改锚的成因与 `#136` 原判据的关系必须写在代码里**，不能只留在变更包中

## 2. 测试（`0-学习与工具/test_工具-落库sweep.py`）

- [ ] 2.1 `ManifestCoverageUnitTests` 增：清单项已在 `HEAD` ⇒ 不判缺项 ／ 清单项被忽略 ⇒ 不判缺项 ／ 既不在 `HEAD` 也未被忽略 ⇒ **仍判缺项**（队列 `#507` 期望产出② 的「三态」）
- [ ] 2.2 🔴 **事故本体回归用例**：以 `6557047` 的真实输入形态（清单 8 条，其中 2 条已在 `HEAD`、6 条为新建）构造，断言**仍判缺项、仍整批跳过**。这是本包不得放松 `#136` 的唯一证据
- [ ] 2.3 形状判据三条新 reject 各一条断言；🔴 **另加一条 `CLAUDE.md` 仍被认领**的反例断言（实测反例，不加就会被下一个人一刀切掉）
- [ ] 2.4 ② 自陈段：N<M 时提交信息含自陈且标题逐字不变 ／ N==M 时提交信息与改动前一致
- [ ] 2.5 ④ 升格：达 K 轮追行一次 ／ 当日重复不追 ／ 落库后计数归零 ／ 锁被占时只留日志且退出码不变
- [ ] 2.6 🔴 **非恒真自证**：把 1.1 的两条排除旁路掉后重放 2.1 的同一输入，断言它**重新被判缺项** —— 证明放行确实来自本包，而非被别的既有检查顺手放过（同 `sweep-manifest-scoped-stage` 既有范式）
- [ ] 2.7 `ManifestCoverageFailOpenSourceTests` **不改一行**，跑通即为 design D6 的销账证据

## 3. 验证

- [ ] 3.1 `python -m pytest "0-学习与工具/test_工具-落库sweep.py" -k "ManifestCoverage" -v`（propose 期基线：9 passed / 30 subtests，189.58s）
- [ ] 3.2 `python -m pytest "0-学习与工具/test_工具-落库sweep.py" -q` 全量，与本分支起点基线对比，**零新增失败**
- [ ] 3.3 `openspec validate sweep-manifest-coverage-selflock --strict` ＋ `openspec validate --all --strict`，记录 passed/failed 与基线差额及其来源
- [ ] 3.4 🔴 **`--dry-run` 实机跑一轮**：`python "0-学习与工具/工具-落库sweep.py" --dry-run`，逐条核对本轮被跳过/放行的批次与 0.3 的复算一致

## 4. 历史回扫（队列 `#507` 期望产出④，design D5(a)）

- [ ] 4.1 落地后**现取**一次当前 §二 待处理批次的跳过情况，逐条登记：哪些已自动消化（正常落库／既有「遗留尾巴补销」`#328` 路径）、哪些仍被拦
- [ ] 4.2 仍被拦的逐个点名并归因（预期全部为「清单写了仓库里没有的路径」＝ 登记错误）；🔴 **只报不改**——订正登记写法属登记方，机器不替人改别人写的清单（同 `#136` 既有取舍）
- [ ] 4.3 propose 期已点名的 4 个历史卡死批次（`B-0902_64` / `B-0908_BN` / `B-0830_20` / `B-0830_24`），逐条现取核对其行是否仍在 §二 待处理；已归档的写明「已归档，不再回扫」

## 5. 收口

- [ ] 5.1 队列 §一 `#507` 回填：变更包路径、design 审结论逐点、实测数字、⑤回扫结果；按该行「期望产出①②③④」逐项销账后再议销号
- [ ] 5.2 队列 §四 `#136` 追一段：本次改锚的判据与成因、`6557047` 回归实测结论、`#136` 原防护未被放松的证据（2.2 用例名）
- [ ] 5.3 §二 批次登记 ＋ 触发一轮 sweep，看 `reports/sweep-commit.log` 末几行确认真落库
  - [ ] 5.3.1 🔴 **登记时别把本包文件路径写成会被自己拦住的形态**——本包文件在本分支自行 commit，若 ff 尚未合入 master，主仓工作区对它们没有脏改动。**本包 ① 落地后这一条已不再是坑**（它们会落进「已在 HEAD」而被视为已覆盖），但在 ① 合入 master 之前仍按 `#136` 旧行为登记
- [ ] 5.4 `openspec archive sweep-manifest-coverage-selflock -y`；🔴 **archive ≠ 合入 master**，ff 属 🟡 档、待总线派发
