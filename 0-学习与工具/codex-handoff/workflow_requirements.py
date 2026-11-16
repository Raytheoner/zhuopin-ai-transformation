"""Read-only adapters for the existing requirement lint and workflow stages."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('workflow_requirement_lint', BASE.parent / '工具-需求与变更包门禁lint.py')
lint = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lint
_spec.loader.exec_module(lint)


def inspect(root: Path, task_id: str, *, stage: str = 'admission') -> dict:
    """Planning may lack artifacts; proposal/implement/closeout may not.

    All repository checks retain their existing policy. Only this task's not-yet
    produced artifacts are conditional at admission, and N/N is expected at the
    archive checkpoint. No baseline is created or increased here.
    """
    root = Path(root).resolve()
    if stage not in ('admission', 'proposal', 'implement', 'closeout'):
        raise ValueError('unknown requirement stage')
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,63}', task_id):
        return {'status': 'blocked', 'reason': 'invalid change id'}
    try:
        index = root / lint.INDEX_REL
        text = index.read_text(encoding='utf8')
        matches = [r for r in lint._section_rows(text, '表二：在途变更包四态表') if r[0] == task_id]
        if len(matches) != 1 or len(matches[0]) != 6:
            raise ValueError('change must have exactly one INDEX row')
        row = matches[0]
        if row[2] not in lint.MODES or row[3] != 'active_mvp':
            raise ValueError('change must be active_mvp with a legal mode')
        issues = lint.check_repository(root)
        allowed = lint.PACKAGE_CODES if stage == 'admission' else {'UNARCHIVED_COMPLETE'} if stage == 'closeout' else set()
        issues = [i for i in issues if not (i.subject == task_id and i.code in allowed)]
        change = root / 'openspec/changes' / task_id
        if not change.resolve().is_relative_to(root):
            raise ValueError('change escapes repository')
        meta = change / '.openspec.yaml'
        if meta.is_file() and re.search(r'^\s*skip_specs:\s*true\s*$', meta.read_text(encoding='utf8'), re.M | re.I):
            raise ValueError('feature/refinement cannot skip specs')
        tests = set()
        specs = lint._section_rows(text, '表一：能力与主规格索引')
        delta_names = {p.parent.name for p in (change / 'specs').glob('*/spec.md')}
        for cells in specs:
            if len(cells) == 6 and Path(cells[3]).parent.name in delta_names:
                tests.add(cells[4])
        if stage != 'admission':
            if any(not (change / name).is_file() for name in ('proposal.md', 'design.md', 'tasks.md')):
                raise ValueError('workflow requires proposal, short design and tasks')
            if not delta_names:
                raise ValueError('feature/refinement require delta specs')
            if row[2] == 'refinement' and (not tests or any(not lint._safe_file(root, test) or Path(test).name == 'test_scaffold.py' for test in tests)):
                raise ValueError('delta requires indexed real pytest')
            # Touched workflow packages cannot inherit missing-section exceptions.
            issues.extend(lint._feature_missing(change, row[1]) if row[2] == 'feature' else
                          lint._refinement_missing(change, {Path(c[3]).parent.name:c[4] for c in specs if len(c) == 6}, root))
        if stage == 'closeout':
            checks = lint.CHECKBOX.findall((change / 'tasks.md').read_text(encoding='utf8'))
            if not checks or any(c.lower() != 'x' for c in checks) or lint._legal_hold(change):
                raise ValueError('unfinished tasks or archive hold')
        if issues:
            return {'status': 'blocked', 'reason': 'requirement lint failed',
                    'issues': [dict(code=i.code, subject=i.subject, detail=i.detail) for i in issues]}
        return {'status': 'ready', 'mode': row[2], 'tests': sorted(tests), 'task_id': task_id,
                'business_acceptance_required': True,
                'index_sha256': hashlib.sha256(index.read_bytes()).hexdigest(),
                'package_sha256': lint.package_fingerprint(change) if change.is_dir() else None}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {'status': 'blocked', 'reason': str(exc)}


def implementation_prompt(task_id: str) -> str:
    return (f'\n按 openspec/changes/{task_id}/tasks.md 的同一份任务清单执行；'
            '使用 executing-plans + test-driven-development，在当前已批准执行会话串行切片，'
            '先写/更新 pytest 并观察预期 RED，再最小实现和 GREEN；'
            '最终由原 test 阶段在受影响子项目目录完整运行 pytest，不在仓库根混跑。'
            '保留已冻结独审、HEAD 绑定及专业签认；不自行调用 subagent-driven-development。'
            '不得 git commit/push/ff；提交只由原外层核对该阶段逐文件明确授权后执行。'
            'tasks.md 若是封存输入，报告完成项与证据给原外层回写，不另起任务清单。')


def commit_allowed(approval: dict, *, phase: str, paths: list[str]) -> bool:
    grant = approval.get('git_commit') if isinstance(approval, dict) else None
    return (isinstance(grant, dict) and grant.get('phase') == phase and bool(paths)
            and isinstance(grant.get('allowed_paths'), list)
            and all(isinstance(p, str) for p in grant['allowed_paths'])
            and set(paths).issubset(grant['allowed_paths']))
