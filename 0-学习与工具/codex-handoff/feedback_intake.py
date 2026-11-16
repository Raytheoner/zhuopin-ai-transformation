"""Session document adapter: archive source bytes, then use the original queue tools.

No model, scheduler, approval inference, business code or follow-up README writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import importlib.util
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[1]


def require_owned_lock(root: Path, who: str, queue_file: Path | None = None):
    """Use the existing lock reader/expiry contract, without acquiring a second lock."""
    spec = importlib.util.spec_from_file_location('feedback_existing_lock', TOOLS / '工具-共享文档编辑锁.py')
    lock = importlib.util.module_from_spec(spec); sys.modules[spec.name] = lock; spec.loader.exec_module(lock)
    target = queue_file or Path(root) / '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'
    data = lock._read_lock(target.with_name(target.name + '.editlock'))
    if not data or data.get('who') != who or lock._age_minutes(data) >= lock.STALE_MINUTES:
        raise ValueError('original shared lock must be held by this writer')


def attach_to_queue(root: Path, receipt: dict, *, row: int, who: str, domain: str,
                    execute, queue_file: Path | None = None) -> dict:
    """Attach a source to the existing row under its original lease; do not claim/build."""
    root = Path(root).resolve()
    require_owned_lock(root, who, queue_file)
    source = receipt.get('source') or {}
    original = (root / source.get('path', '')).resolve()
    if (not original.is_relative_to(root / '7-外部文档') or not original.is_file()
            or hashlib.sha256(original.read_bytes()).hexdigest() != source.get('sha256')):
        raise ValueError('source hash or archive path mismatch')
    query = [sys.executable, str(TOOLS / '工具-队列查询.py')]
    edit = [sys.executable, str(TOOLS / '工具-共享文档编辑锁.py')]
    if queue_file is not None:
        query += ['--file', str(queue_file)]
        edit += ['--file', str(queue_file)]
    args = ['--row', str(row), '--section', '一']
    structured = execute(query + args + ['--format', 'json'], cwd=root, timeout=90)
    if structured.get('exit') != 0:
        raise ValueError('original queue query failed')
    value = json.loads(structured['stdout'])
    if value.get('found') is not True or value.get('carrier') != 'live' or value.get('done') is not False or value.get('error') or value.get('read_errors') != []:
        raise ValueError('original queue row must be live and open')
    full = execute(query + args + ['--field', 'all'], cwd=root, timeout=90)
    if full.get('exit') != 0 or not full.get('stdout'):
        raise ValueError('full queue row unavailable')
    token = '来源SHA256=' + source['sha256']
    if token in full['stdout']:
        return {'status':'attached', 'row':row, 'duplicate':True, 'business_started':False}
    note = f"会话转交原件 `{source['path']}`；{token}；仅材料，待按原拆件机制消化"
    # Structured argv input; body never becomes shell syntax. The original tool
    # still enforces row sizes, columns and matching holder at the actual write.
    temp_dir = root / '.tmp'; temp_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', suffix='.json', dir=temp_dir, delete=False) as f:
        json.dump({'append':{'输入（指针）':note}}, f, ensure_ascii=False)
        changes = Path(f.name)
    try:
        written = execute(edit + ['edit-row', '--who', who, '--section', '一', '--number', str(row),
            '--domain', domain, '--changes-json', str(changes)], cwd=root, timeout=90)
        if written.get('exit') != 0:
            raise ValueError('original queue write failed; keep source for retry')
        checked = execute(query + args + ['--field', 'all'], cwd=root, timeout=90)
        if checked.get('exit') != 0 or token not in checked.get('stdout', ''):
            raise ValueError('queue writeback not proven')
    finally:
        changes.unlink(missing_ok=True)
    return {'status':'attached', 'row':row, 'duplicate':False, 'business_started':False}


def archive_document(root: Path, source: Path, *, department: str, scene: str,
                     source_ref: str, submitted_by: str) -> dict:
    # Keep the established external-document department folders; INDEX uses
    # shorter domain names, accepted here only as aliases, not new directories.
    aliases = {'采购':'采购部', '财务':'财务部', '质量':'质量部', '运营':'运营部',
               '工程研发':'工程研发部', '销售':'销售部', 'IT':'IT'}
    department = aliases.get(department, department)
    if department not in aliases.values():
        raise ValueError('department requires explicit known attribution')
    if not re.fullmatch(r'[A-Z][A-Z0-9-]{1,40}', scene) or not source_ref.strip() or not submitted_by.strip():
        raise ValueError('scene and source provenance required')
    root, source = Path(root).resolve(), Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in ('.docx', '.md', '.txt', '.pdf', '.xlsx'):
        raise ValueError('unsupported source document')
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    folder = root / '7-外部文档' / department / '会话转交' / digest
    if not folder.resolve().is_relative_to(root):
        raise ValueError('archive path escapes repository')
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / '来源.json'
    duplicate = receipt.exists()
    if duplicate:
        saved = json.loads(receipt.read_text(encoding='utf8'))
        original = (root / saved['source']['path']).resolve()
        if not original.is_relative_to(folder.resolve()) or hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise ValueError('archive hash mismatch; preserve evidence')
        if saved['scene'] != scene:
            raise ValueError('same source already associated with another scene; review before rebinding')
    else:
        original = folder / source.name
        if original.exists() and original.read_bytes() != raw:
            raise ValueError('archive hash mismatch; never overwrite')
        if not original.exists():
            with original.open('xb') as stream:
                stream.write(raw)
        saved = {'source_kind': 'session_document', 'scene': scene, 'department': department,
                 'source': {'path': original.relative_to(root).as_posix(), 'sha256': digest},
                 'source_author': None, 'letter_number': None, 'approval': False,
                 'business_started': False, 'received_at': datetime.now(timezone.utc).isoformat()}
        with receipt.open('x', encoding='utf8') as stream:
            json.dump(saved, stream, ensure_ascii=False, indent=2)
    # Append provenance, including renamed resubmissions. This is an audit trail,
    # not a second task/status queue. Document prose is never parsed as commands.
    with (folder / '转交记录.jsonl').open('a', encoding='utf8') as stream:
        stream.write(json.dumps({'source_ref': source_ref, 'submitted_by': submitted_by,
            'original_name': source.name, 'sha256': digest, 'duplicate': duplicate,
            'utc': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False) + '\n')
    return {**saved, 'approval':False, 'business_started':False,
            'receipt': receipt.relative_to(root).as_posix(), 'duplicate': duplicate}
