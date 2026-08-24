# env-anchor-collapse Tasks

> 🔴 **本变更包停在 design 审，未 apply。下列任务一律不得在 design 获批前开工。**
> 决策点 1 与 4 **无默认项**，须 Shao Peishen 明确答复后才能确定任务 2 与 3 的形态。
>
> 暂不归档：本包尚未 apply（预期观察窗口：待 design 审）。

## 0. 前置（design 审）

- [ ] 0.1 Shao Peishen 审 design.md 六个决策点；**决策点 1（`.env` 有无作用域／SC1 那份是刻意还是遗留）与决策点 4（缺 `.env` 时报错还是静默）无默认项，须明确答复**
- [ ] 0.2 回答 design「顺带发现」中根 `.env` 第 3 行孤立裸 URL 的处置（**本包不动手**，只等结论）

## 1. 平台底座实现

- [ ] 1.1 新增 `zhuopin_platform/env_anchor.py`（模块名以 design 结论为准），实现三段锚定：`ZP_ENV_FILE` 显式覆盖 > monorepo（marker ＋ `--git-common-dir` 规范化）> 扁平部署根（含 `zhuopin_platform` 子目录的祖先）
- [ ] 1.2 无 git 环境退化路径：`git` 不可用/非 git 目录时**不抛异常**，直接用 marker 所在目录（决策点 2 的 `--git-common-dir` 失败回落）
- [ ] 1.3 返回值携带**实际命中的 `.env` 路径**，供调用方回报；🔴 **spec 硬约束：只回报路径、绝不回显任何键值**
- [ ] 1.4 按决策点 4 结论实现 `required=(...)` 键到位检查（若答 (c)）
- [ ] 1.5 单测：三种布局各一组 ＋ **worktree 与主工作区解出同一份** ＋ 无 git 退化 ＋ 「不回显键值」反例单测
- [ ] 1.6 🔴 **变异验证**：把 A 家族现行写法喂给同一套夹具，确认它在 worktree 夹具下**确实**解出错误的那份——判据若不红，说明夹具没造出真实条件

## 2. 调用点收敛（分三批，批次划分见 design 决策点 6；**每批独立 commit**）

- [ ] 2.1 **批一 · 低危一次性 CLI**：`build_golden_real.py`（含把它并入 #345 stub，它至今自建 `sys.path`）／`verify_material_board_real.py`／`ingest_tax_export.py`／`probe_u9c.py`
- [ ] 2.2 **批二 · 定时任务**：`scan_tax_export_scheduled.py`；🔴 **须构造真实触发条件验一次告警确实发出**，不接受"跑了没报错"（#82 老毛病：建成 9 天、每天在跑、一次都没响过）
- [ ] 2.3 **批三 · 常驻服务，逐个来，不许一批推四个**：
  - [ ] 2.3.1 `run_baoguan_web.py`（8091）→ 部署 `.51` → `/api/ping` ＋ 关键页 200 ＋ 一次全量重算 → 通过后才动下一个
  - [ ] 2.3.2 `run_qd_b_web.py`（8093）→ 同上四关
  - [ ] 2.3.3 `run_fi2_web.py` → 同上四关
  - [ ] 2.3.4 `serve.py`（8092 命令中心，`os.path` 变体）→ 同上四关
  - [ ] 2.3.5 `run_sc2.py`（内联无函数变体）
- [ ] 2.4 每批改完跑对应场景全量测试 ＋ 平台全量，零回归

## 3. CI 门禁（决策点 5）

- [ ] 3.1 扩 `0-学习与工具/工具-引导样板lint.py`：新增「向上逐级找 `.env`」形态判据；**不改文件名**（改名会打断 CI 配置与全库引用），改模块 docstring 的适用范围说明
- [ ] 3.2 判据须能区分「缺陷本身」与「讲解这个反范式的散文」——锚在 AST 节点或结构位置，**不用裸子串**（#355 与 #324 两次教训）
- [ ] 3.3 豁免清单：`0-学习与工具/` 工具族、`wecom-aibot-service` 的 `5-平台底座/.env` 显式指名族、lint 自身与其单测
- [ ] 3.4 单测锁死判据，含**变异验证**（喂 A 家族修改前原文必须红）
- [ ] 3.5 存量清零后才切 `--enforce`（先确认清零、再关门）

## 4. one-in-one-out 收口（协议〇.9 措施 B）

- [ ] 4.1 退休「照抄既有场景的 `.env` 读取范式」这条人守——**落点是四份自陈抄袭的 docstring**（`ingest_tax_export.py`／`scan_tax_export_scheduled.py`／`run_qd_b_web.py`／`run_sc2.py`），随 2.x 各批改写时逐条删掉"同 XXX 既有范式"字样
- [ ] 4.2 `4-数字员工/CLAUDE.md` 场景固定流程第 1 步补一行指针（与 #345 引导 stub 那条并列），**只作指针、不复述判据**

## 5. 收口

- [ ] 5.1 场景 CLAUDE.md 更新（受影响的 SC8／QD-B／FI2／SC2 各自「路径引导」节补 `.env` 半边）
- [ ] 5.2 队列 #354 回写销号 ＋ §二 批次登记
- [ ] 5.3 `/opsx:archive env-anchor-collapse -y`
