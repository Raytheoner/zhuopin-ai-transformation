"""Native preflight wiring with real local Git/PS/query and a synthetic provider."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import pytest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_preflight_batch_fixture',HERE/'test_工具-opener批处理执行v2.py')
batch=importlib.util.module_from_spec(spec);spec.loader.exec_module(batch)
pytestmark=pytest.mark.skipif(os.name!='nt' or shutil.which('pwsh') is None,reason='requires Windows and pwsh')

HEADER='| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n|---|---|---|---|---|---|---|---|\n'
QUEUES={
 '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md':'## 一、任务看板\n\n'+HEADER+
    '| 200 | 合成在办任务 | fixture | 无 | 无 | [S:open][D:机] | 无 | 2026-11-13 |\n'+
    '| 395 | 合成已完任务 | fixture | 无 | 无 | [S:done][D:机] | 无 | 2026-11-13 |\n',
 '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md':'## 一、任务看板\n\n'+HEADER,
 '1-转型规划/0-全景路线图/跨桌任务队列-归档-202608.md':'## 一、任务看板（已完成行）\n\n'+HEADER+
    '| 368 | 合成已归档任务 | fixture | 无 | 无 | [S:open][D:机] | 无 | 2026-08-21 |\n'}

class NativeCase:
    def __init__(self,root):
        self.root=root
        self.script,self.plan=batch.TestBatchCodex().setup(root)
        tools=root/'0-学习与工具'
        for name in ('工具-opener派出前校验.ps1','工具-队列查询.py','工具-opener批处理执行.ps1'):
            shutil.copyfile(HERE/name,tools/name)
        for relative,text in QUEUES.items():
            target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf8')
        base=self.plan.read_text(encoding='utf8')
        blocks=[]
        for identity,title,lane in [('A1','合成归档——队列 #368','lane-skip'),('A2','合成在办——队列 #200','lane-run'),
                                    ('A3','合成完成——队列 #395','lane-run'),('A4','合成无行号——协议〇.8／§四 #44','lane-run')]:
            blocks.append(base.replace('### A1 · 机制验证','### '+identity+' · '+title).replace('泳道：fixture','泳道：'+lane))
        self.plan.write_text('\n'.join(blocks),encoding='utf8')
        self.logs=root/'reports/batch'
        self.original_queue_bytes=self.queue_bytes()

    def queue_bytes(self):return {relative:(self.root/relative).read_bytes() for relative in QUEUES}

    def drop_hook(self):
        text=self.script.read_text(encoding='utf-8-sig')
        needle='    $openers = @(Set-OpenerDispatchDecision -Openers @($openers) -RepoRoot $RepoRoot -Force:$Force)'
        assert text.count(needle)==1
        replacement='    $openers = @($openers | ForEach-Object { $_ | Add-Member -NotePropertyName Skip -NotePropertyValue $false -PassThru })'
        self.script.write_text(text.replace(needle,replacement),encoding='utf-8-sig')

    def run(self,*extra,enabled=True,legacy=False):
        if legacy:
            args=[shutil.which('pwsh'),'-NoProfile','-File',str(self.root/'0-学习与工具/工具-opener批处理执行.ps1'),'-Plan',str(self.plan),'-Yes']
        else:
            args=[shutil.which('pwsh'),'-NoProfile','-File',str(self.script),'-Plan',str(self.plan),'-LogDir',str(self.logs),
                  '-Yes','-MaxParallel','1','-StaggerSec','0','-ContextPollSec','1']
        if enabled:args.append('-ConsumerEnabled')
        return subprocess.run(args+list(extra),cwd=self.root,capture_output=True,text=True,encoding='utf8',timeout=90)

    def directory(self,legacy=False):
        if not legacy:return self.logs
        folders=list((self.root/'reports/opener-batch').iterdir());assert len(folders)==1
        return folders[0]

    def rows(self,legacy=False):return json.loads((self.directory(legacy)/'summary.json').read_text(encoding='utf-8-sig'))
    def requests(self,legacy=False):return [json.loads(p.read_text(encoding='utf8')) for p in self.directory(legacy).rglob('request-args.json')]

@pytest.fixture
def case(tmp_path):
    value=NativeCase(tmp_path)
    yield value
    assert value.queue_bytes()==value.original_queue_bytes

def assert_native_requests(case,expected,legacy=False):
    requests=case.requests(legacy)
    assert len(requests)==expected
    for args in requests:
        assert args[args.index('--model')+1]=='gpt-6-luna'
        assert Path(args[0]).resolve().is_relative_to(case.root)
    return requests

def test_default_pause_starts_no_provider(case):
    result=case.run(enabled=False)
    assert result.returncode==4 and 'consumer-paused' in result.stdout
    assert not list(case.root.rglob('request-args.json'))
    assert not (case.root/'.claude/worktrees/fixture').exists()

def test_native_enabled_preflight_skips_archived_and_done(case):
    result=case.run();assert result.returncode==0,result.stdout+result.stderr
    rows={r['Id']:r for r in case.rows()}
    assert rows['A1']['Status']==rows['A3']['Status']=='SKIPPED'
    assert rows['A2']['Status']==rows['A4']['Status']=='OUTPUT-NEEDS-REVIEW'
    assert rows['A2']['DeliveryAccepted'] is False and rows['A4']['DeliveryAccepted'] is False
    assert_native_requests(case,2)

def test_all_skipped_opens_no_worktree_and_no_provider(case):
    result=case.run('-Only','A1,A3');assert result.returncode==0,result.stdout+result.stderr
    assert len(case.rows())==2 and all(r['Status']=='SKIPPED' for r in case.rows())
    assert not (case.root/'.claude/worktrees/fixture').exists()
    assert_native_requests(case,0)

def test_force_dispatch_is_visible_and_still_not_delivery_acceptance(case):
    result=case.run('-Force');assert result.returncode==0,result.stdout+result.stderr
    assert '[Force]' in result.stdout
    assert len(case.rows())==4 and all(r['Status']=='OUTPUT-NEEDS-REVIEW' and r['DeliveryAccepted'] is False for r in case.rows())
    assert_native_requests(case,4)

def test_missing_helper_warns_and_never_silently_skips(case):
    (case.root/'0-学习与工具/工具-opener派出前校验.ps1').unlink()
    result=case.run();assert result.returncode==0,result.stdout+result.stderr
    assert 'helper 不存在' in result.stdout
    assert len(case.rows())==4 and not any(r['Status']=='SKIPPED' for r in case.rows())
    assert_native_requests(case,4)

def test_bad_query_receipt_warns_and_never_silently_skips(case):
    (case.root/'0-学习与工具/工具-队列查询.py').write_text("print('{}')\n",encoding='utf8')
    result=case.run();assert result.returncode==0,result.stdout+result.stderr
    assert 'precheck-failed' in result.stdout
    assert len(case.rows())==4 and not any(r['Status']=='SKIPPED' for r in case.rows())
    assert_native_requests(case,4)

def test_removing_real_hook_changes_observed_dispatch(case):
    case.drop_hook()
    result=case.run();assert result.returncode==0,result.stdout+result.stderr
    assert len(case.rows())==4 and not any(r['Status']=='SKIPPED' for r in case.rows())
    assert_native_requests(case,4)

def test_active_failure_keeps_skipped_rows_and_stops_its_lane(case,monkeypatch):
    monkeypatch.setenv('CODEX_FIXTURE_MODE','failure')
    result=case.run();assert result.returncode!=0
    rows={r['Id']:r for r in case.rows()}
    assert rows['A1']['Status']==rows['A3']['Status']=='SKIPPED'
    assert rows['A2']['Status'].startswith('FAIL') and 'A4' not in rows
    assert_native_requests(case,1)

def test_compatibility_filename_uses_native_provider_and_preflight(case):
    result=case.run(legacy=True);assert result.returncode==0,result.stdout+result.stderr
    rows={r['Id']:r for r in case.rows(True)}
    assert rows['A1']['Status']==rows['A3']['Status']=='SKIPPED'
    assert rows['A2']['Status']==rows['A4']['Status']=='OUTPUT-NEEDS-REVIEW'
    assert_native_requests(case,2,True)

def test_missing_sentinel_resumes_original_native_thread_once(case,monkeypatch):
    monkeypatch.setenv('CODEX_FIXTURE_MODE','none')
    result=case.run();assert result.returncode!=0
    rows={r['Id']:r for r in case.rows()}
    assert rows['A1']['Status']==rows['A3']['Status']=='SKIPPED'
    assert rows['A2']['Status']=='NO-SENTINEL' and rows['A2']['DeliveryAccepted'] is False
    requests=assert_native_requests(case,2)
    assert sum('--thread' in args for args in requests)==1
    results=[json.loads(p.read_text(encoding='utf8')) for p in case.directory().rglob('result.json')]
    assert len(results)==2 and len({r['thread_id'] for r in results})==1
