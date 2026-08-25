"""`run_baoguan_dashboard.py` 的 `.env` 定位回归守（队列 #354）。

## 这道守卫钉住的那个缺陷

原实现是 `REPO = Path(__file__).resolve().parents[4]`——把"仓库根在上面第 4 层"这个
**开发机布局事实**写死在脚本里。`.51` 的部署布局是扁平的 `C:/baoguan/app/scripts/`，
向上只有 3 层 ⇒ `IndexError: 4`，**本 CLI 在 `.51` 上从未可用过**（2026-08-24 真机复现：
`C:\\baoguan\\app\\scripts\\run_baoguan_dashboard.py, line 36 ... IndexError: 4`）。

**为什么本地测不出来**：本地永远是 monorepo 布局，`parents[4]` 恰好是对的。故本文件
刻意**不在本仓库布局下测**，而是在 `tmp_path` 里合成一个 3 层深的扁平布局——那正是
`parents[4]` 会炸、而正确实现会命中 `C:/<svc>/.env` 的那个形状。

## 🔴 2026-08-25 改判：断言对象从「本脚本自己的 `_find_env`」移到「它调用的收拢实现」

变更包 `env-anchor-collapse`（队列 #354 的收拢半边）把 12 处手抄 `.env` 查找收敛为
`zhuopin_platform.env_anchor`，本脚本的 `_find_env` 随之删除、`load_env()` 变成一行委派。
本文件原先用 AST 从源文件里抽 `_find_env`/`load_env` 两个函数出来在合成布局里 `exec`，
那条路子对"函数还在文件里"这个前提是硬依赖的，收拢后必然失效。

**⚠️ 这是改判，不是放宽——三条契约一条没少，且各自更强了**：
① 扁平布局命中 `C:/<svc>/.env`（原有，保留）；② monorepo 命中仓库根（原有，保留）；
③ 缺 `.env` 时不抛（原有，保留）。**新增**④ linked worktree 与主工作区必须解出同一份
（原实现做不到，故原文件里根本没有这条）。两条变异验证（旧原文的 fail-loud 面与
fail-silent 面）**逐字保留**，`.parents[N]` 结构守也原样保留。

断言仍绑在**生产源码**上：`test_源文件确已委派给收拢实现` 断言脚本真的在调
`env_anchor`，而不是自己又长出一份查找逻辑；其余用例调的正是脚本所调的那个函数。
"""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_baoguan_dashboard.py"

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents
                  if (p / "5-平台底座" / "zhuopin_platform").is_dir())
sys.path.insert(0, str(_REPO_ROOT / "5-平台底座" / "zhuopin_platform"))

from zhuopin_platform.env_anchor import load_env, resolve_env_file  # noqa: E402

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
    `zhuopin_platform/` 下带 `pyproject.toml`：那是收拢实现认扁平部署根的结构判据
    （**不是**「有没有同名子目录」——分发目录自己也含一个内层同名包，朴素判据会少算一层）。
    """
    svc = tmp_path / "baoguan"
    (svc / "app" / "scripts").mkdir(parents=True)
    (svc / "zhuopin_platform" / "zhuopin_platform").mkdir(parents=True)
    (svc / "zhuopin_platform" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (svc / ".env").write_text(env_text, encoding="utf-8")
    return svc / "app" / "scripts" / "run_baoguan_dashboard.py"


def _monorepo_layout(tmp_path: Path, env_text: str) -> Path:
    repo = tmp_path / "企业AI转型"
    scripts = repo / "4-数字员工" / "采购部" / "SC8" / "scripts"
    scripts.mkdir(parents=True)
    (repo / "5-平台底座" / "zhuopin_platform").mkdir(parents=True)
    (repo / "5-平台底座" / "zhuopin_platform" / "pyproject.toml").write_text(
        "[project]\n", encoding="utf-8")
    (repo / ".env").write_text(env_text, encoding="utf-8")
    script = scripts / "run_baoguan_dashboard.py"
    # 必须真的落一个文件：git 不跟踪空目录，worktree 用例里 `scripts/` 会整个不存在。
    script.write_text("# fixture\n", encoding="utf-8")
    return script


class _EnvHolder(dict):
    """只实现 `setdefault` 语义的 `os.environ` 替身（不污染真实进程环境）。"""


# ── 现行实现（断言绑在脚本所调用的那个收拢实现上）────────────────────────────


def test_源文件确已委派给收拢实现():
    """结构守：本脚本不得再自己长出一份 `.env` 查找逻辑。

    判据锚在 **import 节点**上，而不是裸子串——否则会被 docstring 里解释这段历史的散文命中
    （同 #355 的教训：扫源码的守卫必须分得清「缺陷本身」与「描述缺陷的话」）。
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    delegates = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "zhuopin_platform.env_anchor"
        and any(alias.name == "load_env" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert delegates, (
        f"{SCRIPT.name} 应从 zhuopin_platform.env_anchor 导入 load_env（队列 #354 收拢）；"
        "若这里红了，说明有人把查找逻辑又抄回了脚本里"
    )


def test_扁平布局下命中服务根env而不越界(tmp_path):
    script = _flat_layout(tmp_path, "FO_API_BASE=http://flat.example\n")
    assert resolve_env_file(script, env={}).path == (tmp_path / "baoguan" / ".env").resolve()


def test_扁平布局下凭据真的被读进环境(tmp_path):
    script = _flat_layout(tmp_path, 'FO_API_BASE=http://flat.example\nXKY_KEY="q1"\n')
    holder = _EnvHolder()
    load_env(script, env={}, environ=holder)
    assert holder["FO_API_BASE"] == "http://flat.example"
    assert holder["XKY_KEY"] == "q1"          # 引号被剥掉，同既有范式


def test_monorepo布局下仍命中仓库根env(tmp_path):
    """开发机形状：`<repo>/4-数字员工/<域>/<场景>/scripts/`，且场景层没有自己的 .env。"""
    script = _monorepo_layout(tmp_path, "FO_API_BASE=http://repo.example\n")
    assert resolve_env_file(script, env={}).path == (
        tmp_path / "企业AI转型" / ".env").resolve()


def test_没有任何env时静默返回不抛(tmp_path):
    """缺 `.env` 不是错误——凭据也可能由服务环境直接注入（`.51` venv/计划任务）。

    ⚠️ 这条静默只在**调用方没声明 `required=`** 时成立；本脚本声明了 4 个必需键，
    那是调用方自己的选择（决策点 4 的 (c)），与本条契约不冲突——见下一个用例。
    """
    scripts = tmp_path / "a" / "b" / "scripts"
    scripts.mkdir(parents=True)
    holder = _EnvHolder()
    script = scripts / "run_baoguan_dashboard.py"

    assert resolve_env_file(script, env={}).path is None
    load_env(script, env={}, environ=holder)   # 不抛
    assert holder == {}


def test_声明的必需键缺失时fail_loud(tmp_path):
    """本脚本声明了必需键 ⇒ 凭据不全时当场报错，而不是拖到调用端点才炸。"""
    from zhuopin_platform.env_anchor import MissingRequiredKeys

    script = _flat_layout(tmp_path, "FO_API_BASE=http://flat.example\n")
    with pytest.raises(MissingRequiredKeys):
        load_env(script, required=("FO_API_BASE", "FORECAST_API_KEY"),
                 env={}, environ=_EnvHolder())


@pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")
def test_worktree与主工作区解出同一份(tmp_path):
    """🔴 收拢带来的新契约：原实现（无论 `parents[4]` 还是「最近的 .env」）都做不到这条。"""
    # 🔴 git 仓库根必须**就是** monorepo 根（真实形状如此）——夹具若把 `git init` 打在
    # marker 上一层，规范化会给出那个外层根，测的就不是本项目的布局了。
    script_main = _monorepo_layout(tmp_path, "FO_API_BASE=http://fresh.example\n")
    repo = script_main.parents[4]                      # …/企业AI转型
    assert (repo / "5-平台底座" / "zhuopin_platform").is_dir()
    for args in (["init", "-q", "-b", "master"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True,
                   capture_output=True)

    wt = repo / ".claude" / "worktrees" / "stale"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "wip", str(wt)],
                   cwd=str(repo), check=True, capture_output=True)
    # 病灶：worktree 里躺着一份陈旧的 `.env` 副本（gitignore，git 不管它）
    (wt / ".env").write_text("FO_API_BASE=http://STALE\n", encoding="utf-8")
    script_wt = wt / "4-数字员工" / "采购部" / "SC8" / "scripts" / "run_baoguan_dashboard.py"
    assert script_wt.is_file(), "夹具没在 worktree 里造出脚本，本用例失去意义"

    holder = _EnvHolder()
    load_env(script_wt, env={}, environ=holder)
    assert holder["FO_API_BASE"] == "http://fresh.example", (
        "从 worktree 跑却读到了 worktree 自己那份陈旧副本——#354 的病灶复发")


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
    load_env(script, env={}, environ=holder)
    assert holder["FO_API_BASE"] == "http://flat.example"


def test_旧实现_在浅路径上必然IndexError():
    """浅路径 · fail-loud 面：模拟 `C:\\baoguan\\app\\scripts\\`（向上不足 5 层）。

    不建真实目录——`parents[4]` 在路径**字符串**层面就已越界，与文件是否存在无关。
    """
    shallow = Path("C:/baoguan/app/scripts/run_baoguan_dashboard.py")
    assert len(shallow.parents) < 5, "前提：该路径向上不足 5 层，否则本用例失去意义"
    with pytest.raises(IndexError):
        _ = shallow.parents[4]
