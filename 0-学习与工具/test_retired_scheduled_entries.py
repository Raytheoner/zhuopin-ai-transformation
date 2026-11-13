"""Current contracts for an explicitly retired execution system."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('retired_schedule_sweep',HERE/'工具-落库sweep.py')
sweep=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sweep;spec.loader.exec_module(sweep)

@pytest.mark.parametrize('old_state', [None,'broken json','{"orphan":"2026-11-01T00:00:00+00:00"}'])
def test_retired_sources_do_not_execute_publish_commit_or_clear_history(tmp_path,monkeypatch,old_state):
    tools=tmp_path/'0-学习与工具';tools.mkdir()
    marker=tmp_path/'legacy-executed'
    (tools/'工具-定时任务源码备份.py').write_text(f'from pathlib import Path;Path({str(marker)!r}).write_text("ran")\nraise SystemExit(1)',encoding='utf8')
    reports=tmp_path/'reports';reports.mkdir()
    if old_state is not None:
        (reports/'sweep-scheduled-task-coverage-state.json').write_text(old_state,encoding='utf8')
    before={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def forbidden(*args,**kwargs):
        raise AssertionError('retired execution or delivery reached')
    monkeypatch.setattr(sweep.subprocess,'run',forbidden)
    monkeypatch.setattr(sweep,'_track_and_alert_standing_state',forbidden)
    log=[]
    sweep._run_scheduled_task_mirror_sync(tmp_path,log)
    sweep._check_scheduled_task_coverage(tmp_path,log)
    assert not marker.exists()
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before
    assert len(log)==2 and all('退役' in line for line in log)

def test_evidence_tool_has_no_implicit_old_source_or_destination(tmp_path):
    before=list(tmp_path.iterdir())
    run=subprocess.run([sys.executable,'-I','-B',str(HERE/'工具-历史任务镜像核对.py')],
        cwd=tmp_path,capture_output=True,text=True,encoding='utf8',timeout=20)
    assert run.returncode==2
    assert '显式提供' in run.stdout and '退役' in run.stdout
    assert list(tmp_path.iterdir())==before
