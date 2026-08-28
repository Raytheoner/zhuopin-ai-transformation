"""队列 #416 ⑵ 的**机制守**：全包禁止 `str(<被捕获的异常>)`。

🔴 **本文件存在的理由，是 ⑵ 修完之后又在包里找到 5 处漏网的同形态写法**
（`dispatch.py` 两处、`outbox_relay.py` 两处、`followup_readme_bridge.py`
一处）——它们与已收敛的那 24 处**一模一样**，只是当时按 `error=str(exc)`
这个字面量去搜，而这 5 处写成了 `outcome.failed.append((preview, str(exc)))`
与 `_audit(..., str(exc))`（位置参数），字面量搜索看不见它们。

⇒ **判据不能再靠"记得用 `describe_exception`"这条人守**（CLAUDE.md §5
「规则退休制」：人守条目违反 3 次即须机制化）。本测试按 **AST** 判定，只
认一件事：**在 `except X as e:` 的作用域里，对 `e` 调 `str()`**。

**为什么用 AST 而不是 grep**：`str(exc)` 这个字符串同时出现在
`error_text.py` 的实现与多处文档字符串里，grep 必然误报；而位置参数、
f-string 内嵌、嵌套 handler 这些形态 grep 又必然漏报。**一个既误报又漏报
的判据，比没有判据更糟——它会让人以为已经守住了。**
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "aibot_service"

# `error_text.py` 是**实现方**：`describe_exception` 内部必须调 `str(exc)`，
# 那正是它包装的东西。豁免范围刻意精确到这一个文件，不写成目录级通配。
ALLOWED = {"error_text.py"}


class _BareStrExcVisitor(ast.NodeVisitor):
    """找 `except ... as name:` 作用域内的 `str(name)` 调用。"""

    def __init__(self) -> None:
        self.caught: list[str] = []          # 当前嵌套着的 handler 变量名
        self.hits: list[tuple[str, int]] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # `except E:`（无 as）捕不到变量，自然无从 str() 它
        if node.name:
            self.caught.append(node.name)
            self.generic_visit(node)
            self.caught.pop()
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in self.caught
        ):
            self.hits.append((node.args[0].id, node.lineno))
        self.generic_visit(node)


def _scan(path: Path) -> list[tuple[str, int]]:
    visitor = _BareStrExcVisitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
    return visitor.hits


def test_no_bare_str_on_caught_exception_anywhere_in_package():
    offenders: list[str] = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if path.name in ALLOWED:
            continue
        for name, lineno in _scan(path):
            offenders.append(
                f"{path.relative_to(PACKAGE_DIR)}:{lineno} —— str({name})"
            )

    assert not offenders, (
        "发现 `str(<被捕获的异常>)`：无参异常的 `str()` 是空串，会把留痕写成"
        "一条什么都没说的记录（队列 #416 ⑵ 元缺陷）。请改用 "
        "`error_text.describe_exception(...)`：\n  " + "\n  ".join(offenders)
    )


def test_the_guard_actually_catches_the_shapes_it_claims_to(tmp_path):
    """🔴 判据自锚：守卫必须真能咬住这 4 种形态，否则它就是恒真判据。

    本项目已多次吃过「判据恒真、零信息量」的亏——一个永远绿的守卫，和没有
    守卫是同一回事。这里逐个喂进真实出现过的写法，确认它们都被认出来。
    """
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as exc:\n"
        "        a = str(exc)                     # 直接赋值\n"
        "        b = [(1, str(exc))]              # 元组里（dispatch.py 形态）\n"
        "        g(1, 2, str(exc))                # 位置参数（outbox_relay 形态）\n"
        "        h(error=str(exc))                # 关键字参数（原已收敛形态）\n"
        "        return a, b\n",
        encoding="utf-8",
    )
    assert [line for _, line in _scan(sample)] == [5, 6, 7, 8]


def test_guard_does_not_fire_on_unrelated_str_calls(tmp_path):
    """另一侧：不得误报。`str(path)`、`str()` 于非异常名，都必须放过。"""
    sample = tmp_path / "clean.py"
    sample.write_text(
        "def f(path):\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as exc:\n"
        "        return str(path), describe_exception(exc)\n",
        encoding="utf-8",
    )
    assert _scan(sample) == []
