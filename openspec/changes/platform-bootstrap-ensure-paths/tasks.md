# platform-bootstrap-ensure-paths Tasks

> 🔴 **本变更包尚未获批，以下任务一律不得开工**。等 Shao Peishen 审 design.md 五个决策点后再排期。

## 1. 前置

- [ ] 1.1 Shao Peishen 审 design.md 决策点 1-5（不答按默认项执行）
- [ ] 1.2 apply 前重新核对 SC2（opener A2）／O1（opener B）建造 session 是否已收口，避免撞触碰区
- [ ] 1.3 复扫全库确认基数（当前 35 个文件 / 4 种形态；apply 时可能已变）

## 2. 实现 `ensure_paths()`

- [ ] 2.1 新建 `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`，实现 `ensure_paths(caller_file, *, strict=False)`
- [ ] 2.2 单测覆盖四情形：monorepo 命中 / 扁平命中 / 皆无但环境可导入 / 全无（须 raise）
- [ ] 2.3 单测覆盖 `strict=True` 在找不到 monorepo 标记时必然 raise
- [ ] 2.4 确定 stub 的最终形态（决策点 1(a)），写进 CLAUDE.md §5 作为唯一被允许的样板

## 3. 批一 —— 18 个非测试入口

- [ ] 3.1 替换 B 形态 13 个（FI1×2／FI2×3／SC1／SC7／SC8 answer_confidence／QD-B run_qd_b_web／wecom×9 中的非重复项，apply 时以实测清单为准）
- [ ] 3.2 替换 C 形态 2 个（SC8 `run_baoguan_web.py`／`run_baoguan_dashboard.py`）
- [ ] 3.3 替换 D 形态 3 个（FI2 `run_fi2_web.py`／`ingest_tax_export.py`／`scan_tax_export_scheduled.py`）
- [ ] 3.4 每个受影响场景全量测试零漂移
- [ ] 3.5 模拟扁平布局验证回退（临时构造兄弟目录）

## 4. 批二 —— 12 个 `tests/conftest.py`

- [ ] 4.1 替换为 `ensure_paths(strict=True)`
- [ ] 4.2 真实构造缺标记环境，验证 fail-loud 仍然报错（不是"应该会"，要实测）
- [ ] 4.3 全库回归

## 5. 门禁（决策点 4）

- [ ] 5.1 CI lint 新增判据：非 stub 形态的内联引导即违规（过渡期先告警不阻断）
- [ ] 5.2 过渡期结束后转为阻断
- [ ] 5.3 CLAUDE.md §5 场景固定流程第 1 步「照抄既有场景引导片段」改为指向 stub 样板的一行指针（退休该人守规则）

## 6. 发布收口

- [ ] 6.1 🔴 三个 `.51` 常驻服务真部署：8091 保供看板 / 8093 QD-B / 8094 FI2
- [ ] 6.2 🔴 逐个冒烟：`/api/ping` + 关键页 200 + 一次真实全量重算
- [ ] 6.3 全库复扫：非 stub 形态命中数降至 0
- [ ] 6.4 回填队列 #345 ②，`/opsx:archive`
