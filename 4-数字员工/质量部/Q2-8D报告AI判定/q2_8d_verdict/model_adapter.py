"""单件、无工具的 Luna 业务推理；不派生开发/审查任务。"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tomllib
from .ai_advice import AdviceRequest,MODEL,canonical

class ModelError(RuntimeError):pass

DISABLED=('shell_tool','apps','plugins','multi_agent','multi_agent_v2','computer_use','browser_use','browser_use_external','in_app_browser','image_generation','view_image','skill_search','tool_suggest','workspace_dependencies','code_mode_host','code_mode','goals','sleep_tool','tool_search','memories','agent_message_board','remote_plugin')
FAIL_CLOSED_NOTICE='Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.'

def _mcp_ids():
    home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    config_path=home/'config.toml'
    if not config_path.exists():return []
    with config_path.open('rb') as stream:data=tomllib.load(stream)
    return sorted(data.get('mcp_servers',{}))  # 不回显/复制其配置值或凭据。

def build_argv(operation_dir:Path,schema_path:Path,images:list[Path])->list[str]:
    exe=shutil.which('codex.exe') or shutil.which('codex')
    if not exe:raise ModelError('Codex CLI unavailable; no model fallback')
    argv=[exe,'exec','--strict-config','--model',MODEL,'--config','model_reasoning_effort="high"','--sandbox','read-only','--ephemeral','--config','web_search="disabled"']
    for server in _mcp_ids():
        if not server.replace('_','').replace('-','').isalnum():raise ModelError('MCP ID cannot safely scope')
        argv+=['--config',f'mcp_servers.{server}.enabled=false']
    for feature in DISABLED:argv+=['--disable',feature]
    argv+=['--cd',str(operation_dir),'--output-schema',str(schema_path),'--json']
    for path in images:argv+=['--image',str(path)]
    return argv+['-']

def parse_events(text:str)->dict:
    if len(text.encode())>2*1024*1024:raise ModelError('model output limit')
    messages=[];usage=None;observed=None
    try:
        for line in text.splitlines():
            if not line.strip():continue
            event=json.loads(line)
            if event.get('type') in ('error','turn.failed') or event.get('error'):raise ModelError('model transport/runtime error; no automatic replay')
            model=event.get('model') or event.get('response',{}).get('model')
            if model:
                if model!=MODEL and not model.startswith(MODEL+'-'):raise ModelError('observed model mismatch')
                observed=model
            item=event.get('item',{})
            if item.get('type')=='error' and item.get('message')==FAIL_CLOSED_NOTICE:
                continue  # CLI 0.157 的明确能力关闭回执，不是工具执行/业务错误。
            if item and item.get('type') not in ('agent_message','reasoning'):raise ModelError('tool or unexpected item event prohibited')
            if event.get('type')=='item.completed' and item.get('type')=='agent_message':messages.append(item['text'])
            if event.get('type')=='turn.completed':usage=event.get('usage')
        if not messages:raise ModelError('model returned no final JSON')
        payload=json.loads(messages[-1])
        if not isinstance(payload,dict):raise ModelError('model JSON must be object')
        return {'payload':payload,'usage':usage,'observed_model':observed,'tool_calls':0}
    except ModelError:raise
    except (ValueError,KeyError,TypeError) as exc:raise ModelError('invalid model event/JSON') from exc

@dataclass(frozen=True)
class ModelResponse:
    payload:dict
    requested_model:str
    observed_model:str|None
    usage:dict|None
    prompt_hash:str
    schema_hash:str
    request_sha256:str
    exit_code:int
    raw_event_sha256:str
    tool_calls:int=0

class CodexAdviceClient:
    def request(self,request:AdviceRequest,operation_dir:Path)->ModelResponse:
        operation_dir.mkdir(parents=True,exist_ok=False)
        schema=operation_dir/'schema.json';schema.write_text(canonical(request.schema),encoding='utf-8')
        (operation_dir/'request.txt').write_text(request.prompt,encoding='utf-8')
        argv=build_argv(operation_dir,schema,list(request.images))
        (operation_dir/'argv.json').write_text(canonical(argv),encoding='utf-8')
        # 能力与版本回执；不修改全局配置/hook/trust。
        cli=argv[0]
        for args,name in (([cli,'--version'],'cli-version.txt'),([cli,'features','list'],'cli-features.txt')):
            check=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=30)
            (operation_dir/name).write_text(check.stdout,encoding='utf-8')
            if check.returncode:raise ModelError('CLI capability verification failed')
        try:
            result=subprocess.run(argv,input=request.prompt,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=600)
        except subprocess.TimeoutExpired as exc:
            (operation_dir/'failure.txt').write_text('timeout; result unknown; do not automatically replay',encoding='utf-8')
            raise ModelError('model timeout; result unknown; no automatic replay') from exc
        (operation_dir/'events.jsonl').write_text(result.stdout,encoding='utf-8')
        (operation_dir/'stderr.txt').write_text(result.stderr[:65536],encoding='utf-8')
        if result.returncode:raise ModelError(f'model exit {result.returncode}; see restricted operation receipt; no automatic replay')
        parsed=parse_events(result.stdout)
        response=ModelResponse(parsed['payload'],MODEL,parsed['observed_model'],parsed['usage'],request.prompt_hash,request.schema_hash,hashlib.sha256(request.prompt.encode()).hexdigest(),result.returncode,hashlib.sha256(result.stdout.encode()).hexdigest())
        (operation_dir/'response.json').write_text(canonical(asdict(response)),encoding='utf-8')
        return response
