
"""Auditable Codex handoff: source inventory, task preparation and bounded stage execution."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get("ZHUOPIN_CODEX_STATE", str(ROOT / ".codex" / "state")))
QUERY = ROOT / "0-学习与工具" / "工具-队列查询.py"

def provider_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('handoff_provider',Path(__file__).with_name('model_provider.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def codex_command():
    return provider_module().resolve_executable(ROOT)


def model_run(**kwargs):
    return provider_module().run(**kwargs)


def now():
    return datetime.now(timezone.utc).isoformat()

def execute(argv, cwd=ROOT, timeout=90):
    try:
        p = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                           text=True, encoding="utf8", errors="replace", timeout=timeout)
        return {"argv": [str(x) for x in argv], "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"argv": [str(x) for x in argv], "exit": -1, "stdout": "", "stderr": type(e).__name__ + ": " + str(e)}

def git(*args, cwd=ROOT):
    return execute(["git", "-c", "safe.directory=" + str(cwd).replace("\\", "/"),
                    "-c", "core.quotepath=false", *args], cwd=cwd)

def write_json(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    temp.replace(file)

def probe():
    checks = {
        "head": git("rev-parse", "HEAD"), "status": git("status", "--short"),
        "worktrees": git("worktree", "list", "--porcelain"),
        "python": execute([sys.executable, "--version"]),
        "codex": execute([codex_command(), "--version"]),
        "openspec": execute(["pwsh", "-NoProfile", "-Command", "openspec --version"]),
        "queue": execute([sys.executable, QUERY, "--digest", "--actionable"]),
        "ci_matrix": execute([sys.executable, ROOT/"0-学习与工具"/"工具-CI矩阵发现.py"]),
    }
    row = {"time": now(), "root": str(ROOT), "checks": checks,
           "limitations": ["Hooks trust requires /hooks; not inferable from this probe.",
                          "Windows registered-task state is not inferred from source scripts."]}
    target = STATE / "probe.json"
    write_json(target, row)
    print(json.dumps({"report": str(target), "checks": {k:v["exit"] for k,v in checks.items()}}, ensure_ascii=False))
    return int(any(x["exit"] != 0 for x in checks.values()))

def prepare(args):
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,63}", args.id):
        raise ValueError("id must be lowercase slug, 3..64 characters")
    folder = STATE / "runs" / args.id
    folder.mkdir(parents=True, exist_ok=False)
    queue = execute([sys.executable, QUERY, "--row", str(args.row), "--section", args.section,
                     "--format", "json"])
    write_json(folder/"queue.json", queue)
    if queue["exit"]:
        raise RuntimeError("queue query failed; no task prepared")
    head = git("rev-parse", "HEAD")
    if head["exit"]:
        raise RuntimeError("cannot read git HEAD")
    prompt = (
        "请在当前项目执行下述单一队列任务。先读 AGENTS.md、CLAUDE.md、适用规则及全景/实施计划。"
        "真实队列通过查询工具确认，快照不能代替实时状态。\n"
        f"队列：§{args.section} #{args.row}\n意图：{args.intent}\n"
        "工作流：intent 确认 → OpenSpec proposal/design/tasks → 实现 → 按 CI 矩阵逐项目验证"
        " → review → 发布准备。前一阶段证据不满足立即停止。\n"
        "本执行器不授予设计批准、合入、生产部署、外发、L2 签署权限；仍查原项目逐项授权。"
        "部署程序只引用 zhuopin-lan-closeout 正本，不复制纪律。\n"
        "保留其他人的修改；不得绕过 sandbox、hooks trust、编辑锁、队列专用工具或测试。"
        "最终交付命令、退出码、证据路径、未闭合项。不得声称未执行的阶段已完成。\n"
    )
    (folder/"intent.md").write_text(prompt, encoding="utf8")
    write_json(folder/"state.json", {"id": args.id, "created": now(), "source_head": head["stdout"].strip(),
                                   "status": "prepared", "row": args.row, "section": args.section})
    print(str(folder))
    return 0

def run_stage(args):
    folder = STATE / "runs" / args.id
    state_file = folder/"state.json"
    state = json.loads(state_file.read_text(encoding="utf8"))
    workspace = Path(args.workspace).resolve()
    # Model writes are restricted to a separately selected, clean git worktree.
    if workspace == ROOT and args.phase == "implement":
        raise ValueError("implementation requires a separate clean worktree; preserve active source checkout")
    head = git("rev-parse", "HEAD", cwd=workspace)
    status = git("status", "--porcelain", cwd=workspace)
    if head["exit"] or status["exit"]:
        raise ValueError("workspace must be an existing Git checkout")
    if head["stdout"].strip() != state["source_head"]:
        raise ValueError("HEAD drift: re-prepare task against current source before execution")
    if args.phase == "implement" and status["stdout"].strip():
        raise ValueError("implementation workspace must be clean")
    evidence = None
    if args.phase == "implement":
        if not args.authorization:
            raise ValueError("implementation requires existing item-specific design authorization evidence")
        p = Path(args.authorization).resolve()
        evidence = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        if p.stat().st_size == 0:
            raise ValueError("empty authorization evidence")
    lock = folder/"running.lock"
    # Exclusive create, never silently break a stale lock.
    with lock.open("x", encoding="utf8") as f:
        f.write(json.dumps({"pid":os.getpid(), "time":now()}))
    try:
        attempt = folder/(args.phase+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8])
        attempt.mkdir()
        prompt = (folder/"intent.md").read_text(encoding="utf8")
        prompt += "\n当前只执行阶段：" + args.phase + "。"
        if args.phase == "plan":
            prompt += "只读梳理与给出 proposal/design/tasks 草稿；不得实施；指出所需的原项目授权。"
        elif args.phase == "review":
            prompt += "只读评审已存在成果与实跑证据；不得把测试未跑解释为通过。"
        else:
            prompt += "\n先核验逐项授权证据是否真实且覆盖本任务：" + evidence["path"]
            prompt += "。不覆盖则停止。只在本隔离工作树实现及验证；不得合入/部署/发送/改原队列。"
        state.update(status="running", phase=args.phase, attempt=str(attempt), authorization=evidence)
        write_json(state_file, state)
        model_evidence = attempt/'model-evidence'
        try:
            result = model_run(workspace=workspace,evidence=model_evidence,prompt=prompt,
                enabled=True,sandbox='workspace-write' if args.phase=='implement' else 'read-only',
                timeout=args.timeout,source_id=args.id+':'+args.phase,require_context=True)
        except (OSError,ValueError) as exc:
            result = {'status':'adapter_failed','exit_code':None,'thread_id':None,'error':type(exc).__name__}
        code = 0 if result.get('status')=='output_needs_review' else 1
        final = model_evidence/'final.txt'
        if final.is_file():
            shutil.copyfile(final,attempt/'final.txt')
        state.update(status="stage_output_needs_review" if code == 0 else "failed",
                     exit=code, model_exit=result.get('exit_code'),model_status=result.get('status'),
                     thread_id=result.get('thread_id'),model_evidence=str(model_evidence),
                     delivery_accepted=False,finished=now(),workspace=str(workspace))
        # An LLM exit 0 is never a build/review/deployment acceptance.
        write_json(state_file, state)
        print(json.dumps(state, ensure_ascii=False))
        return int(code != 0)
    finally:
        lock.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command", required=True)
    sub.add_parser("probe")
    q=sub.add_parser("prepare")
    q.add_argument("--id",required=True); q.add_argument("--row",required=True,type=int)
    q.add_argument("--section",choices=["一","二","四"],default="一")
    q.add_argument("--intent",required=True)
    r=sub.add_parser("run")
    r.add_argument("--id",required=True); r.add_argument("--phase",choices=["plan","implement","review"],required=True)
    r.add_argument("--workspace",required=True); r.add_argument("--authorization")
    r.add_argument("--timeout",type=int,default=1800)
    args=p.parse_args()
    try:
        return probe() if args.command=="probe" else prepare(args) if args.command=="prepare" else run_stage(args)
    except Exception as e:
        print(type(e).__name__+": "+str(e),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
