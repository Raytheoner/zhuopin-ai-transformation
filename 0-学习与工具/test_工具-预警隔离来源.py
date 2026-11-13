"""Real detector input contracts for three explicitly synthetic sources."""
from pathlib import Path
import importlib.util
import pytest
from _sweep_test_sources import seed_synthetic_sources

spec=importlib.util.spec_from_file_location('synthetic_source_sweep',Path(__file__).with_name('工具-落库sweep.py'))
sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)

def observe(root,monkeypatch):
    seen={}
    def publish(repo,label,source,state,issues,log,*,complete):
        seen[label]=(set(issues),complete)
        return True
    def track(repo,label,state,keys,*args,**kw):
        seen[label]=(set(keys),kw.get('allow_resolve',True))
    monkeypatch.setattr(sweep,'_publish_reminder_health',publish)
    monkeypatch.setattr(sweep,'_track_and_alert_standing_state',track)
    log=[]
    sweep._check_decision_reminder_health(root,log)
    sweep._check_local_reminder_outbox_health(root,log)
    sweep._check_outbox_relay_unreadable_visibility(root,log)
    return seen,log

def prepare(tmp_path,omit=()):
    (tmp_path/'.git').mkdir()
    seed_synthetic_sources(tmp_path,sweep,omit=omit)
    return tmp_path

def test_all_three_valid_synthetic_sources_are_actually_parsed(tmp_path,monkeypatch):
    root=prepare(tmp_path)
    seen,log=observe(root,monkeypatch)
    for label in ('提醒源健康','本地提醒outbox健康','中继读取/通知/审计证据'):
        assert seen[label]==(set(),True),(label,seen,log)

@pytest.mark.parametrize('omit,label',[
    ('reminder','提醒源健康'),('outbox','本地提醒outbox健康'),('relay','中继读取/通知/审计证据')])
def test_missing_source_still_reports_unknown_and_disallows_resolution(tmp_path,monkeypatch,omit,label):
    root=prepare(tmp_path,omit={omit})
    before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    seen,log=observe(root,monkeypatch)
    assert seen[label][0],(label,seen,log)
    assert seen[label][1] is False,(label,seen,log)
    assert {p:p.read_bytes() for p in before}==before
