"""Read-only legacy hook source; explicit resumable pack/verify. Never removes logs."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import io as memory_io
import json
from pathlib import Path
import re
import time
import uuid
import zipfile

spec=importlib.util.spec_from_file_location('archive_io',Path(__file__).with_name('hook_audit_store.py'))
io=importlib.util.module_from_spec(spec);spec.loader.exec_module(io)
LEGACY=re.compile(r'^[0-9a-f]{32}\.json$')


def sha(data):return hashlib.sha256(data).hexdigest()


def source_bytes(path):
    if path.stat().st_size>1024*1024:raise ValueError('legacy event exceeds 1 MiB budget: '+path.name)
    data=path.read_bytes()
    if len(data)>1024*1024:raise ValueError('legacy event grew beyond budget: '+path.name)
    return data


def bounded_map(function,values,workers):
    if not 1<=workers<=4:raise ValueError('I/O workers must be 1..4')
    if workers==1:
        yield from map(function,values);return
    iterator=iter(values)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending=deque()
        for _ in range(workers):
            value=next(iterator,None)
            if value is not None:pending.append(executor.submit(function,value))
        while pending:
            yield pending.popleft().result()
            value=next(iterator,None)
            if value is not None:pending.append(executor.submit(function,value))


def sources(source, cutoff):
    paths=[]
    for path in Path(source).iterdir():
        if not LEGACY.fullmatch(path.name):continue
        if path.is_symlink():raise ValueError('source link refused: '+path.name)
        if path.is_file() and path.stat().st_mtime_ns<=cutoff:paths.append(path)
    return sorted(paths,key=lambda p:p.name)


def verify_part(path, source=None,workers=1):
    # One buffered read per shard avoids thousands of seek/write operations on
    # Windows while preserving a real disk readback and per-source-file SHA.
    if Path(path).stat().st_size>128*1024*1024:raise ValueError('archive shard exceeds memory budget')
    with zipfile.ZipFile(memory_io.BytesIO(Path(path).read_bytes())) as archive:
        index=json.loads(archive.read('index.json'))
        names=[r['name'] for r in index['files']]
        if len(names)!=len(set(names)) or any(not LEGACY.fullmatch(n) for n in names):raise ValueError('invalid archive index')
        if set(archive.namelist())!={'index.json',*names}:raise ValueError('archive coverage mismatch')
        current=bounded_map(lambda row:sha(source_bytes(Path(source)/row['name'])),index['files'],workers) if source is not None else iter([None]*len(names))
        for row,current_hash in zip(index['files'],current):
            data=archive.read(row['name'])
            if sha(data)!=row['sha256'] or len(data)!=row['bytes']:raise ValueError('archive hash mismatch')
            if source is not None and current_hash!=row['sha256']:
                raise ValueError('source changed; preserve archive: '+row['name'])
        return index


def pack(source, output, shard_size=1000, progress=None,workers=1):
    source,output=Path(source).resolve(),Path(output).resolve()
    if source==output or source in output.parents or output in source.parents:
        raise ValueError('archive output must be separate from source')
    if not 1<=shard_size<=1000:raise ValueError('shards must contain 1..1000 files')
    if not 1<=workers<=4:raise ValueError('I/O workers must be 1..4')
    output.mkdir(parents=True,exist_ok=True)
    with io.locked(output/'.archive.lock'):
        plan_path=output/'archive-plan.json'
        if plan_path.exists():
            plan=json.loads(plan_path.read_bytes())
            if plan['source']!=str(source) or plan['shard_size']!=shard_size:raise ValueError('archive identity conflict')
        else:
            plan={'schema':1,'source':str(source),'cutoff_ns':time.time_ns(),'shard_size':shard_size}
        paths=sources(source,plan['cutoff_ns'])
        snapshot=sha('\n'.join(p.name for p in paths).encode())
        if 'snapshot_sha256' in plan and plan['snapshot_sha256']!=snapshot:raise ValueError('legacy source listing changed')
        plan.update(snapshot_sha256=snapshot,files=len(paths))
        if not plan_path.exists():io.atomic(plan_path,json.dumps(plan,ensure_ascii=False,indent=2).encode())
        total=0;changed=[]
        for start in range(0,len(paths),shard_size):
            group=paths[start:start+shard_size]
            label='part-'+str(start//shard_size+1).zfill(6)+'-'+sha('\n'.join(p.name for p in group).encode())[:16]+'.zip'
            target=output/label
            if target.exists():
                index=verify_part(target,source,workers)
                if [r['name'] for r in index['files']]!=[p.name for p in group]:raise ValueError('shard source rebinding refused')
            else:
                temp=output/('.'+label+'.'+uuid.uuid4().hex+'.tmp')
                index={'schema':1,'files':[]}
                buffer=memory_io.BytesIO();budget=0
                with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                    for path,data in zip(group,bounded_map(source_bytes,group,workers)):
                        budget+=len(data)
                        if budget>64*1024*1024:raise ValueError('shard exceeds 64 MiB budget; use smaller shard_size')
                        index['files'].append({'name':path.name,'bytes':len(data),'sha256':sha(data)})
                        archive.writestr(path.name,data)
                    archive.writestr('index.json',json.dumps(index,ensure_ascii=False,sort_keys=True).encode())
                io.atomic(temp,buffer.getvalue())
                verify_part(temp,source,workers)
                if target.exists():raise ValueError('archive appeared concurrently')
                # No source mutation; output commit only after full ZIP/SHA readback.
                temp.replace(target);changed.append(str(target))
            total+=sum(row['bytes'] for row in index['files'])
            if progress:progress({'verified':min(start+shard_size,len(paths)),'total':len(paths),'part':label})
        if sha('\n'.join(p.name for p in sources(source,plan['cutoff_ns'])).encode())!=snapshot:
            raise ValueError('source listing changed during pack')
        summary={'files':len(paths),'source_bytes':total,'zip_bytes':sum(p.stat().st_size for p in output.glob('part-*.zip')),
                 'parts':(len(paths)+shard_size-1)//shard_size,'source_deleted':0,'snapshot_sha256':snapshot}
        data=json.dumps(summary,ensure_ascii=False,indent=2).encode();summary_path=output/'summary.json'
        if summary_path.exists() and summary_path.read_bytes()!=data:raise ValueError('archive summary changed unexpectedly')
        if not summary_path.exists():io.atomic(summary_path,data)
        return dict(summary,changed=bool(changed),paths=changed)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--pack',action='store_true');mode.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if args.pack:
        if not args.output:parser.error('--pack needs --output')
        result=pack(args.source,args.output,workers=args.workers,progress=lambda x:print(json.dumps(x),flush=True) if x['verified']%10000==0 or x['verified']==x['total'] else None)
    elif args.verify:
        if not args.output:parser.error('--verify needs --output')
        plan=json.loads((args.output/'archive-plan.json').read_bytes())
        if Path(plan['source']).resolve()!=args.source.resolve():raise ValueError('archive source identity mismatch')
        result={'verified_parts':0,'files':0,'source_deleted':0}
        names=[]
        for path in sorted(args.output.glob('part-*.zip')):
            index=verify_part(path,args.source,args.workers);result['verified_parts']+=1;result['files']+=len(index['files'])
            names.extend(row['name'] for row in index['files'])
        if len(names)!=len(set(names)) or len(names)!=plan['files'] or sha('\n'.join(sorted(names)).encode())!=plan['snapshot_sha256']:
            raise ValueError('archive whole-list conservation failed')
    else:
        paths=sources(args.source,time.time_ns())
        result={'mode':'check','files':len(paths),'bytes':sum(p.stat().st_size for p in paths),'changed':False}
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'error':str(exc),'source_deleted':0},ensure_ascii=False));raise SystemExit(2)
