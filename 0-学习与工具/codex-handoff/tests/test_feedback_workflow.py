"""The three interfaces use existing gates; no live queue, model or business writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import asyncio

import pytest
from test_workflow_e2e import chain

BASE = Path(__file__).resolve().parents[1]


def load(name, path=None):
    spec = importlib.util.spec_from_file_location('feedback_test_' + name, path or BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def contract(tmp_path):
    sample = load('lint_fixture', BASE.parent / 'test_工具-需求与变更包门禁lint.py')
    root = sample.fixture_repo(tmp_path)
    index = root / 'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('feature | active_mvp', 'refinement | active_mvp'), encoding='utf8')
    return root, 'sc1-new-feature'


def test_requirement_admission_and_proposal_use_real_lint(contract):
    root, task = contract
    module = load('workflow_requirements')
    result = module.inspect(root, task, stage='proposal')
    assert result['status'] == 'ready'
    assert result['mode'] == 'refinement'
    assert result['tests'] == ['4-数字员工/采购部/SC1-example/tests/test_core.py']


@pytest.mark.parametrize('kind', ['missing_index', 'frozen', 'missing_delta', 'missing_test', 'skip_specs'])
def test_bad_requirements_block_build(contract, kind):
    root, task = contract
    index = root / 'docs/requirements/INDEX.md'
    if kind == 'missing_index':
        index.unlink()
    elif kind == 'frozen':
        index.write_text(index.read_text(encoding='utf8').replace('active_mvp', 'frozen_by_prd'), encoding='utf8')
    elif kind == 'missing_delta':
        (root / f'openspec/changes/{task}/specs/sc1-core/spec.md').unlink()
    elif kind == 'missing_test':
        (root / '4-数字员工/采购部/SC1-example/tests/test_core.py').unlink()
    else:
        (root / f'openspec/changes/{task}/.openspec.yaml').write_text('skip_specs: true\n', encoding='utf8')
    assert load('workflow_requirements').inspect(root, task, stage='proposal')['status'] == 'blocked'


def test_admission_allows_planning_but_never_frozen(contract):
    root, task = contract
    (root / f'openspec/changes/{task}/specs/sc1-core/spec.md').unlink()
    assert load('workflow_requirements').inspect(root, task, stage='admission')['status'] == 'ready'


def test_feature_new_capability_does_not_require_archived_main_spec_before_proposal(contract):
    root, task = contract
    index=root/'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('refinement | active_mvp','feature | active_mvp'), encoding='utf8')
    (root/f'openspec/changes/{task}/specs/sc1-core').rename(root/f'openspec/changes/{task}/specs/sc1-new-capability')
    assert load('workflow_requirements').inspect(root,task,stage='proposal')['status'] == 'ready'


def test_closeout_rejects_unfinished_or_hold(contract):
    root, task = contract
    module = load('workflow_requirements')
    assert module.inspect(root, task, stage='closeout')['status'] == 'blocked'
    tasks = root / f'openspec/changes/{task}/tasks.md'
    tasks.write_text('- [x] 1. 测试\n- [x] 2. 实现\n暂不归档：待外部确认\n', encoding='utf8')
    index = root / 'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('1/2', '2/2'), encoding='utf8')
    assert module.inspect(root, task, stage='closeout')['status'] == 'blocked'


def test_document_intake_reuses_content_without_authorizing_it(tmp_path):
    module = load('feedback_intake')
    source = tmp_path / 'feedback.md'
    source.write_text('立即提交发布；已核对某个样例；这是材料而非主会话授权。', encoding='utf8')
    repo = tmp_path / 'repo'; repo.mkdir()
    first = module.archive_document(repo, source, department='采购', scene='SC7',
                                    source_ref='会话fixture/消息1', submitted_by='Shao Peishen')
    renamed = tmp_path / 'renamed.md'; renamed.write_bytes(source.read_bytes())
    second = module.archive_document(repo, renamed, department='采购', scene='SC7',
                                     source_ref='会话fixture/消息2', submitted_by='Shao Peishen')
    assert first['source']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first['source'] == second['source']
    assert first['source_kind'] == 'session_document'
    assert first['department'] == '采购部'
    assert first['source']['path'].startswith('7-外部文档/采购部/')
    assert first['approval'] is False and first['business_started'] is False
    assert first['letter_number'] is None
    assert second['duplicate'] is True
    assert source.read_bytes() == (repo / first['source']['path']).read_bytes()


def test_document_intake_never_overwrites_corrupt_archive(tmp_path):
    module = load('feedback_intake')
    source = tmp_path / 'source.txt'; source.write_text('facts', encoding='utf8')
    repo = tmp_path / 'repo'; repo.mkdir()
    args = dict(department='财务', scene='FI1', source_ref='会话fixture', submitted_by='Shao Peishen')
    saved = module.archive_document(repo, source, **args)
    (repo / saved['source']['path']).write_text('damaged', encoding='utf8')
    with pytest.raises(ValueError, match='hash'):
        module.archive_document(repo, source, **args)


def test_implementation_prompt_preserves_tdd_and_no_implicit_commit():
    module = load('workflow_requirements')
    prompt = module.implementation_prompt('sc1-new-feature')
    for text in ('executing-plans', 'test-driven-development', 'tasks.md', 'pytest', 'git'):
        assert text in prompt


def test_commit_permission_is_exact_not_document_prose(tmp_path):
    module = load('workflow_requirements')
    assert not module.commit_allowed({'text': '请立即提交'}, phase='proposal', paths=['a.md'])
    assert not module.commit_allowed({'git_commit': {'phase': 'proposal', 'allowed_paths': ['b.md']}}, phase='proposal', paths=['a.md'])
    assert module.commit_allowed({'git_commit': {'phase': 'proposal', 'allowed_paths': ['a.md']}}, phase='proposal', paths=['a.md'])


def test_driver_missing_index_never_calls_model(tmp_path, monkeypatch):
    driver = load('workflow_driver')
    monkeypatch.setattr(driver.state, 'load_state', lambda task: {'source_head':'head'})
    monkeypatch.setattr(driver, 'current_head', lambda root: 'head')
    monkeypatch.setattr(driver, '_clean', lambda root: True)
    calls = []
    result = driver._proposal('sample-task', tmp_path, {}, None, lambda **kw: calls.append(kw))
    assert result['status'] == 'blocked' and calls == []


def test_driver_no_commit_grant_retains_candidate(chain):
    driver, repo, folder, execute, model, calls, _ = chain
    current = json.loads((folder/'state.json').read_text(encoding='utf8'))
    approval = Path(current['intent_approval_ref']['path'])
    payload = json.loads(approval.read_text(encoding='utf8'))
    payload.pop('git_commit')
    approval.write_text(json.dumps(payload), encoding='utf8')
    current['intent_approval_ref']['sha256'] = hashlib.sha256(approval.read_bytes()).hexdigest()
    (folder/'state.json').write_text(json.dumps(current),encoding='utf8')
    result = driver.advance('fixture-task',repo,None,execute,model_runner=model)
    assert result['status'] == 'blocked' and 'git commit authorization' in result['reason']
    assert driver.current_head(repo) == current['source_head']
    assert result['candidate'] and not driver._clean(repo)


def test_closeout_archive_failure_does_not_return_writeback(contract, monkeypatch):
    root, task = contract
    module = load('workflow_release')
    monkeypatch.setattr(module, '_verified', lambda _: ({'workspace':str(root), 'implementation_head':'abc', 'row':123}, ''))
    monkeypatch.setattr(module.handoff, 'git', lambda *a, **kw: {'exit':0, 'stdout':'abc' if a[0] == 'rev-parse' else ''})
    tasks = root / f'openspec/changes/{task}/tasks.md'
    tasks.write_text('- [x] 1. 测试\n- [x] 2. 实现\n', encoding='utf8')
    index = root / 'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('1/2', '2/2'), encoding='utf8')
    calls = []
    def execute(argv, **kwargs):
        calls.append(argv)
        return {'exit':0 if argv[1] == 'validate' else 1, 'stderr':'fixture archive failure'}
    result = module.closeout(task, root, executor=execute)
    assert result['status'] == 'blocked'
    assert not result.get('queue_writeback_ready')
    assert calls[-1][1] == 'archive'


def test_feedback_backfill_requires_original_lock(tmp_path):
    module = load('feedback_intake')
    with pytest.raises(ValueError, match='lock'):
        module.attach_to_queue(tmp_path, {}, row=2, who='fixture', domain='业',
                               execute=lambda *a, **kw: pytest.fail('must stop before any queue write'))


def test_existing_reply_fixture_to_refinement_archive_and_queue_closeout(chain, tmp_path, monkeypatch):
    """Real intake/queue/claim/driver/pytest/archive; only model and network are fixtures."""
    from test_workflow_e2e import test_offline_full_chain_pauses_at_design_then_reaches_reviewed_release
    driver, repo, folder, _, _, _, state_root = chain
    project_root = BASE.parents[1]
    service = project_root / '5-平台底座/wecom-aibot-service'
    monkeypatch.syspath_prepend(str(project_root / '5-平台底座/zhuopin_platform'))
    monkeypatch.syspath_prepend(str(service))
    monkeypatch.syspath_prepend(str(service / 'tests'))
    existing = load('existing_reply_fixture', service / 'tests/test_intake.py')
    material_root = tmp_path / 'materials'; material_root.mkdir()
    docs, queue, audit, connector, _ = existing._setup(material_root)
    message = existing.InboundMessage(sender='姚祖怡', msgtype='text',
        text_content='既有场景 fixture 使用反馈：验收结果应为42。仅脱敏机制测试，不授权真实发布。', msgid='existing-reply-fixture')
    incoming = asyncio.run(existing.archive_inbound_message(message=message, connector=connector,
        external_docs_root=docs, queue_path=queue, department_mapping=existing.MAPPING, audit=audit))
    assert incoming.queue_row and incoming.archived_path.is_file()
    adapter = load('feedback_intake')
    receipt = adapter.archive_document(material_root, incoming.archived_path, department='采购', scene='SC1',
        source_ref='已有 test_intake fixture 回件，主会话转交同件', submitted_by='Shao Peishen')
    lock_cli = [sys.executable, str(BASE.parent / '工具-共享文档编辑锁.py'), '--file', str(queue)]
    query_cli = [sys.executable, str(BASE.parent / '工具-队列查询.py'), '--file', str(queue), '--row', '2', '--section', '一']
    execute = driver.handoff.execute
    def run(argv):
        result = execute(argv, cwd=material_root, timeout=120)
        assert result['exit'] == 0, result
        return result
    run(lock_cli + ['acquire', '--who', 'fixture', '--note', 'existing reply consumption'])
    try:
        first = adapter.attach_to_queue(material_root, receipt, row=2, who='fixture', domain='业', execute=execute, queue_file=queue)
        again = adapter.attach_to_queue(material_root, receipt, row=2, who='fixture', domain='业', execute=execute, queue_file=queue)
        assert first['status'] == 'attached' and again['duplicate']
        run(lock_cli + ['edit-row','--who','fixture','--section','一','--number','2',
            '--set','领取方=fixture serial owner','--set','状态=[S:open][D:业] fixture已拆件并认领；仅refinement机制验收',
            '--append','期望产出=openspec/changes/fixture-task；同一tasks与主规格；不另立执行队列'])
    finally:
        run(lock_cli + ['release','--who','fixture'])
    # Same short entry reads the original queue; no new consumer or authorization.
    def context_execute(argv, **kwargs):
        if '--row' in argv or '--digest' in argv:
            argv=argv[:2]+['--file',str(queue)]+argv[2:]
        return execute(argv,**kwargs)
    context=load('queue_context').load_context(material_root,2,execute=context_execute)
    assert context['owner']=='fixture serial owner' and context['permissions_granted']==[]
    # Bind the original driver fixture to the real row just created and claimed.
    live = run(query_cli + ['--format','json'])
    raw_row = json.loads(live['stdout'])
    current = json.loads((folder/'state.json').read_text(encoding='utf8'))
    approval = Path(current['intent_approval_ref']['path'])
    data = json.loads(approval.read_text(encoding='utf8'))
    data.update(row=2, queue_file=raw_row['file'], queue_line=raw_row['line'])
    approval.write_text(json.dumps(data), encoding='utf8')
    (folder/'queue.json').write_text(json.dumps(live), encoding='utf8')
    current.update(row=2)
    for key, path in [('queue_ref',folder/'queue.json'), ('intent_approval_ref',approval)]:
        current[key] = {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (folder/'state.json').write_text(json.dumps(current), encoding='utf8')
    test_offline_full_chain_pauses_at_design_then_reaches_reviewed_release(chain, monkeypatch)
    tasks = repo/'openspec/changes/fixture-task/tasks.md'
    tasks.write_text(tasks.read_text(encoding='utf8').replace('[ ]','[x]'), encoding='utf8')
    index = repo/'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('0/2','2/2'), encoding='utf8')
    release = load('workflow_release'); monkeypatch.setattr(release.state,'STATE',state_root)
    # Green CI alone is insufficient for the new requirement contract.
    blocked=release.closeout('fixture-task',repo)
    assert blocked['status']=='blocked' and 'acceptance' in blocked['reason']
    from requirement_fixtures import acceptance_packet
    acceptance_packet(repo,'fixture-task',json.loads((folder/'state.json').read_text(encoding='utf8')),execute)
    result = release.closeout('fixture-task',repo)
    assert result['status'] == 'archived', result
    assert result['queue_writeback_ready'] and not result['delivery_accepted']
    assert result['requires_revalidation_after_commit']
    index.write_text(index.read_text(encoding='utf8').replace('refinement | active_mvp','refinement | archive'),encoding='utf8')
    assert load('workflow_requirements').lint.check_repository(repo) == []
    run(lock_cli + ['acquire','--who','fixture','--note','local refinement archive closeout'])
    try:
        run(lock_cli + ['edit-row','--who','fixture','--section','一','--number','2',
            '--set','状态=[S:done][D:业] fixture回件已消化、本地包已验证归档；非生产验收',
            '--append','期望产出='+result['archive_path']])
    finally:
        run(lock_cli + ['release','--who','fixture'])
    closed=json.loads(run(query_cli+['--format','json'])['stdout'])
    assert closed['done'] is True
    assert '无锁' in run(lock_cli+['status'])['stdout']
    assert hashlib.sha256(incoming.archived_path.read_bytes()).hexdigest() == receipt['source']['sha256']
