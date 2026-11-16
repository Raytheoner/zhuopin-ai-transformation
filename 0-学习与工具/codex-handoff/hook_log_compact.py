"""Compact verified legacy ZIPs into two-entry shards; no source deletion."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile

spec=importlib.util.spec_from_file_location('compact_local_io',Path(__file__).with_name('hook_audit_store.py'))
local=importlib.util.module_from_spec(spec);spec.loader.exec_module(local)
NAME=re.compile(r'^[0-9a-f]{32}\.json$')


def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def unpack_legacy(raw):
    if len(raw)>128*1024*1024:raise ValueError('source shard exceeds budget')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if any(i.file_size>1024*1024 for i in z.infolist()) or sum(i.file_size for i in z.infolist())>65*1024*1024:
            raise ValueError('uncompressed source exceeds budget')
        index=json.loads(z.read('index.json'));names=[r['name'] for r in index['files']]
        if len(names)>1000 or len(names)!=len(set(names)) or any(not NAME.fullmatch(n) for n in names):raise ValueError('source index invalid')
        if set(z.namelist())!={'index.json',*names} or len(z.namelist())!=len(names)+1:raise ValueError('source coverage mismatch')
        rows=[];blocks=[];offset=0
        for row in index['files']:
            data=z.read(row['name'])
            if len(data)!=row['bytes'] or sha(data)!=row['sha256']:raise ValueError('source SHA mismatch')
            rows.append(dict(row,offset=offset));blocks.append(data);offset+=len(data)
        return rows,b''.join(blocks)


def verify(path):
    raw=Path(path).read_bytes()
    if len(raw)>128*1024*1024:raise ValueError('compact shard exceeds budget')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sorted(z.namelist())!=['index.json','records.bin']:raise ValueError('compact coverage mismatch')
        if sum(i.file_size for i in z.infolist())>65*1024*1024:raise ValueError('uncompressed compact exceeds budget')
        index=json.loads(z.read('index.json'));data=z.read('records.bin');offset=0;names=set()
        if index['schema']!=2:raise ValueError('unknown compact schema')
        for row in index['files']:
            if not NAME.fullmatch(row['name']) or row['name'] in names or row['offset']!=offset or row['bytes']<0:
                raise ValueError('compact source rebinding refused')
            block=data[offset:offset+row['bytes']]
            if len(block)!=row['bytes'] or sha(block)!=row['sha256']:raise ValueError('compact SHA mismatch')
            names.add(row['name']);offset+=row['bytes']
        if offset!=len(data):raise ValueError('unmapped compact bytes')
        return index


def compact(source,output):
    source,output=Path(source).resolve(),Path(output).resolve()
    if source==output or source in output.parents or output in source.parents:raise ValueError('independent output required')
    plan=json.loads((source/'archive-plan.json').read_bytes());old=json.loads((source/'summary.json').read_bytes())
    paths=sorted(source.glob('part-*.zip'))
    if len(paths)!=old['parts']:raise ValueError('source shard missing')
    output.mkdir(parents=True,exist_ok=True);all_names=[];total=0;changed=[];provenance=[]
    with local.locked(output/'.compact.lock'):
        for path in paths:
            raw=path.read_bytes();rows,data=unpack_legacy(raw)
            index={'schema':2,'source_zip':path.name,'source_zip_sha256':sha(raw),'files':rows}
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as z:
                for name,block in [('records.bin',data),('index.json',encoded(index))]:
                    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
                    z.writestr(info,block,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
            target=output/path.name;packed=buffer.getvalue()
            if target.exists():
                if target.read_bytes()!=packed:raise ValueError('immutable compact output differs: '+target.name)
            else:local.atomic(target,packed);changed.append(str(target))
            if verify(target)!=index:raise ValueError('compact readback differs')
            all_names.extend(row['name'] for row in rows);total+=len(data)
            provenance.append({'name':path.name,'source_sha256':sha(raw),'compact_sha256':sha(packed)})
        snapshot=sha('\n'.join(sorted(all_names)).encode())
        if len(all_names)!=len(set(all_names)) or len(all_names)!=plan['files'] or snapshot!=plan['snapshot_sha256'] or total!=old['source_bytes']:
            raise ValueError('whole-list conservation failed')
        for path,value in [(output/'provenance.json',provenance),(output/'summary.json',
            {'schema':2,'files':len(all_names),'parts':len(paths),'source_bytes':total,'zip_bytes':sum(p.stat().st_size for p in output.glob('part-*.zip')),
             'snapshot_sha256':snapshot,'source_deleted':0,'source_archive_summary_sha256':sha((source/'summary.json').read_bytes())})]:
            payload=encoded(value)
            if path.exists() and path.read_bytes()!=payload:raise ValueError('immutable compact receipt differs')
            if not path.exists():local.atomic(path,payload)
        return dict(json.loads((output/'summary.json').read_bytes()),changed=bool(changed),paths=changed)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode':'check','source_parts':len(list(args.source.glob('part-*.zip'))),'changed':False}));return 0
    result=compact(args.source,args.output)
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'error':str(exc),'source_deleted':0},ensure_ascii=False));raise SystemExit(2)
