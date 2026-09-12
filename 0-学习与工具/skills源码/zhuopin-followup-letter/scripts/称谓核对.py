"""skill `zhuopin-followup-letter` §5 步骤 2「代词自检」的可执行体（队列 §一 `#566` ④）。

本 skill 目录此前只有 `SKILL.md` 与 `CHANGELOG.md`、零脚本——v3.5（2026-08-20
「第 ≥6 次纠正后机制化」）实为把规则写进文本，而规则活在「知道」里不产生动作。
本文件是一层薄壳：**判据与名录零复制**，只定位仓库根并转调
`0-学习与工具/工具-称谓核对.py`（它再复用 `工具-共享文档编辑锁.py` 的
`PERSON_GENDER_ROSTER` 与 `gender_pronoun_findings`）。

用法（在仓库任意子目录下均可）：

    python "0-学习与工具/skills源码/zhuopin-followup-letter/scripts/称谓核对.py" <信件.md> [<信件.docx>]
    python ".../scripts/称谓核对.py" --dirty     # 工作区脏的跟进信件

退出码同主工具：0 命中 0 处／1 有命中／2 无法执行（找不到主工具也是 2，不静默通过）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAIN_TOOL_REL = Path("0-学习与工具") / "工具-称谓核对.py"


def _find_repo_root(start: Path) -> Path | None:
    """从 `start` 向上找到含主工具的目录——skill 被 `save_skill` 装到别处时，
    脚本自身位置不可靠，只能按 cwd 找仓库。"""
    for candidate in (start, *start.parents):
        if (candidate / MAIN_TOOL_REL).is_file():
            return candidate
    return None


def main(argv: list[str]) -> int:
    root = _find_repo_root(Path.cwd().resolve()) or _find_repo_root(Path(__file__).resolve().parent)
    if root is None:
        print(f"✗ 找不到主工具 `{MAIN_TOOL_REL.as_posix()}`——请在仓库 `C:\\Dev\\zhuopin-ai` 内运行；"
              "本壳不自带判据，找不到即无法执行（退出码 2，不算通过）。", file=sys.stderr)
        return 2
    # 相对路径按**调用者的 cwd** 解析成绝对路径再转交——主工具以仓库根为基准解析
    # 相对路径，在子目录里跑会把路径接错而报「文件不存在」。
    cwd = Path.cwd().resolve()
    passthrough = [
        str((cwd / a).resolve()) if not a.startswith("-") and (cwd / a).exists() else a
        for a in argv
    ]
    cmd = [sys.executable, str(root / MAIN_TOOL_REL), *passthrough]
    return subprocess.run(cmd, cwd=str(root)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
