"""Test-only real readonly CLI sources with synthetic README/Git inputs."""
from datetime import date
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

PURE_SOURCES = (
    '0-学习与工具/工具-跟进信README查询.py',
    '5-平台底座/wecom-aibot-service/scripts/draft_gap_check.py',
    '5-平台底座/wecom-aibot-service/aibot_service/__init__.py',
    '5-平台底座/wecom-aibot-service/aibot_service/readme_table.py',
    '5-平台底座/wecom-aibot-service/aibot_service/draft_gap_detection.py',
    '5-平台底座/wecom-aibot-service/aibot_service/repo_paths.py',
    '5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py',
    '5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py',
    '5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/followup_gate.py',
)
README_REL = '6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md'

def seed_readonly_cli_sources(repo):
    repo = Path(repo).resolve()
    source = Path(__file__).resolve().parents[1]
    if (not os.environ.get('PYTEST_CURRENT_TEST') or not repo.is_dir()
            or not repo.is_relative_to(Path(tempfile.gettempdir()).resolve())
            or repo == source or (repo/'.git').exists()):
        raise ValueError('fresh owned temporary fixture required')
    hashes = {}
    for relative in PURE_SOURCES:
        original = source/relative
        target = repo/relative
        raw = original.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        assert target.read_bytes() == raw
        hashes[relative] = hashlib.sha256(raw).hexdigest()
    readme = repo/README_REL
    readme.parent.mkdir(parents=True, exist_ok=True)
    number = '机制部#9001'
    readme.write_text('## 现有跟进信清单\n\n'
        '| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n'
        '|---|---|---|---|---|---|\n'
        f'| {number} | {date.today().isoformat()} | 机制部 · 合成人 | synthetic-only | 无业务交期 | 🆕 待发 |\n',encoding='utf8')
    event = repo/'4-数字员工/采购部/SC8-客户订单交期智能承诺/synthetic-mechanism-fixture.txt'
    event.parent.mkdir(parents=True)
    event.write_text('Synthetic local Git event only; no business artifact.\n',encoding='utf8')
    def git(*args):
        return subprocess.run(['git','-c','user.name=MechanismFixture','-c','user.email=fixture@example.invalid',*args],
            cwd=repo,check=True,capture_output=True,text=True,encoding='utf8').stdout.strip()
    git('init','-q','-b','master')
    git('config','commit.gpgsign','false')
    git('add','--',*PURE_SOURCES,README_REL,event.relative_to(repo).as_posix())
    git('commit','-q','-m','synthetic readonly CLI sources')
    return {'readme_number':number,'commit_sha':git('rev-parse','HEAD'),'source_hashes':hashes}
