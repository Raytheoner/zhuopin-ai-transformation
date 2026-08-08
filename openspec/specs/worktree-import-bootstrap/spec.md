# worktree-import-bootstrap Specification

## Purpose
定义"pytest 测试收集"与"服务入口脚本启动"这两个时刻，`zhuopin_platform` 平台底座包与场景自身包必须解析到调用方所在 git worktree 自身磁盘代码、且不依赖任何全局 editable 安装（`pip install -e`）当前状态的行为契约——确保多个 `git worktree` 并行开发时，一个 worktree 执行 `pip install -e` 不会静默影响另一个 worktree 的测试结果或服务行为。
## Requirements
### Requirement: 测试收集时优先解析本 worktree 代码
含 `zhuopin_platform` 或场景自身包依赖的 `tests/conftest.py` MUST 在文件顶部、任何该类 import 语句之前，把本 worktree 的 `5-平台底座/zhuopin_platform` 目录与本场景自身根目录插入 `sys.path` 最前端（`sys.path.insert(0, ...)`，而非追加），使后续 `import` 无论全局 editable 安装当前指向哪个 worktree，都解析到本 worktree 磁盘上的代码。

#### Scenario: 全局 editable 指针指向另一 worktree 时仍测到本 worktree 代码
- **WHEN** 全局 `site-packages` 的 `zhuopin_platform` editable 安装当前指向 worktree A，而 `pytest` 在 worktree B 的场景目录下执行
- **THEN** worktree B 的测试用例 `import zhuopin_platform` 解析到的是 worktree B 磁盘上的代码，而非 worktree A 的代码

#### Scenario: 未曾执行过 pip install -e 时测试仍可正常运行
- **WHEN** 某 worktree 从未执行过 `pip install -e`（全局 site-packages 中不存在任何该 worktree 相关的 editable 指针）
- **THEN** 该 worktree 内 `pytest` 仍能正确 `import zhuopin_platform` 与本场景自身包并正常运行测试

### Requirement: 服务入口脚本启动时优先解析本 worktree 代码
含 `zhuopin_platform` 或场景自身包依赖的服务入口脚本（`scripts/run_*.py`）MUST 在文件顶部、任何该类 import 语句之前，执行与 conftest.py 相同规则的路径引导。

#### Scenario: 服务入口脚本在任意 worktree 下启动均使用自身代码
- **WHEN** 服务入口脚本（如 `run_baoguan_web.py`）在某 worktree 下被直接执行（`python scripts/run_xxx.py`）
- **THEN** 脚本内 `zhuopin_platform`/场景包相关 import 解析到的是该脚本所在 worktree 磁盘上的代码，与全局 editable 安装当前指向谁无关

### Requirement: 仓库根发现使用文件系统标记，不依赖 git 子进程
路径引导逻辑 MUST 通过从调用文件 `__file__` 向上遍历父目录、检测 `5-平台底座/zhuopin_platform` 子目录是否存在来定位仓库根，MUST NOT 依赖派生 `git` 子进程或其它需要外部可执行文件的机制；找不到该标记时 MUST 显式抛出异常（fail-loud），MUST NOT 静默跳过路径引导后继续执行。

#### Scenario: 找不到仓库根标记时显式报错
- **WHEN** 从调用文件向上遍历全部祖先目录均未发现 `5-平台底座/zhuopin_platform` 子目录
- **THEN** 路径引导逻辑抛出显式异常，终止执行，不静默回退到"不做任何路径引导"的旧行为

### Requirement: 不覆盖临时诊断命令与无平台依赖的入口
本契约 MUST NOT 要求对不 `import zhuopin_platform` 或场景自身包的文件（如纯标准库实现的服务入口）添加路径引导；手动在交互式解释器或临时命令行中执行的 `import` 语句不受本契约约束，其解析结果继续如实反映全局 editable 安装的当前状态。

#### Scenario: 无平台底座依赖的入口不要求路径引导
- **WHEN** 某服务入口脚本或场景本身经核实不 `import zhuopin_platform` 也不 `import` 任何场景自身包
- **THEN** 该文件不要求添加本契约描述的路径引导代码

