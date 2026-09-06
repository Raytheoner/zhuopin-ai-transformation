"""tasks §1.6 断言测试 —— **D8：台账目录下不得出现子目录**。

主断言 ＝ `test_D8_台账目录出现子目录即lint失败`：
在 tmp 台账里建一个子目录并往里放一个 `.jsonl`，`lint_ledger_dir()` 必须报 fatal、
`assert_clean()` 必须抛，且报告里点出「`!` 例外不递归、其中的 .jsonl 并未入库」。

成因（审材料 §6.3 第 4 条对照组，真仓库 `OP-0906-Q` 已复现）：`.gitignore` 第 32 行
`**/*.jsonl` 之后的 `!…/口径点台账/*.jsonl` 例外**不递归** —— 子目录里的 `.jsonl`
仍被吞掉，**不报错、不提示、`git add` 也不抱怨**。又一个「错误不产生任何信号」，
只有主动去找的 lint 能拦。

🔴 本文件全部数据造在 `tmp_path`；对真台账目录**只读**（跑 lint，不写一个字节）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    REAL_LEDGER_DIR,
    REPO_ROOT,
    make_store,
    tree_fingerprint,
)

from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    Domain,
    LedgerLintError,
    assert_clean,
    lint_ledger_dir,
)


def test_D8_台账目录出现子目录即lint失败(tmp_path):
    """**D8 主断言**：目录下出现子目录 ⇒ lint fatal ＋ `assert_clean()` 抛。

    断言四件：
      ⑴ 干净目录先过 lint —— 否则「加了子目录就红」可能只是它本来就红；
      ⑵ 加一个子目录后 `ok` 变 False，且发现类型是 `子目录`；
      ⑶ 报告里点出子目录内的 `.jsonl` **此刻并未入库**（这才是这条 lint 的真实危害）；
      ⑷ `assert_clean()` 抛 `LedgerLintError`，供 CI／收工自检直接用。
    """
    store = make_store(tmp_path)
    # ⑴
    clean = lint_ledger_dir(store.ledger_dir)
    assert clean.ok, clean.render()
    assert clean.findings == ()

    # ⑵ 建一个子目录，并在里面放一份「看上去很合理」的域文件
    sub = store.ledger_dir / "2026归档"
    sub.mkdir()
    (sub / "财务域.jsonl").write_text("", encoding="utf-8")

    report = lint_ledger_dir(store.ledger_dir)
    assert not report.ok
    kinds = {f.kind for f in report.fatal}
    assert kinds == {"子目录"}, report.render()

    # ⑶
    detail = report.fatal[0].detail
    assert "不递归" in detail
    assert "并未入库" in detail

    # ⑷
    with pytest.raises(LedgerLintError):
        assert_clean(store.ledger_dir)


def test_D8_干净目录lint通过且不改动磁盘(tmp_path):
    """lint 是**只读**检查：跑完目录指纹逐字节不变。"""
    store = make_store(tmp_path)
    before = tree_fingerprint(store.ledger_dir)
    assert lint_ledger_dir(store.ledger_dir).ok
    assert tree_fingerprint(store.ledger_dir) == before


def test_D8_空子目录同样算违规(tmp_path):
    """子目录**当下是空的**也要报 —— 违规发生在建目录那一刻，不是放文件那一刻。

    🔑 「等里面有文件了再说」＝ 等到静默丢数据已经发生。
    """
    store = make_store(tmp_path)
    (store.ledger_dir / "临时").mkdir()
    report = lint_ledger_dir(store.ledger_dir)
    assert not report.ok
    assert report.fatal[0].kind == "子目录"


def test_D8_域文件缺失也报fatal(tmp_path):
    """五份域文件缺一份即 fatal —— 缺的那份会被 `append` 顺手建出来、不报警。"""
    store = make_store(tmp_path)
    (store.ledger_dir / Domain.SALES.filename).unlink()
    report = lint_ledger_dir(store.ledger_dir)
    assert not report.ok
    assert {f.kind for f in report.fatal} == {"域文件缺失"}


def test_D8_额外jsonl只提醒不判死(tmp_path):
    """五份之外的 `.jsonl` 会被 `!*.jsonl` 例外一并放行入库 ⇒ 提醒（非 fatal）。"""
    store = make_store(tmp_path)
    (store.ledger_dir / "临时导出.jsonl").write_text("", encoding="utf-8")
    report = lint_ledger_dir(store.ledger_dir)
    assert report.ok, "多一份 .jsonl 不判死"
    assert {f.kind for f in report.findings} == {"意外jsonl"}


def test_D8_目录不存在时报fatal而非静默通过(tmp_path):
    """目录压根不在 ⇒ fatal。

    🔑 对不存在的目录返回「合规」是最典型的假绿：**什么都没检查也叫全过**。
    """
    report = lint_ledger_dir(tmp_path / "根本没有这个目录")
    assert not report.ok
    assert report.fatal[0].kind == "目录不存在"


def test_D8_命令行入口可用作CI闸(tmp_path):
    """`python -m ...lint <dir>` 违规时退出码非 0 —— CI 直接挂这个就行。"""
    store = make_store(tmp_path)
    (store.ledger_dir / "子目录").mkdir()

    proc = subprocess.run(
        [sys.executable, "-m", "zhuopin_platform.coverage_point_ledger.lint",
         str(store.ledger_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT / "5-平台底座" / "zhuopin_platform"),
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "子目录" in proc.stdout

    ok_proc = subprocess.run(
        [sys.executable, "-m", "zhuopin_platform.coverage_point_ledger.lint",
         str(make_store(tmp_path / "干净").ledger_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT / "5-平台底座" / "zhuopin_platform"),
    )
    assert ok_proc.returncode == 0, ok_proc.stdout + ok_proc.stderr


@pytest.mark.skipif(
    not REAL_LEDGER_DIR.is_dir(),
    reason="真台账目录尚未入库（tasks §1.1／§1.2 的产物在主仓工作区、未 commit）",
)
def test_D8_真台账目录当前合规():
    """把 lint 指向**真**台账目录跑一遍（只读）。

    🔑 tmp 目录上验的是**规则逻辑**，不是真仓库状态 —— 与 design「apply 前置 ⑴」
    同一条判据：两者之间隔着一份可能已被别人改过的目录。
    """
    report = lint_ledger_dir(REAL_LEDGER_DIR)
    assert report.ok, report.render()
