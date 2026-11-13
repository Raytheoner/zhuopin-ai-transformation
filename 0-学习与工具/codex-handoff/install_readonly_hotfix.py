"""Explicit, single-file emergency repair; never edits hook registrations or trust."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

MARKER = '# ZHUOPIN_READONLY_HOTFIX_V1'
ANCHOR = '  $tool = [string]$j.tool_name'
HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    temp = path.with_name(path.name + '.readonly-hotfix.tmp')
    with temp.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def patched(original, helper, repo):
    text = original.decode('utf-8-sig')
    if MARKER in text:
        raise ValueError('existing hotfix requires its original state receipt')
    if text.count(ANCHOR) != 1:
        raise ValueError('legacy source changed: expected exactly one tool assignment')
    newline = '\r\n' if b'\r\n' in original else '\n'
    block = '\n'.join([
        MARKER,
        '  # Only explicit reads in this repository bypass the old path-only test.',
        '  # Any missing/changed helper or exception falls back to the original guard.',
        '  try {',
        '    $readHelper = ' + ps_literal(helper),
        "    if ((Get-FileHash -LiteralPath $readHelper -Algorithm SHA256).Hash -eq " + ps_literal(sha(helper.read_bytes())) + ') {',
        '      . $readHelper',
        '      if (Test-ZhuopinReadOnlyHookEvent -Event $j -RepoRoot ' + ps_literal(repo) + ') { exit 0 }',
        '    }',
        '  } catch { }',
        '  # END_ZHUOPIN_READONLY_HOTFIX_V1',
    ]).replace('\n', newline)
    body = text.replace(ANCHOR, ANCHOR + newline + block)
    return (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'') + body.encode('utf8')


def operate(repo, legacy, state_dir, action='preflight'):
    repo, legacy, state_dir = map(lambda p: Path(p).resolve(), (repo, legacy, state_dir))
    helper = repo/'0-学习与工具/codex-handoff/readonly_guard_hotfix.ps1'
    if not helper.is_file():
        raise ValueError('missing classifier')
    state_dir.mkdir(parents=True, exist_ok=True)
    # OS lock is released if interrupted; the lock file and recovery state remain.
    with (state_dir/'install.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            return locked(repo, legacy, helper, state_dir, action)
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def locked(repo, legacy, helper, state_dir, action):
    receipt = state_dir/'state.json'
    current = legacy.read_bytes()
    if receipt.exists():
        state = json.loads(receipt.read_bytes())
        if state['legacy'] != str(legacy) or state['repo'] != str(repo):
            raise ValueError('state ownership conflict')
        backup = state_dir/state['backup']
        original = backup.read_bytes()
        if sha(original) != state['before_sha256']:
            raise ValueError('backup hash mismatch; no files changed')
        installed = patched(original, helper, repo)
        if sha(installed) != state['after_sha256']:
            raise ValueError('classifier changed; no files changed')
    else:
        if action == 'rollback':
            raise ValueError('no installation receipt; nothing restored')
        original = current
        installed = patched(original, helper, repo)
        state = dict(repo=str(repo), legacy=str(legacy), backup='guard-before.bin',
                     before_sha256=sha(original), after_sha256=sha(installed),
                     helper_sha256=sha(helper.read_bytes()), status='prepared')
    if sha(current) not in (state['before_sha256'], state['after_sha256']):
        raise ValueError('author edit preserved: guard no longer matches receipt')
    result = dict(action=action, legacy=str(legacy), repo=str(repo),
                  installed=sha(current) == state['after_sha256'], changed=False,
                  trust='Use the normal Codex trust prompt if requested; trust records are untouched.',
                  paths=[])
    if action == 'preflight':
        return result
    backup = state_dir/state['backup']
    if not receipt.exists():
        with backup.open('xb') as stream:
            stream.write(original); stream.flush(); os.fsync(stream.fileno())
        atomic(receipt, (json.dumps(state, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
    desired = installed if action == 'install' else original
    # Recheck immediately before replacing the one explicitly named target.
    if legacy.read_bytes() != current:
        raise ValueError('author edit during installation preserved')
    if sha(helper.read_bytes()) != state['helper_sha256']:
        raise ValueError('classifier changed during installation')
    if current != desired:
        atomic(legacy, desired)
        result.update(changed=True, paths=[str(legacy)])
    if legacy.read_bytes() != desired:
        raise ValueError('post-install readback mismatch; recovery receipt retained')
    state['status'] = 'installed' if action == 'install' else 'rolled_back'
    atomic(receipt, (json.dumps(state, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
    result['installed'] = action == 'install'
    return result


def main():
    parser = argparse.ArgumentParser(description='旧单文件热修安装入口已退役；原生只读分类器由现役 hook 配置承载。')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--rollback', action='store_true')
    parser.parse_args()
    print(json.dumps({'status':'retired','changed':False,
        'entry':'codex-handoff/hook_configuration.py',
        'detail':'不读取或修改旧全局 hook；现役受保护配置按既有人工变更流程处理。'},ensure_ascii=False))
    return 2


if __name__ == '__main__':
    sys.exit(main())
