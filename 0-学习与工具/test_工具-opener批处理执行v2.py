"""完全独立临时git仓库；stub provider写产物，无真实模型/队列/通知。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

pytestmark=pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="需要 Windows + PowerShell；与旧套件平台条件一致")

ROOT=Path(__file__).resolve().parents[1]

class TestBatchCodex:
    def setup(self,tmp):
        tools=tmp/'0-学习与工具'; tools.mkdir()
        script=tools/'工具-opener批处理执行v2.ps1'
        text=(ROOT/'0-学习与工具/工具-opener批处理执行v2.ps1').read_text(encoding='utf-8-sig')
        # 旧代码未适配时也无法解析任何真实Claude。
        text=text.replace('Get-Command claude -ErrorAction SilentlyContinue','Get-Command __forbidden_legacy__ -ErrorAction SilentlyContinue')
        script.write_text(text,encoding='utf-8-sig')
        config=tmp/'.codex'; config.mkdir()
        (config/'runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
        (tmp/'AGENTS.md').write_text('Only mechanism fixture.',encoding='utf-8')
        (config/'hooks.json').write_text('{"hooks":{}}')
        (config/'config.toml').write_text('')
        (tmp/'.gitignore').write_text('reports/\n.claude/worktrees/\n.codex/runtime.local.json\n')
        provider=tools/'codex-handoff/model_provider.py'; provider.parent.mkdir()
        provider.write_text('''import json,sys,pathlib,os,uuid
args=sys.argv
get=lambda key:args[args.index(key)+1]
prompt=sys.stdin.read()
e=pathlib.Path(get('--evidence')); e.mkdir(parents=True)
tid=get('--thread') if '--thread' in args else str(uuid.uuid5(uuid.NAMESPACE_URL,get('--source-id')))
(e/'session.json').write_text(json.dumps({'thread_id':tid}))
(e/'result.json').write_text(json.dumps({'thread_id':tid,'status':'output_needs_review','accepted':False}))
if '--meter-file' in args:
 m=pathlib.Path(get('--meter-file')); m.parent.mkdir(parents=True,exist_ok=True); m.write_text(json.dumps({'lastContext':40000,'session_id':tid}))
pathlib.Path('made.txt').write_text('fixture')
mode=os.environ.get('CODEX_FIXTURE_MODE','ok')
import time,subprocess
retry='--thread' in args
started=time.time()
if mode=='parallel': time.sleep(8)
if mode in ('hard','soft','soft-disabled'):
 value=250000 if mode=='hard' else 160000
 m.write_text(json.dumps({'lastContext':value,'session_id':tid}))
 time.sleep(4 if mode!='hard' else 30)
if mode=='retry-timeout' and retry: time.sleep(30)
if mode=='reports':
 p=pathlib.Path('reports/nested/report.txt');p.parent.mkdir(parents=True);p.write_text('recover fixture')
if mode in ('leak','bystander'):
 name='leaked-fixture.txt'
 if mode=='leak':
  pathlib.Path(name).write_text('lane')
  subprocess.run(['git','add',name],check=True,capture_output=True)
  subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture'],check=True,capture_output=True)
 pathlib.Path(os.environ['ZHUOPIN_MAIN_REPO'],name).write_text('main leak')
if mode=='partial' or (mode=='retry-partial' and retry): print('OPENER_PARTIAL: fixture')
elif mode not in ('none','retry-none','partial') and (not mode.startswith('retry') or retry): print('OPENER_DONE')
(e/'interval.json').write_text(json.dumps({'start':started,'end':time.time()}))
if mode=='failure' or (mode=='retry-failure' and retry): sys.exit(7)
''',encoding='utf-8')
        for args in (['init','-b','master'],['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture']):
            subprocess.run(['git','-C',str(tmp),*args],check=True,capture_output=True)
        plan=tmp/'plan.md'
        plan.write_text('''### A1 · 机制验证
▶ 粘贴端：Codex
泳道：fixture
```text
【设置】执行环境：Codex ｜ 分支：master（从 master 起 `codex/fixture`） ｜ worktree：☑（fixture，新 worktree，收工自删） ｜ 模型：inherit
只写made.txt并输出OPENER_DONE；不调用业务。
```
''',encoding='utf-8')
        return script,plan

    def run(self,tmp,*extra,transform=None):
        script,plan=self.setup(tmp)
        if transform: plan.write_text(transform(plan.read_text(encoding="utf-8")),encoding="utf-8")
        return subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(script),'-Plan',str(plan),
            '-LogDir',str(tmp/'reports/batch'),'-Yes','-StaggerSec','0','-ContextPollSec','1',*extra],cwd=tmp,
            capture_output=True,text=True,encoding='utf-8',timeout=60)

    def test_default_pause(self,tmp_path):
        r=self.run(tmp_path)
        assert r.returncode!=0
        assert 'consumer-paused' in r.stdout+r.stderr
        assert not (tmp_path/'.claude/worktrees/fixture').exists()

    def test_fixture_end_to_end(self,tmp_path):
        r=self.run(tmp_path,'-ConsumerEnabled')
        assert r.returncode==0,r.stdout+r.stderr
        results=list((tmp_path/'reports/batch').rglob('result.json'))
        assert len(results)==1
        assert (tmp_path/'.claude/worktrees/fixture/made.txt').read_text()=='fixture'
        assert not (tmp_path/'made.txt').exists()
        summary=(tmp_path/'reports/batch/summary.txt').read_text(encoding='utf-8-sig')
        assert json.loads(results[0].read_text())['thread_id'] in summary
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']=='OUTPUT-NEEDS-REVIEW'
        assert rows[0]['DeliveryAccepted'] is False
        assert rows[0]['SourceId'] and rows[0]['Evidence']

    def test_failure_with_done_sentinel_is_not_success(self,tmp_path,monkeypatch):
        monkeypatch.setenv('CODEX_FIXTURE_MODE','failure')
        result=self.run(tmp_path,'-ConsumerEnabled')
        assert result.returncode!=0
        assert len(list((tmp_path/'reports/batch').rglob('result.json')))==1
        assert 'FAIL' in (tmp_path/'reports/batch/summary.txt').read_text(encoding='utf-8-sig')

    def test_missing_sentinel_resumes_once(self,tmp_path,monkeypatch):
        monkeypatch.setenv('CODEX_FIXTURE_MODE','retry')
        result=self.run(tmp_path,'-ConsumerEnabled')
        assert result.returncode==0,result.stdout+result.stderr
        results=list((tmp_path/'reports/batch').rglob('result.json'))
        assert len(results)==2
        assert '补问' in (tmp_path/'reports/batch/summary.txt').read_text(encoding='utf-8-sig')


class TestCodexEntryCompatibility:
    def test_generator_emits_codex_route_and_branch(self,tmp_path,monkeypatch):
        import importlib.util
        spec=importlib.util.spec_from_file_location('original_opener_fixture',ROOT/'0-学习与工具/test_工具-opener生成.py')
        fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
        monkeypatch.setattr(fixture.M,'REPO_ROOT',tmp_path)
        monkeypatch.setattr(fixture.M,'CLAIMS_FILE',tmp_path/'claims.jsonl')
        kwargs=dict(fixture.VALID_CC_KWARGS,model='inherit')
        result=fixture.M.generate_opener(**kwargs)
        assert '模型：inherit' in result
        assert 'codex/op0905a-demo-slug' in result

    def test_old_entry_fails_closed_without_enable(self,tmp_path):
        tools=tmp_path/'0-学习与工具'; tools.mkdir()
        for name in ['工具-opener批处理执行.ps1','工具-opener批处理执行v2.ps1']:
            content=(ROOT/'0-学习与工具'/name).read_text(encoding='utf-8-sig')
            content=content.replace('Get-Command claude -ErrorAction SilentlyContinue','Get-Command __forbidden_legacy__ -ErrorAction SilentlyContinue')
            (tools/name).write_text(content,encoding='utf-8-sig')
        result=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(tools/'工具-opener批处理执行.ps1')],capture_output=True,text=True,encoding='utf-8',timeout=20)
        assert result.returncode==4,result.stdout+result.stderr
        assert 'consumer-paused' in result.stdout

class TestNativeOpener:
    def fixture(self,tmp_path,monkeypatch):
        import importlib.util
        spec=importlib.util.spec_from_file_location('native_fixture',ROOT/'0-学习与工具/test_工具-opener生成.py')
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        monkeypatch.setattr(m.M,'REPO_ROOT',tmp_path)
        monkeypatch.setattr(m.M,'CLAIMS_FILE',tmp_path/'claims.jsonl')
        return m

    def test_native_standard_has_no_source_api(self,tmp_path,monkeypatch):
        f=self.fixture(tmp_path,monkeypatch)
        text=f.M.generate_opener(**dict(f.VALID_CC_KWARGS,env='Codex'))
        assert '【Codex】' in text and '执行环境：Codex' in text
        assert 'mcp__ccd_' not in text and 'set_session_title' not in text
        assert '会话标识：' in text and 'source_id' in text
        claims=[json.loads(line) for line in (tmp_path/'claims.jsonl').read_text(encoding='utf-8').splitlines()]
        assert claims[0]['env']=='Codex'
        lint=f.M._load_lint_module()
        assert lint.check_block(lint.iter_fenced_blocks(text)[0])==[]
        bad=text.replace('会话标识：','丢失标识：')
        assert lint.check_block(lint.iter_fenced_blocks(bad)[0])
        bad=text.replace('会话标识：','mcp__ccd_session_mgmt__set_session_title 会话标识：')
        assert lint.check_block(lint.iter_fenced_blocks(bad)[0])

    def test_native_subtask_never_renames_parent(self,tmp_path,monkeypatch):
        f=self.fixture(tmp_path,monkeypatch)
        text=f.M.generate_opener(**dict(f.VALID_CC_KWARGS,env='Codex',variant='subtask_lane'))
        assert 'set_thread_title' not in text and '会话标识：' not in text
        lint=f.M._load_lint_module()
        assert lint.check_block(lint.iter_fenced_blocks(text)[0],is_subtask_lane=True)==[]

class TestDetachPaths:
    def test_detached_plan_and_script_with_spaces(self,tmp_path):
        import time
        root=tmp_path/'space fixture'; root.mkdir()
        result=TestBatchCodex().run(root,'-ConsumerEnabled','-Detach')
        assert result.returncode==0,result.stdout+result.stderr
        end=time.monotonic()+45
        done=root/'reports/batch/exit.txt'
        error=root/'reports/batch/launcher-stderr.log'
        while not done.exists() and time.monotonic()<end:
            if error.exists() and error.read_text(encoding='utf-8-sig').strip(): break
            time.sleep(0.2)
        assert done.exists(), error.read_text(encoding='utf-8-sig') if error.exists() else 'no detached completion'
        assert done.read_text(encoding='utf-8-sig').strip()=='0'

class TestRetainedBatchBehavior:
    @pytest.mark.parametrize('mode,expected,attempts',[
        ('partial','PARTIAL',1),('none','NO-SENTINEL',2),
        ('retry-partial','PARTIAL',2),('retry-failure','NO-SENTINEL',2),
        ('retry-timeout','NO-SENTINEL',2)])
    def test_sentinel_outcomes(self,tmp_path,monkeypatch,mode,expected,attempts):
        monkeypatch.setenv('CODEX_FIXTURE_MODE',mode)
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled','-SentinelRetryTimeoutSec','2')
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']==expected,result.stdout+result.stderr
        assert rows[0]['DeliveryAccepted'] is False
        assert len(list((tmp_path/'reports/batch').rglob('result.json')))==attempts
        assert (result.returncode==0)==(expected=='PARTIAL')

    @pytest.mark.parametrize('mode,grace,expected,relay',[
        ('hard','15','PARTIAL',True),('soft','0.02','PARTIAL',True),
        ('soft-disabled','0','OUTPUT-NEEDS-REVIEW',False)])
    def test_context_termination_and_relay(self,tmp_path,monkeypatch,mode,grace,expected,relay):
        monkeypatch.setenv('CODEX_FIXTURE_MODE',mode)
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled','-ContextGraceMin',grace)
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']==expected,result.stdout+result.stderr
        assert bool(list((tmp_path/'reports/batch').glob('*.续棒.json')))==relay
        assert len(list((tmp_path/'reports/batch').rglob('result.json')))==1

    @pytest.mark.parametrize('mode,expected',[('leak','FAIL(main-leak)'),('bystander','OUTPUT-NEEDS-REVIEW')])
    def test_main_tree_leak_attribution(self,tmp_path,monkeypatch,mode,expected):
        monkeypatch.setenv('CODEX_FIXTURE_MODE',mode)
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled')
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']==expected,result.stdout+result.stderr
        assert (tmp_path/'leaked-fixture.txt').read_text()=='main leak'
        assert bool(list((tmp_path/'reports/batch').glob('*main-leak.patch')))==(mode=='leak')

    def test_reports_recovered_without_deleting_worktree(self,tmp_path,monkeypatch):
        monkeypatch.setenv('CODEX_FIXTURE_MODE','reports')
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled')
        assert result.returncode==0,result.stdout+result.stderr
        assert (tmp_path/'reports/_from-worktree/fixture/nested/report.txt').read_text()=='recover fixture'
        assert (tmp_path/'.claude/worktrees/fixture/reports/nested/report.txt').is_file()

class TestBatchValidation:
    @pytest.mark.parametrize('before,after',[
        ('执行环境：Codex','执行环境：CC'),
        ('worktree：☑（fixture，新 worktree，收工自删）','worktree：☐'),
        ('☑（fixture，','☑（../escape，'),
        ('模型：inherit','模型：sonnet')])
    def test_invalid_contract_never_starts_provider(self,tmp_path,before,after):
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled',transform=lambda p:p.replace(before,after))
        assert result.returncode!=0,result.stdout+result.stderr
        assert not list((tmp_path/'reports/batch').rglob('result.json'))

    def test_failure_stops_rest_of_same_lane(self,tmp_path,monkeypatch):
        monkeypatch.setenv('CODEX_FIXTURE_MODE','failure')
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled',transform=lambda p:p+'\n'+p.replace('A1','A2'))
        assert result.returncode!=0
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert len(rows)==1 and rows[0]['Id']=='A1'

    def test_dry_run_starts_no_model_or_worktree(self,tmp_path):
        result=TestBatchCodex().run(tmp_path,'-DryRun')
        assert result.returncode==0,result.stdout+result.stderr
        assert not list((tmp_path/'reports/batch').rglob('result.json'))
        assert not (tmp_path/'.claude/worktrees/fixture').exists()

    def test_parallel_limit_with_real_isolated_jobs(self,tmp_path,monkeypatch):
        monkeypatch.setenv('CODEX_FIXTURE_MODE','parallel')
        def plan(p):
            return p+'\n'+p.replace('A1','A2').replace('fixture','fixture2')+'\n'+p.replace('A1','A3').replace('fixture','fixture3')
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled','-MaxParallel','2',transform=plan)
        assert result.returncode==0,result.stdout+result.stderr
        intervals=[json.loads(f.read_text()) for f in (tmp_path/'reports/batch').rglob('interval.json')]
        assert len(intervals)==3
        events=sorted([(i['start'],1) for i in intervals]+[(i['end'],-1) for i in intervals])
        active=peak=0
        for _,delta in events:
            active+=delta; peak=max(peak,active)
        assert peak==2

class TestNativeBatchIntegration:
    def prepared(self,root,*args):
        return subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(root/'0-学习与工具/工具-opener批处理执行v2.ps1'),
            '-Plan',str(root/'plan.md'),'-LogDir',str(root/'reports/batch'),'-Yes','-ConsumerEnabled','-StaggerSec','0','-ContextPollSec','1',*args],
            cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=80)

    def test_legal_generator_lint_to_isolated_execution(self,tmp_path,monkeypatch):
        TestBatchCodex().setup(tmp_path)
        f=TestNativeOpener().fixture(tmp_path,monkeypatch)
        kwargs=dict(f.VALID_CC_KWARGS,env='Codex',branch='fixture',worktree='☑（fixture，新 worktree，收工自删）')
        body=f.M.generate_opener(**kwargs)
        (tmp_path/'plan.md').write_text('### A1 · 原生生成链\n▶ 粘贴端：Codex\n泳道：fixture\n'+body,encoding='utf-8')
        result=self.prepared(tmp_path)
        assert result.returncode==0,result.stdout+result.stderr
        assert (tmp_path/'.claude/worktrees/fixture/made.txt').read_text()=='fixture'
        assert not (tmp_path/'made.txt').exists()

    def test_two_operations_have_distinct_source_and_native_ids(self,tmp_path):
        result=TestBatchCodex().run(tmp_path,'-ConsumerEnabled',transform=lambda p:p+'\n'+p.replace('A1','A2'))
        assert result.returncode==0,result.stdout+result.stderr
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert len({r['Session'] for r in rows})==2
        assert len({r['SourceId'] for r in rows})==2
        assert not any(r['DeliveryAccepted'] for r in rows)

    def test_legacy_powershell_entry_keeps_native_provider(self,tmp_path):
        shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        assert shell.is_file(), 'Windows baseline lacks PowerShell5.1'
        script,plan=TestBatchCodex().setup(tmp_path)
        result=subprocess.run([str(shell),'-NoProfile','-File',str(script),'-Plan',str(plan),
            '-LogDir',str(tmp_path/'reports/batch'),'-ConsumerEnabled','-Yes','-StaggerSec','0','-ContextPollSec','1'],
            cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=80)
        assert result.returncode==0,result.stdout+result.stderr
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']=='OUTPUT-NEEDS-REVIEW'

class TestBatchMutationAndStagger:
    @pytest.mark.parametrize('marker,mode,expected',[
        ('#550 补问','retry','NO-SENTINEL'),
        ('#639 软线兜底','soft','OUTPUT-NEEDS-REVIEW')])
    def test_removing_guard_changes_observed_outcome(self,tmp_path,monkeypatch,marker,mode,expected):
        monkeypatch.setenv('CODEX_FIXTURE_MODE',mode)
        script,plan=TestBatchCodex().setup(tmp_path)
        content=script.read_text(encoding='utf-8-sig')
        begin=content.index('# >>> '+marker+' begin')
        begin=content.rfind('\n',0,begin)+1
        end=content.index('\n',content.index('# <<< '+marker+' end',begin))+1
        script.write_text(content[:begin]+content[end:],encoding='utf-8-sig')
        result=TestNativeBatchIntegration().prepared(tmp_path,'-ContextGraceMin','0.02')
        rows=json.loads((tmp_path/'reports/batch/summary.json').read_text(encoding='utf-8-sig'))
        assert rows[0]['Status']==expected,result.stdout+result.stderr
        assert (expected=='NO-SENTINEL')==(result.returncode!=0)

    def test_stagger_between_real_job_launches(self,tmp_path,monkeypatch):
        from datetime import datetime
        import re
        monkeypatch.setenv('CODEX_FIXTURE_MODE','parallel')
        script,plan=TestBatchCodex().setup(tmp_path)
        text=plan.read_text(encoding='utf-8')
        plan.write_text(text+'\n'+text.replace('A1','A2').replace('fixture','fixture2'),encoding='utf-8')
        result=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(script),'-Plan',str(plan),
            '-LogDir',str(tmp_path/'reports/batch'),'-ConsumerEnabled','-Yes','-StaggerSec','5','-MaxParallel','2','-ContextPollSec','1'],
            cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',timeout=80)
        assert result.returncode==0,result.stdout+result.stderr
        starts=re.findall(r'启动 (\d{2}:\d{2}:\d{2})',result.stdout)
        assert len(starts)==2,result.stdout
        seconds=(datetime.strptime(starts[1],'%H:%M:%S')-datetime.strptime(starts[0],'%H:%M:%S')).total_seconds()%86400
        assert seconds>=5
