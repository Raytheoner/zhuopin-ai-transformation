# fix-d: Antigravity 评审整改

## 背景

2026-07-04 Antigravity 外部评审（`3-治理与合规/外部评审/Antigravity评审结果-默会知识纠正与批次制机制-2026-07-04.md`）
triage 后识别出 4 项整改项，其中 P0×2 / P1×1 / P2×1：

| 编号 | 优先级 | 问题 |
|------|--------|------|
| ①    | P0 | QD-A/QD-B/FI1/SC8 场景 `.gitignore` 缺少 `*.json` 兜底，CLI `--output result.json` 可泄漏至根目录 |
| ②    | P0 | `qda_prefill/scrubber.py` `_ORG_RE` 不匹配裸名（比亚迪/上汽/理想等无后缀词客户），脱敏建议遗漏 |
| ③    | P1 | FI1 `needs_review` 差异项无 L2 改判入口，审计链缺 `override_reason` |
| ④    | P2 | `openspec/templates/proposal-template.md` 已建，但 `propose.md` 命令未接线，新 proposal 不自动含强制节 |

## 整改方案

### ① .gitignore JSON 泄漏口（P0，已完成）
在 QD-A / QD-B / FI1 的 `.gitignore` 补 `*.json` 兜底；SC8 无根级 `.gitignore`，新建一份覆盖
`reports/`, `real_frozen/`, `*.json`, `*.db`, `.env` 等所有运行产物。
`git check-ignore -v result.json tests/x.json` 自证通过。

### ② Scrubber OEM 别名裸名检测（P0，已完成）
新增 `_OEM_ALIAS_RE`，匹配 `比亚迪|BYD|上汽|SAIC|理想|Li Auto|蔚来|NIO|吉利|长城|奇瑞|特斯拉|广汽|东风|一汽|长安` 等裸名。
- CJK 左边界保护（`[一-鿿]`，不使用 `re.IGNORECASE` 避免 Python 已知 CJK 范围 quirk）
- 右边界只拦截 ASCII 字母/数字（中文句子中 OEM 名后必然紧跟 CJK 动词/助词，故放行）
- 5 新增测试，31 passed（原 26 零回归）

### ③ FI1 L2 改判录入路径（P1，待实现）
新建 `4-数字员工/财务部/FI1-供应链仓库对账/fi1/confirm.py`：
- CLI：`python -m fi1.confirm --period YYYY-MM --item <差异项ID> --conclusion <人工结论> --reason <必填理由>`
- 写 `AuditEvent(scenario="FI1", action="l2_override", override_reason=reason)`
- `needs_review` 项目在 `confirm.py` 未执行前不可关闭
- 不依赖外部服务，纯本地 JSONL 审计

### ④ openspec 模板接线（P2，待实现）
修改 `.claude/commands/opsx/propose.md`：在生成的 `proposal.md` 中注入
`openspec/templates/proposal-template.md` 的两个强制节（知识资产三问 + 验收与晋档条件）。
dry-run 验证新 proposal 包含两节。

## 知识资产三问（强制）
1. **本流程哪些判断是人脑默会经验？** 脱敏边界判定（哪些是 OEM 名、哪些是技术词）。
2. **由谁显性化？** 陈忱（质量部）+ Paul 审定客户名单。
3. **用什么方法提取？** 白名单正则 + 边界规则（已成文 `_OEM_ALIAS_RE` 注释）。

## 验收与晋档条件（强制）
- **本变更包交付后场景所处档位**：档1 mock 验证（QD-A/QD-B/FI1 均在 mock 阶段）
- **晋下一档的条件**：
  - ③ FI1 confirm.py：财务对接人提供真实差异分类口径 + ERP CSV 样本
  - ④ propose.md 接线：下次 `/opsx:propose` 命令输出验证两强制节存在
- **价值指标**：脱敏遗漏率（OEM 裸名漏标）由 100% 降至 <5%（陈忱 7 月批改会可验证）
