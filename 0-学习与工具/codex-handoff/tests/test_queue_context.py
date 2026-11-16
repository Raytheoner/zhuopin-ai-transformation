import json
from pathlib import Path
import pytest
from test_feedback_workflow import load


def query_fixture(state='open', owner='未领', broken=False):
    full=f'【#】\n7\n\n【任务】\nSC1风险反馈\n\n【领取方】\n{owner}\n\n【输入（指针）】\n`docs/source.md`\n\n【期望产出】\n缺数必须显示未知\n\n【状态】\n[S:{state}][D:业] 尚未批准生产\n\n【触碰区】\nSC1\n'
    def execute(argv,**kwargs):
        if broken:return {'exit':1,'stdout':''}
        if '--digest' in argv:return {'exit':0,'stdout':f'7｜[S:{state}][D:业]｜SC1风险反馈\n'}
        if '--format' in argv:return {'exit':0,'stdout':json.dumps({'row':'7','section':'一','found':True,'carrier':'live','done':state=='done','status_field':state,'file':'queue.md','line':3,'error':None,'read_errors':[]})}
        return {'exit':0,'stdout':full}
    return execute


def test_short_entry_recovers_fields_without_granting_permissions(tmp_path):
    (tmp_path/'docs').mkdir();(tmp_path/'docs/source.md').write_text('已经批准的材料引用，不是新授权',encoding='utf8')
    result=load('queue_context').load_context(tmp_path,7,execute=query_fixture())
    assert result['goal']=='缺数必须显示未知'
    assert result['source_refs'][0]['path']=='docs/source.md'
    assert result['permissions_granted']==[]
    assert result['owner']=='未领'
    assert 'existing_approval_scope' in result['checks_required']
    assert 'approval_evidence' not in result['missing']  # unverified is not absent; do not ask again


@pytest.mark.parametrize('state',['blocked','hold','timed=2026-12-01','done'])
def test_context_never_unlocks_old_states(tmp_path,state):
    result=load('queue_context').load_context(tmp_path,7,execute=query_fixture(state))
    assert result['execution_ready'] is False
    assert result['queue_status']==state


def test_queue_failure_is_not_empty_pool(tmp_path):
    with pytest.raises(ValueError,match='query'):
        load('queue_context').list_rows(tmp_path,execute=query_fixture(broken=True))


def test_reference_escape_never_reads_outside_repo(tmp_path):
    module=load('queue_context')
    assert module.resolve_refs(tmp_path,'`../outside.md` `C:/secrets.txt`')==[]


def test_existing_owner_is_not_reassigned(tmp_path):
    result=load('queue_context').load_context(tmp_path,7,execute=query_fixture(owner='原执行会话'))
    assert result['owner']=='原执行会话'
    assert result['execution_ready'] is False


def test_expected_queue_hash_detects_stale_handoff(tmp_path):
    with pytest.raises(ValueError,match='drift'):
        load('queue_context').load_context(tmp_path,7,execute=query_fixture(),expected_sha256='0'*64)


def digest_fixture(lines):
    return lambda argv, **kwargs: {'exit': 0, 'stdout': '\n'.join(lines)}


@pytest.mark.parametrize('line', [
    '7｜[S:open][D:机]｜🛑 排队，原前置未解',
    '7｜[S:partial][D:机]｜**🛑 排队** 历史仍保留',
    '7｜[S:open][D:机] 🛑 暂非可动｜机制任务',
])
def test_default_pool_does_not_offer_stopped_task_or_status(tmp_path, line):
    module = load('queue_context')
    assert module.list_rows(tmp_path, execute=digest_fixture([line])) == []
    assert [row['row'] for row in module.list_rows(
        tmp_path, execute=digest_fixture([line]), all_open=True)] == [7]


def test_elapsed_timed_row_is_review_only_and_future_remains_out(tmp_path):
    from datetime import date
    rows = load('queue_context').list_rows(tmp_path, execute=digest_fixture([
        '259｜[S:timed=2026-11-01][D:机]｜S1外审排期',
        '95｜[S:timed=2027-03-01][D:业]｜远期覆盖率',
    ]), today=date(2026, 11, 15))
    assert [row['row'] for row in rows] == [259]
    assert rows[0]['review_only'] is True
    assert '不授予' in rows[0]['next_check']


@pytest.mark.parametrize('state', ['blocked', 'hold', 'timed=2099-01-01'])
def test_full_digest_does_not_unlock_frozen_rows(tmp_path, state):
    module = load('queue_context')
    execute = digest_fixture([f'7｜[S:{state}][D:业]｜原任务'])
    assert module.list_rows(tmp_path, execute=execute) == []
    assert len(module.list_rows(tmp_path, execute=execute, all_open=True)) == 1


def test_missing_or_invalid_status_is_visible_for_review(tmp_path):
    rows = load('queue_context').list_rows(tmp_path, execute=digest_fixture([
        '7｜[S:unknown][D:机]｜状态损坏',
        '8｜[D:业]｜状态缺失',
    ]))
    assert [row['row'] for row in rows] == [7, 8]
    assert all(row['review_only'] for row in rows)


def test_stop_mention_inside_task_does_not_freeze_independent_work(tmp_path):
    rows = load('queue_context').list_rows(tmp_path, execute=digest_fixture([
        '7｜[S:open][D:业]｜离网准备；生产🛑仍保留',
    ]))
    assert [row['row'] for row in rows] == [7]


def test_digest_hides_status_body_so_original_actionable_filter_is_required(tmp_path):
    # The real digest prints only [S:][D:], not the leading stop in status prose.
    def execute(argv, **kwargs):
        return {'exit': 0, 'stdout': ('digest §一 0 行' if '--actionable' in argv
            else '7｜[S:open][D:机]｜任务标题没有排队标记\n')}
    assert load('queue_context').list_rows(tmp_path, execute=execute) == []
