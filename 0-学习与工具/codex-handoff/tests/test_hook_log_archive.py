import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('archive_test',BASE/'hook_log_archive.py')
archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)


def fixture(tmp_path):
    source=tmp_path/'中文 logs';source.mkdir()
    for n in range(7):(source/(str(n).zfill(32)+'.json')).write_bytes(json.dumps({'n':n}).encode()+b'\r\n')
    return source,tmp_path/'archives'


@pytest.mark.parametrize('workers',[1,4])
def test_pack_all_bytes_idempotent_without_source_deletion(tmp_path,workers):
    source,out=fixture(tmp_path);before={p.name:p.read_bytes() for p in source.iterdir()}
    result=archive.pack(source,out,shard_size=3,workers=workers)
    assert result['files']==7 and result['parts']==3 and result['source_deleted']==0
    assert archive.pack(source,out,shard_size=3,workers=workers)['changed'] is False
    assert {p.name:p.read_bytes() for p in source.iterdir()}==before
    assert sum(len(archive.verify_part(p,source)['files']) for p in out.glob('*.zip'))==7


def test_interrupt_resume_uses_verified_parts(tmp_path):
    source,out=fixture(tmp_path)
    def interrupt(row):raise InterruptedError('synthetic crash after committed part')
    with pytest.raises(InterruptedError):archive.pack(source,out,shard_size=3,progress=interrupt)
    first=next(out.glob('*.zip'));before=first.read_bytes()
    assert archive.pack(source,out,shard_size=3)['files']==7
    assert first.read_bytes()==before


def test_source_edit_during_recovery_refused_and_preserved(tmp_path):
    source,out=fixture(tmp_path);archive.pack(source,out,shard_size=3)
    path=next(source.iterdir());path.write_bytes(b'author edit')
    with pytest.raises(ValueError):archive.pack(source,out,shard_size=3)
    assert path.read_bytes()==b'author edit'


def test_corrupt_zip_not_silently_replaced(tmp_path):
    source,out=fixture(tmp_path);archive.pack(source,out,shard_size=3)
    path=next(out.glob('*.zip'));path.write_bytes(b'damaged')
    with pytest.raises(zipfile.BadZipFile):archive.pack(source,out,shard_size=3)
    assert path.read_bytes()==b'damaged'
