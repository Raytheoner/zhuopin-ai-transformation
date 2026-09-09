"""口径点台账三个断言测试文件共用的造数与守卫工具。

🔴 **只造 tmp 目录里的数据**：真台账 `6-人才与组织/部门AI专员跟进/口径点台账/*.jsonl`
在本轮（`OP-0906-Z`）必须保持 **0 字节**，任何测试都不得往那五份文件写一个字节。
本文件里没有任何一处指向仓库内台账的写路径。

（文件名以 `_` 开头 ⇒ pytest 不把它当测试模块收集。）
"""
from __future__ import annotations

import builtins
import hashlib
import io
import os
import pathlib
import sys
from contextlib import contextmanager
from pathlib import Path

# —— 平台底座路径引导（与 tests/conftest.py 同一样板，队列 #345 收拢；`工具-引导样板lint.py` 守）——
# 🔴 下面五行只负责让 `bootstrap` 自身可被 import、**不含任何判断分支**；开发机 monorepo 与
# `.51` 扁平部署两种布局的分歧一律由 `ensure_paths` 处理（队列 #520：本文件 2026-09-06 由
# `1ea9ac8` 引入时漏了这两行收拢调用，被 `引导样板lint::test_存量已清零` 判为「引导块未收拢」）。
# 第二参数＝调用方自身的包根：`tests/` 下的文件传 `_HERE.parent.parent`＝`5-平台底座/zhuopin_platform/`。
# `strict=True` 与同目录 `conftest.py` 一致——测试就该跑在仓库里，找不到标记说明环境真错了，
# 此时静默回退到环境里的另一份平台底座，会让测试悄悄测了别人的代码。
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent, strict=True)  # noqa: E402

from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    Event,
    LedgerEvent,
    LedgerStore,
    PointType,
    Status,
)

#: 仓库根（tests/ → zhuopin_platform/ → 5-平台底座/ → 仓库根）
REPO_ROOT = _HERE.parents[3]
#: 真台账目录（**只读、只用于存在性判断与 lint 复核，绝不写**）
REAL_LEDGER_DIR = REPO_ROOT / "6-人才与组织" / "部门AI专员跟进" / "口径点台账"


def make_store(tmp_path: Path) -> LedgerStore:
    """在 tmp 目录里建一份五文件齐全的空台账。"""
    store = LedgerStore(tmp_path / "口径点台账")
    store.initialize()
    return store


def create_event(
    point_id: str,
    *,
    scene: str,
    fact_date: str = "2026-09-06",
    recorded_on: str = "2026-09-06T21:30:00+08:00",
    by: str = "OP-0906-Z-test",
    proposer: str = "测试提出人",
    point_type: PointType = PointType.CRITERION,
    carrier: tuple[str, ...] = ("openspec:coverage-point-ledger",),
    due: str | None = None,
    **kwargs,
) -> LedgerEvent:
    """一条合法的 `建点` 行（tmp 用测试数据，非真实口径点）。"""
    return LedgerEvent(
        id=point_id,
        event=Event.CREATE,
        status=Status.ASKING,
        type=point_type,
        scene=scene,
        proposer=proposer,
        fact_date=fact_date,
        recorded_on=recorded_on,
        by=by,
        case_text="测试用判例原文（非真实口径点）",
        proposed_ruling="测试用拟改判定（非真实口径点）",
        carrier=carrier,
        due=due,
        **kwargs,
    )


def transition_event(
    point_id: str,
    status: Status,
    *,
    fact_date: str = "2026-09-10",
    recorded_on: str = "2026-09-10T09:35:00+08:00",
    by: str = "OP-0906-Z-test",
    **kwargs,
) -> LedgerEvent:
    return LedgerEvent(
        id=point_id,
        event=Event.TRANSITION,
        status=status,
        fact_date=fact_date,
        recorded_on=recorded_on,
        by=by,
        **kwargs,
    )


# ---------------------------------------------------------------- 落盘探测

def tree_fingerprint(root: Path) -> dict[str, str]:
    """整棵目录树的指纹：每个条目 → ``dir`` 或 ``<字节数>:<sha256 前 16 位>``。

    比「只数文件个数」严格一格：**原地覆盖**（个数不变、内容变了）也会被抓到。
    """
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            out[rel] = "dir"
        else:
            data = path.read_bytes()
            out[rel] = f"{len(data)}:{hashlib.sha256(data).hexdigest()[:16]}"
    return out


class WriteAttempted(AssertionError):
    """被守卫拦下的一次落盘尝试（含建目录、建空文件）。"""


_WRITE_MODE_CHARS = frozenset("wax+")


def _mode_is_write(mode) -> bool:
    return isinstance(mode, str) and bool(_WRITE_MODE_CHARS & set(mode))


@contextmanager
def no_disk_write_guard():
    """在 `with` 块内**禁止任何写盘动作**，一旦发生立即抛 `WriteAttempted`。

    拦五条路，缺一条就会有绕过去的写法：

      · ``builtins.open`` —— 直接 `open(path, "w")`
      · ``io.open``       —— `pathlib.Path.open` 内部走的是它，**不是** `builtins.open`
      · ``Path.write_text`` / ``Path.write_bytes`` —— 一行式写文件
      · ``Path.touch``    —— 建空文件（缓存文件常以「先 touch 再填」出现）
      · ``Path.mkdir``    —— 建目录（合并产物常先建一个 `.cache/` 目录）

    🔴 **读一律放行**：本守卫要证的是「聚合只读」，不是「聚合什么都不干」。
    """
    real_builtins_open = builtins.open
    real_io_open = io.open
    real_write_text = pathlib.Path.write_text
    real_write_bytes = pathlib.Path.write_bytes
    real_touch = pathlib.Path.touch
    real_mkdir = pathlib.Path.mkdir

    def _guarded_open(file, mode="r", *args, **kwargs):
        effective = kwargs.get("mode", mode)
        if _mode_is_write(effective):
            raise WriteAttempted(
                f"🔴 D3 违规：跨域聚合期间试图以写模式打开 {file!r}（mode={effective!r}）。"
                f"跨域聚合必须只读、只在内存——任何合并落盘产物（含缓存）都不允许。"
            )
        return real_builtins_open(file, mode, *args, **kwargs)

    def _guarded_io_open(file, mode="r", *args, **kwargs):
        effective = kwargs.get("mode", mode)
        if _mode_is_write(effective):
            raise WriteAttempted(
                f"🔴 D3 违规：跨域聚合期间试图以写模式打开 {file!r}（mode={effective!r}）"
            )
        return real_io_open(file, mode, *args, **kwargs)

    def _guarded_write_text(self, *a, **k):
        raise WriteAttempted(f"🔴 D3 违规：聚合期间 Path.write_text({self!r})")

    def _guarded_write_bytes(self, *a, **k):
        raise WriteAttempted(f"🔴 D3 违规：聚合期间 Path.write_bytes({self!r})")

    def _guarded_touch(self, *a, **k):
        raise WriteAttempted(f"🔴 D3 违规：聚合期间 Path.touch({self!r})（建空缓存文件也算）")

    def _guarded_mkdir(self, *a, **k):
        raise WriteAttempted(f"🔴 D3 违规：聚合期间 Path.mkdir({self!r})（建缓存目录也算）")

    builtins.open = _guarded_open
    io.open = _guarded_io_open
    pathlib.Path.write_text = _guarded_write_text
    pathlib.Path.write_bytes = _guarded_write_bytes
    pathlib.Path.touch = _guarded_touch
    pathlib.Path.mkdir = _guarded_mkdir
    try:
        yield
    finally:
        builtins.open = real_builtins_open
        io.open = real_io_open
        pathlib.Path.write_text = real_write_text
        pathlib.Path.write_bytes = real_write_bytes
        pathlib.Path.touch = real_touch
        pathlib.Path.mkdir = real_mkdir


@contextmanager
def chdir(target: Path):
    """临时切换工作目录 —— 用来抓「写到相对路径」的缓存产物。"""
    old = os.getcwd()
    os.chdir(target)
    try:
        yield Path(target)
    finally:
        os.chdir(old)
