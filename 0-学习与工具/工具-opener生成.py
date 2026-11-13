"""兼容文件名；实现及 CLI 唯一正本为工具-Codex开场生成.py。"""
from pathlib import Path as _Path
_native = _Path(__file__).with_name('工具-Codex开场生成.py')
exec(compile(_native.read_text(encoding='utf-8-sig'), str(_native), 'exec'), globals())
