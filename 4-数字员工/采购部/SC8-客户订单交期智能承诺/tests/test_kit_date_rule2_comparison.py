from datetime import date, timedelta
from dataclasses import replace
from pathlib import Path
import json
import pytest
from sc8 import baoguan, config
from sc8.kit_date_comparison import compare_rows
from sc8.models import SalesOrder
from zhuopin_platform.shared_tools.models import BomRow

TODAY = date(2026,9,2)

@pytest.fixture
def clean_code_identity(monkeypatch):
    """Unit seam only; real Git dirty-state coverage is tested separately."""
    from scripts import compare_kit_date_rule2 as runner
    def clean_git(argv, **kwargs):
        if argv[-2:] == ['rev-parse', 'HEAD']:
            return 'a' * 40 + '\n'
        if 'status' in argv:
            return ''
        raise AssertionError(f'unexpected Git command: {argv}')
    monkeypatch.setattr(runner.subprocess, 'check_output', clean_git)

def make_pair(monkeypatch, *, dates=('2026-11-30','2026-12-01')):
    orders = [SalesOrder(so_id='SAME-FO',customer_id='',customer_name='合成客户',
        item_code='SYN-P',qty=10,required_date=d,doc_type='预测订单') for d in dates]
    material_bom = [BomRow(product_id='SYN-P',component_id='NF',component_name='合成子件',
        level=1,qty_per_unit=1.0,loss_rate=0.0,unit='PCS')]
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','on')
    monkeypatch.setenv('SC8_NET_INVENTORY','off')
    sides=[]
    for flag in ('off','on'):
        monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL',flag)
        sides.append(baoguan.build_dashboard(orders,material_bom,[],today=TODAY,
                                            preserve_input_order=True))
    return sides

def test_duplicate_fo_is_not_collapsed(monkeypatch):
    before,after=make_pair(monkeypatch)
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert [r['source_index'] for r in result['rows']] == [0,1]
    assert result['moved'] == result['color_changed'] == 2
    assert result['coverage']['color_direction'] == 'triggered'

def test_identical_duplicate_rows_still_have_two_positions(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2026-11-30','2026-11-30'))
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert len(result['rows']) == 2 and result['moved'] == 2

def test_later_or_redder_is_rejected(monkeypatch):
    before,after=make_pair(monkeypatch)
    later=[replace(after[0],kit_date=before[0].kit_date+timedelta(days=1)),after[1]]
    with pytest.raises(AssertionError,match='later'):
        compare_rows(before,later,today=TODAY,params=config.ForecastParams())
    fake_before=[replace(before[0],risk=baoguan.RISK_GREEN),before[1]]
    with pytest.raises(AssertionError,match='redder'):
        compare_rows(fake_before,after,today=TODAY,params=config.ForecastParams())

def test_outside_horizon_change_is_rejected(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2027-01-20',))
    altered=[replace(after[0],kit_date=after[0].kit_date-timedelta(days=1))]
    with pytest.raises(AssertionError,match='outside'):
        compare_rows(before,altered,today=TODAY,params=config.ForecastParams())

def test_unchanged_colors_are_explicitly_unverified(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2026-11-20',))
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert result['moved'] == 1 and result['color_changed'] == 0
    assert result['coverage']['color_direction'] == 'untriggered_unverified'

def test_missing_or_bad_cache_never_falls_back(tmp_path,monkeypatch,clean_code_identity):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY','on')
    missing=tmp_path/'missing.json'
    out=tmp_path/'comparison.md'
    arguments=['--cache',str(missing),'--out',str(out),'--today','2026-09-02',
               '--rule1','on','--input-head','a'*40]
    with pytest.raises(SystemExit): runner.main(arguments)
    assert not out.exists()
    missing.write_text('{"orders":[]}',encoding='utf-8')
    with pytest.raises(ValueError,match='cache format invalid'):
        runner.main(arguments)
    assert not out.exists()

def test_runner_restores_both_flags_and_writes_receipt(tmp_path,monkeypatch,clean_code_identity):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY','on')
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','off')
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    cache=tmp_path/'inputs.json';out=tmp_path/'comparison.md'
    cache.write_text(json.dumps({'orders':[],'bom':[],'srm':[],
        'inventory':{},'purchase_orders':{},'commitments':{}}),encoding='utf-8')
    assert runner.main(['--cache',str(cache),'--out',str(out),'--today','2026-09-02',
        '--rule1','on','--input-head','a'*40]) == 0
    import os
    assert os.environ['SC8_KIT_DATE_RULE1'] == 'off'
    assert os.environ['SC8_KIT_DATE_RULE2_LITERAL'] == 'on'
    receipt=json.loads(out.with_suffix('.md.receipt.json').read_text('utf-8'))
    assert receipt['coverage']['color_direction'] == 'untriggered_unverified'
    assert receipt['parameters']['on']['param_version'].endswith('+rule1+rule2')


def test_receipt_hash_binds_the_bytes_consumed_by_loader(tmp_path, monkeypatch, clean_code_identity):
    import hashlib
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY', 'on')
    cache = tmp_path / 'frozen.json'
    out = tmp_path / 'hash-bound.md'
    raw = json.dumps({'orders': [], 'bom': [], 'srm': [], 'inventory': {},
                     'purchase_orders': {}, 'commitments': {}}).encode('utf-8')
    cache.write_bytes(raw)
    original_loader = runner._load_inputs
    def loader_and_later_file_change(source):
        inputs = original_loader(source)
        cache.write_bytes(raw + b'\n')
        return inputs
    monkeypatch.setattr(runner, '_load_inputs', loader_and_later_file_change)
    assert runner.main(['--cache', str(cache), '--out', str(out), '--today', '2026-09-02',
                        '--rule1', 'on', '--input-head', 'a' * 40]) == 0
    receipt = json.loads(out.with_suffix('.md.receipt.json').read_text('utf-8'))
    assert receipt['cache_sha256'] == hashlib.sha256(raw).hexdigest()


def test_external_boundary_rejects_other_checkout(tmp_path):
    from scripts import compare_kit_date_rule2 as runner
    checkout = tmp_path / 'other-checkout'
    checkout.mkdir()
    (checkout / '.git').write_text('gitdir: external-common-dir', encoding='utf-8')
    with pytest.raises(ValueError, match='repository checkouts'):
        runner._external(str(checkout / 'inputs.json'))


def test_same_fo_from_different_customers_cannot_match(monkeypatch):
    before, after = make_pair(monkeypatch)
    wrong_customer = [replace(after[0], customer_name='另一个合成客户'), after[1]]
    with pytest.raises(AssertionError, match='identity mismatch'):
        compare_rows(before, wrong_customer, today=TODAY, params=config.ForecastParams())


def _empty_comparison_args(tmp_path):
    cache = tmp_path / 'synthetic-inputs.json'
    out = tmp_path / 'comparison.md'
    cache.write_text(json.dumps({'orders': [], 'bom': [], 'srm': [],
        'inventory': {}, 'purchase_orders': {}, 'commitments': {}}), encoding='utf-8')
    return out, ['--cache', str(cache), '--out', str(out), '--today', '2026-09-02',
                 '--rule1', 'on', '--input-head', 'a' * 40]


@pytest.mark.parametrize('dirty_status', [' M sc8/forecast.py\n', '?? sc8/extra.py\n'])
def test_runner_refuses_dirty_code_before_loading(tmp_path, monkeypatch, dirty_status):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY', 'on')
    out, argv = _empty_comparison_args(tmp_path)
    monkeypatch.setattr(runner.subprocess, 'check_output',
        lambda command, **kwargs: dirty_status if 'status' in command else 'a' * 40 + '\n')
    with pytest.raises(ValueError, match='dirty code worktree'):
        runner.main(argv)
    assert not out.exists() and not out.with_suffix('.md.receipt.json').exists()


def test_runner_refuses_code_head_drift_before_publication(tmp_path, monkeypatch):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY', 'on')
    out, argv = _empty_comparison_args(tmp_path)
    heads = iter(['a' * 40 + '\n', 'b' * 40 + '\n'])
    monkeypatch.setattr(runner.subprocess, 'check_output',
        lambda command, **kwargs: '' if 'status' in command else next(heads))
    with pytest.raises(ValueError, match='code HEAD changed'):
        runner.main(argv)
    assert not out.exists() and not out.with_suffix('.md.receipt.json').exists()


def test_runner_refuses_code_dirtied_during_calculation(tmp_path, monkeypatch):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY', 'on')
    out, argv = _empty_comparison_args(tmp_path)
    statuses = iter(['', ' M sc8/forecast.py\n'])
    monkeypatch.setattr(runner.subprocess, 'check_output',
        lambda command, **kwargs: next(statuses) if 'status' in command else 'a' * 40 + '\n')
    with pytest.raises(ValueError, match='dirty code worktree'):
        runner.main(argv)
    assert not out.exists() and not out.with_suffix('.md.receipt.json').exists()


def test_code_identity_checks_actual_git_tracked_and_untracked_changes(tmp_path):
    import subprocess
    from scripts import compare_kit_date_rule2 as runner
    repo = tmp_path / 'synthetic-git'
    repo.mkdir()
    subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True, capture_output=True)
    source = repo / 'source.py'
    source.write_text('SYNTHETIC = 1\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(repo), 'add', 'source.py'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Synthetic Test',
        '-c', 'user.email=synthetic@example.invalid', '-c', 'commit.gpgsign=false',
        'commit', '-qm', 'synthetic test only'], check=True, capture_output=True)
    expected = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    assert runner._code_identity(repo) == expected
    source.write_text('SYNTHETIC = 2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='dirty code worktree'):
        runner._code_identity(repo)
    source.write_text('SYNTHETIC = 1\n', encoding='utf-8')
    (repo / 'extra.py').write_text('SYNTHETIC = 3\n', encoding='utf-8')
    with pytest.raises(ValueError, match='dirty code worktree'):
        runner._code_identity(repo)


@pytest.mark.parametrize('supply_case', ['no_bom', 'fully_covered', 'shortage'])
def test_same_display_name_different_customer_codes_cannot_swap(monkeypatch, supply_case):
    orders = [SalesOrder(so_id='SAME-FO', customer_id=customer_id,
        customer_name='', item_code='SYN-P', qty=10, required_date='2026-11-30',
        doc_type='预测订单') for customer_id in ('SYN-C1', 'SYN-C2')]
    material_bom = [BomRow(product_id='SYN-P', component_id='NF', component_name='合成子件',
        level=1, qty_per_unit=1.0, loss_rate=0.0, unit='PCS')]
    if supply_case == 'no_bom':
        material_bom = []
    inventory = {'NF': 100.0} if supply_case == 'fully_covered' else {}
    monkeypatch.setenv('SC8_NET_INVENTORY', 'on')
    monkeypatch.setenv('SC8_KIT_DATE_RULE1', 'on')
    sides = []
    for flag in ('off', 'on'):
        monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL', flag)
        sides.append(baoguan.build_dashboard(orders, material_bom, [], today=TODAY,
            inventory=inventory, preserve_input_order=True))
    before, after = sides
    assert [getattr(row, 'customer_id', None) for row in before] == ['SYN-C1', 'SYN-C2']
    compare_rows(before, after, today=TODAY, params=config.ForecastParams())
    with pytest.raises(AssertionError, match='identity mismatch'):
        compare_rows(before, list(reversed(after)), today=TODAY, params=config.ForecastParams())



@pytest.mark.parametrize('case,expected', [
    ('count', 'row count changed'),
    ('identity', 'identity mismatch'),
    ('outside', 'outside future horizon'),
    ('later', 'kit date later'),
    ('unknown', 'unknown risk'),
    ('redder', 'risk redder'),
    ('switch', 'switch not connected'),
    ('controls', 'non-P1 controls drifted'),
    ('missing', 'missing kit date changed'),
])
def test_failure_guards_survive_python_optimization(case, expected):
    """Real production guards must still reject bad inputs under python -O."""
    import os
    import subprocess
    import sys
    code = r"""
import sys, os
from types import SimpleNamespace
from datetime import date, timedelta
from sc8 import config, baoguan
from sc8.kit_date_comparison import compare_rows
from scripts import compare_kit_date_rule2 as runner
case, expected = sys.argv[1:]
today = date(2026, 9, 2)
def row(**changes):
    fields = dict(so_id='SYN', product_id='SYN-P', ship_date=date(2026,11,30),
        qty=10, customer_name='synthetic', customer_id='SYN-C',
        kit_date=date(2027,2,28), gap_days=90, risk=baoguan.RISK_RED,
        bottleneck_material='SYN-NF')
    fields.update(changes)
    return SimpleNamespace(**fields)
before, after = [row()], [row(kit_date=date(2026,12,1), gap_days=1, risk=baoguan.RISK_YELLOW)]
try:
    if case == 'switch':
        runner.config.forecast_context = lambda: SimpleNamespace(rule1=False, rule2=False)
        runner.build_dashboard = lambda *args, **kwargs: []
        runner._run('on', 'on', ([],[],[],{},{},{}), today)
    elif case == 'controls':
        class Cache:
            def is_file(self): return True
            def read_bytes(self): return b'{}'
        class NoOutput:
            def __getattr__(self, name): raise RuntimeError('must reject before output')
        runner._external = lambda path: Cache() if path == 'cache' else NoOutput()
        runner._code_identity = lambda: 'a' * 40
        runner._load_inputs = lambda source: ([],[],[],{},{},{})
        os.environ['SC8_NET_INVENTORY'] = 'on'
        os.environ['SC8_PO_TRANSIT'] = 'off'
        runner.config.po_transit_enabled = lambda: os.environ['SC8_PO_TRANSIT'] == 'on'
        def drift(flag, rule1, inputs, business_date):
            if flag == 'on': os.environ['SC8_PO_TRANSIT'] = 'on'
            return [], SimpleNamespace(params=config.ForecastParams())
        runner._run = drift
        runner.main(['--cache','cache','--out','out','--today',today.isoformat(),
                     '--rule1','on','--input-head','a'*40])
    else:
        if case == 'count': after = []
        if case == 'identity': after[0].customer_id = 'OTHER'
        if case == 'outside':
            before[0].ship_date = after[0].ship_date = date(2027,1,20)
        if case == 'later': after[0].kit_date = before[0].kit_date + timedelta(days=1)
        if case == 'unknown': after[0].risk = 'UNKNOWN'
        if case == 'redder': before[0].risk = baoguan.RISK_GREEN
        if case == 'missing': after[0].kit_date = None
        compare_rows(before, after, today=today, params=config.ForecastParams())
except AssertionError as exc:
    if expected not in str(exc):
        raise RuntimeError(f'wrong guard: {exc}') from exc
    print('rejected: ' + str(exc))
else:
    raise RuntimeError('invalid input accepted under -O')
"""
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(str(p) for p in sys.path if p)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([sys.executable, '-O', '-c', code, case, expected],
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'rejected: ' in result.stdout and expected in result.stdout
