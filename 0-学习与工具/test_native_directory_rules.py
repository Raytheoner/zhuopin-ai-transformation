"""Exercise authoritative content, dangling entries and legacy-only compatibility."""
from pathlib import Path
import importlib.util
import sys
import pytest

HERE=Path(__file__).resolve().parent
def module(filename, name):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj
    spec.loader.exec_module(obj)
    return obj

lint=module('工具-CLAUDE进度段lint.py','directory_rule_lint')
sweep=module('工具-落库sweep.py','directory_rule_sweep')
carrier=module('工具-承载性一致性扫描.py','directory_rule_carrier')

def write(root, rel, text):
    p=root/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8')
    return p

SCENE='4-数字员工/采购部/SC8-客户订单交期智能承诺'

def test_lint_uses_native_root_instead_of_small_stub(tmp_path):
    write(tmp_path,'AGENTS.md','# native\n')
    write(tmp_path,'CLAUDE.md','# stub\n')
    assert lint.target_files(tmp_path,True)==['AGENTS.md']

def test_lint_checks_complete_native_body(tmp_path):
    write(tmp_path,SCENE+'/CLAUDE.md','# stub\n')
    write(tmp_path,SCENE+'/AGENTS.md','entry')
    write(tmp_path,SCENE+'/CODEX-RULES.md','complete body')
    paths=lint.target_files(tmp_path,False)
    assert SCENE+'/CODEX-RULES.md' in paths
    assert SCENE+'/CLAUDE.md' not in paths

@pytest.mark.parametrize('missing',['missing','empty'])
def test_native_directory_entry_dangling_reference_is_hard_failure(tmp_path,missing):
    write(tmp_path,'AGENTS.md','# Root\n')
    write(tmp_path,SCENE+'/AGENTS.md',f'完整规则：`{SCENE}/CODEX-RULES.md`\n')
    write(tmp_path,SCENE+'/CLAUDE.md','旧文件仍存在，不能以此放行。'*30)
    if missing=='empty':write(tmp_path,SCENE+'/CODEX-RULES.md','')
    violations,*_=lint.check_sentinels(tmp_path)
    assert violations and any('CODEX-RULES.md' in s for s in violations)

def test_lint_root_native_reference_missing_is_not_ignored(tmp_path):
    write(tmp_path,'AGENTS.md','先读 `5-平台底座/CODEX-RULES.md`\n')
    violations,*_=lint.check_sentinels(tmp_path)
    assert violations

def test_size_scanner_uses_native_root_and_full_body(tmp_path):
    write(tmp_path,'AGENTS.md','root')
    write(tmp_path,'CLAUDE.md','stub')
    write(tmp_path,SCENE+'/CLAUDE.md','stub')
    write(tmp_path,SCENE+'/AGENTS.md','entry')
    write(tmp_path,SCENE+'/CODEX-RULES.md','x'*(sweep.CLAUDE_MD_SCENE_BYTE_CAP+1))
    targets=dict(sweep._claude_md_targets(tmp_path))
    assert 'AGENTS.md' in targets and 'CLAUDE.md' not in targets
    assert SCENE+'/CODEX-RULES.md' in targets
    assert SCENE+'/CLAUDE.md' not in targets

def test_native_root_over_cap_is_still_detected(tmp_path):
    write(tmp_path,'AGENTS.md','x'*(sweep.CLAUDE_MD_ROOT_BYTE_CAP+1))
    write(tmp_path,'CLAUDE.md','tiny compatibility stub')
    assert sweep.claude_md_root_over_cap(tmp_path)==1

def test_native_rules_reuse_original_caps_and_reject_consumer(tmp_path):
    old='.claude/rules/场景建造与合规.md'
    new='docs/codex/rules/场景建造与合规.md'
    cap=sweep.CLAUDE_MD_RULES_BYTE_CAP_BY_FILE[old]
    write(tmp_path,old,'stub')
    write(tmp_path,new,'x'*(cap+1))
    assert sweep.claude_md_rules_over_cap(tmp_path)[new]==1
    assert sweep.batch_touches_claude_md_rules([new])
    assert sweep.batch_touches_claude_md_root(['AGENTS.md'])

def test_deployment_trace_requires_native_body_after_migration(tmp_path):
    prefix=SCENE+'/'
    write(tmp_path,prefix+'AGENTS.md','entry')
    write(tmp_path,prefix+'CODEX-RULES.md','deployment state')
    assert prefix not in sweep._find_missing_deployment_trace({prefix+'sc8/webapp.py',prefix+'CODEX-RULES.md'},tmp_path)
    assert prefix in sweep._find_missing_deployment_trace({prefix+'sc8/webapp.py',prefix+'CLAUDE.md'},tmp_path)

def test_retired_marker_read_from_native_authority(tmp_path):
    write(tmp_path,SCENE+'/CLAUDE.md','compatibility pointer')
    write(tmp_path,SCENE+'/CODEX-RULES.md','本场景已退役')
    assert sweep._scenario_is_retired(tmp_path/SCENE)

def test_legacy_only_repository_does_not_supply_native_authority(tmp_path):
    write(tmp_path,SCENE+'/CLAUDE.md','本场景已退役')
    assert not sweep._scenario_is_retired(tmp_path/SCENE)
    assert lint.target_files(tmp_path,True)==['AGENTS.md']

def test_carrier_scans_native_business_claims(tmp_path):
    write(tmp_path,SCENE+'/CODEX-RULES.md','机器守＝`0-学习与工具/nonexistent.py`。')
    assert SCENE+'/CODEX-RULES.md' not in dict(carrier._iter_rule_texts(tmp_path))
    texts=dict(carrier._iter_rule_texts(tmp_path,include_directory_rules=True))
    assert SCENE+'/CODEX-RULES.md' in texts

def test_opening_budget_counts_native_root(tmp_path):
    write(tmp_path,'AGENTS.md','A'*100)
    write(tmp_path,'CLAUDE.md','stub')
    parts,total=lint.opening_budget(tmp_path)
    assert any(rel=='AGENTS.md' and size==100 for _,rel,size in parts)
    assert total==100


def test_intent_gate_reads_deployment_from_native_authority(tmp_path):
    intent=module('工具-场景包intent闸lint.py','directory_rule_intent')
    write(tmp_path,SCENE+'/CLAUDE.md','compatibility pointer')
    write(tmp_path,SCENE+'/CODEX-RULES.md','## 部署状态\n已经部署')
    assert intent.build_scene_index(tmp_path)['SC8'].has_deploy_section

def test_missing_native_rule_is_not_legacy_fallback(tmp_path):
    intent=module('工具-场景包intent闸lint.py','directory_rule_intent_missing')
    write(tmp_path,SCENE+'/AGENTS.md','entry')
    write(tmp_path,SCENE+'/CLAUDE.md','## 部署状态\n旧导航不代表上线')
    with pytest.raises(FileNotFoundError):intent.build_scene_index(tmp_path)
