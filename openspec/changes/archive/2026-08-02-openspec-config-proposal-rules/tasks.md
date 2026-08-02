## 1. A 段：可行性验证（rules 能否强制产出含两节）

- [x] 1.1 摸清 1.7.0 `config.yaml`/`rules` 语义，读 `dist/core/artifact-graph/instruction-loader.js`、`dist/core/project-config.js` 源码确认字段结构与读取时机（运行时读取，非构建时烘焙）
- [x] 1.2 双盲测验证：spawn 独立子代理（不知情"这是在测试 rules 机制"），仅按 `.claude/commands/opsx/propose.md` 标准流程执行，验证 `rules.proposal` 内容能否使产出 proposal.md 含《知识资产三问》《验收与晋档条件》两节——盲测 1（propose.md 含指针注释）与盲测 2（propose.md 不含任何定制内容，纯上游文案）均通过
- [x] 1.3 结论：rules 语义**匹配**（可行），不需要转 A2 自定义 schema 载体

## 2. B 段：落地迁移

- [x] 2.1 `openspec/config.yaml` 新增 `rules.proposal`（4 条规则：MANDATORY 总纲 + 两节各自填写要求 + 一条显式反转"rules 不进产出"默认语义的元说明）
- [x] 2.2 `.claude/commands/opsx/propose.md` 硬编码门禁段（13 行正文）替换为一行指针注释（说明规则已迁至 config.yaml、迁移原因、以及"rules 不得复制进产出"不豁免结构性要求）
- [x] 2.3 `openspec/changes/openspec-config-proposal-rules/.openspec.yaml` 补 `skip_specs: true`（本变更零 capability delta，纯工具链/机制类）

## 3. C 段：抗覆盖验证

- [x] 3.1 C1：迁移已完成（同 2.1/2.2）
- [x] 3.2 C2：真跑 `/opsx:propose` 验证两节确实出现在产出中——本变更包自己的 `proposal.md` 即为该验证的产出（递归自检，见 design.md「验证结果」）
- [x] 3.3 C3：固化改前证据（SHA256 哈希）→ 真跑 `openspec update --force`（比普通 update 更严格，强制重写而非"已最新跳过"）→ 核对 diff：`config.yaml` 哈希改前改后完全一致，`propose.md` 指针注释按预期被删除（已重新补回）→ **C3 通过，新载体确认不被覆盖**

## 4. D 段：收尾（待 design 审通过后执行）

- [x] 4.1 停下，等待 Shao Peishen 审 design.md（技术决策拍板：载体选择 config.yaml rules 而非自定义 schema、指针注释的定位）——2026-08-02 已批准 (a)
- [x] 4.2 design 获批后：`/opsx:archive` 归档本变更包
- [x] 4.3 回填队列 #206（C3 抗覆盖验证结论为核心内容）；#195 的观察（本次 C3 顺带确认其余 4 个 opsx 命令文件 + 5 个 skill 文件当前均无定制内容）另起一句写入 #195 行
- [x] 4.4 CC 自行 commit + push；收工重跑一次文档台账
- [x] 4.5 会话末用固定小节「需你定夺」列决策项（是非题/选择题格式）
