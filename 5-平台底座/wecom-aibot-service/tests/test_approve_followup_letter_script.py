"""队列 #559 回归锁定：`scripts/approve_followup_letter.py` 的审计落点锚点
必须与常驻 listener 同源，不得随 cwd/worktree 分叉。

背景（真实事故，2026-09-11 `OP-0910-H` 实测）：本脚本此前独漏未跟进 #269
（2026-08-06）已修过、其余 7 个兄弟入口早已采用的
`resolve_default_queue_anchor()` 锚点，在 CC worktree 里跑批准/驳回时，
把审计写进了那个临时 worktree 自己的物理文件——常驻 listener 与主仓
审计完全看不到这条人工门禁决策。本文件用两层断言钉死不再回归：

① **行为层**（`test_audit_anchor_resolves_to_main_checkout_from_linked_
   worktree`）：模拟"本脚本的 `NAIVE_REPO_ROOT` 恰好是一个临时 linked
   worktree"这一真实故障场景，断言脚本实际使用的解析链路（导入脚本模块
   后原样调用其 `resolve_default_queue_anchor`/`resolve_repo_root` 引用）
   解出的是主工作区根，不是这个临时 worktree 自己。

② **结构层**（`test_source_does_not_regress_to_manual_anchor_pattern`）：
   直接读脚本源码文本，钉死"不得再出现 #269 那个已知失效模式的手写
   拼接"、"必须仍在调用 `resolve_default_queue_anchor`"两条——即便有人
   将来手滑改回旧写法但忘了删导入，①仍会因为脚本代码路径整体没被这个
   断言真正跑过而可能漏判（②比①更早、更直接地拦住"抄旧代码回来"这个
   最常见的回归形态），双保险同 D8 门禁"AST 扫描 + 依赖清单文本扫描"
   一贯做法（见 `CLAUDE.md` §4 D8）。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "approve_followup_letter.py"
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "master")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    return path


def _load_script_module():
    """把 `approve_followup_letter.py` 当模块 import（不执行 `main()`），
    复用其顶层已 import 好的 `resolve_default_queue_anchor`/`resolve_repo_root`
    ——这样断言的是"脚本实际持有的那个引用"，不是另起一份同名函数。"""
    spec = importlib.util.spec_from_file_location(
        "approve_followup_letter_under_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_audit_anchor_resolves_to_main_checkout_from_linked_worktree(tmp_path: Path):
    """队列 #559 核心场景：脚本自身所在的 `NAIVE_REPO_ROOT` 恰好是一个
    用完即删的临时 linked worktree（本项目 CC 的常规工作方式）——解析
    出的仓库根必须是主工作区，不是这个 worktree 自己。"""
    mod = _load_script_module()

    main_repo = _init_repo(tmp_path / "main_repo")
    (main_repo / "1-转型规划" / "0-全景路线图").mkdir(parents=True, exist_ok=True)
    worktree_b = tmp_path / "worktree_b"
    _git(main_repo, "worktree", "add", "-q", "-b", "feature", str(worktree_b))

    # 模拟"本脚本这次跑在 worktree_b 里"：直接用脚本模块持有的那两个函数
    # 引用，喂入 worktree_b 作为 NAIVE_REPO_ROOT（即模块真实计算出的值，
    # 见脚本 `SERVICE_DIR.parents[1]`），env 传空 dict 排除本机真实环境变量
    # 干扰（同 test_repo_paths.py 既有惯例）。
    anchor = mod.resolve_default_queue_anchor(worktree_b, env={})
    resolved_repo_root = mod.resolve_repo_root(anchor, fallback=worktree_b, env={})

    assert resolved_repo_root.resolve() == main_repo.resolve()
    assert resolved_repo_root.resolve() != worktree_b.resolve()

    audit_path = mod.resolve_audit_path(resolved_repo_root)
    assert audit_path.resolve().is_relative_to(main_repo.resolve())
    assert not audit_path.resolve().is_relative_to(worktree_b.resolve())


def test_source_does_not_regress_to_manual_anchor_pattern():
    """结构层守卫（AST 级，不做易受注释/文档串误伤的裸字符串扫描）：
    脚本必须仍在某处调用 `resolve_default_queue_anchor`，且不得再 import
    `DEFAULT_QUEUE_RELATIVE_PATH`——#269/#559 那个已知失效的手写拼接
    `NAIVE_REPO_ROOT / DEFAULT_QUEUE_RELATIVE_PATH` 当默认锚点，必须先拿到
    这个符号才可能写出来；import 消失即该回归形态在语法层面不可能复活，
    比对散文/注释做子串匹配更不易被误伤也更难被绕过。"""
    import ast

    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SCRIPT_PATH))

    imported_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "resolve_default_queue_anchor" in called_names, (
        "锚点计算必须调用 resolve_default_queue_anchor——直接手写路径拼接"
        "正是 #559 的根因，见本脚本文首长注。"
    )
    assert "DEFAULT_QUEUE_RELATIVE_PATH" not in imported_names, (
        "DEFAULT_QUEUE_RELATIVE_PATH 不应再被本脚本 import——它是 #269/#559 "
        "已知失效的手写拼接锚点（'本 checkout 自身'）的必要前提符号。"
    )
