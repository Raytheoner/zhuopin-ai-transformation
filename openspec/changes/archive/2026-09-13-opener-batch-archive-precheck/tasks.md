# opener-batch-archive-precheck Tasks

> 🟩 **本包状态：design 审已签认（Shao Peishen 2026-09-12 回 `4:P1a,P2a,P3a,P6ab另立`），apply 已由 CC 泳道 `OP-0912-Z`（分支 `claude/op0912z-p1-archive-precheck-apply`，2026-09-12）完成；下列勾选只勾本棒真做完且附手段的项。**
> 出件 2026-08-25（队列 #397，#395 已并入）；apply 母行 §一 `#561`。**未归档**——7.3 属 🟡 关包动作，留待 ff master 后由看护者／总线执行（见 7.3 行内）。
> 单测文件＝`0-学习与工具/test_工具-opener派出前校验.py`（35＋1 用例，`pytest` 全绿，2026-09-12）；下文「T:」＝该文件内用例名前缀。

## 0. design 审前置（🔴 阻塞全部后续任务）

- [x] 0.1 Shao Peishen 审 **决策点 1**：四态判定表（C 态"归档命中即完成、不读状态列"；D 态 fail-open）。**无默认项。** ✅ 签认 (a)，留痕＝`design.md` `## Decisions` 节首签认段（2026-09-12，经 `OP-0912-E` 转达）。
- [x] 0.2 Shao Peishen 审 **决策点 2**：锚点沿用 opener 标题、`§四 #N` 排除、多行号取合取。**无默认项。** ✅ 签认 (a)，同上。
- [x] 0.3 Shao Peishen 审 **决策点 3**：挂点位置与共用 helper；跳过不得流入哨兵判定。**无默认项。** ✅ 签认 (a)，同上。
- [x] 0.4 Shao Peishen 审 **决策点 6**：派单件 status 义务 (a)+(b)，(b) 另立一行紧跟 #396。**无默认项。** ✅ 签认 (a)+(b)、(b) 另立＝队列 §一 `#572`（本包不做）。
- [x] 0.5 决策点 4／5 按建议 (a) 执行（不答即按建议——二者均不改变对外语义，符合默认项两个前提）。✅ 未另行改动，按 (a)：不缓存；只加两个可选开关。

## 1. 单测先行（真实行号回放，不用构造数据）

> ⚠️ 2026-09-12 现取：`#395`／`#396` 已于 2026-09-09 清扫迁入 `归档-202609.md`（L323／L324），live 已无 `[S:done]` 且从未进归档的 #395 可回放 ⇒ B 态改用夹具（临时 git 仓库、真身路径、原样复刻 #368 归档行）；A／C／D 态夹具＋真数据双跑。

- [x] 1.1 A 态：`#397`（live 机制环境 · 现为 `[S:blocked]`，非 done）⇒ 派出。T:`test_1_1_A态`；真数据 `--row 397 --include-archive --format json` → `carrier=live, done=false, reason=live-open`。
- [x] 1.2 B 态：`#395`（live 机制环境 · `[S:done]`）⇒ 跳过，理由 `live-done`。T:`test_1_2_B态`（夹具）；真数据现用 `#443`（live `[S:done][D:机]`）→ `live-done`。
- [x] 1.3 C 态：`#368`（`归档-202608.md` 第 583 行）⇒ 跳过，理由 `archived`。T:`test_1_3_C态`；真数据 → `file=…归档-202608.md, line=583, reason=archived`。
- [x] 1.4 🔴 **C 态防回归（本包最关键的一条）**：断言 `#368` 判定**不依赖 `cells[5]`**。T:`test_1_4_C态防回归`——同时断言 `status_field=="open"` 与 `done==True`；真数据回显亦为 `"status_field": "open", "done": true`。
- [x] 1.5 D 态：不存在的行号（`#9999`）⇒ **派出** ＋ 告警 `unresolved`。T:`test_1_5_D态`＋`HelperTests.test_四态映射`。
- [x] 1.6 D 态：无行号标题（A2 的 `协议〇.8／§四 #44`）⇒ 派出 ＋ 告警，且文案与 1.5 **可区分**（`no-row-ref` vs `unresolved`）。T:`test_1_6_无行号标题`＋`test_四态映射`。
- [x] 1.7 锚点排除：A22 标题 `#353／§四 #108(a)` ⇒ 只抽出 `353`。T:`test_1_7_锚点排除`。
- [x] 1.8 合取语义：仅一行 done ⇒ **派出**；两行皆 done ⇒ 跳过；archived＋unresolved ⇒ 派出。T:`test_1_8_合取`；真数据 `队列 #368／#397` → 派出（08-25 泳道计划 A27 回放同）。
- [x] 1.9 假阳性防护：`#368` 命中首格为 `368` 的那一行，正文提及行（夹具 363/364/§二/§四 88）不命中。T:`test_1_9_假阳性防护`；真数据 line=583（`grep -n "^| *368 *|"` 独立核得 583）。
- [x] 1.10 章节归属：archive 中 `§四 #88` 存在 ⇒ 查 §一 `#88` 不得命中它。T:`test_1_10_章节归属`（夹具）；真数据 §一 #88 命中的是 `归档-202607.md:91`（真 §一 行），非 `202608.md:1028`（§四）。
- [x] 1.11 多 §一 表：`归档-202608.md` 内多个 §一 表（H2 `## §一` ×2、H3 `### §一` ×2、`## §一 #214` 无表段）全部被扫到，逐份解析后合并。T:`test_1_11_单文件多个节一表`。
- [x] 1.12 🔴 哨兵短路：被跳过的 opener **不得**被判为 `NO-SENTINEL`；v1 不 `break`、v2 不停泳道。T:`RunnerHookTests.test_1_12_v1_*`／`test_1_12_5_2_v2_*`（桩 claude，被跳过项无 .log、后续项照跑、退出码 0）。
- [x] 1.13 `-Force` 绕过校验，且日志留痕 `[Force]`。T:`test_1_13_Force`／`test_v1_Force`／`test_v2_Force`。

## 2. 实现：`工具-队列查询.py`（决策点 5）

- [x] 2.1 新增 `--include-archive`（默认关）与 `--format json`（默认 text）。
- [x] 2.2 归档件发现：glob `1-转型规划/0-全景路线图/跨桌任务队列-归档-*.md`（`ARCHIVE_DIR_REL`＋`ARCHIVE_GLOB` 常量，spec 已写契约）。
- [x] 2.3 归档侧章节匹配 `^#{2,3}\s*§?\s*一[、\s·]`（`ANY_SECTION_HEADING_RE`，兼容 live／archive 写法、H2/H3、单文件多表）。
- [x] 2.4 JSON 契约按 design 决策点 5：`carrier=archive ⇒ done=true`，**不看 `status_field`**（`_run_lookup_json`）。
- [x] 2.5 回归：不传新开关时，输出与退出码与现状**逐字一致**。手段：分支脚本 vs 纯 master `4fb9eab` 脚本，同 10 组命令（`--row 368/397/561/9999/88/443/1`、`--digest`、`--digest --grep`、`--file …`）stdout+stderr+exit 逐组 md5 比对 **10/10 同字节**；T:`test_2_5_*` 两条钉住文案。⚠️ 现状「未找到」exit＝**1**（非本文原写的 0，design 2026-09-12 已更正），逐字不变以 master 现状为准。

## 3. 实现：`工具-opener派出前校验.ps1`（新增，决策点 3）

- [x] 3.1 `Set-OpenerDispatchDecision -Openers -RepoRoot [-Force] [-Quiet]`，补 `Skip`/`SkipReason`（另附 `QueueRows`/`PrecheckNote`）。
- [x] 3.2 锚点抽取：先剥 `§四 #N(x)` 与 `§二 …`，再取 `(?:队列|§一)\s*#N[／#M…]`（`Get-OpenerQueueRowIds`）。
- [x] 3.3 调 Python 只读 JSON `done`，**不解析中文文案、不依赖退出码**（`Invoke-QueueRowLookup`，只认 stdout 以 `{` 开头的行）。
- [x] 3.4 Python 调用失败／JSON 解析失败／helper 文件缺失 ⇒ **fail-open**（派出 ＋ 告警）。T:`test_3_4_fail_open_查询工具缺失`／`_崩溃`／`test_3_4_helper缺失_v1_v2_均fail_open`。

## 4. 挂接 v1（`工具-opener批处理执行.ps1`，v1.2）

- [x] 4.1 dot-source helper；在 `-Only` 过滤后（现 L84–95）调用一次。
- [x] 4.2 `foreach` 内 `Skip` ⇒ `continue`，记 `SKIPPED`，**在状态计算之前短路**（现 L123）。
- [x] 4.3 汇总表与收尾提示加 `SKIPPED` 行（含行号与理由），另落 `<日志目录>/skipped.txt`（`git check-ignore -v` → `.gitignore:50 **/reports/`，不新增未忽略形态）。
- [x] 4.4 `-DryRun` 显示跳过标记与理由。T:`test_v1_DryRun`。
- [x] 4.5 **#395 并入项**：停批提示改为 `-Command` 形态整行可粘贴命令（现 L159，保留 -Plan／-FullAuto／-Model／-Force）。T:`test_4_5_v1_停下时续跑提示是整行可粘贴命令`（桩无哨兵触发 NO-SENTINEL 后正则命中整行）。

## 5. 挂接 v2（`工具-opener批处理执行v2.ps1`，v2.3）

- [x] 5.1 dot-source helper；在 `-Only` 过滤后、泳道分组前调用一次（现 L133–147，design 2026-09-12 更正的 L121 之后位点）。
- [x] 5.2 分组时滤除 `Skip` 成员；**整泳道被跳空 ⇒ 不 `Start-Job`**（泳道名从未跳过成员取，空泳道根本不进队列）。T:`test_1_12_5_2_v2_*`／`test_v2_全部跳过_无泳道`。
- [x] 5.3 泳道清单打印反映真实将执行的成员。T:`test_v2_DryRun_泳道清单只含实际将派出的成员`。
- [x] 5.4 `SKIPPED` 进汇总表、`summary.txt`（`SKIPPED=N`＋逐条 `[skipped]`）与 `summary.json`；退出码不受跳过影响。T:`test_5_4_v2_退出码不受跳过影响_有FAIL仍为1`。

## 6. 端到端回放验收

- [x] 6.1 用 `本周计划-2026-08-24.md` 原文回放（v1 `-DryRun`，pwsh 与 Windows PowerShell 5.1 各一次）：**A4 被跳过 ✅**（`#368 archived@跨桌任务队列-归档-202608.md:583`）。⚠️ 「其余 13 项照常派出」是 08-25 时点的预期，2026-09-12 数据上另有 5 项因所引行**其后已迁归档**而同被跳过（A0 #383/#384/#389→202608:541/542/545；A1 #371/#375→202608:584/585；A8 #355→202609:320；A9 #352→202609:319；A14 #361→202609:600），9 项照常派出、2 项 `no-row-ref` 告警（A2/A5）——每一处跳过都附命中载体行号可复核，属数据漂移而非判据过宽。
- [x] 6.2 用 `建造波次-2026-08-25-泳道版.md` 回放（v2 `-DryRun`）：6 泳道成员正确，A25（`#401`→202609:354）跳过，A27 `#397／#396` 按合取派出。
- [x] 6.3 v1 与 v2 各跑一次 `-DryRun`（同一 08-25 计划）：跳过标记与原因两处一致（均且仅 A25）。
- [x] 6.4 价值指标基线填真值：A4 实测 **4 分 14 秒（4.2 分钟）**，手段与互证见 `proposal.md` 价值指标段 🟩 注。

## 7. 收口

- [x] 7.1 零回归：分支侧 7 份相关测试文件同命令跑全，失败集 ⊆ 纯 master `4fb9eab` 失败集（两条 `test_工具-共享文档编辑锁.py::ReleaseStructuralValidationTests::test_row_length_*` 在 master 同命令逐条复现；`test_工具-opener块lint.py`／`--digest` 两侧输出一致）。实测数见 §一 `#561` 追段。
- [x] 7.2 队列回写：§一 `#561`（apply 母行）与 `#397` 追段；`#395`／`#396` 已在归档件内不动（历史记录不追改）。
- [x] 7.3 `/opsx:archive opener-batch-archive-precheck -y`——🟩 **已执行（2026-09-13 03:3x 本地，Cowork 环境总线 `OP-0912-E`，Shao Peishen 当轮回「全按推荐」＝定夺 2a）**：分支 `claude/op0912z-p1-archive-precheck-apply` 已经六道守卫机器 ff 入 master `a6f75dc`（四 ref 一致），归档前置「产出已在 master」由此满足。🔴 **§8 三项刻意不勾**——它们是「不在本包范围」的如实登记，不是遗漏：8.1 属 `#396` 自己的活；8.2 已另立队列 §一 `#572`；8.3 建议登记 §四 交值周清扫。原文：🟡 **关包属关行类动作，本泳道无权**（`#561` 行内「归档动作本身属 🟡，本棒只出建议不执行」）；留待分支 ff 入 master 后由看护者／总线执行。

## 8. 不在本包范围（如实登记，非遗漏）

- [ ] 8.1 **#396 治标**（9 份派单件逐份核实改对）——#396 自己的活（#396 已清扫入 `归档-202609.md`）。
- [ ] 8.2 **sweep 派单件 status 常驻告警**（决策点 6 的 (b)）——已另立队列 §一 `#572`，本包不碰 `工具-落库sweep.py` 一行。
- [ ] 8.3 **归档 `#368` 状态列与任务列自相矛盾**（design 取证二附带发现）——本包判据刻意不依赖它，修不修不影响正确性；建议登记 §四 提请值周清扫在迁移时同步状态列。
