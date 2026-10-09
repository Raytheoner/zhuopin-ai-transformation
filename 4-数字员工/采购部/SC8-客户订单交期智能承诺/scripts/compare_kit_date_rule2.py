from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date,datetime,timezone
from pathlib import Path

_HERE=Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / '5-平台底座' / 'zhuopin_platform').is_dir():
        sys.path.insert(0, str(_p / '5-平台底座' / 'zhuopin_platform'))
        break
from zhuopin_platform.bootstrap import ensure_paths
ensure_paths(__file__, _HERE.parent.parent)
_REPO_ROOT=next(p for p in _HERE.parents
                if (p/'5-平台底座'/'zhuopin_platform').is_dir())
from scripts.compare_kit_date_rule1 import _load_inputs
from sc8 import config
from sc8.baoguan import build_dashboard
from sc8.kit_date_comparison import compare_rows

@dataclass(frozen=True)
class _FrozenCacheText:
    """Feed one captured read to the existing cache decoder without reopening the file."""
    text: str

    def read_text(self, encoding: str = 'utf-8') -> str:
        return self.text

def _external(path: str) -> Path:
    resolved=Path(path).resolve()
    if any(resolved.is_relative_to(p) for p in
           (_REPO_ROOT,Path('C:/Dev/zhuopin-ai').resolve())) or any(
               (parent / '.git').exists() for parent in (resolved, *resolved.parents)):
        raise ValueError('real input/output must stay outside repository checkouts')
    return resolved

def _run(flag: str,rule1: str,inputs: tuple,today: date):
    keys=('SC8_KIT_DATE_RULE1','SC8_KIT_DATE_RULE2_LITERAL')
    saved={key:os.environ.get(key) for key in keys}
    try:
        os.environ[keys[0]]=rule1;os.environ[keys[1]]=flag
        ctx=config.forecast_context()
        if not (ctx.rule1 == (rule1 == 'on') and ctx.rule2 == (flag == 'on')):
            raise AssertionError('switch not connected')
        orders,bom,srm,inventory,purchase_orders,commitments=inputs
        rows=build_dashboard(orders,bom,srm,today=today,context=ctx,
            inventory=inventory,purchase_orders=purchase_orders,
            material_commitments=commitments,preserve_input_order=True)
        return rows,ctx
    finally:
        for key,value in saved.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value

def _cell(value) -> str:
    return str(value if value is not None else '—').replace('|','\\|').replace('\n',' ')

def _code_identity(repo_root: Path | None = None) -> str:
    """Bind the comparison to one clean tracked/untracked Git worktree."""
    root = _REPO_ROOT if repo_root is None else repo_root
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                   text=True).strip()
    status = subprocess.check_output(['git', '-C', str(root), 'status',
        '--porcelain=v1', '--untracked-files=all'], text=True)
    if status.strip():
        raise ValueError('dirty code worktree; commit the candidate before comparison')
    return head

def main(argv=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--today',required=True,type=date.fromisoformat)
    ap.add_argument('--rule1',required=True,choices=('on','off'))
    ap.add_argument('--input-head',required=True)
    args=ap.parse_args(argv)
    cache=_external(args.cache);out=_external(args.out)
    if not cache.is_file(): ap.error('existing frozen cache is required; no network fallback')
    if not re.fullmatch('[0-9a-f]{40}',args.input_head): ap.error('input-head must be a 40-digit SHA')
    if not config.net_inventory_enabled(): ap.error('production comparison requires net inventory ON')
    code_head = _code_identity()
    try:
        cache_bytes = cache.read_bytes()
        inputs=_load_inputs(_FrozenCacheText(cache_bytes.decode('utf-8')))
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        raise ValueError(f'cache format invalid: {type(exc).__name__}') from exc
    controls={'net_inventory':config.net_inventory_enabled(),
              'po_transit':config.po_transit_enabled(),'bom_max_depth':config.bom_max_depth()}
    before,off_ctx=_run('off',args.rule1,inputs,args.today)
    after,on_ctx=_run('on',args.rule1,inputs,args.today)
    if not (controls == {'net_inventory': config.net_inventory_enabled(), 'po_transit': config.po_transit_enabled(), 'bom_max_depth': config.bom_max_depth()}):
        raise AssertionError('non-P1 controls drifted')
    comparison=compare_rows(before,after,today=args.today,params=off_ctx.params)
    receipt={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'today':args.today.isoformat(),'cache_sha256':hashlib.sha256(cache_bytes).hexdigest(),
        'input_head_declared':args.input_head,'code_head':code_head,
        'code_worktree_clean':True,'controls':controls,
        'rule1':args.rule1,'parameters':{'off':asdict(off_ctx.params),'on':asdict(on_ctx.params)},
        'changed':comparison['changed'],'moved':comparison['moved'],
        'color_changed':comparison['color_changed'],'coverage':comparison['coverage'],
        'network_used':False}
    lines=['# SC8 规则2 前后对照','',
        '齐料日提前 ≠ 交期变好。本项采纳更乐观的估算判据，不代表供应商实际改善。','',
        f'业务日期：{args.today}；输入 SHA：`{receipt["cache_sha256"]}`；代码 HEAD：`{code_head}`。','',
        '覆盖状态：`'+json.dumps(comparison['coverage'],ensure_ascii=False)+'`。',
        'untriggered_unverified 表示本轮空过、未获验证；没有反例不能作为已覆盖。','',
        '| 源位置 | FO | 物料 | 数量 | 出货日 | OFF齐料/色 | ON齐料/色 | 前移天数 |',
        '|---:|---|---|---:|---|---|---|---:|']
    for row in comparison['rows']:
        values=(row['source_index'],row['so_id'],row['product_id'],row['qty'],row['ship'],
                str(row['before_kit'])+'/'+row['before_risk'],
                str(row['after_kit'])+'/'+row['after_risk'],row['advance_days'])
        lines.append('| '+' | '.join(_cell(v) for v in values)+' |')
    if _code_identity() != code_head:
        raise ValueError('code HEAD changed during comparison; use a stable candidate')
    out.parent.mkdir(parents=True,exist_ok=True)
    receipt_path=out.with_suffix(out.suffix+'.receipt.json')
    if out.exists() or receipt_path.exists(): raise FileExistsError('use a new report path')
    with out.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines)+'\n')
    with receipt_path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(receipt,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'report':str(out),'receipt':str(receipt_path),
                      'changed':comparison['changed'],'coverage':comparison['coverage']},
                     ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
