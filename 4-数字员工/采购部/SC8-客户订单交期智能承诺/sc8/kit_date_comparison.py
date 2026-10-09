from __future__ import annotations
from datetime import date
from sc8.baoguan import BaoguanRow, RISK_GREEN, RISK_YELLOW, RISK_GAP, RISK_RED
from sc8.config import ForecastParams
from sc8.forecast import ship_within_horizon

_RANK={RISK_GREEN:0,RISK_YELLOW:1,RISK_GAP:2,RISK_RED:3}

def compare_rows(before: list[BaoguanRow],after: list[BaoguanRow],*,
                 today: date,params: ForecastParams) -> dict:
    if not (len(before) == len(after)):
        raise AssertionError('row count changed')
    results=[];changed=0;moved=0;color_changed=0
    for index,(old,new) in enumerate(zip(before,after)):
        old_key=(old.so_id,old.product_id,old.ship_date,old.qty,old.customer_name,old.customer_id)
        new_key=(new.so_id,new.product_id,new.ship_date,new.qty,new.customer_name,new.customer_id)
        if not (old_key == new_key):
            raise AssertionError(f'row identity mismatch at {index}')
        fields=('kit_date','gap_days','risk','bottleneck_material')
        differs=any(getattr(old,f)!=getattr(new,f) for f in fields)
        eligible=old.ship_date>today and ship_within_horizon(today,old.ship_date,params)
        if not (eligible or not differs):
            raise AssertionError(f'change outside future horizon at {index}')
        if (old.kit_date is None)!=(new.kit_date is None):
            raise AssertionError(f'missing kit date changed at {index}')
        advance=None
        if old.kit_date is not None:
            if not (new.kit_date <= old.kit_date):
                raise AssertionError(f'kit date later at {index}')
            advance=(old.kit_date-new.kit_date).days
            moved+=int(advance>0)
        if not (old.risk in _RANK and new.risk in _RANK):
            raise AssertionError(f'unknown risk at {index}')
        if not (_RANK[new.risk] <= _RANK[old.risk]):
            raise AssertionError(f'risk redder at {index}')
        color_changed+=int(old.risk!=new.risk);changed+=int(differs)
        results.append({'source_index':index,'so_id':old.so_id,
            'product_id':old.product_id,'ship':old.ship_date.isoformat(),
            'qty':old.qty,'before_kit':old.kit_date.isoformat() if old.kit_date else None,
            'after_kit':new.kit_date.isoformat() if new.kit_date else None,
            'before_gap':old.gap_days,'after_gap':new.gap_days,
            'before_risk':old.risk,'after_risk':new.risk,
            'before_bottleneck':old.bottleneck_material,
            'after_bottleneck':new.bottleneck_material,'advance_days':advance})
    return {'rows':results,'changed':changed,'moved':moved,'color_changed':color_changed,
        'coverage':{'branch_direction':'triggered' if changed else 'untriggered_unverified',
                    'date_direction':'triggered' if moved else 'untriggered_unverified',
                    'color_direction':'triggered' if color_changed else 'untriggered_unverified'}}
