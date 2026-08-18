"""平台底座路径引导 —— 把手抄 35 份、已漂成 4 种语义的 `sys.path` 引导收拢为一处。

> 变更包：`openspec/changes/platform-bootstrap-ensure-paths/`；起因见队列 #345、#300。

## 为什么需要它

两种布局都真实存在、都必须支持，而它们对"找不到仓库根标记"的正确反应恰好相反：

| | 开发机（monorepo） | 生产机（`.51` 扁平） |
|---|---|---|
| 布局 | `<repo>/5-平台底座/zhuopin_platform` ＋ `<repo>/4-数字员工/<域>/<场景>/` | `C:/<svc>/zhuopin_platform` ＋ `C:/<svc>/app`（兄弟目录） |
| 平台底座怎么来 | N 个 worktree 平等副本，全局 editable 指针只有一个、指向谁不确定 | `deploy-server.ps1` `pip install -e` 进该服务专属 venv，全机唯一一份 |
| 引导该做什么 | **必须**前插本 worktree 的路径，压过全局指针（#300） | **不该**做任何事，交给环境解析即可 |
| 找不到标记意味着 | 环境真的错了 | 正常，本就没有那层目录 |

2026-08-18 一天内两条互不知情的 session 各自撞上"开发机语义被抄进生产入口"的后果
（SC8/8091 与 QD-B/8093 相继起不来：计划任务 `LastResult=0` 而进程秒退、端口无监听、
`/api/ping` 502），各自修了一遍。**根因不是某个文件写错，而是同一段逻辑靠复制粘贴分发**
——每份副本都能独立漂移，且没有任何机制会发现它们已经不一致。

## 用法（唯一被允许的样板；`工具-引导样板lint.py` 守）

调用方顶部写这段 stub —— 它只负责"让 bootstrap 自己可被 import"，**不含任何判断分支**：

```python
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402
```

第二个参数是**调用方自身的包根**（其下的模块要能被 import 的那个目录），随文件位置而定，
故显式传入而不自动推断：`<scene>/tests/conftest.py` 与 `<scene>/pkg/x.py` 传
`_HERE.parent.parent`；`<scene>/main.py` 传 `_HERE.parent`。**自动推断在这里会静默猜错**
（`tests/` 通常没有 `__init__.py`，按"最近的非包目录"推断会得到 `tests/` 本身）。

`tests/conftest.py` 一律传 `strict=True`：测试就该跑在仓库里，找不到标记说明环境真错了，
此时静默回退到环境里的另一份平台底座，会让测试悄悄测了别人的代码。

## 已知边界（如实写明，不假装它不存在）

stub 里那句 `from zhuopin_platform.bootstrap import ensure_paths` 是鸡生蛋问题的残留：
两种布局都不成立时，调用方拿到的是 `ModuleNotFoundError: No module named 'zhuopin_platform'`
而不是本模块那条含调用方路径的 `RuntimeError`。这是把判断集中到一处所付的代价——但该
错误本身是诚实的（平台底座确实不可导入），且比原先那条"未找到仓库根标记"更少误导：
后者会把人引向"仓库布局不对"，而 `.51` 上真正的事实是布局本就不该有那层目录。
"""
from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path

__all__ = ["ensure_paths", "MARKER_PARTS"]

# 仓库根标记：`<repo>/5-平台底座/zhuopin_platform`（monorepo 布局特有，扁平部署布局没有）
MARKER_PARTS = ("5-平台底座", "zhuopin_platform")


def _find_monorepo_platform(caller: Path) -> Path | None:
    """从调用方文件向上逐级找 `5-平台底座/zhuopin_platform`，返回该目录或 None。"""
    for parent in (caller, *caller.parents):
        candidate = parent.joinpath(*MARKER_PARTS)
        if candidate.is_dir():
            return candidate
    return None


def _insert_front(path: Path, inserted: list[str]) -> None:
    """把 path 插到 sys.path 最前；已在其中则不重复插入（spec：不产生同一路径多份条目）。"""
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
        inserted.append(text)


def ensure_paths(
    caller_file: str | Path,
    self_path: str | Path,
    *,
    strict: bool = False,
) -> list[str]:
    """确保 `zhuopin_platform` 与调用方自身包根都可被 import。

    参数
    ----
    caller_file
        调用方的 `__file__`。仅用于定位与错误信息，不做任何目录结构假设。
    self_path
        调用方自身的包根（其下模块要能被 import 的那个目录）。显式传入，见模块 docstring。
    strict
        `True` 时**不允许**回退到扁平布局：找不到 monorepo 标记即 `RuntimeError`，
        即便环境中存在可导入的 `zhuopin_platform`。供 `tests/conftest.py` 使用。

    返回
    ----
    本次真正插入 `sys.path` 的路径（已在其中的不计）。顺序为插入顺序，供 `--verbose`
    与排查这类"本地看不出来"的问题时留痕。

    抛出
    ----
    RuntimeError
        `strict=True` 且未找到 monorepo 标记；或两条分支都走完后 `zhuopin_platform`
        仍不可导入。**不静默跳过、不返回 None、不吞异常**——那会把失败点推迟到更难归因处。
    """
    caller = Path(caller_file).resolve()
    inserted: list[str] = []

    platform_dir = _find_monorepo_platform(caller)

    if platform_dir is not None:
        # 开发机：前插本 worktree 的平台底座，压过全局 editable 指针（#300 原语义）。
        # 顺序与原内联块一致：先插平台底座、再插自身包根 ⇒ 自身包根最终在最前。
        _insert_front(platform_dir, inserted)
        _insert_front(Path(self_path).resolve(), inserted)
        return inserted

    if strict:
        raise RuntimeError(
            f"未找到仓库根标记 {'/'.join(MARKER_PARTS)}（从 {caller} 向上查找）；"
            "本调用点声明了 strict=True——测试必须跑在仓库内，此处回退到环境中的"
            "另一份平台底座会让测试悄悄测了别人的代码"
        )

    # 生产机（扁平布局）：只插自身包根，平台底座交由环境（该服务 venv）解析。
    _insert_front(Path(self_path).resolve(), inserted)

    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 {'/'.join(MARKER_PARTS)}（从 {caller} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包"
        )

    return inserted
