# platform-bootstrap-ensure-paths Tasks

> ✅ **design 已获 Shao Peishen 2026-08-18 批准（五决策点全按默认项），apply 已于同日完工**（CC，worktree `platform-bootstrap-apply`，commits `1e0ad57`／`f1f1c52`／`6dafcc8`，均已 ff 入 master）。
> 逐项完成情况见各条行尾注；**两处未逐个做的事已如实标注，未假装完工**。

## 1. 前置

- [x] 1.1 Shao Peishen 审 design.md 决策点 1-5（不答按默认项执行）
- [x] 1.2 apply 前重新核对 SC2（opener A2）／O1（opener B）建造 session 是否已收口，避免撞触碰区
- [x] 1.3 复扫全库确认基数 —— 总数仍 35，但**形态分布与 propose 估算不同**：实测 24 非测试入口（B 19／C 2／D 3）＋ 11 个 `conftest.py`（propose 记 18＋12＋5）。SC2 `run_sc2.py` 已由 opener G 节先行修成 B 形态，故按 I 节「G 已跑则跳过」并入批一常规替换。

## 2. 实现 `ensure_paths()`

- [x] 2.1 新建 `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`，实现 `ensure_paths(caller_file, *, strict=False)`
- [x] 2.2 单测覆盖四情形：monorepo 命中 / 扁平命中 / 皆无但环境可导入 / 全无（须 raise）
- [x] 2.3 单测覆盖 `strict=True` 在找不到 monorepo 标记时必然 raise
- [x] 2.4 确定 stub 的最终形态（决策点 1(a)），写进 CLAUDE.md §5 作为唯一被允许的样板

## 3. 批一 —— 18 个非测试入口

- [x] 3.1 替换 B 形态 —— 实测 **19 个**（FI1×2／FI2×3／SC1 main／SC2 run_sc2／SC7 agent／SC8 answer_confidence／QD-B run_qd_b_web／wecom×9）。
- [x] 3.2 替换 C 形态 2 个（SC8 `run_baoguan_web.py`／`run_baoguan_dashboard.py`）
- [x] 3.3 替换 D 形态 3 个（FI2 `run_fi2_web.py`／`ingest_tax_export.py`／`scan_tax_export_scheduled.py`）
- [x] 3.4 每个受影响场景全量测试零漂移
- [x] 3.5 模拟扁平布局验证回退 —— 24/24 通过，且**逐个核对解析到的确是构造出的那份底座**（非仓库副本、非全局 editable 指针）。⚠️ 首版验证脚本自身有两个 bug（短路径比对、模块名 import 撞上全局 editable 包）险些给出假结论，修正后才是真验证。

## 4. 批二 —— 12 个 `tests/conftest.py`

- [x] 4.1 替换为 `ensure_paths(strict=True)`
- [x] 4.2 真实构造缺标记环境验证 fail-loud —— 已实测，并沉淀为**常驻回归**（`test_worktree_import_bootstrap.py::test_strict_raises_when_marker_absent_in_all_ancestors`）：该用例**故意让环境中存在一份可导入的平台底座**，若 strict 语义丢失、退化成回退，测试会悄悄跑在"别人的代码"上而依然全绿。
- [x] 4.3 全库回归

## 5. 门禁（决策点 4）

- [x] 5.1 CI lint 新增判据 —— `0-学习与工具/工具-引导样板lint.py`（默认告警不阻断，`--enforce` 才阻断）。**过渡期那一轮真跑出了东西**：首轮命中 10 处，核实后 8 处属另一族（#313④⑤ 刻意设计的兜底桩），据此把判据收窄到「向上逐级搜索祖先目录」这一个签名。
- [x] 5.2 转为阻断 —— CI job `bootstrap-stub-lint` 直接上 `--enforce`。依据：5.1 的过渡期一轮已对**与 CI 同一份 `git ls-files` 扫描面**跑过并据以收窄判据，收窄后存量真实为 0，首次运行即为绿；`git ls-files -c core.quotepath=false` 与全局 `PYTHONUTF8` 两个已知 CI 环境坑均已按既有 `工具-密钥扫描lint.py` 的成熟做法规避。
- [x] 5.3 CLAUDE.md §5 场景固定流程第 1 步「照抄既有场景引导片段」改为指向 stub 样板的一行指针（退休该人守规则）

## 6. 发布收口

- [x] 6.1 三个 `.51` 常驻服务真部署 —— 8091／8093／8094 **＋ 8096 SC2**（超出本条列举范围但必须做：批一改到了它已部署的 `run_sc2.py`，不同步即是 #221/#228 那族「master 与生产分叉」）。四者进程 CreationDate 逐个核对真实刷新，服务器侧 8 个文件 SHA256 与 master 逐字节一致。
- [x] 6.2 逐个冒烟 —— `/api/ping` 与关键页**从笔记本外部**实测 200（四服务全绿，非只在 `.51` 本机）。⚠️ **「一次真实全量重算」只在 SC2 上真实完成**（`run_sc2.py report --mode real`，exit 0／25s／真实 ERP 出表并写快照）；8091／8093／8094 **未逐个触发**——其 HTTP 重算入口在登录门禁之后，SC8 的 CLI 重算入口被既有缺陷 `parents[4]` 越界挡住（已另立 #348），FI2 的 `scan_tax_export_scheduled.py` 可能触发对外通知故未擅自运行。**如实标注为「未逐个做」，不写成已做。**
- [x] 6.3 全库复扫 —— 非 stub 形态命中数 **0**（lint `--enforce` 绿；`for _p in (_HERE, *_HERE.parents)` 仅剩 lint 工具与其单测中的字符串字面量）。**复扫过程另揪出一处遗漏**：11 个 `conftest.py` 与 `run_sc2.py` 的旧 #300 注释块位于 `import sys` 之上、被 import 行与引导块隔开，替换时未被吃掉，留下「文件自称做 A、实际做 B」的陈旧描述，已由 `6dafcc8` 清除（12 处、三种旧文案全库归零）。
- [x] 6.4 回填队列 #345 ② 并 archive —— #345 已转 `[S:done]` 全行收口。🔴 **决策点 5 的另一半未完成，如实登记**：`_find_env()` 同族收拢行已起草并取号 §一 #348，但 `release` **硬阻断**（机制类可动 WIP 24/16 超上限，协议〇.9 措施 C／§四 #58 ⑶ 自 2026-08-17 起由提示改为阻断）；**按 opener I 节明文约束未走 `WIP豁免：` 逃生阀**，故已撤回该行、#348 号留空不复用，**待机制类 WIP 清扫后补立、由值周巡检接**——拟写内容已完整保留在队列 #345 行 ⑤ 内，补立时可直接取用。
