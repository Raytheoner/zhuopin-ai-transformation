# sweep-manifest-coverage-guard Tasks

> 🔴 **本包零代码改动、无 apply 阶段**——建造侧已于 2026-08-29 落地并 ff 入 master（commit `38f3898`）。本文件只有「转写核对」与「收口」两段。
> 🔴 **design 审通过前不得开工 1.x 之后的任何一步。** 0.x 是前置闸。
> 执行环境：**CC**（纯库内文档，不触碰 `.51`／企微机器人／定时任务）。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 确认 design 决策点 **5**（口头人守例外撤不撤）与 **6**（跳过要不要接企微）的拍板结果已白纸黑字回填队列 §四 `#136`，不凭记忆
  - [ ] 0.1.1 若 5 答 (a)：**本包不执行撤回**，只在 §四 `#136` 登记一行「待总线另行派单落地（触碰区＝根 `CLAUDE.md` §3／`.claude/rules/队列与落库.md`）」
  - [ ] 0.1.2 若 6 答 (b)：**本包不扩范围**，spec 里「出声形态限于日志」那条 Requirement 保持原样，另开变更包时以 MODIFIED 改写
- [ ] 0.2 复核 `openspec/changes/sweep-startup-nonblocking` 与 `sweep-ops-webhook-cutover` 两个在途包与本包**无 spec 重叠**（design「触碰区核对」里标为「写作时只读核对、未加锁」的那项，在此销账）

## 1. 转写核对（🔴 事后补包的核心工序：证明 spec 没写超过代码）

- [ ] 1.1 白盒重读 `0-学习与工具/工具-落库sweep.py` 的 `_DECLARED_PATH_TAIL_RE`／`_DECLARED_PATH_REJECT_CHARS`／`_looks_like_declared_path()`／`_manifest_coverage_gap()` 与 `main()` 内的调用点，确认 spec 六条 Requirement 与实现逐条对得上
- [ ] 1.2 🔴 **逐条销账：spec 里每一条 SHALL/MUST 必须指得出一处代码或一条测试断言背书。** 对照表附进本包（新建 `转写对照表.md`），逐行写「Requirement → 代码位置／测试用例名」
  - [ ] 1.2.1 **凡指不出背书的条目，删掉，不留在 spec 里**——事后补包最大的失真形态就是「spec 写的比代码实际做的多」（`retroactive-mechanism-specs` 已确立的转写纪律）
  - [ ] 1.2.2 反向也要过一遍：**代码里有、spec 里漏掉的行为**如实补记（补进 spec 或在对照表里写明「有意不写入 spec，理由＝…」）
- [ ] 1.3 跑一次 `python -m pytest "0-学习与工具/test_工具-落库sweep.py" -k "ManifestCoverage"`，确认 proposal §Impact 列出的 6 个用例**全绿且确实存在**（用例名若已漂移，以实测名为准更新 proposal，不留错引用）
- [ ] 1.4 🔴 **现网复核形状判据的实测数字**：proposal 与 design 里引用的「182 行／1544 个片段／757 个非路径／344 个形状合格」是 2026-08-29 的快照。**重跑一次取现值**，若已显著漂移，在对照表里注明「原数字＝2026-08-29 快照，现值＝…」，**原文不追改**（历史记录不追改口径）

## 2. 验证

- [ ] 2.1 `openspec validate sweep-manifest-coverage-guard --strict` 通过
- [ ] 2.2 `openspec validate --all --strict` 复核**不引入新失败**（与本包 propose 前的基线对比，不是「全绿」——基线本身可能已有失败）
- [ ] 2.3 本包零代码改动，**无需跑全量回归**（同 `retroactive-mechanism-specs` 2.2 的既有判法）；1.3 那次针对性跑已足够

## 3. 收口

- [ ] 3.1 队列 §四 `#136` 回填：变更包路径、design 审结论（决策点 5/6）、转写对照表要点、**并按该行原文「补完即整体销号」的约定处置该行状态**
- [ ] 3.2 队列 §一 `#483` ⑴ 回填并标已完成（⑵ 另见 `fi2-invoice-level-idempotency` 包；**两子项都完才销 `#483` 整行**）
- [ ] 3.3 §二 批次登记 ＋ 触发一次 sweep，**看一眼 `reports/sweep-commit.log` 末几行确认真落库**（协议〇.8 已记：触发不等于一定会落库）
  - [ ] 3.3.1 🔴 **登记时别把本包文件路径写成会被自己拦住的形态**——本包若在 worktree 建造并自行 commit 合入，那些路径 MUST NOT 再用反引号写进文件清单（spec「覆盖范围须被如实声明」那条 Requirement 的登记侧口径，**本批就是它的第一个自测**）
- [ ] 3.4 `/opsx:archive sweep-manifest-coverage-guard -y`
