# env-anchor-collapse Tasks

> ✅ **design 已审通过**（Shao Peishen 2026-08-25 答晨复盘 D-4/D-5 均选 (a)，登记于队列 §四 #109）：
> **决策点 1 ＝ (c)** 承认作用域但显式化（依据＝他明答「SC1 那份 `.env` 是早期遗留的历史副本」）；
> **决策点 4 ＝ (c)** 默认静默 ＋ 调用方声明 `required` 键清单；其余四点按 design 行内默认。
> **决策点 2 的处置**＝根 `.env` 第 3 行孤立裸 URL 判**误粘贴**、删除并入 apply 首步。
>
> 🔴 **暂不归档｜预期观察窗口：7 天** —— 2.3.x 的 `.51` 真机复验（4 个常驻服务逐个部署冒烟）
> 因本轮为**无头批处理会话、本机 off-LAN** 未执行，见下方「LAN 留步」小节。**未验的不勾。**

## 0. 前置（design 审）

- [x] 0.1 Shao Peishen 审 design.md 六个决策点；决策点 1／4 无默认项已明确答复（见上方）
- [x] 0.2 根 `.env` 第 3 行孤立裸 URL 的处置结论＝**误粘贴，删除**（Shao Peishen 答 D-5 选 (a)）

## 1. 平台底座实现

- [x] 1.1 新增 `5-平台底座/zhuopin_platform/zhuopin_platform/env_anchor.py`，三段锚定：
      `ZP_ENV_FILE` 显式覆盖 > monorepo（marker ＋ `--git-common-dir` 规范化）> 扁平部署根
- [x] 1.2 无 git 环境退化路径：`git` 不可用/非 git 目录/非零退出**均不抛异常**，回落 marker 所在目录
- [x] 1.3 返回值携带实际命中的 `.env` 路径（`EnvLoadResult.path` ＋ `describe()`）；
      🔴 **`EnvLoadResult` 结构上不持有任何键值**，反例单测锁死
- [x] 1.4 按决策点 4(c) 实现 `required=(...)` 键到位检查（**空值视同缺失**；对「凭据由进程环境
      直接注入」同样成立，故 `.51` 常驻服务不会被打挂）
- [x] 1.5 单测 27 例：三种布局各一组 ＋ worktree 与主工作区同解 ＋ 无 git 退化 ＋ 作用域显式化
      ＋ 「不回显键值」反例 ＋ 解析口径不变
- [x] 1.6 🔴 **变异验证**：A 家族现行写法喂给同一套 git worktree 夹具，实测**确实**解出那份
      陈旧副本（`test_mutation_a_family_writing_picks_the_stale_copy`），判据非空转
- [x] 1.7 **（apply 期新增，由单测夹具撞出）** `--git-common-dir` 的结果须自带一次校验：
      规范化后的目录必须**也**含 marker，否则不采纳——否则本仓库若位于另一个外层 git 仓库
      内部（嵌套 clone／上层 `git init` 过），解析会一路跑到仓库外面去。已补 spec ＋ 单测

## 2. 调用点收敛

> 🔴 **实测清单比 design 附录多 3 处：A 家族是 12 不是 9。**
> `compare_kit_date_cumulative.py`／`compare_kit_date_rule1.py`／`find_cumulative_evidence.py`
> **是 2026-08-25 当天新出生的**（commit `734ee18`，晚于 design 那份 08-24 的人工清单），
> **由本变更包新装的门禁自己扫出来**——这恰好是「人工清单会过期、门禁不会」的一个当场证据。

- [x] 2.1 **批一 · 低危一次性 CLI**：`build_golden_real.py`（含并入 #345 stub，它至今自建
      `sys.path`）／`verify_material_board_real.py`／`ingest_tax_export.py`／`probe_u9c.py`
      ＋ 新发现的 `compare_kit_date_cumulative.py`／`compare_kit_date_rule1.py`／
      `find_cumulative_evidence.py`（后者一并补上 #345 stub）
- [x] 2.2 **批二 · 定时任务**：`scan_tax_export_scheduled.py`（#354 的原始举证点）
  - [ ] 2.2.1 🔴 **LAN 留步**：构造真实触发条件验一次告警确实发出（#82 老毛病：建成 9 天、
        每天在跑、一次都没响过）。**本轮 off-LAN ＋ 无人在场，未执行，不接受「跑了没报错」**
- [x] 2.3 **批三 · 常驻服务代码侧**：`run_baoguan_web.py`（8091）／`run_qd_b_web.py`（8093）／
      `run_fi2_web.py`／`run_sc2.py`／`run_baoguan_dashboard.py`
  - [x] 2.3.0 🔴 **`serve.py`（8092 命令中心）改判为「不 import 平台底座」**——见下方「范围改判」
  - [ ] 2.3.1 🔴 **LAN 留步**：`run_baoguan_web.py` → 部署 `.51` → `/api/ping` ＋ 关键页 200
        ＋ 一次全量重算 → 通过后才动下一个
  - [ ] 2.3.2 🔴 **LAN 留步**：`run_qd_b_web.py`（8093）→ 同上四关
  - [ ] 2.3.3 🔴 **LAN 留步**：`run_fi2_web.py` → 同上四关
  - [ ] 2.3.4 🔴 **LAN 留步**：`serve.py`（8092）→ 同上四关
  - [ ] 2.3.5 🔴 **LAN 留步**：`run_sc2.py` 周五自动推送真实触发一次
  - [ ] 2.3.6 🔴 **LAN 留步**：4 个常驻服务的 `REQUIRED_ENV_KEYS` 按 `.51` 实测填实
        （当前刻意留空＝保持今天的行为不变；填之前不得声称决策点 4 已完整落地）
- [x] 2.4 每批改完跑对应场景全量测试 ＋ 平台全量，零回归（见下方「回归」）

## 3. CI 门禁（决策点 5(a)：扩既有 lint、不新起守卫、不改文件名）

- [x] 3.1 扩 `0-学习与工具/工具-引导样板lint.py`：新增判据二「向上逐级找 `.env`」；
      **未改文件名**，改写模块 docstring 说明它现在守两族（并写明为何不改名）
- [x] 3.2 判据锚在 **AST 节点**（`for`/`while` 子树内「`.env` 字面量」与「向上走」的合流），
      不用裸子串——收拢后 9 个入口的 docstring 全在逐字描述该反范式，裸子串会把它们全点亮
- [x] 3.3 豁免清单：`0-学习与工具/` 工具族／`env_anchor.py` 自身／两份含变异夹具的测试／
      `serve.py`；**每条豁免与理由成对登记**，并有单测断言「理由不得为空」
- [x] 3.4 单测 27 例锁死判据，含**变异验证**（A 家族／内联变体／`os.path` 变体／2026-08-25
      新出生的第三变体，喂原文必须红）＋ 两条误判反例（docstring 散文、注释）
- [x] 3.5 **存量已清零**（全库 443 个已跟踪 `.py`，判据二命中 0），单测 `test_env锚定存量已清零` 常驻守
  - [ ] 3.5.1 切 `--enforce` —— 🔴 **按 design 的上线节奏，须先满足「连续一周告警为 0」
        ＋ 2.3.x 的 `.51` 冒烟全过**，两者均未到，**本轮刻意不切**（先确认清零、再关门）

## 4. one-in-one-out 收口（协议〇.9 措施 B）

- [x] 4.1 退休「照抄既有场景的 `.env` 读取范式」这条人守——四份自陈抄袭的 docstring
      （`ingest_tax_export.py`／`scan_tax_export_scheduled.py`／`run_qd_b_web.py`／`run_sc2.py`）
      的「同 XXX 既有范式」字样已随改写全部消失（grep 复核：`.env` 主题零残留）
- [x] 4.2 `4-数字员工/CLAUDE.md` 场景固定流程第 1 步补一行指针（与 #345 引导 stub 那条并列），
      只作指针、不复述判据

## 5. 收口

- [x] 5.1 受影响场景的 `CLAUDE.md`：本次改动落在各场景 `scripts/` 入口的 `load_env()` 内部，
      **对外行为与调用序列未变**，故不新增场景级记忆条目；判据与样板由 `4-数字员工/CLAUDE.md`
      的指针 ＋ lint 承接（守「机制化优于新增人守」，不复述即不漂移）
- [x] 5.2 队列 #354 回写 ＋ §二 批次登记
- [ ] 5.3 `/opsx:archive env-anchor-collapse -y` —— **暂不归档**，见文件顶部；解锁条件＝
      2.2.1／2.3.1-2.3.6 的 LAN 留步项全过 ＋ 3.5.1 切 `--enforce`

---

## 范围改判（apply 期实测，须留痕）

**`1-转型规划/AI运营指挥中心/serve.py` 不 import 平台底座**，改为**内联同一套解析语义 ＋
等价性测试守**。

- **为什么**：该服务「零三方依赖」是**既定设计原则**（其文件顶部就三处写明，`simple_gate`
  与 `access_log` 已因同一理由各自内联一份）；`.51` 上由 `deploy-server.ps1` 注册的计划任务跑的是
  **裸 `python serve.py`**，实测其部署脚本**既不建 venv、也不 `pip install -e zhuopin_platform`**。
  若在此 import 平台底座，8092 命令中心会在 `.51` 上直接起不来——**而本地测起来永远是绿的**
  （#345 原话：「本地永远能找到仓库根标记，本地全绿与它毫无关系」）。
- **例外不能没有约束**：新增 `1-转型规划/AI运营指挥中心/tests/test_serve_env_anchor_parity.py`
  （8 例），对同一套夹具**逐布局**断言两份实现给出同一答案，含 worktree 场景与变异验证。
  spec 已补一条 Requirement 把这个手段写成契约。
- **其实质缺陷已修**：原 `_find_env` 从 `ROOT` 向上找最近的 `.env`，从 worktree 跑会拿到陈旧
  副本、门禁口令可能是上一代的。

## LAN 留步（本轮 off-LAN ＋ 无人在场，如实登记，未假装闭合）

`.51` 部署侧的真机复验**一项未做**：2.2.1（告警真实发出）／2.3.1-2.3.5（4 个常驻服务 ＋ SC2
逐个部署冒烟）／2.3.6（`REQUIRED_ENV_KEYS` 按实测填实）。

🔴 **这不是「差不多了」——它恰好是本变更包最该被真机验的那一段**：改的是「凭据从哪来」，
而 `.51` 是唯一一个**没有 git、且布局与开发机不同**的环境，其解析走的是第 ③ 段扁平部署锚点，
**开发机全绿与它毫无关系**（#345 的原话，本变更包在 `serve.py` 一处又撞见同一件事）。

## 回归（本轮实测，零漂移）

| 范围 | 结果 |
|---|---|
| 平台底座 | **407 passed, 1 skipped**（380 基线 ＋ 27 新增 `test_env_anchor.py`） |
| SC8 | **503 passed, 4 skipped** |
| QD-B | 151 passed, 30 skipped |
| FI2 | 179 passed, 9 skipped |
| SC2 | 155 passed |
| AI 运营指挥中心 | **22 passed**（14 基线 ＋ 8 新增 parity） |
| 企微机器人服务 | 498 passed, 1 skipped |
| 引导与凭据锚定 lint | ✓ 通过（443 个已跟踪 `.py`，两条判据均 0 命中） |
| `openspec validate --strict` | ✓ 通过 |

⚠️ **既有测试被改判 1 份，如实登记（非放宽）**：
`4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_run_baoguan_dashboard_env_resolution.py`
原先用 AST 从源文件里抽 `_find_env`/`load_env` 出来在合成布局里 `exec`，对「这两个函数还在文件里」
是硬依赖——收拢后 `_find_env` 已删除，故必然失效。改为断言**脚本所调用的那个收拢实现**，
并新增一条结构守（AST 断言脚本确已 `from zhuopin_platform.env_anchor import load_env`，
防止有人把查找逻辑又抄回脚本里）。**三条原有契约一条没少，两条变异验证逐字保留，
并新增「worktree 与主工作区同解」一条**（原实现做不到，故原文件里根本没有这条）。用例 7 → 10。
