
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

BASE = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
bridge=load("hook_bridge")
workflow=load("handoff")

def test_patch_multiple_files_and_rename():
    patch="*** Begin Patch\n*** Update File: a.md\n*** Move to: b.md\n@@\n-old\n+new\n*** Add File: c.py\n+x=1\n*** Delete File: d.md\n*** End Patch"
    assert bridge.targets("apply_patch",patch)==[
        {"path":"a.md","text":""},{"path":"b.md","text":"new\n"},
        {"path":"c.py","text":"x=1\n"},{"path":"d.md","text":""}]

@pytest.mark.parametrize("payload",[{},{"patch":7},{"patch":"bad"}])
def test_bad_patch_fails_loud(payload):
    with pytest.raises(ValueError): bridge.targets("apply_patch",payload)

def test_plain_tool_is_not_invented_file_write():
    assert bridge.targets("exec_command",{"cmd":"echo 'a.md'"})==[]

def test_pre_patch_reuses_lock_guard(tmp_path):
    event={"hook_event_name":"PreToolUse","tool_name":"apply_patch","cwd":str(tmp_path),
           "tool_input":{"patch":"*** Add File: z.md\n+hello"}}
    calls=bridge.calls(event)
    assert len(calls)==1
    assert calls[0][0]=="hooks-pretooluse-editlock-guard.ps1"
    assert calls[0][1]["tool_input"]["file_path"]==str(tmp_path/"z.md")

def test_post_reuses_two_sentinels(tmp_path):
    event={"hook_event_name":"PostToolUse","tool_name":"apply_patch","cwd":str(tmp_path),
           "tool_input":{"input":"*** Add File: z.md\n+hello"}}
    assert [x[0] for x in bridge.calls(event)]==["sentinel-mojibake.ps1","sentinel-pronoun.ps1"]

def test_native_exec_command_maps_cmd():
    event={"hook_event_name":"PreToolUse","tool_name":"exec_command","tool_input":{"cmd":"Get-Content 'queue.md'"}}
    calls=bridge.calls(event)
    assert len(calls)==2
    assert calls[0][1]["tool_name"]=="Bash"
    assert calls[0][1]["tool_input"]["command"]=="Get-Content 'queue.md'"

def test_audit_does_not_store_payload(tmp_path,monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE",str(tmp_path))
    bridge.audit({"hook_event_name":"PreToolUse","tool_input":{"secret":"DO_NOT_PERSIST"}},[])
    contents=next((tmp_path/"hooks").glob("*.json")).read_text()
    assert "DO_NOT_PERSIST" not in contents
    assert "input_sha256" in contents

def test_missing_queue_does_not_prepare_success(tmp_path,monkeypatch):
    monkeypatch.setattr(workflow,"STATE",tmp_path)
    monkeypatch.setattr(workflow,"execute",lambda *a,**k:{"exit":2,"stdout":"","stderr":"not found"})
    with pytest.raises(RuntimeError):
        workflow.prepare(SimpleNamespace(id="sample-task",row=99999,section="一",intent="test"))
    assert not (tmp_path/"runs/sample-task/state.json").exists()

def setup_run(tmp_path,monkeypatch):
    monkeypatch.setattr(workflow,"STATE",tmp_path)
    folder=tmp_path/"runs/sample"
    folder.mkdir(parents=True)
    (folder/"state.json").write_text(json.dumps({"source_head":"a"}))
    (folder/"intent.md").write_text("test")
    return folder

def test_head_drift_blocks_execution(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,"git",lambda *a,**k:{"exit":0,"stdout":"b"})
    with pytest.raises(ValueError,match="HEAD drift"):
        workflow.run_stage(SimpleNamespace(id="sample",phase="plan",workspace=str(tmp_path)))

def test_implementation_rejects_main_checkout(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="separate clean worktree"):
        workflow.run_stage(SimpleNamespace(id="sample",phase="implement",workspace=str(workflow.ROOT)))

def test_implementation_requires_authorization(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,"git",lambda *a,**k:{"exit":0,"stdout":"a" if a[0]=="rev-parse" else ""})
    with pytest.raises(ValueError,match="authorization"):
        workflow.run_stage(SimpleNamespace(id="sample",phase="implement",workspace=str(tmp_path),authorization=None))

def test_active_lock_is_not_broken(tmp_path,monkeypatch):
    folder=setup_run(tmp_path,monkeypatch)
    (folder/"running.lock").write_text("busy")
    monkeypatch.setattr(workflow,"git",lambda *a,**k:{"exit":0,"stdout":"a" if a[0]=="rev-parse" else ""})
    with pytest.raises(FileExistsError):
        workflow.run_stage(SimpleNamespace(id="sample",phase="plan",workspace=str(tmp_path)))
    assert (folder/"running.lock").read_text()=="busy"

def test_model_success_is_not_delivery_success(tmp_path,monkeypatch):
    folder=setup_run(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,"git",lambda *a,**k:{"exit":0,"stdout":"a" if a[0]=="rev-parse" else ""})
    monkeypatch.setattr(workflow,"model_run",lambda **k:{"status":"output_needs_review","exit_code":0,"thread_id":"fixture"})
    assert workflow.run_stage(SimpleNamespace(id="sample",phase="plan",workspace=str(tmp_path),timeout=10))==0
    assert json.loads((folder/"state.json").read_text())["status"]=="stage_output_needs_review"
    assert not (folder/"running.lock").exists()

def test_model_failure_is_fail_stop(tmp_path,monkeypatch):
    folder=setup_run(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,"git",lambda *a,**k:{"exit":0,"stdout":"a" if a[0]=="rev-parse" else ""})
    monkeypatch.setattr(workflow,"model_run",lambda **k:{"status":"failed","exit_code":1,"thread_id":"fixture"})
    assert workflow.run_stage(SimpleNamespace(id="sample",phase="plan",workspace=str(tmp_path),timeout=10))==1
    assert json.loads((folder/"state.json").read_text())["status"]=="failed"

def test_real_legacy_lock_guard_positive_negative(tmp_path,monkeypatch):
    import os, subprocess
    from datetime import datetime, timezone
    source=Path("C:/Dev/zhuopin-ai/0-学习与工具/hooks")
    if not source.exists():
        pytest.skip("source hooks not present on this machine")
    target=tmp_path/"1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
    target.parent.mkdir(parents=True)
    env=dict(os.environ,ZHUOPIN_SENTINEL_REPO_ROOT=str(tmp_path),PYTHONUTF8="1")
    event={"hook_event_name":"PreToolUse","tool_name":"apply_patch","cwd":str(tmp_path),
           "tool_input":"*** Update File: 1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md\n@@\n+x"}
    script,payload=bridge.calls(event)[0]
    def invoke():
        return subprocess.run(["pwsh","-NoProfile","-File",str(source/script)],
                              input=json.dumps(payload,ensure_ascii=False),capture_output=True,
                              text=True,encoding="utf8",env=env,cwd=tmp_path,timeout=20)
    assert invoke().returncode==2
    lock=Path(str(target)+".editlock")
    lock.write_text(json.dumps({"held_since":datetime.now(timezone.utc).isoformat(),"who":"fixture"}),encoding="utf8")
    assert invoke().returncode==0
    lock.write_text(json.dumps({"held_since":datetime.now(timezone.utc).isoformat(),"who":"fixture","released":True}),encoding="utf8")
    assert invoke().returncode==2

@pytest.mark.parametrize('provider_status,expected',[('incomplete',1),('tool_failed',1),('output_needs_review',0)])
def test_stage_uses_structured_provider_outcome(tmp_path,monkeypatch,provider_status,expected):
    folder=setup_run(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,'git',lambda *a,**k:{'exit':0,'stdout':'a' if a[0]=='rev-parse' else ''})
    # Safe RED: old runner is intercepted too; never starts any native model.
    monkeypatch.setattr(workflow.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0))
    monkeypatch.setattr(workflow,'model_run',lambda **kw:{'status':provider_status,'exit_code':0,'thread_id':'fixture','accepted':False},raising=False)
    code=workflow.run_stage(SimpleNamespace(id='sample',phase='plan',workspace=str(tmp_path),timeout=10))
    assert code==expected
    state=json.loads((folder/'state.json').read_text())
    assert state['model_status']==provider_status
    assert state['delivery_accepted'] is False
    assert not (folder/'running.lock').exists()
