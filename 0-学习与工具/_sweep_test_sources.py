"""Synthetic sources for unrelated alert tests. No live source or service is used."""
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


def seed_synthetic_sources(repo, sweep, *, omit=()):
    repo=Path(repo).resolve()
    if (not os.environ.get('PYTEST_CURRENT_TEST') or not (repo/'.git').exists()
            or not repo.is_relative_to(Path(tempfile.gettempdir()).resolve())):
        raise ValueError('test-only temporary repository required')
    omitted=set(omit)
    if not omitted.issubset({'reminder','outbox','relay'}):raise ValueError('unknown synthetic source')

    def write(rel,data):
        path=(repo/rel).resolve()
        if not path.is_relative_to(repo):raise ValueError('fixture path outside temporary repository')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(data,encoding='utf8')

    if 'reminder' not in omitted:
        write(sweep.REMINDER_HEALTH_REL,json.dumps({'fixture':True,'exit_code':0,'coverage':'complete',
            'finished_at_utc':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()},ensure_ascii=False))
    if 'outbox' not in omitted:write(sweep.LOCAL_REMINDER_OUTBOX_REL,'')
    if 'relay' not in omitted:write(sweep.OUTBOX_RELAY_UNREADABLE_STATE_REL,'{}')

    # Derive the two actual pure functions from the frozen offline source, never a
    # hand-maintained detector or a service with business consumers and networking.
    source=Path(__file__).resolve().parents[1]/'5-平台底座/wecom-aibot-service/aibot_service/outbox_relay.py'
    raw=source.read_bytes();text=raw.decode('utf-8-sig')
    definitions={n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    pure='\n\n'.join(ast.get_source_segment(text,definitions[name]) for name in ('_parse_iso','list_persistently_unreadable'))
    module='# Test-only exact pure functions; offline source SHA256 '+hashlib.sha256(raw).hexdigest()+'\nfrom datetime import datetime\nfrom typing import Optional\n\n'+pure+'\n'
    ast.parse(module)
    service=Path(sweep.OUTBOX_RELAY_SERVICE_DIR_REL)
    if service.is_absolute():raise ValueError('relative synthetic service directory required')
    write((service/'aibot_service/__init__.py').as_posix(),'"""Synthetic pure-function package only."""\n')
    write((service/'aibot_service/outbox_relay.py').as_posix(),module)
