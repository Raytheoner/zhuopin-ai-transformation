## Purpose

定义 `zhuopin_platform.bootstrap.ensure_paths()` 的行为契约——把当前手抄 35 份、已漂成 4 种彼此不等价语义的 `sys.path` 引导收拢为单一实现，使「开发机 monorepo 布局」与「`.51` 扁平部署布局」两种形态由一处代码同时覆盖，并把「何时该 fail-loud」由默会经验变成显式参数。

## ADDED Requirements

### Requirement: 双布局解析

`ensure_paths()` SHALL 依次尝试两种布局，并在任一命中后停止：从调用方文件向上逐级查找 `5-平台底座/zhuopin_platform` 标记（monorepo）；未命中时 SHALL 将调用方自身包路径插入 `sys.path`，并将平台底座的解析交由环境（扁平部署布局的 venv）完成。

#### Scenario: monorepo 布局命中标记

- **WHEN** 调用方文件位于某 worktree 内，其上级存在 `5-平台底座/zhuopin_platform` 目录
- **THEN** 该目录与调用方自身包路径 SHALL 被插入 `sys.path` 最前，使 import 结果与全局 editable 安装当前指向谁无关

#### Scenario: 扁平部署布局未命中标记

- **WHEN** 调用方文件位于 `C:/<svc>/app/...`，其任一上级均不存在 `5-平台底座/zhuopin_platform` 目录，而 `zhuopin_platform` 已由部署脚本安装进该服务 venv
- **THEN** `ensure_paths()` SHALL NOT 抛出异常，且调用方自身包路径 SHALL 被插入 `sys.path`，`zhuopin_platform` 由环境正常解析

#### Scenario: 已在 sys.path 中的路径不重复插入

- **WHEN** 待插入的路径已存在于 `sys.path`
- **THEN** 该路径 SHALL NOT 被重复插入

### Requirement: 不引入静默失败

两条分支均走完后，若 `zhuopin_platform` 仍不可导入，`ensure_paths()` SHALL 抛出 `RuntimeError`，且错误信息 SHALL 同时包含「未找到仓库根标记」与「环境中也没有可导入的 zhuopin_platform」两层事实及调用方文件的实际路径。MUST NOT 以静默跳过、返回 `None` 或吞掉异常的方式让调用方在更晚的位置以更难归因的形式失败。

#### Scenario: 两种布局都不成立

- **WHEN** 既找不到 monorepo 标记，`find_spec("zhuopin_platform")` 亦为 `None`
- **THEN** SHALL 抛出 `RuntimeError`，其消息包含调用方文件的绝对路径，且该路径 SHALL 被真实插值（不得是未求值的字面量占位符）

#### Scenario: 平台底座存在但其子模块缺失

- **WHEN** `zhuopin_platform` 可导入，但调用方随后 import 的具体子模块不存在
- **THEN** `ensure_paths()` SHALL NOT 拦截该错误，调用方 SHALL 收到原生 `ModuleNotFoundError`，以保留真实失败点

### Requirement: strict 模式保留测试侧 fail-loud

`ensure_paths()` SHALL 接受 `strict` 参数（默认 `False`）。当 `strict=True` 且未找到 monorepo 标记时，SHALL 直接抛出 `RuntimeError`，不进入扁平布局回退分支——即便环境中存在可导入的 `zhuopin_platform`。

#### Scenario: conftest.py 在仓库外被执行

- **WHEN** 某 `tests/conftest.py` 以 `strict=True` 调用，而其上级不存在 `5-平台底座/zhuopin_platform` 标记
- **THEN** SHALL 抛出 `RuntimeError`，因为测试必须跑在仓库内，此处静默回退到环境中的另一份平台底座会让测试悄悄测了别人的代码

#### Scenario: strict 模式在 monorepo 内正常工作

- **WHEN** `strict=True` 且找到 monorepo 标记
- **THEN** 行为与 `strict=False` 时的 monorepo 分支 SHALL 完全一致

### Requirement: 与内联引导块向后兼容

在收拢过渡期，`ensure_paths()` 与尚未替换的内联引导块 SHALL 可在同一次进程启动中共存，互不干扰；本能力 MUST NOT 要求 35 处调用点一次性全部切换。

#### Scenario: 过渡期混合形态

- **WHEN** 同一进程内一个入口已改用 `ensure_paths()`、另一个仍为内联块
- **THEN** 两者 SHALL 各自正确完成路径解析，且 `sys.path` 中 SHALL NOT 出现因重复插入导致的同一路径多份条目

### Requirement: 禁止非 stub 形态的内联引导

仓库内新增或修改的 `.py` 文件 SHALL NOT 包含携带判断分支的内联路径引导块；唯一被允许的形态是调用 `ensure_paths()` 的极小 stub。CI lint SHALL 对违反者报告违规。

#### Scenario: 新场景 scaffold 时抄入旧形态

- **WHEN** 一个新增 `.py` 文件包含 `for _p in (_HERE, *_HERE.parents)` 且其后带 `else` 分支或 `raise`
- **THEN** CI lint SHALL 报告违规并指向 stub 样板；该形态正是 SC2（2026-08-18 新建）出生即带 fail-loud 副本的直接成因

#### Scenario: 合规 stub 不误报

- **WHEN** 一个 `.py` 文件仅含定位并 import `ensure_paths` 的 stub、无任何回退判断
- **THEN** CI lint SHALL NOT 报告违规
