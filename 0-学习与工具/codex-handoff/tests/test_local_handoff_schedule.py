import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quality_handoff as qh


def module():
    path = Path(__file__).resolve().parents[1] / 'local_handoff_schedule.py'
    spec = importlib.util.spec_from_file_location('local_schedule_test', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_beijing_thursday_boundary_and_first_install_skip():
    m=module(); installed=datetime.fromisoformat('2026-10-28T10:00:00+08:00')
    assert m.period(datetime.fromisoformat('2026-10-29T03:59:59+00:00')) < installed
    assert m.period(datetime.fromisoformat('2026-10-29T04:00:00+00:00')).isoformat()=='2026-10-29T12:00:00+08:00'
    assert m.next_due(datetime.fromisoformat('2026-10-30T18:00:00+08:00')).isoformat()=='2026-11-05T12:00:00+08:00'


@pytest.fixture
def runner(tmp_path):
    m=module(); calls=[]; notices=[]; clock=[datetime.fromisoformat('2026-10-29T12:00:00+08:00')]
    config={'installed_at':'2026-10-28T10:00:00+08:00'}
    s=m.Runner(tmp_path,config,check=lambda:{'items':1},maintain=lambda:calls.append('apply') or {'changed':False,'paths':[]},dirty=lambda:False,notify=lambda x:notices.append(x) or True,clock=lambda:clock[0])
    return m,s,calls,notices,clock


def test_shared_cycle_key_missed_run_and_reentry(runner):
    _,s,calls,_,clock=runner;clock[0]+=timedelta(days=2)
    assert s.run()['outcome']=='maintained'
    assert s.run()['outcome']=='already_completed' and calls==['apply']


def test_dirty_author_only_check_not_archive_success(runner):
    _,s,calls,_,_=runner;s.dirty=lambda:True
    assert s.run()['outcome']=='checked_only' and calls==[]
    assert s.read_state().get('success_period') is None
    s.dirty=lambda:False;assert s.run()['outcome']=='maintained'


def test_installation_does_not_backfill_old_period(runner):
    _,s,calls,_,clock=runner;s.config['installed_at']='2026-10-30T18:00:00+08:00';clock[0]=datetime.fromisoformat(s.config['installed_at'])
    assert s.run()['outcome']=='before_installation' and not calls


def test_hourly_finite_retry_notification_failure_and_dedup(runner):
    _,s,_,notices,clock=runner
    def fail():raise RuntimeError('same failure')
    s.check=fail;s.notify=lambda x:notices.append(x) or False
    assert s.run()['outcome']=='failed'
    assert s.read_state()['unresolved']['notified'] is False
    assert s.run()['outcome']=='retry_not_due'
    clock[0]+=timedelta(hours=1);s.notify=lambda x:notices.append(x) or True
    assert s.run()['outcome']=='failed' and len(notices)==2
    clock[0]+=timedelta(hours=1);s.run();assert len(notices)==2
    clock[0]+=timedelta(hours=1);s.run();clock[0]+=timedelta(hours=1)
    assert s.run()['outcome']=='exhausted' and s.read_state()['attempts']==4
    assert s.reset_retry()['success_recorded'] is False
    assert list((s.root/'operator-resets').glob('*.json'))
    assert s.read_state()['attempts']==0
    s.check=lambda:{}
    assert s.run()['outcome']=='maintained'


def test_recovery_clears_fingerprint_for_future_new_incident(runner):
    _,s,_,notices,clock=runner
    def fail():raise RuntimeError('same failure')
    s.check=fail;s.run();clock[0]+=timedelta(hours=1);s.check=lambda:{};s.run()
    assert s.read_state().get('unresolved') is None
    clock[0]+=timedelta(days=7);s.check=fail;s.run();assert len(notices)==2


def test_concurrent_scheduler_entry_rejected(runner):
    m,s,_,_,_=runner
    with s.guard.lock():
        with pytest.raises(qh.HandoffError,match='busy'):s.run()


def test_repository_identity_distinguishes_projects(tmp_path):
    m=module();assert m.identity(tmp_path/'one')!=m.identity(tmp_path/'two')


@pytest.mark.parametrize('scenario',['success','enable_failure','other_repository','same_repo_other_path'])
def test_installer_fake_scheduler_ownership_and_rollback(tmp_path,scenario):
    root=tmp_path/'任务 中文';folder=root/'0-学习与工具/codex-handoff';folder.mkdir(parents=True)
    for name in ['quality_handoff.py','local_handoff_schedule.py','install_local_handoff_task.ps1']:
        shutil.copyfile(Path(__file__).resolve().parents[1]/name,folder/name)
    (root/'.codex').mkdir();(root/'.codex/runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
    for domain in qh.DOMAINS:
        store=qh.domain_store(root,domain);source=root/store.entry_rel
        source.parent.mkdir(parents=True,exist_ok=True)
        sections=qh.R5_SECTIONS if domain=='phase1' else (None,)
        source.write_text('合成资料 #612\n'*len(sections),encoding='utf-8')
        store.initialize({i:{'title':'合成资料',**({'r5_section':section,'entry_summary':'合成摘要'} if section else {})} for i,section in enumerate(sections,1)})
    rid=module().identity(root)
    harness=root/'fake-install.ps1'
    script=r'''
$global:events=@(); $global:task=$null; $global:lastRun=[datetime]'2000-01-01'
function Get-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath) if($global:task){$global:task} }
function Register-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath,$Xml,[switch]$Force)
 $global:events+='register'; $doc=[xml]$Xml
 $global:task=[pscustomobject]@{TaskName=$TaskName;TaskPath=$TaskPath;Description=$doc.Task.RegistrationInfo.Description;Actions=@([pscustomobject]@{Execute=$doc.Task.Actions.Exec.Command;Arguments=$doc.Task.Actions.Exec.Arguments});Settings=[pscustomobject]@{Enabled=$false};State='Ready'}
}
function Enable-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath) if($env:FAKE_SCENARIO -eq 'enable_failure'){throw 'fake enable failure'}; $global:events+='enable';$global:task.Settings.Enabled=$true }
function Disable-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath) $global:task.Settings.Enabled=$false }
function Start-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath) $global:events+='start';$global:lastRun=Get-Date }
function Get-ScheduledTaskInfo { [CmdletBinding()]param($TaskName,$TaskPath) [pscustomobject]@{LastRunTime=$global:lastRun;LastTaskResult=0;NextRunTime=(Get-Date).AddDays(7)} }
function Unregister-ScheduledTask { [CmdletBinding()]param($TaskName,$TaskPath,[switch]$Confirm) $global:events+='unregister';$global:task=$null }
if($env:FAKE_SCENARIO -eq 'other_repository'){$global:task=[pscustomobject]@{TaskName=$env:FAKE_TASK;TaskPath='\';Description='another repository';Actions=@();Settings=[pscustomobject]@{Enabled=$false}}}
if($env:FAKE_SCENARIO -eq 'same_repo_other_path'){$global:task=[pscustomobject]@{TaskName='old-local-task';TaskPath='\Other\';Description=$env:FAKE_MARKER;Actions=@();Settings=[pscustomobject]@{Enabled=$false}}}
$errorText=$null
try { & $env:FAKE_INSTALLER -Install } catch { $errorText=$_.Exception.Message }
@{events=$global:events;error=$errorText;task_exists=($null -ne $global:task)} | ConvertTo-Json -Compress | Set-Content -LiteralPath $env:FAKE_RESULT -Encoding utf8
'''
    harness.write_text(script,encoding='utf-8');result=root/'fake-result.json'
    env=dict(os.environ,FAKE_SCENARIO=scenario,FAKE_TASK='ZhuopinHandoff-'+rid,FAKE_MARKER='zhuopin-local-handoff:'+rid,FAKE_INSTALLER=str(folder/'install_local_handoff_task.ps1'),FAKE_RESULT=str(result))
    r=subprocess.run(['pwsh','-NoProfile','-File',str(harness)],env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert r.returncode==0,r.stderr
    state=json.loads(result.read_text(encoding='utf-8-sig'))
    if scenario=='success':assert state['error'] is None and state['events']==['register','enable','start']
    elif scenario=='enable_failure':
        assert state['error'] and state['events']==['register','unregister'] and not state['task_exists']
        assert not (root/'reports/local-handoff'/rid/'schedule.json').exists()
    else:assert state['error'] and not state['events'] and state['task_exists']


def test_all_entries_share_one_worker_and_official_locks(tmp_path, monkeypatch):
    m=module(); calls=[]
    for domain in qh.DOMAINS:
        s=qh.domain_store(tmp_path,domain);p=tmp_path/s.entry_rel;p.parent.mkdir(parents=True,exist_ok=True)
        sections=qh.R5_SECTIONS if domain=='phase1' else (None,)
        p.write_text('合成未完资料\n'*len(sections),encoding='utf-8')
        s.initialize({i:{'title':'待核',**({'r5_section':section,'entry_summary':'合成摘要'} if section else {})} for i,section in enumerate(sections,1)})
    def run(argv, **kwargs):
        calls.append((argv[3],argv[4]))
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(m.subprocess,'run',run)
    result=m.maintain_all(tmp_path,'fixture',lambda:False)
    assert not result['changed'] and set(result['domains'])==set(qh.DOMAINS)
    assert calls==[(p['entry'],a) for p in qh.DOMAINS.values() for a in ('acquire','release')]
    assert set(m.related_paths())=={p[k] for p in qh.DOMAINS.values() for k in ('entry','base')}
    calls.clear()
    with pytest.raises(qh.HandoffError,match='author edits'):
        m.maintain_all(tmp_path,'fixture',lambda:True)
    assert calls==[(qh.ENTRY,'acquire'),(qh.ENTRY,'release')]
