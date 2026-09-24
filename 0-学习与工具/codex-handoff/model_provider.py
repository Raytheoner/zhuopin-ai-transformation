"""Codex 模型进程适配：只产生执行证据，绝不把进程成功当交付验收。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def resolve_executable(workspace):
    override = os.environ.get('ZHUOPIN_CODEX_EXECUTABLE')
    if override:
        return override
    runtime = os.environ.get('ZHUOPIN_CODEX_RUNTIME')
    config = Path(runtime) if runtime else Path(workspace)/'.codex/runtime.local.json'
    if not config.is_file() and not runtime:
        try:
            common = subprocess.run(['git','-c',f'safe.directory={Path(workspace).as_posix()}',
                '-C',str(workspace),'rev-parse','--path-format=absolute','--git-common-dir'],
                capture_output=True,text=True,encoding='utf-8',timeout=15)
            if common.returncode == 0:
                config = Path(common.stdout.strip()).parent/'.codex/runtime.local.json'
        except (OSError, subprocess.SubprocessError):
            pass
    if runtime and not config.is_file():
        raise FileNotFoundError('Explicit Codex runtime configuration is unavailable')
    if config.is_file():
        data = json.loads(config.read_text(encoding='utf-8-sig'))
        if data.get('codex_executable'):
            return data['codex_executable']
    found = shutil.which('codex')
    if not found:
        raise FileNotFoundError('Codex executable unavailable; Claude fallback is prohibited')
    return found


def resolve_model(model, workspace):
    if not model or model == 'inherit':
        return None
    if model in ('routine','design'):
        path=Path(workspace)/'.codex/model-policy.json'
        if not path.is_file():
            raise ValueError('model route has no explicit policy')
        routes=json.loads(path.read_text(encoding='utf-8-sig')).get('routes',{})
        if model not in routes:
            raise ValueError('model route not configured')
        return routes[model]
    return model


def command(executable, workspace, final, sandbox, *, thread=None, model=None):
    if sandbox not in ('read-only', 'workspace-write'):
        raise ValueError('Only bounded Codex sandbox modes are permitted')
    if model and (model.lower() in ('sonnet', 'opus', 'haiku') or model.startswith('-')):
        raise ValueError('Legacy model aliases are not Codex model routes')
    if thread:
        uuid.UUID(thread)
    args = [str(executable), '-a', 'never', '-s', sandbox, '-C', str(workspace)]
    if model:
        args += ['-m', model]
    args += ['exec']
    if thread:
        args += ['resume']
    args += ['--json', '-o', str(final)]
    if thread:
        args += [thread]
    return args + ['-']


def summarize(events, exit_code):
    thread_id = None
    tool_events = tool_failures = 0
    completed = failed = False
    usage = None
    for event in events:
        kind = event.get('type')
        if kind == 'thread.started':
            thread_id = event.get('thread_id')
        if kind == 'turn.completed':
            completed = True
            usage = event.get('usage')
        if kind in ('turn.failed', 'error'):
            failed = True
        if kind == 'item.completed':
            item = event.get('item', {})
            if item.get('type') in ('command_execution', 'file_change', 'mcp_tool_call', 'web_search'):
                tool_events += 1
                if item.get('status') == 'failed' or item.get('exit_code') not in (None, 0) or item.get('error'):
                    tool_failures += 1
    status = ('failed' if exit_code or failed else 'tool_failed' if tool_failures else
              'output_needs_review' if completed and thread_id else 'incomplete')
    return {'provider':'codex', 'thread_id':thread_id, 'exit_code':exit_code,
            'status':status, 'accepted':False, 'tool_events':tool_events,
            'tool_failures':tool_failures, 'turn_completed':completed,
            'usage':usage, 'current_context_tokens':None,
            'context_source':'unavailable: CLI aggregate usage is not current context',
            'hook_acceptance':'not_evaluated', 'artifact_acceptance':'not_evaluated'}


def native_telemetry(path, thread_id, workspace):
    """原生rollout的最近请求上下文估计，绝不使用total_token_usage。"""
    result = {'current_context_tokens':None, 'actual_model':None,
              'context_source':'unavailable', 'telemetry_file':str(path)}
    matched = False
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue  # 活跃JSONL末行可能尚未写完
        payload = event.get('payload', {})
        if event.get('type') == 'session_meta':
            if payload.get('id') != thread_id or Path(payload.get('cwd','')).resolve() != Path(workspace).resolve():
                raise ValueError('native telemetry session/workspace mismatch')
            matched = True
        if not matched:
            continue
        if event.get('type') == 'turn_context':
            result['actual_model'] = payload.get('model')
            result.update(current_context_tokens=None, context_source='unavailable: new native turn')
        if event.get('type') == 'event_msg' and payload.get('type') == 'token_count':
            result.update(current_context_tokens=None, context_source='unavailable: latest token event')
            info = payload.get('info') or {}
            value = (info.get('last_token_usage') or {}).get('total_tokens')
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                result.update(current_context_tokens=value, context_source='native.last_token_usage.total_tokens')
    if not matched:
        raise ValueError('native telemetry session metadata missing')
    return result


def find_telemetry(thread_id, workspace):
    uuid.UUID(thread_id)
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    files = list((home/'sessions').glob('*/*/*/*'+thread_id+'*.jsonl'))
    if len(files) != 1:
        return {'current_context_tokens':None, 'actual_model':None, 'context_source':'unavailable'}
    return native_telemetry(files[0], thread_id, workspace)


def context_guard(current, *, now, started, soft_since, grace_seconds=900):
    if current is None:
        return ('context_unavailable' if now-started > 120 else None), soft_since
    if current >= 250000:
        return 'hard_limit', soft_since
    if current >= 150000 and soft_since is None:
        soft_since = now
    if grace_seconds > 0 and soft_since is not None and now-soft_since >= grace_seconds:
        return 'soft_grace_expired', soft_since
    return None, soft_since


def event_objects(path):
    result=[]
    if Path(path).exists():
        for line in Path(path).read_text(encoding='utf-8-sig', errors='replace').splitlines():
            try:
                event=json.loads(line)
                if isinstance(event,dict): result.append(event)
            except ValueError:
                pass
    return result


def stop_child(proc):
    """只终止本适配器持有的子进程树；绝不按进程名批量杀。"""
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        result = subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],
                                capture_output=True, timeout=15)
        if result.returncode and proc.poll() is None:
            proc.kill()
    else:
        proc.kill()
    proc.wait(timeout=15)


def run(*, workspace, evidence, prompt, enabled=False, sandbox='read-only', timeout=1200,
        thread=None, model=None, source_id='', executable=None, popen=subprocess.Popen,
        argv_override=None, require_context=False, meter_file=None, grace_seconds=900):
    workspace, evidence = Path(workspace).resolve(), Path(evidence).resolve()
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    evidence.mkdir(parents=True, exist_ok=False)
    started = stamp()
    base = {'source_id':source_id, 'workspace':str(workspace), 'started_at':started,
            'sandbox':sandbox, 'requested_model':model or 'inherit',
            'actual_model':None, 'resume_thread':thread,
            'prompt_sha256':hashlib.sha256(prompt.encode('utf-8')).hexdigest()}
    if not enabled:
        result = {**summarize([], None), **base, 'status':'paused', 'ended_at':stamp()}
        write_json(evidence/'result.json', result)
        return result
    timed_out = False
    context_reason = None
    telemetry = {}
    seen_thread = thread
    soft_since = None
    meter_started = time.monotonic()
    error = None
    argv = None
    exit_code = None
    proc = None
    try:
        argv = command(executable or resolve_executable(workspace), workspace,
                       evidence/'final.txt', sandbox, thread=thread, model=resolve_model(model, workspace))
        # 可注入进程夹具，仅供 Python 测试 API；CLI 不暴露任意命令入口。
        if argv_override is not None:
            argv = list(argv_override)
        write_json(evidence/'request.json', {**base, 'argv':argv})
        with (evidence/'events.jsonl').open('w', encoding='utf-8') as out, \
             (evidence/'stderr.txt').open('w', encoding='utf-8') as err:
            proc = popen(argv, cwd=workspace, stdin=subprocess.PIPE, stdout=out, stderr=err,
                         text=True, encoding='utf-8', errors='replace',
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            write_json(evidence/'process.json', {'pid':proc.pid, 'started_at':started})
            pending_input = prompt
            while True:
                elapsed = time.monotonic()-meter_started
                if elapsed >= timeout:
                    timed_out = True
                    stop_child(proc)
                    break
                try:
                    proc.communicate(pending_input, timeout=min(2.0, timeout-elapsed))
                    process_done = True
                except subprocess.TimeoutExpired:
                    process_done = False
                pending_input = None
                current_events = event_objects(evidence/'events.jsonl')
                for event in current_events:
                    if event.get('type') == 'thread.started': seen_thread = event.get('thread_id')
                if seen_thread:
                    try:
                        telemetry = find_telemetry(seen_thread, workspace)
                    except (OSError, ValueError) as exc:
                        telemetry = {'current_context_tokens':None, 'context_source':'unavailable', 'telemetry_error':str(exc)}
                    write_json(evidence/'session.json', {'thread_id':seen_thread, 'source_id':source_id, 'workspace':str(workspace)})
                if meter_file:
                    meter_path = Path(meter_file)
                    meter_path.parent.mkdir(parents=True, exist_ok=True)
                    write_json(meter_path, {'lastContext':telemetry.get('current_context_tokens'),
                        'session_id':seen_thread, 'source_id':source_id, 'utc':stamp(), **telemetry})
                if require_context:
                    context_reason, soft_since = context_guard(telemetry.get('current_context_tokens'),
                        now=time.monotonic(), started=meter_started, soft_since=soft_since, grace_seconds=grace_seconds)
                    if process_done and telemetry.get('current_context_tokens') is None:
                        context_reason = 'context_unavailable'
                    if context_reason:
                        stop_child(proc)
                        break
                if process_done:
                    break
            exit_code = proc.returncode
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        error = f'{type(exc).__name__}: {exc}'
        if proc is not None and proc.poll() is None:
            try:
                stop_child(proc)
                exit_code = proc.returncode
            except (OSError, subprocess.SubprocessError) as cleanup_error:
                error += f'; child cleanup failed: {cleanup_error}'
    events = []
    malformed = 0
    event_file = evidence/'events.jsonl'
    if event_file.exists():
        for line in event_file.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError('event must be an object')
                events.append(value)
            except (ValueError, TypeError):
                malformed += 1
    result = {**summarize(events, exit_code), **base, 'ended_at':stamp(),
              'malformed_events':malformed, 'error':error, 'timed_out':timed_out,
              'context_reason':context_reason, **telemetry}
    if context_reason:
        result['status'] = 'context_stopped'
    elif timed_out:
        result['status'] = 'timeout'
    elif error:
        result['status'] = 'start_failed'
    elif malformed:
        result['status'] = 'protocol_error'
    write_json(evidence/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--source-id', default='')
    parser.add_argument('--sandbox', choices=['read-only','workspace-write'], default='read-only')
    parser.add_argument('--timeout', type=float, default=1200)
    parser.add_argument('--thread')
    parser.add_argument('--model')
    parser.add_argument('--enabled', action='store_true', help='Explicit bounded run; default is paused')
    parser.add_argument('--require-context', action='store_true')
    parser.add_argument('--meter-file')
    parser.add_argument('--grace-seconds', type=float, default=900)
    parser.add_argument('--emit-final', action='store_true')
    args = parser.parse_args()
    emit_final = args.emit_final
    del args.emit_final
    result = run(**vars(args), prompt=sys.stdin.read())
    if emit_final:
        final = Path(args.evidence)/'final.txt'
        if final.exists(): print(final.read_text(encoding='utf-8'))
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'output_needs_review' else 124 if result['status'] == 'timeout' else 1


if __name__ == '__main__':
    raise SystemExit(main())
