"""The declared native registry cannot lose routes silently."""
from pathlib import Path
import importlib.util
import json
import os
import sys
import types
import pytest

SOURCE = Path(__file__).resolve().with_name('工具-Codex规则lint.py')
ANCHOR_FILE = SOURCE

def module():
    raw=SOURCE.read_bytes()
    obj=types.ModuleType('native_registry_contract')
    obj.__file__=str(ANCHOR_FILE)
    sys.modules[obj.__name__]=obj
    exec(compile(raw,str(ANCHOR_FILE),'exec'),obj.__dict__)
    return obj

@pytest.fixture
def lane(tmp_path):
    scopes=['1-转型规划/0-全景路线图','4-数字员工','5-平台底座']
    root=tmp_path
    def write(rel,text):
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf8');return path
    text='# zhuopinAI\n唯一正本\n# Codex规则路由\ndocs/codex/rules/\n先读 `5-平台底座/CODEX-RULES.md`。\n'+'native policy\n'*30
    write('AGENTS.md',text)
    paths={'CLAUDE.md':'AGENTS.md'}
    for scope in scopes:
        paths[scope+'/CLAUDE.md']=scope+'/CODEX-RULES.md'
        write(scope+'/AGENTS.md','本目录正本：`'+scope+'/CODEX-RULES.md`。\n')
        write(scope+'/CODEX-RULES.md','policy\n'*50)
    index=write('docs/codex/directory-rule-map.json',json.dumps({'version':1,'root':'AGENTS.md','paths':paths},ensure_ascii=False))
    return root,index,paths,write

def faults(root):return module().check_sentinels(root)[0]

def test_complete_registry_and_root_counter_are_independent(lane):
    root,_,_,_=lane
    violations,_,total,faulted,_=module().check_sentinels(root)
    assert violations==[]
    assert total==1 and faulted==0

@pytest.mark.parametrize('change', ['missing-entry','empty-entry','wrong-reference','missing-body','missing-root',
    'missing-registry','bad-json','bad-version','bad-root','bad-paths','dropped-scope','parent-traversal','duplicate-key','cross-scope'])
def test_registry_fault_is_never_a_clean_empty_scan(lane,change):
    root,index,paths,write=lane
    data=json.loads(index.read_text(encoding='utf8'))
    if change=='missing-entry':(root/'4-数字员工/AGENTS.md').unlink()
    elif change=='empty-entry':write('4-数字员工/AGENTS.md','')
    elif change=='wrong-reference':
        write('4-数字员工/AGENTS.md','先读 `5-平台底座/CODEX-RULES.md`。')
    elif change=='missing-body':(root/'4-数字员工/CODEX-RULES.md').unlink()
    elif change=='missing-root':(root/'AGENTS.md').unlink()
    elif change=='missing-registry':index.unlink()
    elif change=='bad-json':index.write_text('{',encoding='utf8')
    elif change=='bad-version':data['version']=99
    elif change=='bad-root':data['root']='CLAUDE.md'
    elif change=='bad-paths':data['paths']=[]
    elif change=='dropped-scope':data['paths'].pop('4-数字员工/CLAUDE.md')
    elif change=='parent-traversal':data['paths']['4-数字员工/CLAUDE.md']='../outside/CODEX-RULES.md'
    elif change=='duplicate-key':index.write_text('{"version":1,"version":2}',encoding='utf8')
    elif change=='cross-scope':data['paths']['4-数字员工/CLAUDE.md']='5-平台底座/CODEX-RULES.md'
    if change in ('bad-version','bad-root','bad-paths','dropped-scope','parent-traversal','cross-scope'):
        index.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    assert faults(root),change

def test_generic_nonregistered_fixture_keeps_existing_behavior(tmp_path):
    (tmp_path/'AGENTS.md').write_text('# root\n',encoding='utf8')
    assert module().check_sentinels(tmp_path)==([],[],0,0,0)
