"""A retired file cannot become authority when its native counterpart is absent."""
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
def load(filename, name):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module
lint=load('工具-Codex规则lint.py','strict_native_rule_lint')
sweep=load('工具-落库sweep.py','strict_native_sweep')
intent=load('工具-场景包intent闸lint.py','strict_native_intent')
carrier=load('工具-承载性一致性扫描.py','strict_native_carrier')

def test_missing_native_root_keeps_native_target_instead_of_old_body(tmp_path):
    (tmp_path/'CLAUDE.md').write_text('旧正本不应被读作当前规则',encoding='utf8')
    assert lint.target_files(tmp_path,True)==['AGENTS.md']
    assert sweep._current_rule_rel(tmp_path,'CLAUDE.md')=='AGENTS.md'

def test_native_root_schema_accepts_rule_router_and_legacy_progress_stays_checked():
    text='# zhuopinAI\n唯一正本\n# Codex规则路由\ndocs/codex/rules/\n'
    parsed=lint.parse_file('AGENTS.md',text)
    assert parsed.structure=='C' and not parsed.unsupported_reason
    invalid=lint.parse_file('AGENTS.md','unrecognized format')
    assert invalid.unsupported_reason

def test_retirement_marker_in_old_file_does_not_hide_current_scene(tmp_path):
    (tmp_path/'CLAUDE.md').write_text(sweep.SCENARIO_RETIREMENT_MARKER,encoding='utf8')
    assert sweep._scenario_is_retired(tmp_path) is False
    (tmp_path/'CODEX-RULES.md').write_text(sweep.SCENARIO_RETIREMENT_MARKER,encoding='utf8')
    assert sweep._scenario_is_retired(tmp_path) is True

def test_deployment_exemption_only_comes_from_native_body(tmp_path):
    scene=tmp_path/'4-数字员工/测试部/SC99-测试场景'
    scene.mkdir(parents=True)
    (scene/'CLAUDE.md').write_text('## 部署状态\n历史件',encoding='utf8')
    assert intent.build_scene_index(tmp_path)['SC99'].has_deploy_section is False
    (scene/'CODEX-RULES.md').write_text('## 部署状态\n现行正本',encoding='utf8')
    assert intent.build_scene_index(tmp_path)['SC99'].has_deploy_section is True

def test_active_scanner_does_not_load_old_rules_or_skill_sources(tmp_path):
    files=['CLAUDE.md','.claude/rules/old.md','.claude/skills/old/SKILL.md',
           '0-学习与工具/skills源码/old/SKILL.md','AGENTS.md','docs/codex/rules/current.md','.agents/skills/current/SKILL.md']
    for rel in files:
        path=tmp_path/rel;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('machine carrier sample',encoding='utf8')
    loaded={rel for rel,_ in carrier._iter_rule_texts(tmp_path)}
    assert loaded=={'AGENTS.md','docs/codex/rules/current.md','.agents/skills/current/SKILL.md'}

def test_retired_alert_evidence_is_preserved_without_being_marked_resolved(tmp_path):
    rel='reports/state.json';path=tmp_path/rel;path.parent.mkdir()
    keys=['CLAUDE.md','.claude/rules/环境保障线.md','4-数字员工/测试/CLAUDE.md','AGENTS.md']
    data={key:'2026-11-01T00:00:00+00:00' for key in keys}
    path.write_text(json.dumps(data),encoding='utf8');before=path.read_bytes()
    assert sweep._preserve_retired_authority_keys(tmp_path,rel,'rules')==set(keys[:-1])
    assert path.read_bytes()==before

def test_old_carrier_alerts_and_memory_evidence_are_not_false_recoveries(tmp_path):
    rel='reports/carrier.json';path=tmp_path/rel;path.parent.mkdir()
    old='missing:.claude/rules/old.md#L2:机器守='
    new='missing:docs/codex/rules/new.md#L2:机器守='
    path.write_text(json.dumps({old:'2026-11-01T00:00:00+00:00',new:'2026-11-01T00:00:00+00:00'}),encoding='utf8')
    assert sweep._preserve_retired_authority_keys(tmp_path,rel,'carrier')=={old}
    assert sweep.GLOBAL_MEMORY_TARGETS==('~/.codex/AGENTS.md',)
