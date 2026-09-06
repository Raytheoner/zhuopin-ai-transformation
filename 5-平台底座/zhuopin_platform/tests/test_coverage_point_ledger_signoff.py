"""tasks §1.5 断言测试 —— **D5：`已签认` 只能由真实回件驱动，无任何超期自动签认路径**。

成因（tasks §1.5 原文）：判据／口径／阈值类**永不默认生效**是 IATF 显式签认红线。
proposal 已写明「这条须在 tasks 里落成断言测试，不能只写在文档里」—— 本文件就是那条落点。

一条「**不存在**某条路径」的断言没法只用一个用例证明，故从三面同时打：

| 面 | 主断言函数 | 打的是什么 |
|---|---|---|
| 构造面 | `test_D5_已签认无回件则连对象都造不出来` | 没有 `evidence` 的 `已签认` 在 `LedgerEvent` 构造期即抛 |
| 行为面 | `test_D5_超期扫描只出催办草稿_不改状态不加行` | 点超期 1000 天，扫完状态仍是 `在途`，台账一个字节没长 |
| 入口面 | `test_D5_全包只有一处写台账内容的代码` | AST 扫全包，写内容的代码有且只有 `LedgerStore._append_line` |

🔴 本文件全部数据造在 `tmp_path`，**不碰仓库内那五份 0 字节 `.jsonl`**。
"""
from __future__ import annotations

import ast
import dataclasses
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    create_event,
    make_store,
    transition_event,
    tree_fingerprint,
)

import zhuopin_platform.coverage_point_ledger as cpl  # noqa: E402
from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    Event,
    LedgerContractError,
    LedgerEvent,
    LedgerWriteRejected,
    PointType,
    Status,
    aggregate,
    scan_overdue,
)

_PKG_DIR = Path(cpl.__file__).resolve().parent


# ---------------------------------------------------------------- 构造面

def test_D5_已签认无回件则连对象都造不出来():
    """**D5 主断言（构造面）**：`status=已签认` 而无 `evidence` ⇒ 构造期即抛。

    🔑 校验放在构造期而非写入期是刻意的：连一个「没有回件的已签认」**对象**都造不出来，
    就没有任何代码路径能把它拿去碰运气 —— 包括将来某个绕过 `LedgerStore` 的新写法。
    """
    with pytest.raises(LedgerContractError) as exc:
        LedgerEvent(
            id="FI2-D19-03",
            event=Event.TRANSITION,
            status=Status.SIGNED,
            fact_date="2026-09-12",
            recorded_on="2026-09-12T14:02:00+08:00",
            by="OP-0906-Z-test",
        )
    assert "evidence" in str(exc.value)

    # `已回灌` 同样必须带凭据（SCHEMA §二 evidence 行）
    with pytest.raises(LedgerContractError):
        LedgerEvent(
            id="FI2-D19-03",
            event=Event.TRANSITION,
            status=Status.FED_BACK,
            fact_date="2026-09-20",
            recorded_on="2026-09-20T14:02:00+08:00",
            by="OP-0906-Z-test",
        )


def test_D5_带真实回件的已签认可正常写入(tmp_path):
    """**正向对照组**：有落档回件时 `已签认` 必须写得进去。

    🔑 没有这一条，上面那条「拒绝」的断言可能只是因为**根本没人能写成功**——
    一个把所有输入都拒掉的实现同样能让拒绝类断言全绿。
    """
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT, letters=("财务部#17",)))
    store.append(
        transition_event(
            "FI2-D19-03",
            Status.SIGNED,
            fact_date="2026-09-12",
            recorded_on="2026-09-12T14:02:00+08:00",
            evidence="7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md",
        )
    )
    assert store.current_status("FI2-D19-03") is Status.SIGNED


def test_D5_绕过构造器的已签认在写入期被第二道拦下(tmp_path):
    """写入期是**第二道**闸，防的是绕过构造器拼出来的对象（如 `dataclasses.replace`）。

    🔑 一道闸只挡一种绕法。这里用 `object.__setattr__` 把一个合法对象的 `evidence`
    抹掉（frozen dataclass 唯一的后门），模拟「对象是从别处来的」这条路。
    """
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))

    smuggled = transition_event(
        "FI2-D19-03",
        Status.SIGNED,
        fact_date="2026-09-12",
        recorded_on="2026-09-12T14:02:00+08:00",
        evidence="7-外部文档/财务部/占位.md",
    )
    object.__setattr__(smuggled, "evidence", None)

    with pytest.raises(LedgerWriteRejected) as exc:
        store.append(smuggled)
    assert "evidence" in str(exc.value)
    assert store.current_status("FI2-D19-03") is Status.ASKING, "被拒的行不得留下任何痕迹"


# ---------------------------------------------------------------- 行为面

def test_D5_超期扫描只出催办草稿_不改状态不加行(tmp_path):
    """**D5 主断言（行为面）**：一个超期 1000 天的 `在途` 点，扫完仍是 `在途`。

    断言四件：
      ⑴ 扫描确实认出它超期了（否则「状态没变」只是因为压根没扫到）；
      ⑵ 台账目录指纹逐字节不变 —— 扫描没有偷偷追加 `已签认` 行；
      ⑶ 重新聚合后状态仍是 `在途`；
      ⑷ 草稿对象携带的状态是原状态，且草稿类型与写入口所要的 `LedgerEvent`
         **没有任何转换函数** —— 这条路在类型层面就不通。
    """
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2", due="2023-01-01"))
    store.append(
        transition_event("FI2-D19-03", Status.IN_FLIGHT, letters=("财务部#17",))
    )

    before = tree_fingerprint(store.ledger_dir)
    snapshot = aggregate(store)
    drafts = scan_overdue(snapshot, today=date(2025, 9, 27))

    # ⑴
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.point_id == "FI2-D19-03"
    assert draft.days_overdue > 900
    # ⑷
    assert draft.status is Status.IN_FLIGHT
    assert draft.default_window_elapsed is False, "`判据类` 永不默认生效（IATF 红线）"
    assert not hasattr(draft, "to_event"), "催办草稿不得能变成可写入的台账事件"
    # ⑵
    assert tree_fingerprint(store.ledger_dir) == before, "超期扫描往台账里写东西了"
    # ⑶
    assert aggregate(store).points["FI2-D19-03"].status is Status.IN_FLIGHT


def test_D5_判据类不得配默认生效时限():
    """`判据类` 带 `default_after_h` ⇒ 构造期即抛（P4／IATF 红线）。

    🔑 「永不默认生效」若做成一个**默认关闭的开关**，那它就是可以被打开的。
    这里让它连配都配不出来。
    """
    with pytest.raises(LedgerContractError) as exc:
        create_event(
            "FI2-D19-03", scene="FI2", point_type=PointType.CRITERION, default_after_h=48
        )
    assert "默认" in str(exc.value)

    # 对照：`试用反馈` 可以配
    ok = create_event(
        "FI2-D19-04", scene="FI2", point_type=PointType.TRIAL_FEEDBACK, default_after_h=48
    )
    assert ok.default_after_h == 48


def test_D5_试用反馈过默认窗口也只是标记_状态仍不推进(tmp_path):
    """即使 `试用反馈` 过了 `default_after_h`，台账状态**仍不自动推进**。

    🔑 「业务侧可以按默认走了」与「台账写了一行 `已签认`」是两件事。
    本模块只做前者的标记，后者永远要回件。
    """
    store = make_store(tmp_path)
    store.append(
        create_event(
            "FI2-D19-04",
            scene="FI2",
            point_type=PointType.TRIAL_FEEDBACK,
            due="2026-01-01",
            default_after_h=48,
        )
    )
    store.append(transition_event("FI2-D19-04", Status.IN_FLIGHT))

    before = tree_fingerprint(store.ledger_dir)
    drafts = scan_overdue(aggregate(store), today=date(2026, 3, 1))

    assert drafts[0].default_window_elapsed is True
    assert drafts[0].status is Status.IN_FLIGHT
    assert tree_fingerprint(store.ledger_dir) == before
    assert store.current_status("FI2-D19-04") is Status.IN_FLIGHT


# ---------------------------------------------------------------- 入口面

def _write_sites(pkg_dir: Path) -> set[tuple[str, str]]:
    """AST 扫全包，返回所有「写文件**内容**」的调用点 ``(文件名, 所在函数名)``。

    命中三类：
      · ``open(..., mode)`` / ``x.open(..., mode)``，mode 含 w/a/x/+
      · ``x.write_text(...)`` / ``x.write_bytes(...)``

    刻意**不**把 `Path.touch()`／`Path.mkdir()` 算进来 —— 它们只建空文件／空目录，
    带不进任何内容，`LedgerStore.initialize()` 用得着；D5 要盯的是「谁能把
    `已签认` 三个字写进文件」。
    """
    write_mode_chars = set("wax+")
    sites: set[tuple[str, str]] = set()

    for py in sorted(pkg_dir.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        # 建「节点 → 所在函数名」索引
        owner: dict[ast.AST, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    owner.setdefault(child, node.name)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in ("write_text", "write_bytes"):
                sites.add((py.name, owner.get(node, "<模块级>")))
            elif name == "open":
                # 🔴 mode 的位置随调用形态而变，两种都要认，漏一种这条断言就形同虚设：
                #   · `open(path, "a")`      —— 内建函数，mode ＝ 第 2 个位置参数
                #   · `path.open("a")`       —— Path 方法，mode ＝ 第 1 个位置参数
                # （本包实际用的正是后者；早期版本只认前者，结果扫出 0 个写入口、
                #   断言「全包只有一处写盘」以**假绿**通过 —— 又一次「错误不产生信号」。）
                mode_index = 0 if isinstance(func, ast.Attribute) else 1
                mode = None
                if len(node.args) > mode_index and isinstance(node.args[mode_index], ast.Constant):
                    mode = node.args[mode_index].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if isinstance(mode, str) and (write_mode_chars & set(mode)):
                    sites.add((py.name, owner.get(node, "<模块级>")))
    return sites


def test_D5_全包只有一处写台账内容的代码():
    """**D5 主断言（入口面）**：写文件内容的代码有且只有 `store.py::_append_line`。

    🔑 D5 要证的是「超期自动签认这条路**不存在**」。只要全包只有一个写入口、
    而那个入口对 `已签认` 强制 `evidence`，这条路就无处可长。
    将来谁新增第二处写盘（哪怕是「顺手缓存一下」），这条测试立刻红。
    """
    sites = _write_sites(_PKG_DIR)
    assert sites == {("store.py", "_append_line")}, (
        f"全包写内容的代码点变了：{sorted(sites)}。"
        f"预期只有 store.py::_append_line —— 新增写入口须先回 design.md D5 复核。"
    )


def test_写入口扫描器本身有效_反向对照组(tmp_path):
    """**反向对照组**：扫描器必须能同时认出两种写法，否则上一条是假绿。

    🔑 这条测试的由来是一次真实的假绿：`_write_sites` 早期只认 `open(path, "a")`
    的**第 2 个位置参数**，而本包用的是 `path.open("a")`（Path 方法，mode 在第 1 位），
    于是它扫出 0 个写入口 —— 而「全包只有一处写盘」这条断言在 0 个写入口时
    **看起来更像通过而不是失败**。一个从不命中的扫描器与没有扫描器是一回事。
    """
    probe = tmp_path / "probe_pkg"
    probe.mkdir()
    (probe / "a.py").write_text(
        "from pathlib import Path\n"
        "def path_method_form(p):\n"
        "    with Path(p).open('a', encoding='utf-8') as fh:\n"
        "        fh.write('x')\n"
        "def builtin_form(p):\n"
        "    with open(p, 'w') as fh:\n"
        "        fh.write('x')\n"
        "def kwarg_form(p):\n"
        "    return open(p, mode='a')\n"
        "def one_liner(p):\n"
        "    Path(p).write_text('x')\n"
        "def reader(p):\n"
        "    return Path(p).open('r')\n"
        "def toucher(p):\n"
        "    Path(p).touch()\n",
        encoding="utf-8",
    )
    assert _write_sites(probe) == {
        ("a.py", "path_method_form"),
        ("a.py", "builtin_form"),
        ("a.py", "kwarg_form"),
        ("a.py", "one_liner"),
    }, "扫描器漏认了某种写法（或误把只读／touch 当成写内容）"


def test_D5_全包无自动签认入口():
    """公开 API 里不得出现 auto／expire／default 类的签认函数。

    名字级别的守卫：一条「不存在的路径」最常见的复活方式，是有人加一个
    `auto_signoff()` 图省事 —— 名字会先出现，行为随后。
    """
    banned_fragments = ("auto_sign", "autosign", "expire_sign", "sign_off_by_default",
                        "default_sign", "force_sign", "自动签认")
    for name in dir(cpl):
        lowered = name.lower()
        assert not any(frag in lowered for frag in banned_fragments), (
            f"公开 API 出现 {name!r}：D5 要求「不存在任何超期自动签认路径」，"
            f"不是「默认关闭的自动签认」"
        )
    assert "scan_overdue" in cpl.__all__, "超期的唯一出口应当是只出草稿的 scan_overdue"


def test_D5_overdue模块够不着写入口():
    """`overdue.py` 不得 import `LedgerStore` —— 在语法层面就够不着写盘。"""
    tree = ast.parse((_PKG_DIR / "overdue.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
            if node.module:
                imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert "LedgerStore" not in imported
    assert "store" not in imported, "overdue 不得依赖写入口所在模块"


def test_D5_事件对象frozen_历史行改不动():
    """`LedgerEvent` frozen —— 「拿到已有事件改 `fact_date` 再写回」在赋值那行就抛。

    成因（tasks 3.3 实证）：2026-08-23 有 12 封信被批量「补转态」，真实回件日
    **在补记那一刻被覆盖式销毁、不可复原**；度量中位数由 2 天变成 7 天，而底层
    事实一天没变。frozen 让这个动作炸在写代码的那一秒，不是三个月后。
    """
    event = create_event("FI2-D19-03", scene="FI2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.fact_date = "2026-01-01"  # type: ignore[misc]
