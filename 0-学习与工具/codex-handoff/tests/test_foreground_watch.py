"""One foreground wake with real queue/lock CLIs; implementation is a local fixture.

These tests never call an LLM, the running listener, a scheduler or production.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_feedback_workflow import load, BASE


QUEUE_DIR = '1-转型规划/0-全景路线图'
MECHANISM = QUEUE_DIR + '/跨桌任务队列-机制环境.md'
BUSINESS = QUEUE_DIR + '/跨桌任务队列-业务场景.md'
WHO = 'fixture-foreground'


def ref(path, root):
    return {'path': path.relative_to(root).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def foreground(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    tools = root / '0-学习与工具'
    tools.mkdir()
    for name in ('工具-共享文档编辑锁.py', '工具-队列查询.py',
                 '工具-队列结构lint.py', '工具-opener块lint.py', '工具-密钥扫描lint.py'):
        shutil.copyfile(BASE.parent / name, tools / name)
    # Current CLIs use this authoritative parser, not the reduced fallback.
    package = Path('5-平台底座/zhuopin_platform/zhuopin_platform')
    for name in ('__init__.py', 'shared_tools/__init__.py', 'shared_tools/queue_table.py',
                 'shared_tools/followup_gate.py'):
        target = root / package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE.parents[1] / package / name, target)
    (root / '.gitignore').write_text('*.editlock*\nreports/\n__pycache__/\n.pytest_cache/\n', encoding='utf8')
    (root / 'docs').mkdir()
    for row in (1, 2, 3, 4):
        (root / f'docs/approval-{row}.md').write_text(
            f'Shao Peishen fixture approval for original row {row}: isolated candidate and pytest only.',
            encoding='utf8')
    header = ('| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n'
              '|---|---|---|---|---|---|---|---|\n')
    rows = ''.join(
        f'| {n} | Fixture {n} | 未领 | `docs/approval-{n}.md` | Return 42 | '
        f'[S:open][D:业] 原离网批准保持 | `candidate/task{n}.py` | 2026-11-15 |\n'
        for n in (1, 2, 3))
    p = root / MECHANISM
    p.parent.mkdir(parents=True)
    p.write_text('> **编号高水位线：§一 #3 ｜ §四 #0**\n\n## 一、任务看板\n\n' + header +
                 '\n## 二、待 commit 批次\n\n| 批次 | 文件清单 | 说明 | 状态 |\n|---|---|---|---|\n'
                 f'| B-fixture-setup | `{MECHANISM}`、`{BUSINESS}` | 原测试设置写入 | 在办（预登记，收工时精确化） |\n'
                 '\n## 三、冻结事项\n\n\n## 四、决策台账\n\n'
                 '| # | 事项 | 等谁 | 截止 |\n|---|---|---|---|\n', encoding='utf8')
    (root / BUSINESS).write_text('## 一、任务看板\n\n' + header + rows, encoding='utf8')
    for argv in (['git', 'init', '-q'], ['git', 'config', 'user.name', 'fixture'],
                 ['git', 'config', 'user.email', 'fixture@example.invalid'],
                 ['git', 'config', 'core.longpaths', 'true'],
                 ['git', 'add', '-A'], ['git', 'commit', '-qm', 'synthetic fixture baseline']):
        subprocess.run(argv, cwd=root, check=True, capture_output=True)
    calls = []

    def execute(argv, *, cwd=root, timeout=90, input_text=None):
        argv = [str(x) for x in argv]
        if len(argv) > 1 and Path(argv[1]).name in ('工具-队列查询.py', '工具-共享文档编辑锁.py'):
            argv[1] = str(tools / Path(argv[1]).name)
        env = dict(os.environ)
        for name in ('ZHUOPIN_CODEX_FIXTURE_ROOT', 'ZHUOPIN_CODEX_RUNTIME', 'ZHUOPIN_CODEX_STATE'):
            env.pop(name, None)
        proc = subprocess.run(argv, cwd=cwd, input=input_text, capture_output=True,
                              text=True, encoding='utf8', timeout=timeout, env=env)
        result = {'exit': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
        calls.append({'argv': argv, 'result': result})
        return result

    driver = load('workflow_driver')
    context = load('queue_context')

    def cli(*args):
        return execute([sys.executable, str(tools / '工具-共享文档编辑锁.py'), *args])

    def scope(ctx):
        row = ctx['row']
        return {'row': row, 'who': WHO, 'batch': f'B-1115_fixture{row}',
                'queue_sha256': ctx['queue_sha256'],
                'approval_scope': 'Original fixture approval: isolated implementation and pytest only',
                'approval_refs': [ref(root / f'docs/approval-{row}.md', root)],
                'allowed_paths': [f'candidate/task{row}.py', f'tests/test_task{row}.py'],
                'active_writers': []}

    return root, driver, context, execute, cli, scope, calls


def acquire(cli):
    result = cli('acquire', '--who', WHO)
    assert result['exit'] == 0, result


def release(cli):
    result = cli('release', '--who', WHO)
    assert result['exit'] == 0, result


def test_preregister_missing_target_before_first_write(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    ctx = context.load_context(root, 1, execute=execute)
    plan = scope(ctx)
    target = root / plan['allowed_paths'][0]
    assert not target.exists()
    acquire(cli)
    receipt = driver.claim_native_slice(root, plan, execute=execute)
    assert receipt['status'] == 'claimed' and receipt['preregistered'] is True
    assert not target.exists()
    claimed = context.load_context(root, 1, execute=execute)
    assert claimed['owner'].startswith(WHO)
    assert all(path in claimed['scope'] for path in plan['allowed_paths'])
    assert plan['approval_scope'] in claimed['source']
    assert any('append-row' in c['argv'] and '在办（预登记' in ' '.join(c['argv']) for c in calls)
    release(cli)


def test_rejected_registration_never_writes_target(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    ctx = context.load_context(root, 1, execute=execute)
    plan = scope(ctx)
    original = (root / BUSINESS).read_bytes()
    acquire(cli)

    def reject(argv, **kwargs):
        if 'append-row' in argv and '二' in argv:
            return {'exit': 1, 'stdout': '', 'stderr': 'fixture preregistration rejected'}
        return execute(argv, **kwargs)

    with pytest.raises(ValueError, match='preregistration'):
        driver.claim_native_slice(root, plan, execute=reject)
    assert not (root / plan['allowed_paths'][0]).exists()
    assert (root / BUSINESS).read_bytes() == original
    release(cli)


@pytest.mark.parametrize('path', ['../escape.py', '/outside.py', 'C:/outside.py',
                                  'candidate/*.py', 'candidate/../escape.py', 'candidate/'])
def test_unsafe_scope_fails_before_queue_mutation(foreground, path):
    root, driver, context, execute, cli, scope, calls = foreground
    plan = scope(context.load_context(root, 1, execute=execute))
    plan['allowed_paths'] = [path]
    acquire(cli)
    calls.clear()
    with pytest.raises(ValueError, match='path|scope'):
        driver.claim_native_slice(root, plan, execute=execute)
    assert not any('append-row' in c['argv'] or 'edit-row' in c['argv'] for c in calls)
    release(cli)


def test_drifted_approval_is_not_permission(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    plan = scope(context.load_context(root, 1, execute=execute))
    plan['approval_refs'][0]['sha256'] = '0' * 64
    acquire(cli)
    with pytest.raises(ValueError, match='approval'):
        driver.claim_native_slice(root, plan, execute=execute)
    assert not (root / plan['allowed_paths'][0]).exists()
    release(cli)


@pytest.mark.parametrize('owner', ['other-current-writer',
    'Codex现行workflow／全自动泳道看护任务池；本轮唯一实施认领：WinCodex-1115KH2，原边界保持'])
def test_other_writer_and_touch_conflict_are_not_reclaimed(foreground, owner):
    root, driver, context, execute, cli, scope, calls = foreground
    acquire(cli)
    assert cli('edit-row', '--who', WHO, '--section', '一', '--number', '1',
               '--domain', '业', '--set', '领取方=' + owner)['exit'] == 0
    plan = scope(context.load_context(root, 1, execute=execute))
    with pytest.raises(ValueError, match='writer'):
        driver.claim_native_slice(root, plan, execute=execute)
    plan = scope(context.load_context(root, 2, execute=execute))
    plan['active_writers'] = [{'who': 'other-current-writer', 'allowed_paths': ['candidate/']}]
    with pytest.raises(ValueError, match='conflict'):
        driver.claim_native_slice(root, plan, execute=execute)
    assert not (root / 'candidate').exists()
    release(cli)


def test_frozen_and_review_only_items_are_not_claimed(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    acquire(cli)
    for row, state in ((1, 'hold'), (2, 'timed=2026-11-01')):
        result = execute([sys.executable, str(root / '0-学习与工具/工具-共享文档编辑锁.py'),
            'edit-row', '--who', WHO, '--domain', '业', '--section', '一', '--number', str(row), '--stdin-json'],
            input_text=json.dumps({'set': {'状态': f'[S:{state}][D:业] 原边界保持'}}, ensure_ascii=False))
        assert result['exit'] == 0, result
        with pytest.raises(ValueError, match='eligible|review|state'):
            driver.claim_native_slice(root, scope(context.load_context(root, row, execute=execute)), execute=execute)
    assert not (root / 'candidate').exists()
    release(cli)


def test_single_wake_creates_candidate_writes_checkpoint_and_refreshes_pool(foreground, monkeypatch, capsys):
    root, driver, context, execute, cli, scope, calls = foreground
    bridge = load('hook_bridge')
    event = {'hook_event_name': 'UserPromptSubmit', 'prompt': '开启泳道看护'}
    monkeypatch.setattr(bridge.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(json.dumps(event).encode())))
    assert bridge.main() == 0
    route = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'zhuopin-lane-watch' in route and 'claim-slice' in route
    built = []

    def resolve(ctx):
        if ctx['row'] == 1:
            return {'blocked_reason': 'fixture independent prerequisite unavailable'}
        if ctx['row'] == 3:
            return {'blocked_reason': 'fixture new design decision required'}
        return scope(ctx)

    def implement(ctx, receipt):
        assert receipt['preregistered'] and receipt['row'] == 2
        return build_fixture(root, context, execute, ctx, receipt, built)

    result = driver.consume_native_watch(root, who=WHO, resolve_scope=resolve,
        perform_slice=implement, execute=execute)
    assert built == [2]
    assert result['delivery_accepted'] is False
    assert any(x['row'] == 1 and x['status'] == 'blocked' for x in result['outcomes'])
    assert any(x['row'] == 2 and x['status'] == 'checkpointed' for x in result['outcomes'])
    assert result['pool_rechecks'] >= 2
    final = context.load_context(root, 2, execute=execute)
    assert 'candidate/task2.py' in final['source'] and 'mock' in final['source']
    assert (root / 'candidate/task2.py').is_file()
    assert not any('codex' == Path(c['argv'][0]).stem for c in calls)
    print(json.dumps({'fixture': 'one_short_wake', 'outcomes': result,
                     'actual_candidate': ref(root/'candidate/task2.py', root)}, ensure_ascii=False))


def test_pre_registration_does_not_relax_normal_missing_entity_guard(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    acquire(cli)
    result = cli('append-row', '--who', WHO, '--section', '二', '--cell', 'B-1115_missing',
                 '--cell', '`candidate/missing.py`', '--cell', 'fixture', '--cell', '待明确提交指令')
    assert result['exit'] != 0
    assert '凭据形状判据正本无法加载' not in result['stdout']
    assert 'missing.py' in result['stdout']
    assert not (root / 'candidate/missing.py').exists()
    release(cli)


def test_missing_lock_and_drifted_row_never_reach_registration(foreground):
    root, driver, context, execute, cli, scope, calls = foreground
    plan = scope(context.load_context(root, 1, execute=execute))
    with pytest.raises(ValueError, match='lock'):
        driver.claim_native_slice(root, plan, execute=execute)
    acquire(cli)
    assert cli('edit-row', '--who', WHO, '--domain', '业', '--section', '一',
               '--number', '1', '--set', '期望产出=changed original target')['exit'] == 0
    with pytest.raises(ValueError, match='drift'):
        driver.claim_native_slice(root, plan, execute=execute)
    assert not (root / 'candidate').exists()
    release(cli)


def build_fixture(root, context, execute, ctx, receipt, built):
    row = ctx['row']
    assert receipt['preregistered']
    current = context.load_context(root, row, execute=execute)
    assert current['owner'].startswith(WHO)
    assert all(p in current['scope'] for p in receipt['allowed_paths'])
    module, test = [root / p for p in receipt['allowed_paths']]
    test.parent.mkdir(exist_ok=True)
    test.write_text('import runpy\nfrom pathlib import Path\n'
        'def test_value():\n'
        f'    assert runpy.run_path(str(Path(__file__).parents[1]/"candidate/task{row}.py"))["VALUE"] == 42\n', encoding='utf8')
    red_junit = root / f'reports/candidate-red{row}.xml'
    red = execute([sys.executable, '-m', 'pytest', str(test), '-q', '--junitxml=' + str(red_junit)], cwd=test.parent)
    assert red['exit'] == 1 and 'FileNotFoundError' in red['stdout'], red
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text('VALUE = 42\n', encoding='utf8')
    junit = root / f'reports/candidate{row}.xml'
    result = execute([sys.executable, '-m', 'pytest', str(test), '-q', '--junitxml=' + str(junit)], cwd=test.parent)
    assert result['exit'] == 0, result
    built.append(row)
    return {'candidate': [ref(module, root), ref(test, root)],
            'verification': {'exit': 0, 'junit': ref(junit, root), 'level': 'mock', 'red_junit': ref(red_junit, root)},
            'next_action': 'fixture candidate ready for original full acceptance; no production'}


@pytest.mark.parametrize('failure', ['write', 'readback'])
def test_failed_preregistration_continues_next_independent_item(foreground, failure):
    root, driver, context, execute, cli, scope, calls = foreground
    built = []
    def reject(argv, **kwargs):
        if ('B-1115_fixture1' in argv and
            (('append-row' in argv and failure == 'write') or ('--field' in argv and failure == 'readback'))):
            return {'exit': 1, 'stdout': '', 'stderr': 'fixture preregistration rejection'}
        return execute(argv, **kwargs)
    result = driver.consume_native_watch(root, who=WHO,
        resolve_scope=lambda ctx: scope(ctx) if ctx['row'] < 3 else {'blocked_reason': 'fixture prerequisite'},
        perform_slice=lambda ctx, receipt: build_fixture(root, context, execute, ctx, receipt, built), execute=reject)
    assert built == [2], result
    assert not (root / 'candidate/task1.py').exists()
    assert (root / 'candidate/task2.py').exists()
    assert result['pool_rechecks'] >= 2
    final = context.load_context(root, 1, execute=execute)
    assert 'preregistration' in final['source'], result
    print(json.dumps({'fixture': failure, 'outcomes': result, 'actual_candidate': ref(root/'candidate/task2.py', root)}, ensure_ascii=False))


def test_pool_addition_before_hold_is_consumed_without_second_wake(foreground, monkeypatch):
    root, driver, context, execute, cli, scope, calls = foreground
    native_tools = driver._native_tools
    reads, built = [], []
    def wrapped_tools(*args):
        module, lock = native_tools(*args)
        original = module.list_rows
        def list_rows(*args, **kwargs):
            reads.append(1)
            if len(reads) == 2:
                assert cli('acquire', '--who', WHO, '--reserve', '1', '--section', '一')['exit'] == 0
                assert cli('append-row', '--who', WHO, '--domain', '业', '--section', '一', '--number', '4',
                    '--cell', 'new independent fixture', '--cell', '未领', '--cell', '`docs/approval-4.md`',
                    '--cell', 'Return 42', '--cell', '[S:open][D:业] original fixture approval',
                    '--cell', '`candidate/task4.py`', '--cell', '2026-11-15')['exit'] == 0
                release(cli)
            return original(*args, **kwargs)
        module.list_rows = list_rows
        return module, lock
    monkeypatch.setattr(driver, '_native_tools', wrapped_tools)
    result = driver.consume_native_watch(root, who=WHO,
        resolve_scope=lambda ctx: scope(ctx) if ctx['row'] == 4 else {'blocked_reason': 'fixture prerequisite'},
        perform_slice=lambda ctx, receipt: build_fixture(root, context, execute, ctx, receipt, built), execute=execute)
    assert built == [4] and result['pool_rechecks'] >= 3, result
    current = context.load_context(root, 4, execute=execute)
    assert 'candidate/task4.py' in current['source']
    print(json.dumps({'fixture': 'pool_addition', 'outcomes': result, 'actual_candidate': ref(root/'candidate/task4.py', root)}, ensure_ascii=False))
