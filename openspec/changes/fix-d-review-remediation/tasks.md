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

## ③ FI1 L2 改判录入路径（P1，已完成）
- [x] 新建 `fi1/confirm.py` CLI（--period/--item/--conclusion/--reason 四参数）
- [x] 写 `AuditEvent(override_reason=reason)` 到平台 audit（scenario=FI1, action=l2_override）
- [x] 空 reason 拒绝执行（exit 1），不写 audit
- [x] 补测试（3 cases：正常改判 / 缺 reason 报错 / 重复 confirm 幂等）33 passed 零回归

## ④ openspec 模板接线（P2，已完成）
- [x] 修改 `.claude/commands/opsx/propose.md`，添加 MANDATORY 段落指引两个强制节
- [x] 说明来源：`openspec/templates/proposal-template.md`（Antigravity fix-d ④）
- [x] 注明缺节则 proposal 不完整，不进 design 审（行为约束已在指令中明确）
