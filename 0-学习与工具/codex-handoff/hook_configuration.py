"""Machine-specific hooks-only candidate/installer. Default is read-only.

No trust database edits. No full global-settings copy (it can contain secrets).
Exact original hooks bytes and full-file SHA enable conditional byte-exact rollback.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('configuration_io', HERE/'hook_audit_store.py')
io = importlib.util.module_from_spec(spec); spec.loader.exec_module(io)


def sha(data):
    return hashlib.sha256(data).hexdigest()


NATIVE_GUARD_FILES = (
    'hooks-common.ps1', 'hooks-pretooluse-dedup-guard.ps1',
    'hooks-pretooluse-editlock-guard.ps1', 'hooks-pretooluse-queue-read-guard.ps1',
    'mail-native.ps1', 'protected-native.ps1', 'protected-paths.json',
    'sentinel-mojibake.ps1', 'sentinel-pronoun.ps1', 'sentinels-mode.json',
)


def native_guard_paths(repo):
    root = Path(repo)/'0-学习与工具/codex-handoff/guards'
    return [root/name for name in NATIVE_GUARD_FILES]


def verify_native_guard_bundle(repo, expected=None):
    """Check the complete native closure without changing or executing it."""
    paths = native_guard_paths(repo)
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise ValueError('native guard bundle incomplete: '+', '.join(missing))
    if expected is not None and set(expected) != set(NATIVE_GUARD_FILES):
        raise ValueError('native guard binding closure mismatch')
    current = {path.name: sha(path.read_bytes()) for path in paths}
    if expected is not None:
        changed = [name for name, digest in current.items() if digest != expected[name]]
        if changed:
            raise ValueError('native guard source changed: '+', '.join(changed))
    return current


def hooks_span(raw):
    text = raw.decode('utf-8-sig')
    decoder = json.JSONDecoder()
    pos = 0
    def ws(p):
        while p < len(text) and text[p].isspace(): p += 1
        return p
    pos = ws(pos)
    if text[pos] != '{': raise ValueError('configuration must be an object')
    pos += 1; found = []; keys = set()
    while True:
        pos = ws(pos)
        if text[pos] == '}': break
        key, pos = decoder.raw_decode(text, pos)
        if key in keys: raise ValueError('duplicate configuration key')
        keys.add(key); pos = ws(pos)
        if text[pos] != ':': raise ValueError('expected colon')
        start = ws(pos+1)
        value, pos = decoder.raw_decode(text, start)
        if key == 'hooks':
            if not isinstance(value, dict): raise ValueError('hooks must be an object')
            found.append((start, pos, value))
        pos = ws(pos)
        if text[pos] == '}': break
        if text[pos] != ',': raise ValueError('expected comma')
        pos += 1
    if len(found) != 1: raise ValueError('exactly one hooks property required')
    # Validate trailing syntax as well.
    json.loads(text)
    return text, found[0]


def replace_hooks(raw, hooks_text):
    text, (start, end, value) = hooks_span(raw)
    changed = (text[:start] + hooks_text + text[end:]).encode('utf-8')
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + changed


def identity(repo):
    return sha(os.path.normcase(str(Path(repo).resolve())).replace('\\','/').encode())[:16]


def binding_paths(repo,home):
    paths=[repo/'0-学习与工具/codex-handoff'/name for name in
           ('hook_policy.ps1','hook_bridge.py','hook_audit_store.py','hook_configuration.py','hook_log_archive.py','invoke.ps1')]
    return paths+[repo/'.codex/runtime.local.json']+native_guard_paths(repo)


def build(repo, home):
    repo, home = Path(repo).resolve(), Path(home).resolve()
    # Preserve the native-only missing-config contract without reading any
    # configuration content before checking the complete guard closure.
    project_source = repo/'.codex/hooks.json'
    if not project_source.is_file():
        raise FileNotFoundError(f'Native hooks configuration unavailable: {project_source}')
    verify_native_guard_bundle(repo)
    entries = []
    sources = [('project-codex',repo/'.codex/hooks.json'),
               ('global-codex',home/'.codex/hooks.json')]
    for label, path in sources:
        raw = path.read_bytes(); text, (start,end,before) = hooks_span(raw)
        after = copy.deepcopy(before)
        if label == 'project-codex':
            for event in ('UserPromptSubmit','Stop'): after.pop(event, None)
            for group in after.get('PostToolUse',[]):
                group['matcher'] = 'apply_patch|functions.apply_patch|Edit|Write|MultiEdit'
        else:
            for group in after.get('PreToolUse',[]):
                for hook in group.get('hooks',[]):
                    command = hook.get('command','')
                    if 'pretooluse-guard.ps1' in command:
                        kind, legacy = 'Protected', 'pretooluse-guard.ps1'
                        group['matcher'] = 'Edit|Write|MultiEdit|Bash|PowerShell|Read|Grep|Glob|exec_command|functions.exec_command|apply_patch|functions.apply_patch'
                    elif 'outlook-draft-guard.ps1' in command:
                        kind, legacy = 'Mail', 'outlook-draft-guard.ps1'
                        group['matcher'] = 'mcp__plugin_outlook_outlook__outlook_send_mail|mcp__codex_apps__microsoft_outlook_email_send_email'
                    else: continue
                    hook['command'] = 'pwsh -NoProfile -File "{}" -Kind {} -RepoRoot "{}" -LegacyGuard "{}"'.format(
                        repo/'0-学习与工具/codex-handoff/hook_policy.ps1',kind,repo,
                        repo/'0-学习与工具/codex-handoff/guards'/('protected-native.ps1' if kind == 'Protected' else 'mail-native.ps1'))
        rendered = json.dumps(after, ensure_ascii=False, indent=2)
        changed = replace_hooks(raw,rendered)
        entries.append({'label':label,'path':str(path),'before_sha256':sha(raw),'after_sha256':sha(changed),
                        'before_hooks_raw':text[start:end],'after_hooks_raw':rendered})
    bindings = {}
    for path in binding_paths(repo,home):
        bindings[str(path)] = sha(path.read_bytes())
    return {'schema':1,'repo':str(repo),'home':str(home),'identity':identity(repo),'trust_required':True,
            'source_hashes':bindings,'entries':entries}


def validate(package,check_sources=True):
    if package['schema'] != 1 or identity(package['repo']) != package['identity']:
        raise ValueError('repository identity mismatch')
    repo,home = Path(package['repo']),Path(package['home'])
    expected = {str(repo/'.codex/hooks.json'), str(home/'.codex/hooks.json')}
    if {e['path'] for e in package['entries']} != expected or len(package['entries']) != len(expected):
        raise ValueError('configuration ownership conflict')
    expected_sources={str(p) for p in binding_paths(repo,home)}
    if set(package['source_hashes'])!=expected_sources:raise ValueError('guard source binding mismatch')
    if check_sources:
        verify_native_guard_bundle(repo, {path.name: package['source_hashes'][str(path)]
                                        for path in native_guard_paths(repo)})
    for path, expected_hash in package['source_hashes'].items() if check_sources else ():
        if sha(Path(path).read_bytes()) != expected_hash:
            raise ValueError('guard source changed: '+path)


def verify_release(result_path,repo):
    if str(result_path)=='latest-full':
        folders=sorted((Path(repo)/'reports/hook-optimization-20261031').glob('verify-*'))
        reports=[]
        for folder in folders:
            path=folder/'result.json'
            if path.exists():
                value=json.loads(path.read_bytes())
                if value.get('full_requested') or value.get('stage')=='external-pytest-temp-preflight':reports.append(path)
        if not reports:raise ValueError('full verification evidence required')
        result_path=reports[-1]
    result_path=Path(result_path)
    value=json.loads(result_path.read_bytes())
    if not value.get('full_verified') or value.get('source_drift') or value.get('exit')!=0:
        raise ValueError('latest full verification not passed; configuration activation blocked')
    if {p['project'] for p in value['projects'] if p['exit']==0}!={'tools','handoff'}:
        raise ValueError('both complete projects must pass')
    hashes=json.loads((result_path.parent/'candidate-after.json').read_bytes())
    mandatory = {str(p) for p in binding_paths(Path(repo), Path.home())}
    if not mandatory.issubset(hashes):raise ValueError('full verification lacks source binding')
    for name,expected_hash in hashes.items():
        if sha(Path(name).read_bytes()).upper()!=expected_hash.upper():raise ValueError('verified candidate changed: '+name)
    return str(result_path)


def rollback(package, state_path):
    """Restore only our exact output, preserving any concurrent author edit."""
    conflicts=[]; restored=[]
    for entry in reversed(package['entries']):
        path=Path(entry['path'])
        try:current=path.read_bytes()
        except OSError:
            conflicts.append(str(path));continue
        current_hash=sha(current)
        if current_hash == entry['before_sha256']: continue
        if current_hash != entry['after_sha256']:
            conflicts.append(str(path)); continue
        original=replace_hooks(current,entry['before_hooks_raw'])
        if sha(original) != entry['before_sha256']: raise ValueError('rollback preimage mismatch')
        io.atomic(path,original); restored.append(str(path))
    state={'status':'conflict' if conflicts else 'rolled_back','conflicts':conflicts,'restored':restored}
    io.atomic(state_path,json.dumps(state,ensure_ascii=False,indent=2).encode())
    if conflicts: raise ValueError('author edits preserved or file unavailable; recovery pending: '+','.join(conflicts))
    return state


def install(package, state_path, writer=None):
    validate(package)
    state_path=Path(state_path); state_path.parent.mkdir(parents=True,exist_ok=True)
    with io.locked(state_path.with_suffix('.lock')):
        if state_path.exists():
            prior=json.loads(state_path.read_bytes())
            if prior['status']=='applied' and all(sha(Path(e['path']).read_bytes())==e['after_sha256'] for e in package['entries']):
                return {'status':'applied','changed':False,'paths':[],'trust_required':True}
            if prior['status'] != 'rolled_back': raise ValueError('existing install journal requires explicit recovery')
        updates=[]
        for entry in package['entries']:
            raw=Path(entry['path']).read_bytes()
            if sha(raw)!=entry['before_sha256']: raise ValueError('configuration changed: '+entry['path'])
            result=replace_hooks(raw,entry['after_hooks_raw'])
            if sha(result)!=entry['after_sha256']: raise ValueError('candidate hash mismatch')
            updates.append((Path(entry['path']),result))
        io.atomic(state_path,json.dumps({'status':'pending','identity':package['identity']}).encode())
        try:
            for entry,(path,data) in zip(package['entries'],updates):
                if sha(path.read_bytes()) != entry['before_sha256']:
                    raise ValueError('author edited configuration during install: '+str(path))
                (writer or io.atomic)(path,data)
            io.atomic(state_path,json.dumps({'status':'applied','identity':package['identity']}).encode())
        except Exception:
            rollback(package,state_path)
            raise
        return {'status':'applied','changed':True,'paths':[str(p) for p,d in updates],'trust_required':True}


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--build',action='store_true');mode.add_argument('--apply',action='store_true');mode.add_argument('--rollback',action='store_true')
    parser.add_argument('--package',type=Path);parser.add_argument('--verification',type=Path);args=parser.parse_args()
    repo=HERE.parents[1];home=Path(os.environ['USERPROFILE'])
    if not args.apply and not args.rollback:
        package=build(repo,home)
        if args.build:
            if not args.package: parser.error('--build needs --package')
            data=json.dumps(package,ensure_ascii=False,indent=2).encode()
            args.package.parent.mkdir(parents=True,exist_ok=True)
            if args.package.exists() and args.package.read_bytes()!=data: raise ValueError('immutable package already differs; choose new path')
            if not args.package.exists(): io.atomic(args.package,data)
        print(json.dumps({'mode':'candidate' if args.build else 'check','identity':package['identity'],
                          'config_paths':[e['path'] for e in package['entries']],'applied':False,'trust_required':True},ensure_ascii=False))
        return 0
    if not args.package: parser.error('explicit package required')
    package=json.loads(args.package.read_bytes())
    if Path(package['repo']).resolve()!=repo or Path(package['home']).resolve()!=home.resolve():
        raise ValueError('package belongs to another machine/repository')
    state=args.package.with_suffix('.install-state.json')
    if args.rollback:
        validate(package,check_sources=False)
        if not state.exists(): raise ValueError('no owned install journal')
        with io.locked(state.with_suffix('.lock')): result=rollback(package,state)
    else:
        if not args.verification:raise ValueError('--apply requires --verification <result.json|latest-full>')
        already=state.exists() and json.loads(state.read_bytes()).get('status')=='applied' and all(sha(Path(e['path']).read_bytes())==e['after_sha256'] for e in package['entries'])
        if not already:verify_release(args.verification,repo)
        result=install(package,state)
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'blocked','error':str(exc)},ensure_ascii=False));raise SystemExit(2)
