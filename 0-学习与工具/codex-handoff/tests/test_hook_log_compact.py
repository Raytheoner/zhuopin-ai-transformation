import importlib.util
from pathlib import Path
import zipfile
import pytest

BASE=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location('compact_test_'+name,BASE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
archive=load('hook_log_archive');compact=load('hook_log_compact')


def fixture(tmp_path):
    source=tmp_path/'合成 logs';source.mkdir()
    for n in range(100):
        (source/(str(n).zfill(32)+'.json')).write_bytes(b'\xef\xbb\xbf'+('重复的完整原文'*40).encode()+str(n).encode()+b'\r\n')
    packed=tmp_path/'legacy';archive.pack(source,packed)
    return source,packed,tmp_path/'compact'


def test_dense_smaller_byte_exact_and_idempotent(tmp_path):
    source,old,out=fixture(tmp_path)
    before={p.name:p.read_bytes() for p in source.iterdir()}
    result=compact.compact(old,out)
    assert result['files']==100 and result['zip_bytes']<result['source_bytes']
    assert result['zip_bytes']<sum(p.stat().st_size for p in old.glob('*.zip'))
    for path in out.glob('*.zip'):
        index=compact.verify(path)
        with zipfile.ZipFile(path) as z:
            data=z.read('records.bin')
            assert all(data[r['offset']:r['offset']+r['bytes']]==before[r['name']] for r in index['files'])
    assert compact.compact(old,out)['changed'] is False
    assert {p.name:p.read_bytes() for p in source.iterdir()}==before


def test_missing_old_shard_and_corrupt_output_refuse(tmp_path):
    source,old,out=fixture(tmp_path);compact.compact(old,out)
    path=next(out.glob('*.zip'));path.write_bytes(b'author edit')
    with pytest.raises(ValueError,match='immutable'):compact.compact(old,out)
    assert path.read_bytes()==b'author edit'


def test_missing_old_shard_fails_without_partial_success(tmp_path):
    source,old,out=fixture(tmp_path);next(old.glob('*.zip')).rename(old/'retained-material.tmp')
    with pytest.raises(ValueError,match='missing'):compact.compact(old,out)
