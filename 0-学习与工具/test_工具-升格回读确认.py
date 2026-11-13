"""Exact JSON readback; never infer success from an append exit code alone."""
from pathlib import Path
import importlib.util
import json
import sys
import pytest

spec=importlib.util.spec_from_file_location('escalation_receipt_sweep',Path(__file__).with_name('工具-落库sweep.py'))
sweep=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
QUEUE='1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'

def row():
    return {'row':'2','section':'四','found':True,'carrier':'live','file':QUEUE,'line':12,
        'status_field':None,'done':False,
        'reason':'live-open','error':None,'read_errors':[]}

def full_text(number='2',matter='synthetic matter with exact receipt binding'):
    return f'【#】\n{number}\n\n【事项】\n{matter}\n\n【等谁】\nsynthetic\n\n【截止】\nnone\n\n'

def test_valid_official_json_and_text_return_only_bound_matter():
    data=row()
    assert sweep._parse_exact_section_four_query(json.dumps(data),full_text(),'2',QUEUE)=='synthetic matter with exact receipt binding'

def test_windows_crlf_full_text_keeps_exact_identity_checks():
    assert sweep._parse_exact_section_four_query(json.dumps(row()),full_text().replace('\n','\r\n'),'2',QUEUE)=='synthetic matter with exact receipt binding'

@pytest.mark.parametrize('key,value',[
    ('row','3'),('row',2),('section','一'),('found',False),('found',1),
    ('carrier','archive'),('carrier','none'),('file','other-queue.md'),
    ('line',0),('line',True),('line','12'),('status_field','spoofed matter'),
    ('error','partial read failure'),('read_errors',['unreadable other source']),('read_errors',None),
])
def test_wrong_or_incomplete_binding_never_confirms(key,value):
    data=row();data[key]=value
    with pytest.raises(ValueError):sweep._parse_exact_section_four_query(json.dumps(data),full_text(),'2',QUEUE)

@pytest.mark.parametrize('key',['row','section','found','carrier','file','line','status_field','error','read_errors'])
def test_missing_required_metadata_never_confirms(key):
    data=row();del data[key]
    with pytest.raises(ValueError):sweep._parse_exact_section_four_query(json.dumps(data),full_text(),'2',QUEUE)

@pytest.mark.parametrize('raw',['not json','[]','null','{"found":true,"found":false}'])
def test_bad_or_duplicate_json_is_rejected(raw):
    with pytest.raises(ValueError):sweep._parse_exact_section_four_query(raw,full_text(),'2',QUEUE)

@pytest.mark.parametrize('raw',[
    full_text(number='3'),full_text(matter=''),full_text()+'【#】\n2\n',
    'unreadable warning\n'+full_text(),full_text().replace('【事项】','【other】'),
    full_text().replace('【#】\n2\n\n',''),None,
])
def test_wrong_duplicate_or_incomplete_full_text_never_confirms(raw):
    with pytest.raises(ValueError):sweep._parse_exact_section_four_query(json.dumps(row()),raw,'2',QUEUE)
