"""Windows publication keeps the original no-overwrite and complete-JSON contract."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

spec=importlib.util.spec_from_file_location('exclusive_plan_entry',Path(__file__).resolve().parents[1]/'guardian_entry.py')
entry=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=entry
spec.loader.exec_module(entry)

def test_complete_plan_is_published_once_and_existing_author_cannot_be_replaced(tmp_path):
    record=tmp_path/'plan.json'
    original={'task_id':'fixture','evidence':'完整计划'}
    entry._publish_plan(record,original)
    before=record.read_bytes()
    assert json.loads(before)==original
    with pytest.raises(FileExistsError):
        entry._publish_plan(record,{'task_id':'other-author'})
    assert record.read_bytes()==before
    assert list(tmp_path.glob('*.tmp'))==[]

def test_flush_failure_exposes_no_partial_plan_and_preserves_existing_author(tmp_path,monkeypatch):
    record=tmp_path/'plan.json'
    record.write_bytes(b'{"previous":"author"}')
    before=record.read_bytes()
    def fail_flush(_fd):
        raise OSError('synthetic disk flush failure')
    monkeypatch.setattr(entry.os,'fsync',fail_flush)
    with pytest.raises(OSError,match='disk flush'):
        entry._publish_plan(record,{'task_id':'new'})
    assert record.read_bytes()==before
    assert list(tmp_path.glob('*.tmp'))==[]
