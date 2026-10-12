"""Run the real source child + unchanged IT orchestrator, with synthetic HTTP only."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

APP=Path(__file__).resolve().parents[1]
FAKE_REQUESTS=r'''
import os,re
class RequestException(Exception):pass
class Timeout(RequestException):pass
class Response:
    def __init__(self,status=200,records=None,payload=None):
        self.status_code=status
        self.text="synthetic-response-canary"
        self.payload=payload if payload is not None else {"code":200,"result":{"records":records or []}}
    def json(self):return self.payload
def get(url,headers=None,params=None,timeout=None,**kwargs):
    assert ".invalid" in url,"Refuse non-synthetic HTTP host"
    q=params["q"].lower()
    if q=="select id from account limit 0,1":return Response(records=[{"id":"account-1"}])
    entity=re.search(r"\bfrom\s+(\w+)",q).group(1)
    offset=int(re.search(r"\blimit\s+(\d+)\s*,",q).group(1))
    mode=os.environ.get("SALES_TEST_MODE","success")
    target=os.environ.get("SALES_TEST_ENTITY","lead")
    row={"id":entity+"-1","phone":"synthetic-phone","email":"synthetic@example.invalid",
         "money":123,"winRate":100,"accountId":"account-1","accountName":"Synthetic Company"}
    if entity==target:
        if mode=="empty":return Response()
        if mode=="first_http":return Response(503)
        if offset:
            if mode=="later_http":return Response(503)
            if mode=="later_timeout":raise Timeout("synthetic timeout")
            if mode=="later_schema":return Response(payload={"code":200,"result":{}})
            if mode=="duplicate" and offset==1:return Response(records=[row])
    return Response(records=[row] if offset==0 else [])
def post(*args,**kwargs):raise AssertionError("No token refresh permitted in simulation")
'''

@pytest.fixture
def chain(tmp_path,monkeypatch):
    path=APP/'tests'/'fixtures'/'run_sync_daily_it.py'
    spec=importlib.util.spec_from_file_location('it_daily_fixture',path)
    it=importlib.util.module_from_spec(spec);spec.loader.exec_module(it)
    monkeypatch.setattr(it,'restrict_acl',lambda *a,**k:True)
    monkeypatch.setattr(it,'inheritance_blocked',lambda *a,**k:True)
    base=tmp_path/'sales';(base/'crm_data').mkdir(parents=True)
    portal=tmp_path/'portal'/'sales_dashboard_data.json';portal.parent.mkdir()
    paths=[base/'crm_data'/'raw_data.json',base/'crm_data'/'dashboard_data.json',portal]
    previous=[
        b'{"previous":"raw-snapshot"}',
        b'{"sync_time":"2026-10-12T14:42:39","kpis":{"total_leads":1721}}',
        b'{"sync_time":"2026-10-12T14:42:39","high_risk_leads":[]}'
    ]
    for p,b in zip(paths,previous):p.write_bytes(b)
    before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]
    fake=tmp_path/'fake';fake.mkdir()
    (fake/'requests.py').write_text(FAKE_REQUESTS,encoding='utf-8')
    (fake/'dotenv.py').write_text('def load_dotenv(*a,**k): return False\n',encoding='utf-8')
    monkeypatch.setenv('PYTHONPATH',str(fake))
    monkeypatch.setenv('XIAOSHOUYI_API_DOMAIN','fixture.invalid')
    monkeypatch.setenv('XIAOSHOUYI_ACCESS_TOKEN','synthetic-only')
    monkeypatch.setattr(sys,'argv',[
        'run_sync_daily.py','--skip-refresh','--base',str(base),
        '--sync-script',str(APP/'xiaoshouyi_data_sync_fixed.py'),'--portal',str(portal)
    ])
    return it,paths,before

@pytest.mark.parametrize('mode,entity',[
    ('later_http','lead'),('later_timeout','account'),('later_schema','opportunity'),
    ('first_http','contact'),('empty','lead'),('empty','contact'),('duplicate','lead')
])
def test_fetch_failure_cannot_overwrite_source_or_publish(chain,monkeypatch,mode,entity):
    it,paths,before=chain
    monkeypatch.setenv('SALES_TEST_MODE',mode);monkeypatch.setenv('SALES_TEST_ENTITY',entity)
    assert it.main()!=0
    assert [(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]==before

def test_complete_fetch_preserves_it_mapping_and_masks_before_publish(chain,monkeypatch):
    it,paths,before=chain
    monkeypatch.setenv('SALES_TEST_MODE','success')
    assert it.main()==0
    raw,dashboard,portal=[json.loads(p.read_bytes()) for p in paths]
    assert {k:len(raw[k]) for k in ('leads','opportunities','customers','contacts')}=={
        'leads':1,'opportunities':1,'customers':1,'contacts':1}
    assert dashboard['kpis']['total_leads']==1
    assert portal['sync_time']==dashboard['sync_time']
    assert portal['sync_time']!='2026-10-12T14:42:39'
    for row in portal['high_risk_leads']:
        assert (row['contact'],row['phone'],row['email'])==('已脱敏','已脱敏','已脱敏')
