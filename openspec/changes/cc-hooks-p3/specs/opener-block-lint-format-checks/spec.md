## ADDED Requirements

### Requirement: `check_block` SHALL 判定标题值、六字段顺序、首行三类新增格式

在既有形态①②基础上，`工具-opener块lint.py::check_block` SHALL 新增三类判定，判据正本＝
`专线opener模板库.md` §〇.00：

- **形态③**（仅 CC 侧、且已调用 `set_session_title` 的块）：块内 MUST 含匹配
  `[Win]MMDDX-<短名>`（真实四位数字日期 ＋ 字母后缀）的标题值；骨架占位符原样未替换
  （字面 `MMDDX`）MUST 判定违规。
- **形态④**（任一 opener 块，不分执行环境）：`【设置】` 行 MUST 依次含六字段标签
  `执行环境｜分支｜worktree｜工作区｜session｜派出线`；缺字段或顺序颠倒 MUST 判定违规，
  违规详情 MUST 列出缺失字段与颠倒的相邻字段对。
- **形态⑤**（任一 opener 块，不分执行环境）：块**首行**（去首尾空白后）MUST 匹配
  `[OP-MMDD-X]【CC／Cowork】<短名>`，短名长度 MUST ≤12 字符；不匹配 MUST 判定违规。

三类新增判定 MUST 复用既有 `Block`/`settings_line`/`block_env` 结构，MUST NOT 引入第二套
块识别逻辑。

#### Scenario: 标题占位符未替换
- **WHEN** CC 块调用了 `set_session_title`，标题值仍为字面 `[Win]MMDDX-<短名>`
- **THEN** 命中形态③

#### Scenario: 六字段顺序颠倒
- **WHEN** `【设置】` 行文本中 `worktree` 出现在 `分支` 之前
- **THEN** 命中形态④，详情含 `分支→worktree`

#### Scenario: 六字段缺失
- **WHEN** `【设置】` 行只含三个字段标签
- **THEN** 命中形态④，详情列出全部缺失的三个标签

#### Scenario: 首行短名超长
- **WHEN** opener 块首行短名部分为 13 字符
- **THEN** 命中形态⑤

#### Scenario: 首行短名恰好 12 字符
- **WHEN** opener 块首行短名部分恰为 12 字符
- **THEN** 不命中形态⑤

#### Scenario: Cowork 块不受形态③约束
- **WHEN** Cowork 块调用了 `set_session_title`，标题值不匹配 `[Win]MMDDX-<短名>`
- **THEN** 不命中形态③（该形态判据正本明写「CC 块」）

#### Scenario: 形态④⑤对 Cowork 块同样生效
- **WHEN** Cowork 块 `【设置】` 字段缺失或首行格式错
- **THEN** 分别命中形态④／⑤（§〇.00 两套骨架的六字段与首行格式相同，不因执行环境收窄）

### Requirement: 三类新增判定 SHALL 复用既有「当前在用 vs 历史」三层分类

形态③④⑤ MUST 复用既有 `classify_carrier` 的 H1/H2/H3 三层判据，生效日 MUST 为
2026-09-04（本变更落库当日）。规则生效前最后一次提交的文件 MUST 判为历史件、不计入
`--enforce` 阻断范围——与形态①②的既有先例一致，新规则不追溯既有内容。

#### Scenario: 规则生效前的存量文件不阻断
- **WHEN** 某文件最后一次提交发生在 2026-09-04 之前，且命中形态④
- **THEN** 该命中判为历史件，`--enforce` 模式下不计入阻断集合

### Requirement: 工具 SHALL 提供 `--file` 单文件自检模式

`工具-opener块lint.py` SHALL 支持 `--file <路径>` 参数，行为 MUST 为：只读取该一份文件、
MUST NOT 调用任何 git 子进程、MUST NOT 区分「当前在用／历史」（全部命中按「当前」处理）；
存在任一命中 MUST 以退出码 1 结束（不受 `--enforce` 开关影响），零命中 MUST 退出码 0。

#### Scenario: 自检模式对未跟踪临时文件可用
- **WHEN** 对一份从未 `git add` 过的临时 `.md` 跑 `--file`
- **THEN** 正常扫描并给出判定，不因「git 历史取不到」而将结果归类为不可判

#### Scenario: 自检模式命中即非零退出
- **WHEN** `--file` 目标含至少一处命中（任意形态）
- **THEN** 退出码为 1，且不受是否传入 `--enforce` 影响

#### Scenario: 自检模式零命中即成功退出
- **WHEN** `--file` 目标全部块均合规
- **THEN** 退出码为 0

### Requirement: release 侧 opener 守卫 MUST 通过复用 `check_block` 自动获得新判据

`工具-共享文档编辑锁.py::_opener_guard_violations` 既有实现已逐字复用
`工具-opener块lint.py::check_block` 的返回值、不按形态代码做白名单过滤。新增形态③④⑤
MUST 通过这一既有复用路径自动生效，MUST NOT 在 `_opener_guard_violations` 中新增任何
形态相关的判断分支或形态代码枚举。

#### Scenario: release 守卫无需改动即感知新形态
- **WHEN** 本次持锁期间触碰的 `.md` 内某 opener 块命中形态④
- **THEN** `_opener_guard_violations` 的既有循环（`for form, detail in lint.check_block(block)`）
  照常将其计入 `problems`，无需修改 `工具-共享文档编辑锁.py` 任何代码
