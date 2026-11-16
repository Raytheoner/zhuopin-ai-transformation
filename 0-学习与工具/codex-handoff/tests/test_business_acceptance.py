import hashlib
import json
from pathlib import Path
import pytest
from test_feedback_workflow import load


def ref(root,path):
    return {'path':path,'sha256':hashlib.sha256((root/path).read_bytes()).hexdigest()}


@pytest.fixture
def evidence(tmp_path):
    change=tmp_path/'openspec/changes/example-task';(change/'specs/example').mkdir(parents=True)
    (change/'specs/example/spec.md').write_text('## ADDED Requirements\n### Requirement: Unknown is visible\nSHALL show unknown.\n#### Scenario: Missing price\n- WHEN absent\n- THEN unknown\n',encoding='utf8')
    (change/'design.md').write_text('已批准的缺数不可当零目标',encoding='utf8')
    for name,content in [('test_core.py','def test_missing(): pass'),('core.py','value=None'),('result.xml','<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="test_core" name="test_missing"/></testsuite></testsuites>'),('audit.json','{"display":"未知","source":null}')]:
        (tmp_path/name).write_text(content,encoding='utf8')
    packet={'task_id':'example-task','level':'mock','design':ref(tmp_path,'openspec/changes/example-task/design.md'),
        'candidate':[ref(tmp_path,'core.py'),ref(tmp_path,'test_core.py')],
        'specs':[ref(tmp_path,'openspec/changes/example-task/specs/example/spec.md')],
        'coverage':[{'scenario':'example::Unknown is visible::Missing price',
            'junit':ref(tmp_path,'result.xml'),'classname':'test_core','testcase':'test_missing',
            'test_source':ref(tmp_path,'test_core.py'),'functional':ref(tmp_path,'audit.json')}]}
    return tmp_path,packet


def test_acceptance_preserves_mock_boundary(evidence):
    root,packet=evidence
    result=load('business_acceptance').verify(root,'example-task',packet)
    assert result['status']=='accepted'
    assert result['level']=='mock' and result['production_accepted'] is False


@pytest.mark.parametrize('fault',['missing_scenario','wrong_scenario','wrong_case','failed','skipped','candidate_drift','spec_drift','missing_functional','wrong_design','outside_source'])
def test_green_count_cannot_hide_requirement_or_evidence_gap(evidence,fault):
    root,p=evidence
    if fault=='missing_scenario':p['coverage']=[]
    elif fault=='wrong_scenario':p['coverage'][0]['scenario']='invented'
    elif fault=='wrong_case':p['coverage'][0]['testcase']='invented'
    elif fault in ('failed','skipped'):
        tag='failure' if fault=='failed' else 'skipped'
        (root/'result.xml').write_text(f'<testsuites><testsuite tests="1"><testcase classname="test_core" name="test_missing"><{tag}/></testcase></testsuite></testsuites>')
        p['coverage'][0]['junit']=ref(root,'result.xml')
    elif fault=='candidate_drift':(root/'core.py').write_text('value=0')
    elif fault=='spec_drift':(root/p['specs'][0]['path']).write_text('changed')
    elif fault=='missing_functional':p['coverage'][0].pop('functional')
    elif fault=='wrong_design':p['design']=ref(root,'core.py')
    else:p['coverage'][0]['test_source']={'path':'../other.py','sha256':'0'*64}
    assert load('business_acceptance').verify(root,'example-task',p)['status']=='blocked'


def test_driver_acceptance_cannot_substitute_an_unverified_junit(evidence):
    root,p=evidence
    assert load('business_acceptance').verify(root,'example-task',p,trusted_junit=[])['status']=='blocked'
