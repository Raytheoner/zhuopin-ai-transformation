"""CI 测试矩阵自动发现（队列 #309 步骤 2 追加设计输入，2026-08-08）。

背景：`.github/workflows/ci.yml` 的测试矩阵此前是一份手写的 13 项路径
清单——CC 步骤 1 逐子项目实跑坐实这 13 项，Cowork「环境总线」独立复核
步骤 1 产出时指出这份清单本身是**隐性白名单**：下一个新场景建成时若
忘了把路径加进 `ci.yml`，CI 照样全绿、该场景零覆盖——这正是 CI 立项要
消灭的「靠人记得」，在 CI 自己身上原样复活。

本脚本用一条可复算的规则替代手写清单：扫描 `git ls-files` 匹配
`test_*.py`/`*_test.py` 的文件，按其位置归并到"项目根"，输出去重后的
根目录列表（相对仓库根路径，JSON 数组，供 `ci.yml` 动态生成矩阵）。

判据（与 CLAUDE.md 现存三种目录形态逐一对齐，本机全量验证过恰好复现
现有 13 项矩阵，不多不少）：
- 若测试文件直接父目录名为 `tests`，项目根 = 该目录的父目录
  （标准形态 `X/tests/test_*.py`，11 个子项目属此类）。
- 否则项目根 = 测试文件所在目录本身（`X/test_*.py` 直接散在根目录，
  或 `X/子目录/test_*.py` 形态，各按此计）。
- **内容级过滤**：文件名匹配但不含任何 `def test_*(`/`class *Test*` 定义
  的，不计入（真实案例：`wecom-aibot-service/scripts/echo_test.py` 是
  手动联调脚本，文件名恰好命中 `*_test.py` 但零 pytest 用例，计入会把
  它错误地当成一个独立子项目）——只看文件名会产生假阳性，本判据用
  轻量正则扫描内容而非真跑 `pytest --collect-only`（更快、零副作用）。

用法：
  python 0-学习与工具/工具-CI矩阵发现.py            # 打印 JSON 数组到 stdout
  python 0-学习与工具/工具-CI矩阵发现.py --pretty    # 人类可读，每行一项
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEST_FILENAME_RE = re.compile(r"^(test_.+\.py|.+_test\.py)$")
TEST_DEF_RE = re.compile(r"^\s*(def test_\w*\s*\(|class \w*Test\w*\s*[:(])", re.MULTILINE)


def discover_project_roots(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    roots: set[str] = set()
    for line in result.stdout.splitlines():
        if not line:
            continue
        p = Path(line)
        if not TEST_FILENAME_RE.match(p.name):
            continue
        full = repo_root / p
        try:
            content = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not TEST_DEF_RE.search(content):
            continue
        parent = p.parent
        root = parent.parent if parent.name == "tests" else parent
        roots.add(str(root).replace("\\", "/"))
    return sorted(roots)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pretty", action="store_true", help="人类可读输出，每行一项，末尾附总数")
    args = parser.parse_args()

    roots = discover_project_roots(REPO_ROOT)

    if args.pretty:
        for r in roots:
            print(r)
        print(f"\nTOTAL: {len(roots)}")
    else:
        print(json.dumps(roots, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
