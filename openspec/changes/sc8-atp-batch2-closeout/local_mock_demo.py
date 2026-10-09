"""Local synthetic SC8 demo bound to the approved candidate; no production runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from datetime import date, datetime, timezone
from urllib.request import Request, build_opener, ProxyHandler

HERE = Path('C:/Dev/zhuopin-ai/reports/sc8-r2-integration-1009')
TREE = Path('C:/Users/Paul Shao/.codex/worktrees/sc8-rule2-align-1009/zhuopin-ai')
SCENE = TREE / '4-数字员工/采购部/SC8-客户订单交期智能承诺'
HEAD = '640ba847278f4ba775dd2b65bea2dd48137e3b92'
TODAY = date(2026, 9, 2)  # Synthetic business date, not the current operational date.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rule2', choices=['off', 'on'], default='off')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--port', type=int, default=8878)
    args = parser.parse_args()
    actual = subprocess.check_output(['git', '-C', str(TREE), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != HEAD:
        raise SystemExit(f'Candidate mismatch: expected {HEAD}, actual {actual}')
    # These overrides live only in this demo process; no .env is read or edited.
    os.environ.update(SC8_DATA_SOURCE='mock', CUSTOMER_OUTBOUND_ENABLED='false',
                      SC8_KIT_DATE_RULE1='on', SC8_KIT_DATE_RULE2_LITERAL=args.rule2,
                      SC8_NET_INVENTORY='on', PYTHONDONTWRITEBYTECODE='1')
    for name in ('SC8_RUN_REAL', 'U9C_RUN_REAL', 'ZP_GATE_PASSWORD'):
        os.environ.pop(name, None)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(SCENE), str(TREE / '5-平台底座/zhuopin_platform')]

    # Any accidental real connector use fails locally; only this demo's loopback is allowed.
    attempted_egress = []
    allowed_port = [None]
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def guarded(original):
        def call(sock, address):
            if (isinstance(address, tuple) and address[0] == '127.0.0.1'
                    and address[1] == allowed_port[0]):
                return original(sock, address)
            attempted_egress.append(str(address))
            raise PermissionError('Synthetic demo blocks external connections')
        return call

    socket.socket.connect = guarded(connect)
    socket.socket.connect_ex = guarded(connect_ex)

    from flask import abort, request
    from werkzeug.serving import make_server
    from sc8 import baoguan, config, material_board, webapp
    from sc8.baoguan_service import Snapshot, SnapshotStore
    from sc8.case_store import CaseStore
    from sc8.models import SalesOrder
    from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

    context = config.forecast_context()
    specs = [
        ('SYN-FUTURE', '2026-11-30', 'SYN-NF1'),
        ('SYN-GAP-ZERO', '2026-12-01', 'SYN-NF2'),
        ('SYN-RED', '2026-11-27', 'SYN-NF3'),
        ('SYN-PAST', '2026-09-01', 'SYN-NF4'),
        ('SYN-CONFIRMED', '2026-11-30', 'SYN-C1'),
        ('SYN-GREEN', '2026-11-30', 'SYN-C2'),
        ('SYN-NOBOM', '2026-11-30', None),
    ]
    orders = [SalesOrder(so_id=f'FO-{pid}', customer_id='SYN', customer_name='合成客户',
                        item_code=pid, qty=10, required_date=ship, doc_type='预测订单',
                        item_name=pid) for pid, ship, _ in specs]
    bom = [BomRow(product_id=pid, component_id=mid, component_name=f'合成物料 {mid}',
                  level=1, qty_per_unit=1.0, loss_rate=0.0, unit='PCS')
           for pid, _, mid in specs if mid]
    deliveries = [SrmDeliveryOrder(delivery_id=f'D-{mid}', demand_id='', supplier_id='SYN',
                   material_id=mid, qty_committed=20, committed_date=day, status='confirmed')
                  for mid, day in [('SYN-C1', '2026-12-05'), ('SYN-C2', '2026-11-29')]]
    purchase = {mid: 20 for _, _, mid in specs if mid}
    inventory = {mid: 0 for mid in purchase}
    commitments = {d.material_id: [(date.fromisoformat(d.committed_date), d.qty_committed)]
                   for d in deliveries}

    def synthetic_snapshot(**_ignored):
        rows = baoguan.build_dashboard(orders, bom, deliveries, today=TODAY,
                    inventory=inventory, purchase_orders=purchase,
                    material_commitments=commitments, context=context,
                    preserve_input_order=True)
        packed = [baoguan.row_to_dict(r) for r in rows]
        board = material_board.build_material_board(rows, today=TODAY, commitments=commitments,
                     supply_by_material={m: {'suppliers': ['合成供应商']} for m in purchase})
        counts = {k: sum(r['risk'] == k for r in packed) for k in ('red', 'gap', 'yel', 'grn')}
        snap = Snapshot(generated_at=datetime.now().isoformat(timespec='seconds'),
                today=TODAY.isoformat(), rows=packed, counts=counts, status='2',
                param_version=context.params.param_version, components=len(bom), srm_hit=2,
                note=f'MOCK合成演示；业务日期固定 {TODAY}；R2 {args.rule2.upper()}；不作真实签认',
                materials=board.rows, materials_meta=board.meta())
        (HERE / f'demo-{args.rule2}.snapshot.json').write_text(
            json.dumps(snap.to_dict(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        return snap

    webapp.compute_snapshot = synthetic_snapshot  # Production data loaders are never called.
    store = SnapshotStore(None)
    store.set(synthetic_snapshot())
    app = webapp.create_app(snapshot_store=store, case_store=CaseStore(':memory:'),
                           audit=None, ops_webhook_url=None)

    @app.before_request
    def demo_routes_only():
        allowed = {'/', '/materials', '/api/ping', '/api/baoguan', '/api/materials', '/api/refresh'}
        if request.path not in allowed or (request.method != 'GET'
                    and not (request.method == 'POST' and request.path == '/api/refresh')):
            abort(403)

    @app.after_request
    def label_demo(response):
        if response.mimetype == 'text/html' and response.status_code == 200:
            banner = ('<div style="padding:10px;background:#FAEEDA;color:#664300;text-align:center">'
                      f'MOCK 合成演示 · 业务日期 {TODAY} · R2 {args.rule2.upper()} · 不作真实业务签认</div>')
            response.set_data(response.get_data(as_text=True).replace('<body>', '<body>'+banner, 1))
        return response

    server = make_server('127.0.0.1', 0 if args.verify else args.port, app, threaded=True)
    allowed_port[0] = server.server_port
    url = f'http://127.0.0.1:{server.server_port}'
    provenance = {'candidate': actual, 'tree': str(TREE), 'rule2': args.rule2,
                  'business_date': str(TODAY), 'data_source': 'synthetic',
                  'module_files': {m.__name__: m.__file__ for m in (config, baoguan, webapp)},
                  'demo_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'real_calls': False, 'bind': url}
    print(json.dumps(provenance, ensure_ascii=False), flush=True)
    if not args.verify:
        print(f'Demo: {url}/  Materials: {url}/materials  Ctrl+C to stop.', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return

    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    opener = build_opener(ProxyHandler({}))
    results = []
    try:
        for route in ('/', '/api/ping', '/api/baoguan', '/materials', '/api/materials'):
            with opener.open(url+route, timeout=10) as response:
                body = response.read()
                assert response.status == 200
                results.append({'route': route, 'status': response.status,
                                'sha256': hashlib.sha256(body).hexdigest()})
                suffix = 'html' if route in ('/', '/materials') else 'json'
                name = route.strip('/').replace('/', '-') or 'dashboard'
                (HERE / f'demo-{args.rule2}-{name}.{suffix}').write_bytes(body)
        with opener.open(Request(url+'/api/refresh', data=b'{}', method='POST',
                                 headers={'Content-Type': 'application/json'}), timeout=10) as response:
            result = json.load(response)
            assert result['ok'] and result['rows'] == 7
            results.append({'route': '/api/refresh', 'status': response.status, 'response': result})
        from urllib.error import HTTPError
        try:
            opener.open(url+'/cases/new', timeout=10)
            raise AssertionError('Undeclared route exposed')
        except HTTPError as error:
            assert error.code == 403
            results.append({'route': '/cases/new', 'status': 403})
        by_id = {r['id']: r for r in store.get().rows}
        expected = ('2026-12-01', 1, 'yel') if args.rule2 == 'on' else ('2027-02-28', 90, 'red')
        row = by_id['SYN-FUTURE']
        assert (row['kit'], row['gap'], row['risk']) == expected
        assert by_id['SYN-CONFIRMED']['kit'] == '2026-12-05'
        assert by_id['SYN-GREEN']['risk'] == 'grn'
        assert by_id['SYN-NOBOM']['kit'] is None
        if args.rule2 == 'on':
            assert (by_id['SYN-GAP-ZERO']['gap'], by_id['SYN-GAP-ZERO']['risk']) == (0, 'gap')
        assert bool('+rule2' in store.get().param_version) == (args.rule2 == 'on')
        assert store.get().materials, 'Material board fixture must be nonempty'
        assert not attempted_egress
        receipt = {**provenance, 'verified_at': datetime.now(timezone.utc).isoformat(),
                   'exit': 0, 'routes': results, 'expected_future': expected,
                   'snapshot': store.get().to_dict(), 'attempted_egress': attempted_egress}
        (HERE / f'demo-{args.rule2}.receipt.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f'PASS: R2 {args.rule2}, 5 GET + synthetic refresh + route guard; 7 fixture rows', flush=True)
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


if __name__ == '__main__':
    main()
