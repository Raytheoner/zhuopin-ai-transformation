"""`run_baoguan_dashboard.py` 的 `.env` 定位回归守（队列 #354）。

## 这道守卫钉住的那个缺陷

原实现是 `REPO = Path(__file__).resolve().parents[4]`——把"仓库根在上面第 4 层"这个
**开发机布局事实**写死在脚本里。`.51` 的部署布局是扁平的 `C:/baoguan/app/scripts/`，
向上只有 3 层 ⇒ `IndexError: 4`，**本 CLI 在 `.51` 上从未可用过**（2026-08-24 真机复现：
`C:\\baoguan\\app\\scripts\\run_baoguan_dashboard.py, line 36 ... IndexError: 4`）。

**为什么本地测不出来**：本地永远是 monorepo 布局，`parents[4]` 恰好是对的。故本文件
刻意**不在本仓库布局下测**，而是在 `tmp_path` 里合成一个 3 层深的扁平布局——那正是
`parents[4]` 会炸、而正确实现会命中 `C:/<svc>/.env` 的那个形状。

## 为什么用 AST 抽函数、而不是 import 这个脚本

`run_baoguan_dashboard.py` 顶部有平台底座路径引导 stub（`ensure_paths`），import 它会
产生 `sys.path` 副作用、并把测试绑到真实布局上——那恰好会掩盖本缺陷。这里改为从**真实
源文件**里按 AST 抽出 `_find_env` / `load_env` 两个函数、在合成布局上执行，测的仍是
生产源码本身，但不触发引导副作用。

🔴 **变异验证（本文件非空转的证据）**：`test_旧实现_在扁平布局下必然IndexError` 把
修复前的 master 原文喂给同一套夹具，断言它**确实**炸 —— 判据若失效，该用例会先红。
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_baoguan_dashboard.py"

#: 修复前的 master 原文（队列 #354 的缺陷本体），只用于变异验证，不代表任何现行实现。
_LEGACY_SOURCE = textwrap.dedent(
    '''
    REPO = Path(__file__).resolve().parents[4]


    def load_env() -> None:
        env = REPO / ".env"
        if not env.exists():
            return
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    '''
)


def _extract_env_funcs(source: str) -> str:
    """从源码里抽出 `_find_env` / `load_env` 两个顶层函数定义（含各自 docstring）。"""
    tree = ast.parse(source)
    wanted = {"_find_env", "load_env"}
    picked = [n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in picked} == wanted, (
        f"{SCRIPT.name} 里应同时存在 _find_env 与 load_env，实测 "
        f"{sorted(n.name for n in picked)}——若函数被改名，请同步改本守卫，不要删掉它"
    )
    return "\n".join(ast.get_source_segment(source, n) for n in picked)


def _run_in_layout(body: str, script_path: Path, env_holder: dict) -> dict:
    """在给定 `__file__` 下执行一段 env 定位代码，返回其命名空间。"""
    ns: dict = {
        "__file__": str(script_path),
        "Path": Path,
        "os": type("_OsStub", (), {"environ": env_holder})(),
    }
    exec(compile(body, "<env-funcs>", "exec"), ns)  # noqa: S102 — 夹具内执行受控源码
    return ns


def _flat_layout(tmp_path: Path, env_text: str) -> Path:
    """合成 `.51` 扁平部署布局：`<svc>/{.env, zhuopin_platform/, app/scripts/}`。

    深度刻意只有 3 层——`parents[4]` 在这里必然越界，这正是本文件要钉的形状。
    """
    svc = tmp_path / "baoguan"
    (svc / "app" / "scripts").mkdir(parents=True)
    (svc / "zhuopin_platform").mkdir()
    (svc / ".env").write_text(env_text, encoding="utf-8")
    return svc / "app" / "scripts" / "run_baoguan_dashboard.py"


class _EnvHolder(dict):
    """只实现 `setdefault` 语义的 `os.environ` 替身（不污染真实进程环境）。"""


# ── 现行实现 ────────────────────────────────────────────────────────────────


def test_扁平布局下命中服务根env而不越界(tmp_path):
    script = _flat_layout(tmp_path, 'FO_API_BASE=http://flat.example\n')
    ns = _run_in_layout(_extract_env_funcs(SCRIPT.read_text(encoding="utf-8")),
                        script, _EnvHolder())

    found = ns["_find_env"]()
    assert found == tmp_path / "baoguan" / ".env"


def test_扁平布局下凭据真的被读进环境(tmp_path):
    script = _flat_layout(tmp_path, 'FO_API_BASE=http://flat.example\nXKY_KEY="q1"\n')
    holder = _EnvHolder()
    ns = _run_in_layout(_extract_env_funcs(SCRIPT.read_text(encoding="utf-8")),
                        script, holder)

    ns["load_env"]()
    assert holder["FO_API_BASE"] == "http://flat.example"
    assert holder["XKY_KEY"] == "q1"          # 引号被剥掉，同既有范式


def test_monorepo布局下仍命中仓库根env(tmp_path):
    """开发机形状：`<repo>/4-数字员工/<域>/<场景>/scripts/`，且场景层没有自己的 .env。"""
    repo = tmp_path / "企业AI转型"
    scripts = repo / "4-数字员工" / "采购部" / "SC8" / "scripts"
    scripts.mkdir(parents=True)
    (repo / ".env").write_text("FO_API_BASE=http://repo.example\n", encoding="utf-8")

    ns = _run_in_layout(_extract_env_funcs(SCRIPT.read_text(encoding="utf-8")),
                        scripts / "run_baoguan_dashboard.py", _EnvHolder())
    assert ns["_find_env"]() == repo / ".env"


def test_没有任何env时静默返回不抛(tmp_path):
    """缺 `.env` 不是错误——凭据也可能由服务环境直接注入（`.51` venv/计划任务）。"""
    scripts = tmp_path / "a" / "b" / "scripts"
    scripts.mkdir(parents=True)
    holder = _EnvHolder()
    ns = _run_in_layout(_extract_env_funcs(SCRIPT.read_text(encoding="utf-8")),
                        scripts / "run_baoguan_dashboard.py", holder)

    assert ns["_find_env"]() is None
    ns["load_env"]()                           # 不抛
    assert holder == {}


def test_源文件不得再出现硬数层级的parents下标():
    """本文件是 #354 的落点之一：这个脚本此后不得回到 `parents[N]` 形态。

    判据锚在**赋值语句右侧的下标表达式**上，而不是裸子串——否则本守卫会被上方
    docstring 里解释这个反范式的散文命中（同 #355 的教训：扫源码的守卫必须分得清
    「缺陷本身」与「描述缺陷的话」，否则它会逼着后人删掉解释）。
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    offenders = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
    ]
    assert not offenders, (
        f"{SCRIPT.name} 第 {offenders} 行又出现了 `.parents[N]` 硬数层级——"
        "该写法在 `.51` 扁平布局下越界，见队列 #354"
    )


# ── 变异验证：同一套夹具喂给修复前的原文，必须红 ──────────────────────────────
#
# 🔴 **本节写作过程中撞出的一个订正，如实留档**：原先这里断言「旧实现在扁平布局下必然
# `IndexError`」，实测 **DID NOT RAISE**。原因是 `tmp_path` 本身埋得很深
# （`…/pytest-of-…/test_xxx0/baoguan/app/scripts/`），`parents[4]` 存在、只是**指错了目录**。
#
# ⇒ **`parents[4]` 这个缺陷有两副面孔，取决于脚本被放得离盘根多远**：
#   · **浅路径**（真实 `.51` ＝ `C:\baoguan\app\scripts\`，向上只有 3 层）→ `IndexError`，
#     **fail-loud**，一跑就炸。2026-08-24 真机已复现。
#   · **深路径**（任何埋得够深的部署位置）→ 算出一个**存在但不相干**的目录，那里没有
#     `.env` ⇒ `load_env()` 静默返回、凭据一个都没读进来，**fail-silent**，
#     直到后面连接器报鉴权错才暴露，而那时归因已经指向别处了。
#
# 队列 #354 原文把 `parents[N]` 归为「找不到、当场炸（fail-loud）」、把 `_find_env` 归为
# 「找到了错的、静默用下去（fail-silent）」，**这个二分只在浅路径下成立**——同一行代码
# 换个部署深度就会从一族滑到另一族。收拢方案须同时挡住两副面孔，不能只挡会炸的那副。


def test_旧实现_在扁平布局下静默漏读凭据(tmp_path):
    """深路径 · fail-silent 面：`parents[4]` 指到不相干目录，凭据一个都没读进来、且不报错。"""
    script = _flat_layout(tmp_path, "FO_API_BASE=http://flat.example\n")
    holder = _EnvHolder()
    ns = _run_in_layout(_LEGACY_SOURCE, script, holder)

    assert ns["REPO"] != script.parents[2], "前提：parents[4] 没指到服务根，否则本用例失去意义"
    ns["load_env"]()
    assert holder == {}, "旧实现本就该在这里静默漏掉凭据；若它读到了，本变异验证已失效"

    # 同一布局喂给现行实现 —— 必须读得到。两者对照才是这条守卫的意义所在。
    fixed = _run_in_layout(_extract_env_funcs(SCRIPT.read_text(encoding="utf-8")),
                           script, holder)
    fixed["load_env"]()
    assert holder["FO_API_BASE"] == "http://flat.example"


def test_旧实现_在浅路径上必然IndexError(tmp_path, monkeypatch):
    """浅路径 · fail-loud 面：模拟 `C:\\baoguan\\app\\scripts\\`（向上不足 5 层）。

    真机证据（2026-08-24，`.51` 实跑）：
        File "C:\\baoguan\\app\\scripts\\run_baoguan_dashboard.py", line 36
          REPO = Path(__file__).resolve().parents[4]
        IndexError: 4

    `tmp_path` 造不出这个深度（pytest 的 basetemp 本身就埋得很深），故此处只对
    `Path.resolve` 打桩换成那条真实浅路径——测的仍是 `parents[4]` 这个表达式本身。
    """
    shallow = Path(tmp_path.anchor) / "baoguan" / "app" / "scripts" / "run_baoguan_dashboard.py"
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: shallow)

    with pytest.raises(IndexError):
        _run_in_layout(_LEGACY_SOURCE, shallow, _EnvHolder())


def test_旧实现_在monorepo布局下恰好正确(tmp_path):
    """说明这个缺陷为什么活了这么久：本地布局下它是对的，本地全绿与它毫无关系。"""
    repo = tmp_path / "企业AI转型"
    scripts = repo / "4-数字员工" / "采购部" / "SC8" / "scripts"
    scripts.mkdir(parents=True)
    (repo / ".env").write_text("FO_API_BASE=http://repo.example\n", encoding="utf-8")

    holder = _EnvHolder()
    ns = _run_in_layout(_LEGACY_SOURCE, scripts / "run_baoguan_dashboard.py", holder)
    ns["load_env"]()
    assert holder["FO_API_BASE"] == "http://repo.example"
