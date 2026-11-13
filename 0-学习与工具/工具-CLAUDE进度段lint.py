"""Retired filename compatibility entry; implementation lives in Codex authority."""
from pathlib import Path as _Path
_native_source = _Path(__file__).with_name("工具-Codex规则lint.py")
# Execute the native module in this namespace so existing library callers keep
# their monkeypatch/import contract. No old rule body is read.
exec(compile(_native_source.read_text(encoding="utf8"), str(_native_source), "exec"), globals())
