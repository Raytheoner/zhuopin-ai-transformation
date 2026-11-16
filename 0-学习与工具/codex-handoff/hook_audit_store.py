"""Local bounded hook journal. Never stores commands, prompts or transcripts."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


@contextmanager
def locked(path, timeout=5):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if not path.stat().st_size:
            stream.write(b'0'); stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('local hook store busy')
                time.sleep(.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def atomic(path, data):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def append(folder, row, max_bytes=8*1024*1024):
    """Daily shards + one compatible latest summary per session; old JSON untouched.

    A torn final record refuses append and is kept for explicit recovery. A crash
    after journal commit can leave a stale summary; the JSONL remains authoritative.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    if len(data) > 16384:
        raise ValueError('hook metadata row exceeds 16 KiB')
    day = datetime.now(timezone.utc).strftime('%Y%m%d')
    session = hashlib.sha256(str(row.get('session_id') or 'unknown').encode()).hexdigest()[:24]
    with locked(folder / '.journal.lock'):
        paths = sorted(folder.glob('events-' + day + '-*.jsonl'))
        path = paths[-1] if paths else folder / ('events-' + day + '-000001.jsonl')
        if path.exists() and path.stat().st_size:
            with path.open('rb') as stream:
                stream.seek(-1, 2)
                if stream.read(1) != b'\n':
                    raise ValueError('incomplete hook journal; preserve and repair before append')
            if path.stat().st_size + len(data) > max_bytes:
                number = int(path.stem.rsplit('-', 1)[1]) + 1
                path = folder / ('events-' + day + '-' + str(number).zfill(6) + '.jsonl')
        with path.open('ab') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        atomic(folder / ('session-' + session + '.json'), data)
    return path
