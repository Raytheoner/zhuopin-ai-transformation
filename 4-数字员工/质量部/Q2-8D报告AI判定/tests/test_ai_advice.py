import copy
import pytest
from dataclasses import replace
from q2_8d_verdict.document_evidence import DocumentScope,EvidenceBundle,EvidenceRecord
from q2_8d_verdict.models import EightDInput
from q2_8d_verdict.engine import VerdictEngine
from q2_8d_verdict.ai_advice import make_request,validate_advice,AdviceError

def advice_fixture(ruleset):
    scope=DocumentScope('SYNTHETIC-A','T1','B','a'*64)
    text='合成证据：负责人 张三；计划2026-10-15；完成2026-10-15；区域 数量 措施 结果 状态。'
    b=EvidenceBundle(scope,'a'*64,{f'D{i}':text for i in range(1,8)},(EvidenceRecord('p1-s1',1,'1','text',text),),(),(),1,1,True,None,'READ')
    v=VerdictEngine(ruleset=ruleset).evaluate(EightDInput('SYNTHETIC',b.sections,'制造',asil_level='B'))
    p={'source_sha256':b.source_sha256,'oem_label':scope.oem_label,'source_version':scope.source_version,'asil_level':'B','rules_sha256':ruleset.sha256,
       'items':[{'rule_id':r.rule_id,'score':r.score,'refs':['p1-s1'],'quote':'合成证据','reason':'合成：满足本项判据','remediation':'维持并由质量工程师复核','evidence_state':'READ','confidence':'MED'} for r in ruleset.for_scene(v.scene)],'d3_missing':[], 'redline_observations':[]}
    return b,v,p

def test_dynamic_coverage_identity_and_totals(ruleset):
    b,v,p=advice_fixture(ruleset);r=validate_advice(p,b,v,ruleset)
    assert len(r.items)==len(ruleset.for_scene(v.scene))
    assert r.total==ruleset.max_score(v.scene) and r.professional_signoff is False
    assert r.kind=='ai_advice_unconfirmed' and r.disposition=='转人工裁决'
    assert r.redlines[1]['status']=='NOT_ACCEPTED' and r.redlines[2]['status']=='NOT_ACCEPTED'
    req=make_request(b,v,ruleset)
    assert 'M11' in req.prompt and '8b740951' in req.prompt and req.schema_hash

@pytest.mark.parametrize('mutation',['missing','duplicate','foreign','badref','badquote','nan','half','readerror','signoff'])
def test_invalid_advice_never_becomes_complete(ruleset,mutation):
    b,v,p=advice_fixture(ruleset)
    if mutation=='missing':p['items'].pop()
    if mutation=='duplicate':p['items'].append(copy.deepcopy(p['items'][0]))
    if mutation=='foreign':p['oem_label']='OTHER'
    if mutation=='badref':p['items'][0]['refs']=['absent']
    if mutation=='badquote':p['items'][0]['quote']='不存在的证据'
    if mutation=='nan':p['items'][0]['score']=float('nan')
    if mutation=='half':
        sem=next(r for r in ruleset.for_scene(v.scene) if r.is_semantic)
        next(x for x in p['items'] if x['rule_id']==sem.rule_id)['score']=sem.score/2
    if mutation=='readerror':p['items'][0]['evidence_state']='READ_ERROR'
    if mutation=='signoff':p['professional_signoff']=True
    with pytest.raises(AdviceError):validate_advice(p,b,v,ruleset)

def test_deduction_uses_signed_step_cap_and_d3_floor(ruleset):
    b,v,p=advice_fixture(ruleset);p['d3_missing']=['客户端·区域','供应商端·数量']
    next(x for x in p['items'] if x['rule_id']=='D3-06')['score']=0
    r=validate_advice(p,b,v,ruleset)
    assert r.total==ruleset.max_score(v.scene)-3 and r.d3_deduction==2
    p['d3_missing']=['自造字段']
    with pytest.raises(AdviceError):validate_advice(p,b,v,ruleset)

def test_d3_missing_cannot_also_earn_completeness_point(ruleset):
    b,v,p=advice_fixture(ruleset);p['d3_missing']=['客户端·区域']
    with pytest.raises(AdviceError):validate_advice(p,b,v,ruleset)

def test_incomplete_extraction_cannot_make_request(ruleset):
    b,v,p=advice_fixture(ruleset)
    with pytest.raises(AdviceError):make_request(replace(b,complete=False),v,ruleset)

def test_d3_empty_cell_annotation_retains_original_without_new_field(ruleset):
    b,v,p=advice_fixture(ruleset)
    b=replace(b,records=b.records+(EvidenceRecord('empty',1,'2','empty_table_cell',''),))
    p['d3_missing']=['客户端·完成日（empty为空）']
    next(x for x in p['items'] if x['rule_id']=='D3-06')['score']=0
    r=validate_advice(p,b,v,ruleset)
    assert r.d3_missing==('客户端·完成日',) and r.d3_missing_original==('客户端·完成日（empty为空）',)
    p['d3_missing']=['客户端·完成日（p1-s1为空）']
    with pytest.raises(AdviceError):validate_advice(p,b,v,ruleset)
