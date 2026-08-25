"""平台底座凭据锚定 —— 把手抄 12 份、已漂成 5 种语义的 `.env` 查找收拢为一处。

> 变更包：`openspec/changes/env-anchor-collapse/`；起因见队列 #354（#345 决策点 5 留下的那一半）。

## 为什么需要它

`bootstrap.ensure_paths()`（#345）解决的是「代码从哪来」，本模块解决的是「**凭据从哪来**」。
两者方向恰好**相反**，这是本模块最要紧的一句：

| | `ensure_paths()` | 本模块 |
|---|---|---|
| 要的是 | **就近**——每份 worktree 必须测自己的代码（#300 原语义） | **唯一**——同时只该有一份权威凭据 |
| 在 linked worktree 里 | 取 worktree 自己的平台底座（正确） | 🔴 取 worktree 自己的 `.env` 就是 #354 的病灶 |

⇒ **不能把 `.env` 解析塞进 `ensure_paths()` 复用它的查找逻辑**——看起来像复用，语义正好相反。

## 三条本轮实测、且都与直觉相左的事实

**⑴ 「向上找仓库根标记再取其 `.env`」按字面实现是无效的。**
linked worktree 本身就是一个**完整 checkout**，marker `5-平台底座/zhuopin_platform` 在它里面
同样存在 ⇒ 从 worktree 内向上找 marker **停在 worktree 根**，与「找最近的 `.env`」得到同一个
错误答案。真正管用的是 `git rev-parse --git-common-dir` 规范化——本仓库已用它解决过两次同类
问题（`aibot_service/repo_paths.py` #269、`工具-共享文档编辑锁.py` 2026-07-23），而 `.env`
家族 12 处无一采纳。

**⑵ `.51` 上没有 git。** 任何依赖 `git` 的方案**必须能优雅退化**，不能把生产入口钉死在一个
开发机才有的工具上（扁平布局 `C:/<svc>/{app,zhuopin_platform,.env}`）。

**⑶ 「最近的那份 `.env`」这个隐式规则被本模块彻底删掉。** 作用域不靠目录距离猜，由调用方
**指名**（`scope="platform"`）。主工作区里 `4-数字员工/采购部/SC1-供应商风险初筛/.env` 与根
`.env` 有 5 个 `XKY_*` 同名键（Shao Peishen 2026-08-24 确认那份是**早期遗留的历史副本**），
它没有被登记进 `SCOPES` ⇒ **除非被指名，否则永远不会被命中**，不需要 worktree 参与就能复现的
那个引信由此拆除。

## 解析优先级（三段锚定）

1. **`ZP_ENV_FILE` 显式覆盖**——最高优先级，绕开一切自动解析。**设了但文件不存在即 fail-loud**
   （显式声明的意图落空，与「没找到任何 `.env`」不是一回事，不可混为静默）。
2. **monorepo**：向上找 marker `5-平台底座/zhuopin_platform` → 其父目录 ＝ 朴素仓库根 →
   用 `--git-common-dir` 规范化到**所有 linked worktree 共享的那个主工作区根**。git 不可用/
   非 git 目录时**不抛异常**，回落朴素仓库根（决策点 2 的退化路径，见 `_canonical_repo_root`）。
3. **扁平部署根**：向上找「含 `zhuopin_platform/pyproject.toml` 的祖先」＝ `C:/<svc>/`。
   🔴 **判据用 `pyproject.toml` 而不是「有没有 `zhuopin_platform` 子目录」**——后者会被
   `C:/<svc>/zhuopin_platform/`（它自己也含一个同名的**内层包目录**）静默命中，把锚点少算一层。

三段都不命中 ⇒ 返回 `None`（决策点 4：默认静默），由 `required=` 承接失败判定。

## 找不到 `.env` 时报错还是静默（决策点 4 ＝ (c)）

现存 9 份里三种态度、无一处写明理由（8 份静默 `return`／1 份 `SystemExit`／1 份打印后继续）。
本模块的答案：**默认静默 ＋ 调用方声明自己必需的键**——

```python
result = load_env(__file__, required=("FO_API_BASE", "FORECAST_API_KEY"))
```

把判断从「**文件**在不在」移到「**我要的键**到手没有」。后者才是调用方真正关心的事，且对两种
凭据来源（`.env` 文件 / 服务环境与计划任务直接注入）**都成立**——`.51` 常驻服务确有后一种情形，
一律 fail-loud 会打挂它们。

## 🔴 硬约束：只回报路径，绝不回显键值

`EnvLoadResult` **不持有任何键值**（只有路径、键名与来源），`__repr__` 亦然。凭据进日志一次就
再也收不回来，而本模块正是为了让「本次用了哪份凭据」可被打印/写审计而存在——两件事必须同时
成立。反例单测锁死，见 `tests/test_env_anchor.py::test_result_never_exposes_values`。
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional

__all__ = [
    "ENV_FILE_OVERRIDE",
    "MARKER_PARTS",
    "SCOPES",
    "EnvAnchorError",
    "EnvFileOverrideMissing",
    "MissingRequiredKeys",
    "EnvLoadResult",
    "resolve_anchor_dir",
    "resolve_env_file",
    "load_env",
    "parse_env_file",
]

#: 显式覆盖入口。优先级最高，绕开一切自动解析（决策点 2 的 (c)，作为覆盖口保留）。
ENV_FILE_OVERRIDE = "ZP_ENV_FILE"

#: monorepo 仓库根标记，与 `bootstrap.MARKER_PARTS` 同一个结构性事实（刻意不 import 它：
#: 两个模块对「找到标记之后该做什么」的答案相反，共享常量会诱导后来者把逻辑也合并掉）。
MARKER_PARTS = ("5-平台底座", "zhuopin_platform")

#: 已登记的作用域。键＝调用方在代码里指名的名字，值＝相对仓库根的**目录**（其下的 `.env`）。
#:
#: 🔴 **只登记「刻意的服务级 `.env`」，历史遗留副本一律不登记**——不登记即永不被命中，这正是
#: 本模块删掉「最近的那份」这个隐式规则之后得到的性质。
#:
#: - ``"platform"`` → ``5-平台底座/.env``：企微机器人服务专属（6 键），`wecom-aibot-service`
#:   下 8 个脚本此前用 `load_dotenv(SERVICE_DIR.parent / ".env")` **显式指名**要它，是刻意的
#:   服务级作用域、不是漏网的手抄，故予登记（本变更包不改动那 8 个脚本，见 design Non-Goals）。
#:
#: **未登记且刻意不登记**：`4-数字员工/采购部/SC1-供应商风险初筛/.env`（Shao Peishen
#: 2026-08-24 确认＝早期遗留的历史副本）。其清理是独立的一件事，本模块只保证它不再被误命中。
SCOPES: Mapping[str, Path] = {
    "platform": Path("5-平台底座"),
}


class EnvAnchorError(RuntimeError):
    """本模块所有 fail-loud 的基类。"""


class EnvFileOverrideMissing(EnvAnchorError):
    """`ZP_ENV_FILE` 指向的文件不存在——显式声明的意图落空，不静默。"""


class MissingRequiredKeys(EnvAnchorError):
    """调用方 `required=` 声明的键在加载后仍不到位（决策点 4 的 (c)）。

    🔴 异常消息里只出现**键名**与**找过的路径**，不出现任何键值。
    """


@dataclass(frozen=True)
class EnvLoadResult:
    """一次 `load_env()` 的结果。**刻意不持有任何键值**（见模块 docstring 硬约束）。

    属性
    ----
    path
        本次实际命中的 `.env` 绝对路径；三段锚定都不命中时为 `None`。
    anchor
        命中方式，取值 ``"override"`` / ``"monorepo"`` / ``"flat"`` / ``"none"``——
        供排查「我以为读的是 A，其实读的是 B」这类本地看不出来的问题。
    scope
        调用方指名的作用域（`None` ＝ 仓库根）。
    loaded_keys
        本次真正写进 environ 的键**名**（已存在的不覆盖，故不计入）。
    present_keys
        本次读到的 `.env` 里出现过的键名全集（含因已存在而未覆盖的）。
    searched
        解析过程中考察过的候选路径，供 fail-loud 时说明「找过哪些地方」。
    """

    path: Optional[Path]
    anchor: str
    scope: Optional[str] = None
    loaded_keys: tuple[str, ...] = ()
    present_keys: tuple[str, ...] = ()
    searched: tuple[Path, ...] = field(default=(), repr=False)

    def describe(self) -> str:
        """一行人类可读摘要，供入口 `print` 或写审计。**只含路径与计数，不含任何值。**"""
        if self.path is None:
            return f"· .env 未命中（anchor={self.anchor}，值不回显）"
        scope_note = f"，scope={self.scope}" if self.scope else ""
        return (
            f"· .env 已读入：{self.path}（anchor={self.anchor}{scope_note}，"
            f"{len(self.loaded_keys)}/{len(self.present_keys)} 键写入，值不回显）"
        )


def _find_monorepo_root(caller: Path, searched: list[Path]) -> Optional[Path]:
    """向上找 marker `5-平台底座/zhuopin_platform`，返回其父目录（朴素仓库根）。

    ⚠️ 在 linked worktree 里这会停在 **worktree 根**——这是事实、不是缺陷；
    规范化交给 `_canonical_repo_root`，两步刻意分开，便于单测各自钉死。
    """
    for parent in (caller, *caller.parents):
        candidate = parent.joinpath(*MARKER_PARTS)
        searched.append(candidate)
        if candidate.is_dir():
            return parent
    return None


def _canonical_repo_root(naive_root: Path) -> Path:
    """把朴素仓库根规范化为「所有 linked worktree 共享的那个主工作区根」。

    修法与 `aibot_service/repo_paths.resolve_default_queue_anchor`（#269）、
    `工具-共享文档编辑锁.py::_resolve_repo_root`（2026-07-23）同源，已在生产跑了两个多月：
    `--git-common-dir` 在 linked worktree 里指向**主工作区**的 `.git`，取其父目录即得主工作区根；
    普通 clone（非 worktree）下它的父目录就是这个 clone 自己，**行为不变**。

    🔴 **git 不可用（`.51` 无 git）、或该目录根本不在任何 git 工作树里时不抛异常**，直接回落
    `naive_root`——即本函数介入前的答案，不引入新的失败模式（tasks 1.2）。

    🔴 **结果须自带一次校验：规范化后的目录必须**也**含 marker，否则不采纳。**
    本仓库里 git 仓库根与 marker 所在根恰好重合，但那是巧合、不是契约——若本仓库被放进另一个
    外层 git 仓库里（嵌套 clone、或有人在上层 `git init` 过），`--git-common-dir` 会给出那个
    **外层**仓库根，于是解析一路跑到仓库外面去。加这一条后：linked worktree 场景规范化结果
    含 marker ⇒ 照常采纳（#354 的修复不受影响）；嵌套场景不含 ⇒ 回落 `naive_root`，答案仍对。
    **这一条是写单测时被夹具撞出来的**——夹具把 `git init` 打在了 marker 上一层，而那恰好是
    真实世界完全可能出现的形状。
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(naive_root),
             "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return naive_root
    common_dir = result.stdout.strip()
    if not common_dir:
        return naive_root
    canonical = Path(common_dir).parent
    if not canonical.joinpath(*MARKER_PARTS).is_dir():
        return naive_root
    return canonical


def _find_flat_deploy_root(caller: Path, searched: list[Path]) -> Optional[Path]:
    """向上找扁平部署根 `C:/<svc>/`——判据＝其下 `zhuopin_platform/pyproject.toml` 存在。

    🔴 **判据刻意不是「有没有 `zhuopin_platform` 子目录」**：平台底座的分发目录自己也含一个
    同名的**内层包目录**（`<dist>/zhuopin_platform/zhuopin_platform/__init__.py`），朴素判据会
    在 `C:/<svc>/zhuopin_platform/` 处就静默命中、把锚点少算一层——**返回值仍是一个存在的目录，
    不报错**，正是本变更包要根除的那一族失败形态。
    """
    for parent in (caller, *caller.parents):
        candidate = parent / "zhuopin_platform" / "pyproject.toml"
        searched.append(candidate)
        if candidate.is_file():
            return parent
    return None


def resolve_env_file(
    caller_file: str | Path,
    *,
    scope: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> EnvLoadResult:
    """只解析、不读取：回答「本次运行该读哪一份 `.env`」。

    参数
    ----
    caller_file
        调用方的 `__file__`。仅作解析起点，不做任何目录结构假设。
    scope
        作用域名，须是 `SCOPES` 的键；`None` ＝ 仓库根 / 部署根的 `.env`。
        **未登记的作用域名 fail-loud**——打错字静默退化回仓库根，就是把「最近的那份」换了个
        马甲请回来。
    env
        进程环境映射，默认 `os.environ`；测试注入自定义 dict，避免依赖/污染真实环境变量。

    返回
    ----
    `EnvLoadResult`（`loaded_keys`/`present_keys` 为空——本函数不读文件）。
    """
    if env is None:
        env = os.environ
    if scope is not None and scope not in SCOPES:
        raise EnvAnchorError(
            f"未登记的 .env 作用域 {scope!r}；已登记：{sorted(SCOPES)}。"
            "作用域必须显式登记——静默回落到仓库根等于把「最近的那份」换个马甲请回来"
        )

    searched: list[Path] = []

    override = (env.get(ENV_FILE_OVERRIDE) or "").strip()
    if override:
        path = Path(override).expanduser()
        searched.append(path)
        if not path.is_file():
            raise EnvFileOverrideMissing(
                f"{ENV_FILE_OVERRIDE}={override} 指向的文件不存在。显式覆盖是一次明确声明的"
                "意图，落空即报错——与「没找到任何 .env」不是一回事，不可混为静默"
            )
        return EnvLoadResult(path=path, anchor="override", scope=scope,
                             searched=tuple(searched))

    anchor_dir, anchor_kind = _anchor_dir(Path(caller_file).resolve(), searched)
    if anchor_dir is None:
        return EnvLoadResult(path=None, anchor="none", scope=scope, searched=tuple(searched))

    if anchor_kind == "monorepo":
        path = _scoped_env_path(anchor_dir, scope)
    else:
        # 扁平部署布局没有 `5-平台底座/` 这层目录 ⇒ 作用域在此塌缩到部署根本身（该服务的
        # 部署根下本就只有一份 `.env`，这是布局给定的事实，不是本模块的选择）。
        path = anchor_dir / ".env"
    searched.append(path)
    if path.is_file():
        return EnvLoadResult(path=path, anchor=anchor_kind, scope=scope,
                             searched=tuple(searched))
    return EnvLoadResult(path=None, anchor="none", scope=scope, searched=tuple(searched))


def _anchor_dir(caller: Path, searched: list[Path]) -> "tuple[Optional[Path], str]":
    """两段结构锚定（不含 `ZP_ENV_FILE` 覆盖那一段），返回 `(锚点目录, 命中方式)`。"""
    naive_root = _find_monorepo_root(caller, searched)
    if naive_root is not None:
        return _canonical_repo_root(naive_root), "monorepo"
    deploy_root = _find_flat_deploy_root(caller, searched)
    if deploy_root is not None:
        return deploy_root, "flat"
    return None, "none"


def resolve_anchor_dir(
    caller_file: str | Path,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> "tuple[Optional[Path], str]":
    """回答「本次运行的凭据锚点目录是哪个」——仓库根（monorepo）或部署根（扁平）。

    供**需要锚点本身、而不只是那一份 `.env`** 的调用方使用（如 `probe_u9c.py` 要在同一个
    锚点下同时定位 `.env.test` 与 `.env`）。**与 `resolve_env_file` 走同一段解析**，不是
    第二套实现——两套「仓库根在哪」的答案正是本变更包要消灭的东西。

    `ZP_ENV_FILE` 显式覆盖在此表现为**该文件所在目录**（覆盖的是「用哪一份」，锚点随之而定）。

    返回 `(锚点目录或 None, 命中方式)`；命中方式取值同 `EnvLoadResult.anchor`。
    """
    if env is None:
        env = os.environ
    override = (env.get(ENV_FILE_OVERRIDE) or "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise EnvFileOverrideMissing(
                f"{ENV_FILE_OVERRIDE}={override} 指向的文件不存在。显式覆盖是一次明确声明的"
                "意图，落空即报错——与「没找到任何 .env」不是一回事，不可混为静默"
            )
        return path.parent, "override"
    return _anchor_dir(Path(caller_file).resolve(), [])


def _scoped_env_path(repo_root: Path, scope: Optional[str]) -> Path:
    """作用域 → 该作用域的 `.env` 绝对路径（monorepo 布局）。"""
    if scope is None:
        return repo_root / ".env"
    return repo_root / SCOPES[scope] / ".env"


def parse_env_file(path: Path) -> "dict[str, str]":
    """解析 `.env` 为 dict（保持既有 9 份手抄副本的共同语义，不趁机改口径）。

    共同语义＝逐行 strip、跳过空行与 `#` 注释、按**首个** `=` 切分、值去掉一层成对引号，
    编码 `utf-8-sig`（既有副本里有一份用 `utf-8`，BOM 会让第一个键名带上 `\\ufeff`——
    统一取更宽容的那个，属修正而非放宽）。

    🔴 **无键名的行（不含 `=`）一律跳过**，与既有语义一致。2026-08-25 根 `.env` 第 3 行那条
    孤立裸 URL（会被切成「键名＝整段 URL」）已按 Shao Peishen 判定的「误粘贴」移除，但**判据
    保留**——它防的是下一次误粘贴，不是那一行本身。
    """
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def load_env(
    caller_file: str | Path,
    *,
    scope: Optional[str] = None,
    required: Iterable[str] = (),
    env: Optional[Mapping[str, str]] = None,
    environ: Optional[MutableMapping[str, str]] = None,
) -> EnvLoadResult:
    """解析并把命中的 `.env` 读入进程环境（**已存在的不覆盖**，`setdefault` 语义不变）。

    参数
    ----
    caller_file / scope / env
        同 `resolve_env_file`。
    required
        本入口**必需**的键名。读完后检查它们是否真的到位（**不论来自 `.env` 文件还是进程
        环境**——`.51` 常驻服务与计划任务确有直接注入凭据的情形），缺则抛
        `MissingRequiredKeys` 并写明缺哪几个键、找过哪些路径。**空 `required` ＝ 静默**
        （决策点 4 的 (c)：默认静默 ＋ 调用方声明）。
    environ
        待写入的环境映射，默认 `os.environ`；测试注入自定义 dict。

    返回
    ----
    `EnvLoadResult`——`path` ＝ 本次实际命中的 `.env`，供入口打印或写审计。
    🔴 **返回值不含任何键值。**
    """
    if environ is None:
        environ = os.environ
    if env is None:
        env = environ

    resolved = resolve_env_file(caller_file, scope=scope, env=env)

    loaded: list[str] = []
    present: list[str] = []
    if resolved.path is not None:
        for key, value in parse_env_file(resolved.path).items():
            present.append(key)
            if key not in environ:
                environ[key] = value
                loaded.append(key)

    result = EnvLoadResult(
        path=resolved.path,
        anchor=resolved.anchor,
        scope=scope,
        loaded_keys=tuple(loaded),
        present_keys=tuple(present),
        searched=resolved.searched,
    )

    missing = [key for key in required if not (environ.get(key) or "").strip()]
    if missing:
        searched_note = "、".join(str(p) for p in result.searched) or "（无）"
        raise MissingRequiredKeys(
            f"缺少必需的凭据键：{'、'.join(missing)}。"
            f"本次命中的 .env ＝ {result.path or '（未命中）'}（anchor={result.anchor}）；"
            f"考察过的路径：{searched_note}。"
            f"请检查该 .env 是否含这些键，或由服务环境/计划任务直接注入"
        )
    return result
