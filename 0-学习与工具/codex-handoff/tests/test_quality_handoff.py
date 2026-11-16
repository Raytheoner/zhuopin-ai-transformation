"""资料守恒、并发与恢复；仅合成临时目录，无模型/网络/业务状态。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'quality_handoff.py'


def api():
    spec = importlib.util.spec_from_file_location('quality_handoff', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def store(tmp_path):
    m = api()
    root = tmp_path / '中文 项目'
    root.mkdir()
    source = root / '接力 入口.md'
    source.write_bytes(b'\xef\xbb\xbf# legacy\r\n\r\n' + '任务一 #612\r\n任务二 #340\r\n'.encode())
    s = m.Store(root, 'docs/handoff/quality', '接力 入口.md')
    seed = {3: {'title': '任务一', 'topic': 'Q2'}, 4: {'title': '任务二', 'topic': 'QD-B'}}
    s.initialize(seed)
    return m, s, source


def test_exact_bom_crlf_coverage_and_idempotence(store):
    m, s, source = store
    result = s.check()
    assert result['items'] == 2 and result['entry_bytes'] <= 4096
    assert not s.apply()['changed']
    migration = s.read_json('migration.json')
    original = s.path(migration['snapshot']).read_bytes()
    assert original.startswith(b'\xef\xbb\xbf') and original.count(b'\r\n') == 4
    assert [x['line'] for x in migration['lines']] == [1, 2, 3, 4]


@pytest.mark.parametrize('fault', ['missing', 'rebind', 'source_text', 'catalog', 'snapshot', 'revision'])
def test_missing_number_rebinding_and_corruption_fail(store, fault):
    m, s, _ = store
    catalog = s.read_json('catalog.json')
    item_id = next(iter(catalog['known']))
    p = s.item_path(item_id)
    if fault == 'missing':
        p.unlink()
    elif fault in ('rebind', 'source_text'):
        v = json.loads(p.read_text(encoding='utf-8'))
        if fault == 'rebind': v['sources'][0]['start'] += 1
        else: v['original_text'] += 'changed'
        p.write_text(json.dumps(v), encoding='utf-8')
    elif fault == 'catalog':
        catalog['known'].pop(item_id)
        s.path('catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
    elif fault == 'snapshot':
        s.path(s.read_json('migration.json')['snapshot']).write_bytes(b'wrong')
    else:
        h = catalog['revisions'][item_id][0]
        s.path(f'revisions/{item_id}/{h}.json').write_bytes(b'wrong')
    with pytest.raises(m.HandoffError): s.apply()


def test_revision_preserved_and_close_requires_evidence(store):
    m, s, _ = store
    c = s.read_json('catalog.json'); item_id = next(iter(c['known']))
    p = s.item_path(item_id); v = json.loads(p.read_text(encoding='utf-8'))
    v['notes'] = '实际准备仍待核'
    p.write_text(json.dumps(v, ensure_ascii=False), encoding='utf-8')
    assert s.apply()['changed']
    assert len(s.read_json('catalog.json')['revisions'][item_id]) == 2
    v['status'] = 'closed'
    p.write_text(json.dumps(v), encoding='utf-8')
    with pytest.raises(m.HandoffError, match='evidence'): s.apply()
    evidence = s.root / '完成证据.txt'; evidence.write_text('合成验收回执', encoding='utf-8')
    v['completion_evidence'] = [{'path': '完成证据.txt', 'sha256': m.digest(evidence.read_bytes()), 'kind': 'completion'}]
    p.write_text(json.dumps(v), encoding='utf-8')
    s.apply()
    assert s.check()['counts']['closed'] == 1


def test_pagination_complete_and_bounded(store):
    _, s, _ = store
    for i in range(32):
        s.add_record(f'QH-NEW-{i:04}', '新增事项 ' + '中' * 100, '完整记录 ' * 100)
    s.apply()
    pages = list(s.path('views').glob('*.md'))
    assert len(pages) > 1 and all(p.stat().st_size <= 8192 for p in pages)
    text = ''.join(p.read_text(encoding='utf-8') for p in pages)
    assert all(f'QH-NEW-{i:04}' in text for i in range(32))


def test_generated_manual_edit_is_captured_then_requires_explicit_accept(store):
    m, s, source = store
    source.write_text(source.read_text(encoding='utf-8') + '\n作者新待办不得丢\n', encoding='utf-8')
    h = m.digest(source.read_bytes())
    with pytest.raises(m.HandoffError, match='manual'): s.apply()
    assert '作者新待办不得丢' in source.read_text(encoding='utf-8')
    captures = list(s.path('conflicts').glob('*.bin'))
    assert any(m.digest(p.read_bytes()) == h for p in captures)
    s.apply(accept_drift={h})
    assert any('作者新待办不得丢' in p.read_text(encoding='utf-8') for p in s.path('items').glob('*.json'))


@pytest.mark.parametrize('author_edit', [False, True])
def test_interrupted_transaction_recovery_preserves_author(store, author_edit):
    m, s, source = store
    item_id = next(iter(s.read_json('catalog.json')['known']))
    p = s.item_path(item_id); v = json.loads(p.read_text(encoding='utf-8')); v['notes'] = 'revision'
    p.write_text(json.dumps(v), encoding='utf-8')
    def stop(index):
        if index == 0: raise RuntimeError('simulated process loss')
    with pytest.raises(RuntimeError): s.apply(fault=stop)
    assert s.path('.pending.json').exists()
    if author_edit:
        source.write_bytes(b'author concurrent edit')
        with pytest.raises(m.HandoffError, match='conflict'): s.recover()
        assert source.read_bytes() == b'author concurrent edit'
        assert s.path('.pending.json').exists()
    else:
        assert s.recover()['recovery'] == 'completed'
        s.check()


def test_cooperating_process_lock_blocks_concurrent_apply(store):
    _, s, _ = store
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from quality_handoff import Store;s=Store(sys.argv[2],sys.argv[3],sys.argv[4]);s.apply()'
    with s.lock():
        r = subprocess.run([sys.executable, '-c', code, str(MODULE.parent), str(s.root), s.base_rel, s.entry_rel], capture_output=True, text=True, timeout=15)
    assert r.returncode != 0 and 'busy' in r.stderr


def test_check_is_read_only_and_cli_write_requires_official_lock(store):
    _, s, _ = store
    before = {str(p): p.read_bytes() for p in s.base.rglob('*') if p.is_file()}
    s.check()
    after = {str(p): p.read_bytes() for p in s.base.rglob('*') if p.is_file()}
    assert before == after
    with pytest.raises(Exception, match='unsafe|escapes'):
        s.resolve('../outside.md')


@pytest.mark.skipif(os.name != 'nt', reason='Windows CreateFile sharing semantics')
def test_windows_occupied_generated_file_preserves_bytes_and_recovers(store):
    import ctypes
    from ctypes import wintypes
    m, s, _ = store
    p = next(s.path('views').glob('*.md')); original = p.read_bytes()
    item_id = next(iter(s.read_json('catalog.json')['known']))
    item = s.item_path(item_id); v = json.loads(item.read_text(encoding='utf-8')); v['title'] += ' 更新'
    item.write_text(json.dumps(v, ensure_ascii=False), encoding='utf-8')
    create = ctypes.windll.kernel32.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(p), 0x80000000, 1, None, 3, 0x80, None)
    assert handle not in (None, ctypes.c_void_p(-1).value)
    try:
        with pytest.raises(PermissionError): s.apply()
        assert p.read_bytes() == original and s.path('.pending.json').exists()
    finally:
        close = ctypes.windll.kernel32.CloseHandle; close.argtypes = [wintypes.HANDLE]
        close(handle)
    assert s.recover()['recovery'] == 'completed'


def test_real_powershell_readonly_compatibility_entry(tmp_path):
    import shutil
    m = api(); root = tmp_path / '兼容 空格'; root.mkdir()
    folder = root / '0-学习与工具/codex-handoff'; folder.mkdir(parents=True)
    shutil.copyfile(MODULE, folder / MODULE.name)
    shutil.copyfile(MODULE.parent / 'invoke.ps1', folder / 'invoke.ps1')
    source = root / m.ENTRY; source.write_text('合成待办 #612\n', encoding='utf-8')
    m.Store(root).initialize({1: {'title': '合成待办'}})
    config = root / 'runtime.json'; config.write_text(json.dumps({'python': sys.executable, 'state_root': str(root / 'state')}), encoding='utf-8')
    env = dict(os.environ, ZHUOPIN_CODEX_RUNTIME=str(config))
    args = ['pwsh', '-NoProfile', '-File', str(folder / 'invoke.ps1'), '-Mode', 'R5Card', '-R5Action', 'check']
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)['items'] == 1


def test_cli_apply_without_official_lock_rejected(tmp_path):
    r = subprocess.run([sys.executable, str(MODULE), '--root', str(tmp_path), '--apply'], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert r.returncode == 2 and 'official card lock' in r.stdout


def test_r5_registration_does_not_authorize_commit(tmp_path):
    import shutil
    root = tmp_path / '登记中文 空格'; folder = root / '0-学习与工具/codex-handoff'; folder.mkdir(parents=True)
    shutil.copyfile(MODULE.parent / 'invoke.ps1', folder / 'invoke.ps1')
    config = root / 'runtime.json'; config.write_text(json.dumps({'python': sys.executable, 'state_root': str(root / 'state')}), encoding='utf-8')
    (folder.parent / '工具-队列查询.py').write_text('import json;print(json.dumps({"found":False,"error":None,"read_errors":[]}))', encoding='utf-8')
    log = root / 'append.json'
    (folder.parent / '工具-共享文档编辑锁.py').write_text('import sys,json\nfrom pathlib import Path\nif sys.argv[1]=="append-row":Path('+repr(str(log))+').write_text(json.dumps(sys.argv),encoding="utf-8")\nprint("无锁")\n', encoding='utf-8')
    r = subprocess.run(['pwsh', '-NoProfile', '-File', str(folder / 'invoke.ps1'), '-Mode', 'R5Card', '-R5Action', 'register', '-R5Batch', 'B-1030_fixture', '-R5Who', 'fixture', '-R5Note', 'mock'], env=dict(os.environ, ZHUOPIN_CODEX_RUNTIME=str(config)), capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    args = json.loads(log.read_text(encoding='utf-8'))
    assert args[-1].startswith('在办（预登记') and '未授权提交' in args[-1]


def test_actual_repository_gate():
    root = MODULE.parents[2]
    base = root / 'docs/handoff/quality/catalog.json'
    assert base.exists(), 'quality migration must be published before full suite acceptance'
    result = api().Store(root).check()
    assert result['entry_bytes'] <= 4096 and result['items'] > 0


@pytest.mark.parametrize('domain', ['procurement', 'finance'])
def test_domain_metadata_raw_coverage_and_source_isolation(tmp_path, domain):
    m=api();s=m.domain_store(tmp_path,domain);source=tmp_path/s.entry_rel
    source.parent.mkdir(parents=True)
    original=b'\xef\xbb\xbf---\r\ntitle: metadata\r\n---\r\n\r\n# heading\r\n\r\n'+ '#612 未完任务\r\n>\r\n完整段落\r\n'.encode()
    source.write_bytes(original)
    s.initialize({7:{'title':'原编号未完'},9:{'title':'完整段落'}})
    result=s.check();migration=s.read_json('migration.json')
    assert result['items']==2 and not s.apply()['changed']
    assert s.path(migration['snapshot']).read_bytes()==original
    assert len(migration['lines'])==9
    assert {x['line'] for x in migration['lines'] if x['kind']=='item'}=={7,9}
    assert all(i.startswith(m.DOMAINS[domain]['prefix']+'-') for i in s.read_json('catalog.json')['known'])
    with pytest.raises(m.HandoffError,match='domain identity'):
        m.Store(tmp_path,s.base_rel,s.entry_rel).check()
    with pytest.raises(m.HandoffError,match='permanent id'):
        s.item_path('QH-20261020-L007')
    source.write_bytes(source.read_bytes()+'\n人工新增不得丢\n'.encode())
    with pytest.raises(m.HandoffError,match='manual'):s.apply()
    added=list(s.path('items').glob('*-MANUAL-*.json'))
    assert len(added)==1 and added[0].name.startswith(m.DOMAINS[domain]['prefix']+'-')


def test_all_domain_cli_read_only_and_single_domain_lock_required(tmp_path):
    m=api()
    for domain in m.DOMAINS:
        s=m.domain_store(tmp_path,domain);source=tmp_path/s.entry_rel
        source.parent.mkdir(parents=True,exist_ok=True)
        sections=m.R5_SECTIONS if domain=='phase1' else (None,)
        source.write_text('未完 #698\n'*len(sections),encoding='utf-8')
        s.initialize({i:{'title':'合成未完',**({'r5_section':section,'entry_summary':'合成摘要'} if section else {})} for i,section in enumerate(sections,1)})
    args=[sys.executable,str(MODULE),'--root',str(tmp_path)]
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    r=subprocess.run(args+['--domain','all','--check'],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert r.returncode==0 and json.loads(r.stdout)['items']==len(m.DOMAINS)-1+len(m.R5_SECTIONS)
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    r=subprocess.run(args+['--domain','all','--apply'],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert r.returncode==2 and 'read-only' in r.stdout
    for domain in ('procurement','finance'):
        r=subprocess.run(args+['--domain',domain,'--apply','--who','fixture'],capture_output=True,text=True,encoding='utf-8',timeout=15)
        assert r.returncode==2 and 'official card lock required' in r.stdout


def test_actual_all_entry_repository_gate():
    result=api().check_all(MODULE.parents[2])
    assert len(result['domains'])==4 and all(r['entry_bytes']<=4096 for r in result['domains'].values())


@pytest.mark.parametrize('fault', ['missing','duplicate','long_summary'])
def test_phase1_six_section_contract_and_summary_revision_guard(tmp_path, fault):
    m=api();s=m.domain_store(tmp_path,'phase1');source=tmp_path/s.entry_rel
    source.parent.mkdir(parents=True);source.write_text('原完整段落 #639\n'*6,encoding='utf-8')
    s.initialize({i:{'title':section,'r5_section':section,'entry_summary':'当前摘要'} for i,section in enumerate(m.R5_SECTIONS,1)})
    assert [line[3:] for line in source.read_text(encoding='utf-8').splitlines() if line.startswith('## ')]==list(m.R5_SECTIONS)
    item=s.item_path(next(iter(s.read_json('catalog.json')['known'])))
    record=json.loads(item.read_bytes())
    if fault=='missing':record.pop('r5_section')
    elif fault=='duplicate':record['r5_section']=m.R5_SECTIONS[1]
    else:record['entry_summary']='中'*180
    item.write_bytes(m.encode(record))
    with pytest.raises(m.HandoffError,match='R5'):s.apply()


@pytest.mark.parametrize('drift', [False, True])
def test_full_verifier_binds_source_without_trusting_runner_exit(tmp_path, drift):
    import shutil
    root=tmp_path/'验证 中文';folder=root/'0-学习与工具/codex-handoff';folder.mkdir(parents=True)
    shutil.copyfile(MODULE.parent/'verify_serial_handoff.ps1',folder/'verify_serial_handoff.ps1')
    (root/'.codex').mkdir();(root/'.github/workflows').mkdir(parents=True)
    (root/'.github/workflows/ci.yml').write_text('name: fixture',encoding='utf-8')
    (root/'.codex/runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
    (folder/'tests').mkdir();(root/'docs/handoff').mkdir(parents=True)
    (folder/'source.py').write_text('initial',encoding='utf-8')
    (root/'entry.md').write_text('synthetic index',encoding='utf-8')
    (folder/'quality_handoff.py').write_text('DOMAINS={"fixture":{"entry":"entry.md"}}\nif __name__=="__main__":print("{}")\n',encoding='utf-8')
    # 假测试接口只验证封装的哈希/退出码，不能作为真实完整pytest验收。
    (folder/'pytest.py').write_text('from pathlib import Path\n'+('Path("source.py").write_text("author edit")\n' if drift else '')+'print("fake test runner")\n',encoding='utf-8')
    r=subprocess.run(['pwsh','-NoProfile','-File',str(folder/'verify_serial_handoff.ps1'),'-Full','-TempRoot',str(tmp_path/'outside fixture')],capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert r.returncode==(2 if drift else 0),r.stderr
    receipt=next((root/'reports/construction-mechanism-20261030').glob('verify-*/result.json'))
    result=json.loads(receipt.read_text(encoding='utf-8-sig'))
    assert result['pytest_exit']==0 and bool(result['source_drift'])==drift
