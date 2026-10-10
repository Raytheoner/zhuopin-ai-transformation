from pathlib import Path
import argparse,hashlib,json,os,subprocess,uuid
MAIN=Path('C:/Dev/zhuopin-ai')
NATIVE=Path('C:/Users/Paul Shao/.codex/worktrees/sc7-batch-quantity-1010/zhuopin-ai')
BASE='310f54de71149b0cb0281749619ee3cd84f97bca'; REF='codex/candidate-sc7-1010'
GIT=Path('C:/Program Files/Git/cmd/git.exe'); GIT_SHA='37C5725818D602E951BA2563B870D62763322956B73373DA4C33A0B566A80BC9'
MESSAGE='feat(sc7): seal synthetic batch quantity evidence'
FILES={'4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py':'DB97E8682D5D0966FBB47030451614B94B1099DE33B9970CE15D2F0417672972','4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py':'BAFBC7F80DFDBA56A6789B429BA7621DD7AA8D586C54BA2AE2620FBC352B8412'}
FORMAL=MAIN/'docs/superpowers/plans/sc7-local-seal-1010/seal_sc7.py'
PLAN=MAIN/'docs/superpowers/plans/2026-10-10-sc7-local-seal.md'
MANIFEST=MAIN/'docs/superpowers/plans/sc7-local-seal-1010/manifest.json'
AUTH=MAIN/'0-学习与工具/codex-handoff/SC7两文件本地封存批准消费-2026-10-10.json'
sha=lambda b:hashlib.sha256(b).hexdigest().upper()
def require(ok,message):
    if not ok:raise RuntimeError(message)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--seal',action='store_true'); args=parser.parse_args()
    require(sha(GIT.read_bytes())==GIT_SHA,'Git executable identity drift')
    blocked=[k for k,v in os.environ.items() if k.upper().startswith('GIT_') and v and k.upper() not in {'GIT_OPTIONAL_LOCKS','GIT_TERMINAL_PROMPT','GIT_PAGER'}]
    require(not blocked,'Unexpected Git environment controls')
    auth=None
    if args.seal:
        require(Path(__file__).resolve()==FORMAL.resolve(),'Seal requires formal frozen script')
        auth=json.loads(AUTH.read_text(encoding='utf-8')); require(auth.get('schema')=='sc7-seal-approval/v1' and auth.get('approved') is True and auth.get('explicit_human_answer') is True,'Explicit new seal approval missing')
        require(auth.get('plan_sha256')==sha(PLAN.read_bytes()) and auth.get('script_sha256')==sha(FORMAL.read_bytes()) and auth.get('manifest_sha256')==sha(MANIFEST.read_bytes()),'Approved frozen artifacts drift')
        require(auth.get('native_root')==str(NATIVE) and auth.get('branch')==REF and auth.get('base')==BASE and auth.get('file_sha256')==FILES,'Approval scope mismatch')
        require(auth.get('scope_exception')=='sc7_completed_candidate_preservation_only','Precise detached preservation exception missing')
    parent=MAIN/'reports/sc7-batch-quantity-1010/seal'; parent.mkdir(exist_ok=True); run=parent/str(uuid.uuid4()); run.mkdir(exist_ok=False)
    summary={'mode':'seal' if args.seal else 'readonly_preflight','native_root':str(NATIVE),'base':BASE,'branch':REF,'file_sha256':FILES,'git_executable_sha256':GIT_SHA,'committed':False,'complete':False,'error':None}; counter=0
    def save():(run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def git(label,*argv,expected=(0,)):
        nonlocal counter
        counter+=1; command=[str(GIT),'--no-pager','-c','core.quotepath=false','-C',str(NATIVE),*argv]; env=os.environ.copy(); env['GIT_OPTIONAL_LOCKS']='0'; env['GIT_TERMINAL_PROMPT']='0'
        result=subprocess.run(command,cwd=NATIVE,env=env,capture_output=True,check=False)
        prefix=run/f'{counter:03d}-{label}'; prefix.with_suffix('.stdout.bin').write_bytes(result.stdout); prefix.with_suffix('.stderr.bin').write_bytes(result.stderr)
        prefix.with_suffix('.json').write_text(json.dumps({'argv':command,'cwd':str(NATIVE),'actual_exit':result.returncode},ensure_ascii=False,indent=2),encoding='utf-8')
        require(result.returncode in expected,f'{label}: unexpected exit {result.returncode}')
        return result.stdout
    def guard_git_effects():
        require(sha(GIT.read_bytes())==GIT_SHA,'Git executable drift')
        for key in ('core.hooksPath','core.fsmonitor','commit.gpgsign'):
            value=git('config-'+key,'config','--show-origin','--get-all',key,expected=(0,1))
            allowed_false=(key=='core.fsmonitor' and value==b'file:C:/Dev/zhuopin-ai/.git/config\tfalse\n')
            require(value==b'' or allowed_false,f'Unexpected configured {key}; stop before Git mutation')
            summary.setdefault('git_config_origins',{})[key]=value.decode('utf-8')
        hooks=MAIN/'.git/hooks'; inventory={p.name:sha(p.read_bytes()) for p in hooks.iterdir() if p.is_file()}; require(all(name.endswith('.sample') for name in inventory),'Active or unknown Git hook exists')
        require(not any(p.is_dir() or p.is_symlink() for p in hooks.iterdir()),'Unexpected hook directory/symlink')
        summary['hook_sample_sha256']=inventory
        attrs=git('attributes','check-attr','-z','filter','working-tree-encoding','ident','--',*FILES).split(b'\0'); triples=[attrs[i:i+3] for i in range(0,len(attrs)-1,3)]
        require(len(triples)==6 and all(t[2] in (b'unspecified',b'unset') for t in triples),'Git attribute could run a filter or transform bytes')
    def check_bytes():
        for relative,digest in FILES.items():
            path=NATIVE/relative; require(path.is_file() and not path.is_symlink() and sha(path.read_bytes())==digest,'Candidate bytes/path mismatch')
    def status(expected):
        actual=git('status','status','--porcelain=v1','-z','--untracked-files=all'); require(set(actual.split(b'\0')[:-1])==expected and len(actual.split(b'\0')[:-1])==len(expected),'Unexpected Native status')
    try:
        require(Path(git('toplevel','rev-parse','--show-toplevel').decode().strip()).resolve()==NATIVE.resolve(),'Wrong Native checkout')
        require(Path(git('common-dir','rev-parse','--git-common-dir').decode().strip()).resolve()==(MAIN/'.git').resolve(),'Wrong common Git directory')
        gitdir=Path(git('git-dir','rev-parse','--absolute-git-dir').decode().strip()).resolve(); require(gitdir.is_relative_to((MAIN/'.git/worktrees').resolve()),'Unexpected checkout metadata directory'); summary['git_dir']=str(gitdir)
        require(git('head','rev-parse','HEAD').decode().strip()==BASE,'Base drift')
        require(git('branch','symbolic-ref','--quiet','--short','HEAD',expected=(1,))==b'','Expected detached HEAD')
        git('ref-absence','show-ref','--verify','--quiet','refs/heads/'+REF,expected=(1,))
        require(git('base-paths','ls-tree',BASE,'--',*FILES)==b'','Paths already exist at base')
        require(git('index','diff','--cached','--name-only')==b'','Index not empty')
        status({('?? '+p).encode() for p in FILES}); check_bytes(); guard_git_effects(); summary['preflight_passed']=True; save()
        if not args.seal:summary['complete']=True; save(); print(json.dumps({'run':str(run),'preflight_passed':True,'committed':False})); return 0
        claim=AUTH.with_name('SC7两文件本地封存-执行.claim.json')
        with claim.open('x',encoding='utf-8') as f:json.dump({'auth_sha256':sha(AUTH.read_bytes()),'run':str(run),'branch':REF},f,ensure_ascii=False)
        git('switch','switch','-c',REF); require(git('switched-branch','symbolic-ref','--short','HEAD').decode().strip()==REF,'Branch mismatch'); require(git('switched-head','rev-parse','HEAD').decode().strip()==BASE,'Unexpected branch base'); status({('?? '+p).encode() for p in FILES}); check_bytes(); guard_git_effects()
        git('add','add','--',*FILES); git('diff-check','diff','--cached','--check'); status({('A  '+p).encode() for p in FILES})
        changes=git('cached-paths','diff','--cached','--name-status','-z').split(b'\0')[:-1]; require(len(changes)==4 and {tuple(changes[i:i+2]) for i in (0,2)}=={(b'A',p.encode()) for p in FILES},'Staged whitelist mismatch')
        entries=git('index-entries','ls-files','--stage','-z','--',*FILES).split(b'\0')[:-1]; require(len(entries)==2,'Index entry count mismatch')
        for entry in entries:
            meta,relative=entry.split(b'\t',1); mode,oid,stage=meta.split(); require(mode==b'100644' and stage==b'0','Index mode/stage mismatch'); require(sha(git('index-blob','cat-file','blob',oid.decode()))==FILES[relative.decode()],'Index blob identity mismatch')
        check_bytes(); guard_git_effects(); summary.update(commit_attempted=True,committed=None); save(); git('commit','commit','-m',MESSAGE); summary['committed']=True; save()
        commit=git('new-head','rev-parse','HEAD').decode().strip(); require(git('parent','show','-s','--format=%P','HEAD').decode().strip()==BASE,'Parent mismatch'); require(git('message','show','-s','--format=%s','HEAD').decode().strip()==MESSAGE,'Message mismatch')
        raw=git('commit-paths','diff-tree','--no-commit-id','--name-status','-z','-r','HEAD'); require(raw.split(b'\0')[:-1]==changes,'Committed path mismatch')
        for relative,digest in FILES.items():
            tree=git('tree','ls-tree','HEAD','--',relative).decode().strip().split(); require(len(tree)>=4 and tree[0]=='100644' and tree[1]=='blob','Tree mode mismatch'); require(sha(git('commit-blob','cat-file','blob',tree[2]))==digest,'Committed blob identity mismatch')
        status(set()); check_bytes(); require(git('final-branch','symbolic-ref','--short','HEAD').decode().strip()==REF,'Final branch mismatch')
        summary.update(complete=True,commit=commit,parent=BASE,tree=git('tree-id','rev-parse','HEAD^{tree}').decode().strip()); save(); print(json.dumps({'run':str(run),'commit':commit,'complete':True})); return 0
    except Exception as error:
        if summary.get('commit_attempted'):
            summary['commit_outcome_requires_readonly_review']=True
            try:summary['failure_observed_head']=git('failure-head','rev-parse','HEAD').decode().strip()
            except Exception as probe_error:summary['failure_head_probe_error']=type(probe_error).__name__
        summary['error']=type(error).__name__+': '+str(error); save(); print(json.dumps({'run':str(run),'complete':False,'committed':summary['committed'],'error':summary['error']})); return 1
if __name__=='__main__':raise SystemExit(main())
