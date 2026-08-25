"""`zhuopin_platform.env_anchor` 单测（变更包 `env-anchor-collapse`，队列 #354）。

三种真实布局各一组夹具 ＋ 「worktree 与主工作区必须解出同一份」 ＋ 无 git 退化 ＋
「绝不回显键值」反例 ＋ 🔴 **变异验证**（把 A 家族现行写法喂给同一套夹具，它必须解出错的那份
——判据若不红，说明夹具没造出真实条件，整套测试是空转的）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zhuopin_platform.env_anchor import (  # noqa: E402
    ENV_FILE_OVERRIDE,
    EnvAnchorError,
    EnvFileOverrideMissing,
    MissingRequiredKeys,
    load_env,
    parse_env_file,
    resolve_env_file,
)

# ── 夹具：三种真实布局 ───────────────────────────────────────────────────────────

MARKER = Path("5-平台底座") / "zhuopin_platform"


def _make_monorepo(root: Path, *, env_body: str = "ROOT_KEY=root-value\n") -> Path:
    """开发机主工作区：`<repo>/5-平台底座/zhuopin_platform` ＋ `<repo>/.env`。"""
    (root / MARKER).mkdir(parents=True)
    (root / MARKER / "pyproject.toml").write_text("[project]\nname='zhuopin_platform'\n",
                                                  encoding="utf-8")
    (root / ".env").write_text(env_body, encoding="utf-8")
    scene = root / "4-数字员工" / "采购部" / "SC8" / "scripts"
    scene.mkdir(parents=True)
    caller = scene / "run_x.py"
    caller.write_text("# caller\n", encoding="utf-8")
    return caller


def _make_flat_deploy(root: Path, *, env_body: str = "FLAT_KEY=flat-value\n") -> Path:
    """`.51` 扁平部署：`C:/<svc>/{app,zhuopin_platform,.env}`，**没有 git、没有 marker**。

    `zhuopin_platform/` 下刻意再放一层同名的内层包目录——真实分发布局如此，也正是朴素判据
    （「有没有 zhuopin_platform 子目录」）会静默少算一层的地方。
    """
    dist = root / "zhuopin_platform"
    (dist / "zhuopin_platform").mkdir(parents=True)
    (dist / "zhuopin_platform" / "__init__.py").write_text("", encoding="utf-8")
    (dist / "pyproject.toml").write_text("[project]\nname='zhuopin_platform'\n", encoding="utf-8")
    (root / ".env").write_text(env_body, encoding="utf-8")
    scripts = root / "app" / "scripts"
    scripts.mkdir(parents=True)
    caller = scripts / "run_x.py"
    caller.write_text("# caller\n", encoding="utf-8")
    return caller


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, encoding="utf-8")


def _make_git_monorepo_with_worktree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """真 git 仓库 ＋ 真 linked worktree，各自带一份 `.env`（陈旧副本＝#354 的病灶）。

    返回 `(主工作区根, 主工作区里的 caller, worktree 里的 caller)`。
    """
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", "-b", "master", cwd=main)
    _git("config", "user.email", "t@example.com", cwd=main)
    _git("config", "user.name", "t", cwd=main)
    caller_main = _make_monorepo(main, env_body="CRED=fresh-from-main\n")
    (main / ".gitignore").write_text(".env\n", encoding="utf-8")
    _git("add", "-A", cwd=main)
    _git("commit", "-qm", "init", cwd=main)

    wt = main / ".claude" / "worktrees" / "stale"
    _git("worktree", "add", "-q", "-b", "wip", str(wt), cwd=main)
    # linked worktree 是完整 checkout ⇒ marker 在它里面同样存在（本设计最反直觉的一格）。
    assert (wt / MARKER).is_dir()
    # 病灶：worktree 里躺着一份陈旧的 .env 副本（gitignore，git 不管它）。
    (wt / ".env").write_text("CRED=stale-two-generations-old\n", encoding="utf-8")
    caller_wt = wt / "4-数字员工" / "采购部" / "SC8" / "scripts" / "run_x.py"
    assert caller_wt.is_file()
    return main, caller_main, caller_wt


# ── 三种布局各一组 ─────────────────────────────────────────────────────────────


def test_monorepo_layout_resolves_repo_root_env(tmp_path):
    caller = _make_monorepo(tmp_path / "repo")
    result = resolve_env_file(caller, env={})
    assert result.path == (tmp_path / "repo" / ".env").resolve()
    assert result.anchor == "monorepo"


def test_flat_deploy_layout_resolves_deploy_root_env(tmp_path):
    caller = _make_flat_deploy(tmp_path / "baoguan")
    result = resolve_env_file(caller, env={})
    assert result.path == (tmp_path / "baoguan" / ".env").resolve()
    assert result.anchor == "flat"


def test_flat_layout_does_not_stop_at_the_distribution_dir(tmp_path):
    """🔴 锚点必须是 `C:/<svc>/`，不是 `C:/<svc>/zhuopin_platform/`。

    分发目录自己也含一个同名内层包目录；朴素判据会在那里静默命中、把锚点少算一层，
    **返回一个存在的目录且不报错**——正是本变更包要根除的失败形态。
    """
    root = tmp_path / "baoguan"
    _make_flat_deploy(root)
    # 从分发目录内部的脚本起算（`probe_u9c.py` 在扁平布局下就住这儿）
    inner = root / "zhuopin_platform" / "scripts"
    inner.mkdir(parents=True)
    caller = inner / "probe.py"
    caller.write_text("# caller\n", encoding="utf-8")
    # 若锚点少算一层，这里会是 `<root>/zhuopin_platform/.env`（不存在）⇒ 命中 None
    assert resolve_env_file(caller, env={}).path == (root / ".env").resolve()


def test_no_env_anywhere_returns_none_silently(tmp_path):
    """决策点 4 默认静默：找不到任何 `.env` 不抛异常。"""
    caller = _make_monorepo(tmp_path / "repo")
    (tmp_path / "repo" / ".env").unlink()
    result = resolve_env_file(caller, env={})
    assert result.path is None and result.anchor == "none"


# ── worktree 与主工作区必须解出同一份（本模块存在的理由） ──────────────────────


@pytest.mark.skipif(not __import__("shutil").which("git"), reason="需要 git")
def test_worktree_and_main_resolve_the_same_env(tmp_path):
    main, caller_main, caller_wt = _make_git_monorepo_with_worktree(tmp_path)
    from_main = resolve_env_file(caller_main, env={})
    from_wt = resolve_env_file(caller_wt, env={})
    assert from_main.path == from_wt.path == (main / ".env").resolve()
    # 并且拿到的是新鲜凭据，不是 worktree 里那份陈旧副本
    assert parse_env_file(from_wt.path)["CRED"] == "fresh-from-main"


@pytest.mark.skipif(not __import__("shutil").which("git"), reason="需要 git")
def test_mutation_a_family_writing_picks_the_stale_copy(tmp_path):
    """🔴 变异验证：A 家族现行写法喂给同一套夹具，**必须**解出错的那份。

    判据若不红，说明夹具根本没造出真实条件——那么上面那条「解出同一份」的通过也是空的。
    """
    main, _caller_main, caller_wt = _make_git_monorepo_with_worktree(tmp_path)

    def a_family_find_env(caller_file):
        """9 份手抄副本的共同语义：从脚本向上逐级找**最近的** `.env`。"""
        here = Path(caller_file).resolve()
        for d in (here.parent, *here.parents):
            cand = d / ".env"
            if cand.exists():
                return cand
        return None

    stale = a_family_find_env(caller_wt)
    assert stale is not None
    assert stale != (main / ".env").resolve(), "夹具没造出 worktree .env 副本，变异验证空转"
    assert parse_env_file(stale)["CRED"] == "stale-two-generations-old"


# ── 无 git 退化（`.51` 上没有 git） ─────────────────────────────────────────────


def test_degrades_gracefully_when_git_unavailable(tmp_path, monkeypatch):
    """monorepo 布局但 git 不可用（PATH 里没有 git）⇒ 不抛异常，回落朴素仓库根。"""
    caller = _make_monorepo(tmp_path / "repo")

    def _boom(*_a, **_kw):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", _boom)
    result = resolve_env_file(caller, env={})
    assert result.path == (tmp_path / "repo" / ".env").resolve()
    assert result.anchor == "monorepo"


def test_degrades_gracefully_when_not_a_git_worktree(tmp_path):
    """monorepo 布局、有 git 但目录不在任何工作树里 ⇒ 回落朴素仓库根，不抛异常。"""
    caller = _make_monorepo(tmp_path / "repo")
    result = resolve_env_file(caller, env={})
    assert result.path == (tmp_path / "repo" / ".env").resolve()


@pytest.mark.skipif(not __import__("shutil").which("git"), reason="需要 git")
def test_nested_inside_an_outer_git_repo_keeps_the_marker_root(tmp_path):
    """🔴 本仓库被放进另一个外层 git 仓库时，规范化结果不得跑到仓库外面去。

    本仓库里「git 仓库根」与「marker 所在根」恰好重合，但那是巧合、不是契约。若上层还有一个
    git 仓库（嵌套 clone，或有人在上层 `git init` 过），`--git-common-dir` 给出的是**外层**根。
    校验「规范化结果必须也含 marker」即可挡住——本用例就是那条校验的落点。
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    for args in (["init", "-q", "-b", "master"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(outer), check=True, capture_output=True)
    (outer / ".env").write_text("CRED=outer-wrong\n", encoding="utf-8")

    inner = outer / "企业AI转型"
    caller = _make_monorepo(inner, env_body="CRED=inner-correct\n")

    result = resolve_env_file(caller, env={})
    assert result.path == (inner / ".env").resolve()
    assert parse_env_file(result.path)["CRED"] == "inner-correct"


# ── 显式覆盖 `ZP_ENV_FILE` ─────────────────────────────────────────────────────


def test_override_wins_over_everything(tmp_path):
    caller = _make_monorepo(tmp_path / "repo")
    other = tmp_path / "elsewhere.env"
    other.write_text("OVERRIDE_KEY=1\n", encoding="utf-8")
    result = resolve_env_file(caller, env={ENV_FILE_OVERRIDE: str(other)})
    assert result.path == other and result.anchor == "override"


def test_override_pointing_at_missing_file_fails_loud(tmp_path):
    """显式声明的意图落空即报错——与「没找到任何 .env」不是一回事。"""
    caller = _make_monorepo(tmp_path / "repo")
    with pytest.raises(EnvFileOverrideMissing):
        resolve_env_file(caller, env={ENV_FILE_OVERRIDE: str(tmp_path / "nope.env")})


# ── 作用域必须显式登记（决策点 1 ＝ (c)） ──────────────────────────────────────


def test_registered_scope_resolves_service_level_env(tmp_path):
    root = tmp_path / "repo"
    caller = _make_monorepo(root)
    (root / "5-平台底座" / ".env").write_text("WECOM_AIBOT_BOTID=x\n", encoding="utf-8")
    result = resolve_env_file(caller, scope="platform", env={})
    assert result.path == (root / "5-平台底座" / ".env").resolve()


def test_unregistered_scope_fails_loud_instead_of_falling_back(tmp_path):
    """打错作用域名若静默回落仓库根，等于把「最近的那份」换个马甲请回来。"""
    caller = _make_monorepo(tmp_path / "repo")
    with pytest.raises(EnvAnchorError):
        resolve_env_file(caller, scope="platfrom", env={})


def test_unregistered_sibling_env_is_never_hit(tmp_path):
    """🔴 SC1 那份未登记的历史遗留副本永不被命中——即便它离调用方更近。

    这是「删掉『最近的那份』这个隐式规则」在真实病灶上的样子：SC1 的 `.env` 与根 `.env`
    有 5 个 `XKY_*` 同名键，A 家族写法下 SC1 目录里的脚本永远拿不到根那份。
    """
    root = tmp_path / "repo"
    _make_monorepo(root, env_body="XKY_APP_KEY=root-authoritative\n")
    sc1 = root / "4-数字员工" / "采购部" / "SC1-供应商风险初筛"
    (sc1 / "scripts").mkdir(parents=True)
    (sc1 / ".env").write_text("XKY_APP_KEY=sc1-legacy-copy\n", encoding="utf-8")
    caller = sc1 / "scripts" / "run_sc1.py"
    caller.write_text("# caller\n", encoding="utf-8")

    environ: dict[str, str] = {}
    result = load_env(caller, env={}, environ=environ)
    assert result.path == (root / ".env").resolve()
    assert environ["XKY_APP_KEY"] == "root-authoritative"


# ── required= 键到位检查（决策点 4 ＝ (c)） ────────────────────────────────────


def test_required_keys_satisfied_from_env_file(tmp_path):
    caller = _make_monorepo(tmp_path / "repo", env_body="A=1\nB=2\n")
    environ: dict[str, str] = {}
    result = load_env(caller, required=("A", "B"), env={}, environ=environ)
    assert set(result.loaded_keys) == {"A", "B"}


def test_required_keys_satisfied_from_process_environment_without_any_env_file(tmp_path):
    """凭据由服务环境/计划任务直接注入 ⇒ 没有 `.env` 也应通过（一律 fail-loud 会打挂这些入口）。"""
    caller = _make_monorepo(tmp_path / "repo")
    (tmp_path / "repo" / ".env").unlink()
    environ = {"A": "injected"}
    result = load_env(caller, required=("A",), env={}, environ=environ)
    assert result.path is None and result.anchor == "none"


def test_missing_required_key_fails_loud_with_key_names_and_paths(tmp_path):
    caller = _make_monorepo(tmp_path / "repo", env_body="A=1\n")
    with pytest.raises(MissingRequiredKeys) as excinfo:
        load_env(caller, required=("A", "MISSING_ONE"), env={}, environ={})
    message = str(excinfo.value)
    assert "MISSING_ONE" in message and ".env" in message


def test_empty_required_is_silent(tmp_path):
    """默认静默：不声明 required 就不判失败（保持既有 8 份副本的行为，不趁机改口径）。"""
    caller = _make_monorepo(tmp_path / "repo")
    (tmp_path / "repo" / ".env").unlink()
    assert load_env(caller, env={}, environ={}).path is None


def test_blank_value_counts_as_missing(tmp_path):
    """`KEY=` 空值等同缺失——否则「键在但没值」会一路带到调用真实端点时才炸。"""
    caller = _make_monorepo(tmp_path / "repo", env_body="A=\n")
    with pytest.raises(MissingRequiredKeys):
        load_env(caller, required=("A",), env={}, environ={})


# ── setdefault 语义与解析口径不变 ──────────────────────────────────────────────


def test_existing_environ_values_are_not_overwritten(tmp_path):
    caller = _make_monorepo(tmp_path / "repo", env_body="A=from-file\n")
    environ = {"A": "preset"}
    result = load_env(caller, env={}, environ=environ)
    assert environ["A"] == "preset"
    assert result.loaded_keys == () and result.present_keys == ("A",)


def test_parse_skips_comments_blanks_and_keyless_lines(tmp_path):
    """无键名的行（如 2026-08-25 移除的那条孤立裸 URL）一律跳过——判据保留，防下一次误粘贴。"""
    path = tmp_path / ".env"
    path.write_text(
        "# comment\n"
        "\n"
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send\n"   # 无 `=`，跳过
        "A=1\n"
        'B="quoted"\n',
        encoding="utf-8",
    )
    assert parse_env_file(path) == {"A": "1", "B": "quoted"}


def test_parse_keeps_equals_signs_inside_value(tmp_path):
    """按**首个** `=` 切分——企微 webhook URL 的 `?key=...` 不得把值截断。"""
    path = tmp_path / ".env"
    path.write_text("WECOM_WEBHOOK_URL=https://x/send?key=abc=def\n", encoding="utf-8")
    assert parse_env_file(path)["WECOM_WEBHOOK_URL"] == "https://x/send?key=abc=def"


def test_parse_tolerates_utf8_bom(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes("A=1\n".encode("utf-8-sig"))
    assert parse_env_file(path) == {"A": "1"}


# ── 🔴 只回报路径，绝不回显键值（spec 硬约束的反例单测） ───────────────────────


def test_result_never_exposes_values(tmp_path):
    """`EnvLoadResult` 的任何文本表示都不得含键值——凭据进日志一次就再也收不回来。"""
    secret = "s3cr3t-must-never-appear"
    caller = _make_monorepo(tmp_path / "repo", env_body=f"XKY_APP_SECRET={secret}\n")
    result = load_env(caller, env={}, environ={})
    for text in (repr(result), str(result), result.describe()):
        assert secret not in text
    # 结构上也不持有值：字段里只有路径、键名与来源
    assert secret not in repr(tuple(vars(result).values()) if hasattr(result, "__dict__")
                             else result)
    assert result.loaded_keys == ("XKY_APP_SECRET",)


def test_missing_required_error_message_never_exposes_values(tmp_path):
    """fail-loud 的消息同样不得回显——报错路径是最容易漏掉的那条。"""
    secret = "s3cr3t-must-never-appear"
    caller = _make_monorepo(tmp_path / "repo", env_body=f"A={secret}\n")
    with pytest.raises(MissingRequiredKeys) as excinfo:
        load_env(caller, required=("A", "MISSING_ONE"), env={}, environ={})
    assert secret not in str(excinfo.value)


def test_describe_reports_the_hit_path(tmp_path):
    """「本次用了哪份凭据」必须可从输出直接读到（当前 9 个入口里只有 1 个会说）。"""
    root = tmp_path / "repo"
    caller = _make_monorepo(root)
    text = load_env(caller, env={}, environ={}).describe()
    assert str((root / ".env").resolve()) in text and "值不回显" in text


# ── 默认参数走真实 os.environ 时不炸（契约冒烟） ──────────────────────────────


def test_defaults_use_process_environ(tmp_path, monkeypatch):
    caller = _make_monorepo(tmp_path / "repo", env_body="ZP_ENV_ANCHOR_SMOKE=ok\n")
    monkeypatch.delenv(ENV_FILE_OVERRIDE, raising=False)
    monkeypatch.delenv("ZP_ENV_ANCHOR_SMOKE", raising=False)
    result = load_env(caller)
    try:
        assert os.environ["ZP_ENV_ANCHOR_SMOKE"] == "ok"
        assert result.path == (tmp_path / "repo" / ".env").resolve()
    finally:
        os.environ.pop("ZP_ENV_ANCHOR_SMOKE", None)
