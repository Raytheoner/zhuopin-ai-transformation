"""Read the original queue, never dispatch, claim, authorize or mutate it."""
from __future__ import annotations
import hashlib
import json
from datetime import date
from pathlib import Path
import re
import sys

QUERY = Path(__file__).resolve().parents[1] / '工具-队列查询.py'


def _query(root, execute, *args):
    result = execute([sys.executable, str(QUERY), *args], cwd=root, timeout=90)
    if result.get('exit') != 0 or not isinstance(result.get('stdout'), str):
        raise ValueError('queue query failed; not an empty pool')
    return result['stdout']


def list_rows(root, *, execute, all_open=False, today=None):
    # Full official digest is needed to review elapsed timers. This is still a
    # read-only candidate list; it cannot activate a frozen task or grant scope.
    text = _query(root, execute, '--digest')
    today = today or date.today()
    actionable_ids = set()
    if not all_open:
        # Digest intentionally omits status prose. Preserve the original query's
        # authoritative status-stop filter instead of trying to reconstruct it.
        actionable = _query(root, execute, '--digest', '--actionable')
        actionable_ids = {int(m[1]) for m in re.finditer(r'^(\d+)｜', actionable, re.M)}
        if not actionable_ids and 'digest §一' not in actionable and '0 行' not in actionable:
            raise ValueError('actionable queue query output unrecognized')
    rows = []
    recognized = False
    for line in text.splitlines():
        match = re.match(r'^(\d+)｜(.*?)｜(.*)$', line)
        if not match:
            continue
        recognized = True
        status, task = match[2], match[3]
        state_match = re.search(r'\[S:([^\]]+)\]', status)
        state = state_match[1] if state_match else None
        if state == 'done':
            continue
        item = {'row': int(match[1]), 'status': status, 'task': task}
        if not all_open:
            rest = re.sub(r'^(?:\[[^\]]+\]\s*)+', '', status)
            if any(value.lstrip(' \t*_`').startswith('🛑') for value in (task, rest)):
                continue
            if state in ('open', 'partial') and item['row'] not in actionable_ids:
                continue
            if state not in ('open', 'partial'):
                if state in ('blocked', 'hold'):
                    continue
                if state and state.startswith('timed='):
                    try:
                        if date.fromisoformat(state[6:]) > today:
                            continue
                    except ValueError:
                        pass  # Invalid dates stay visible as unknown, never ready.
                item.update(review_only=True,
                            next_check='只复核原定时/状态与前置；不授予执行，不改原批准/冻结。')
        rows.append(item)
    if not recognized and 'digest §一' not in text and '0 行' not in text:
        raise ValueError('queue query output unrecognized')
    return rows


def resolve_refs(root, text):
    root = Path(root).resolve()
    refs = []
    for raw in dict.fromkeys(re.findall(r'`([^`\n]+)`', text)):
        if '\\' in raw or ':' in raw or not '/' in raw:
            continue
        path = (root / raw).resolve()
        # The original specialized query remains the only queue/letter-table reader.
        if (not path.is_relative_to(root) or path.is_symlink()
                or '跨桌任务队列' in path.name or path.name == 'README-跟进机制与命名约定.md'):
            continue
        if path.is_file():
            refs.append({'path':path.relative_to(root).as_posix(),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return refs


def load_context(root, row, *, execute, expected_sha256=None):
    if not isinstance(row,int) or isinstance(row,bool) or row < 1:
        raise ValueError('positive queue row required')
    args = ['--row',str(row),'--section','一']
    state = json.loads(_query(root,execute,*args,'--format','json'))
    if (state.get('found') is not True or state.get('carrier') != 'live'
            or state.get('error') or state.get('read_errors') != []
            or str(state.get('row')) != str(row) or state.get('section') != '一'):
        raise ValueError('queue query is not a valid live row')
    full = _query(root,execute,*args,'--field','all')
    again = json.loads(_query(root,execute,*args,'--format','json'))
    if again != state:
        raise ValueError('queue drift during context lookup')
    digest = hashlib.sha256(full.encode('utf8')).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError('queue drift since previous checkpoint')
    parts = re.split(r'^【([^】]+)】\s*$',full,flags=re.M)
    fields = {parts[i]:parts[i+1].strip() for i in range(1,len(parts)-1,2)}
    missing = [name for name,key in [('goal','期望产出'),('source','输入（指针）'),('scope','触碰区')]
               if not fields.get(key)]
    refs = resolve_refs(root, fields.get('输入（指针）',''))
    # No language classifier can mint permission. Existing decisions remain
    # available verbatim for the responsible session to verify, without re-asking.
    return {'row':row,'queue_status':state.get('status_field'),'queue_file':state['file'],
            'queue_sha256':digest,'task':fields.get('任务',''),
            'goal':fields.get('期望产出',''),'owner':fields.get('领取方',''),
            'source':fields.get('输入（指针）',''),'source_refs':refs,
            'scope':fields.get('触碰区',''),'constraints_and_history':fields.get('状态',''),
            'missing':missing,'permissions_granted':[],'execution_ready':False,
            'checks_required':['existing_approval_scope','spec_test_acceptance_mapping'],
            'consumer_action':'verify_existing_scope_then_claim_and_build',
            'next':'本摘要不授新权；execution_ready=false仅表示读取器不判授权。开启看护后核原批准/唯一写方/触碰区，已批无冲突即持原锁claim-slice预登记后在本主会话构建，不等第二指令；单项留步继续下一独立项，留步或收口前重查原池。'}
