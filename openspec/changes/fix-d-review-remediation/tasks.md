# fix-d tasks

## ① .gitignore JSON 泄漏口（P0）
- [x] QD-A `.gitignore` 加 `*.json` 兜底
- [x] QD-B `.gitignore` 加 `*.json`
- [x] FI1 `.gitignore` 加 `*.json`
- [x] SC8 新建根级 `.gitignore`（含 reports/real_frozen/\*.json/\*.db/.env）
- [x] `git check-ignore` 自证：result.json / tests/x.json 均被拦截

## ② Scrubber OEM 别名裸名检测（P0）
- [x] 新增 `_OEM_ALIAS_RE`（比亚迪/BYD/上汽/SAIC/理想/NIO/蔚来等），不使用 IGNORECASE
- [x] 在 `scrub_text()` 接入，_ORG_RE 之后运行（去重兜底）
- [x] 5 新增测试（正例4 + 边界保护3）
- [x] 全套 31 tests 通过（原 26 零回归）

## ③ FI1 L2 改判录入路径（P1，deadline 7/15）
- [ ] 新建 `fi1/confirm.py` CLI（--period/--item/--conclusion/--reason 四参数）
- [ ] 写 `AuditEvent(override_reason=reason)` 到平台 audit
- [ ] `needs_review` 项目关闭前必须有 confirm 记录
- [ ] 补测试（3 cases：正常改判 / 缺 reason 报错 / 重复 confirm 幂等）

## ④ openspec 模板接线（P2，deadline 7/15）
- [ ] 修改 `.claude/commands/opsx/propose.md`，注入 `openspec/templates/proposal-template.md` 两强制节
- [ ] dry-run 验证：`/opsx:propose "测试场景"` 输出包含「知识资产三问」和「验收与晋档条件」两节
