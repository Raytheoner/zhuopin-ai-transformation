"""Native output and negative execution contracts; all state is temporary."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

BASE=Path(__file__).resolve().parent
def load(file):
    spec=importlib.util.spec_from_file_location('native_entry_contract',BASE/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

@pytest.fixture
def renderer(tmp_path,monkeypatch):
    module=load('工具-opener生成.py')
    monkeypatch.setattr(module,'REPO_ROOT',tmp_path)
    monkeypatch.setattr(module,'CLAIMS_FILE',tmp_path/'op-id-claims.jsonl')
    return module

def args(**changes):
    return dict(op_id='OP-1231-X',env='Codex',short_name='机制核验',branch='demo',
        worktree='☐（不新建）',workspace='无',session='新开',line='机制线 B-1231_核验',
        input_pointer='docs/task.md',task_class='A',**changes)

@pytest.mark.parametrize('variant',['standard','reference','subtask_lane','guardian'])
def test_native_variants_have_no_legacy_entry(renderer,variant):
    kw=args(variant=variant)
    if variant=='guardian':kw['branch']='master（看护者不建分支）'
    if variant=='standard':kw.update(do_items=['保持锁、审批与回读'],dont_items=['不得发送'])
    out=renderer.generate_opener(**kw)
    assert '执行环境：Codex' in out
    assert '`AGENTS.md`' in out
    assert 'CLAUDE.md' not in out and 'mcp__ccd_' not in out
    assert 'set_session_title' not in out and 'claude -p' not in out
    assert '用 Task/Agent' not in out and '再在当前 Codex 会话内加 --run' not in out
    if variant=='standard':assert '保持锁、审批与回读' in out and '不得发送' in out
    assert renderer._load_lint_module().check_block(
        renderer._load_lint_module().iter_fenced_blocks(out)[0],
        is_subtask_lane=variant=='subtask_lane')==[]
    assert renderer.CLAIMS_FILE.exists()

@pytest.mark.parametrize('env',['CC','Cowork'])
def test_old_execution_labels_fail_before_id_claim(renderer,env):
    kw=args();kw['env']=env
    with pytest.raises(renderer.OpenerGenError,match='退役'):renderer.generate_opener(**kw)
    assert not renderer.CLAIMS_FILE.exists()

def test_old_section_cannot_silently_become_native_route(renderer):
    with pytest.raises(renderer.OpenerGenError,match='章节'):renderer.generate_opener(**args(claude_section='5'))
    assert not renderer.CLAIMS_FILE.exists()

def test_invalid_output_does_not_claim_id(renderer,monkeypatch):
    lint=renderer._load_lint_module()
    monkeypatch.setattr(lint,'check_block',lambda *_a,**_kw:[('F1','contract failure')])
    monkeypatch.setattr(renderer,'_load_lint_module',lambda:lint)
    with pytest.raises(renderer.OpenerGenError):renderer.generate_opener(**args())
    assert not renderer.CLAIMS_FILE.exists()

@pytest.mark.parametrize('missing',['定向','受影响项目完整 pytest','失败保留证据'])
def test_native_subtask_requires_actual_testing_contract(renderer,missing):
    out=renderer.generate_opener(**args(variant='subtask_lane'))
    lint=renderer._load_lint_module()
    block=lint.iter_fenced_blocks(out.replace(missing,''))[0]
    assert any(code=='F14' for code,_ in lint.check_block(block,is_subtask_lane=True))

def test_retired_emergency_installer_does_not_touch_any_hook(tmp_path,monkeypatch,capsys):
    path=BASE/'codex-handoff/install_readonly_hotfix.py'
    spec=importlib.util.spec_from_file_location('retired_hotfix',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'operate',lambda *_a,**_kw:pytest.fail('installer executed'))
    monkeypatch.setattr(module.sys,'argv',['hotfix','--install'])
    assert module.main()==2
    receipt=json.loads(capsys.readouterr().out)
    assert receipt['status']=='retired' and receipt['changed'] is False
    assert list(tmp_path.iterdir())==[]

def test_task_registration_preview_never_constructs_cim_objects(tmp_path):
    marker=tmp_path/'cim-called'
    script=tmp_path/'preview.ps1'
    target=BASE/'工具-注册轮询守计划任务.ps1'
    quote=lambda p:"'"+str(p).replace("'","''")+"'"
    definitions='\n'.join('function global:'+name+' { Set-Content -LiteralPath '+quote(marker)+" -Value called; throw 'CIM forbidden' }" for name in ['New-ScheduledTaskAction','New-ScheduledTaskTrigger','New-ScheduledTaskSettingsSet','New-ScheduledTaskPrincipal','Get-ScheduledTask','Register-ScheduledTask'])
    script.write_text(definitions+'\n& '+quote(target)+' -WhatIf\nexit $LASTEXITCODE\n',encoding='utf8')
    run=subprocess.run(['pwsh','-NoProfile','-File',str(script)],cwd=tmp_path,capture_output=True,text=True,encoding='utf8',timeout=30)
    assert run.returncode==0,run.stdout+run.stderr
    assert '[WhatIf]' in run.stdout and not marker.exists()

@pytest.mark.parametrize('entry',['工具-Claude包版本探针.ps1','工具-历史包读数核对.ps1'])
def test_package_evidence_without_input_never_probes_old_engine(tmp_path,entry):
    marker=tmp_path/'old-cli-called'
    wrapper=tmp_path/'package-evidence.ps1'
    quote=lambda p:"'"+str(p).replace("'","''")+"'"
    trap=' { Set-Content -LiteralPath '+quote(marker)+" -Value called; throw 'old probe forbidden' }\n"
    wrapper.write_text(''.join('function global:'+name+trap for name in ['claude','Get-AppxPackage','Get-CimInstance'])+
        '$env:ZHUOPIN_CLAUDE_PROBE_FAKE=$null\n$env:ZHUOPIN_PACKAGE_EVIDENCE_JSON=$null\n& '+quote(BASE/entry)+' -Json\n',encoding='utf8')
    run=subprocess.run(['pwsh','-NoProfile','-File',str(wrapper)],cwd=tmp_path,capture_output=True,text=True,encoding='utf8',timeout=20)
    assert run.returncode==0,run.stdout+run.stderr
    result=json.loads(run.stdout)
    assert 'retired' in result, result
    assert result['retired'] is True and result['verdict']=='unknown'
    assert not marker.exists()
