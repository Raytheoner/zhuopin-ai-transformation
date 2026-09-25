import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import pytest

ROOT = Path(__file__).resolve().parents[3]
GUARD = ROOT/'0-学习与工具/工具-轮询守.ps1'

class TestPollCodex:
    def rig(self, tmp, probe='[NO-SIGNAL]', patrol='[NO-PENDING]', model_exit=0):
        tmp.mkdir(exist_ok=True)
        guard = tmp/'guard.ps1'
        source = GUARD.read_text(encoding='utf-8-sig').replace('Get-Command claude -ErrorAction SilentlyContinue', 'Get-Command __forbidden_legacy_model__ -ErrorAction SilentlyContinue')
        # 副本强制测试锁；原脚本未适配时也绝不触生产Global mutex。
        guard.write_text(source.replace('Global\\ZhuopinPollGuard', 'Local\\PollTest-'+uuid.uuid4().hex),encoding='utf-8')
        (tmp/'probe.py').write_text(f'print({probe!r})',encoding='utf-8')
        (tmp/'patrol.ps1').write_text("Write-Output '"+patrol+"'",encoding='utf-8')
        (tmp/'skill.md').write_text('隔离测试章程',encoding='utf-8')
        (tmp/'provider.py').write_text('''import sys,json,pathlib
args=sys.argv
p=pathlib.Path(args[args.index('--evidence')+1]); p.mkdir(parents=True)
(p/'result.json').write_text(json.dumps({'status':'output_needs_review' if EXIT==0 else 'failed','thread_id':'fixture','accepted':False,'exit_code':EXIT}),encoding='utf-8')
with (p.parent.parent.parent/'calls.txt').open('a') as f: f.write('call\\n')
print(sys.stdin.read())
sys.exit(EXIT)
'''.replace('EXIT',str(model_exit)),encoding='utf-8')
        return [shutil.which('pwsh'),'-NoProfile','-File',str(guard),'-Repo',str(tmp),'-LogDir',str(tmp/'logs'),
                '-ProbeScript',str(tmp/'probe.py'),'-PatrolScript',str(tmp/'patrol.ps1'),
                '-SkillDoc',str(tmp/'skill.md'),'-PythonExe',sys.executable,'-ProviderScript',str(tmp/'provider.py')]

    def launch(self, args):
        return subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)

    def row(self, tmp):
        f=next((tmp/'logs').glob('poll-guard-*.jsonl'))
        return json.loads(f.read_text(encoding='utf-8-sig').splitlines()[-1])

    def test_default_pause_preserves_signals(self,tmp_path):
        args=self.rig(tmp_path,probe='[SIGNAL]')
        result=self.launch(args)
        assert result.returncode!=0
        assert self.row(tmp_path)['skipped']=='consumer-paused'
        assert not list((tmp_path/'logs').rglob('result.json'))

    @pytest.mark.parametrize('probe,expected', [('[NO-SIGNAL]',False),('[SIGNAL]',True),('[UNKNOWN]',True)])
    def test_quiet_and_signal(self,tmp_path,probe,expected):
        result=self.launch(self.rig(tmp_path,probe=probe)+['-ConsumerEnabled'])
        assert result.returncode==0,result.stdout+result.stderr
        row=self.row(tmp_path)
        assert row['woke']==expected
        assert len(list((tmp_path/'logs').rglob('result.json')))==int(expected)
        assert row['model']['provider']=='codex'

    def test_model_nonzero_reaches_scheduler(self,tmp_path):
        result=self.launch(self.rig(tmp_path,probe='[SIGNAL]',model_exit=7)+['-ConsumerEnabled'])
        assert result.returncode!=0
        row=self.row(tmp_path)
        assert row['model']['exit']==7
        assert row['model']['status']=='failed'

    def test_sticky_set_restart_dedup(self,tmp_path):
        args=self.rig(tmp_path,patrol='[WT-BLOCKED] a; b')+['-ConsumerEnabled']
        first=self.launch(args)
        assert first.returncode==0,first.stdout+first.stderr
        assert self.row(tmp_path)['woke']
        (tmp_path/'patrol.ps1').write_text("Write-Output '[WT-BLOCKED] b; a'",encoding='utf-8')
        second=self.launch(args)
        assert second.returncode==0,second.stdout+second.stderr
        assert self.row(tmp_path)['woke'] is False


class TestSchedulerWrappers:
    def test_commit_sweep_propagates_failure(self,tmp_path):
        vbs=tmp_path/'run-commit-sweep-hidden.vbs'
        vbs.write_bytes((ROOT/'0-学习与工具/run-commit-sweep-hidden.vbs').read_bytes())
        (tmp_path/'run-commit-sweep.ps1').write_text('exit 7\n',encoding='utf-8-sig')
        proc=subprocess.run(['cscript','//nologo',str(vbs)],capture_output=True,text=True,timeout=15)
        assert proc.returncode==7,proc.stdout+proc.stderr

    def test_register_generates_codex_wrapper_without_enabling(self,tmp_path):
        proc=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(ROOT/'0-学习与工具/工具-注册轮询守计划任务.ps1'),
            '-Repo',str(ROOT),'-WhatIf','-CodexExe',sys.executable,'-PythonExe',sys.executable,
            '-GitExe',shutil.which('git'),'-NodeExe',sys.executable],capture_output=True,text=True,encoding='utf-8',timeout=25)
        assert proc.returncode==0,proc.stdout+proc.stderr
        assert '-ClaudeExe' not in proc.stdout
        assert 'ZHUOPIN_CODEX_EXECUTABLE' in proc.stdout
        assert '-ConsumerEnabled' not in proc.stdout
        assert '/Interactive' in proc.stdout
