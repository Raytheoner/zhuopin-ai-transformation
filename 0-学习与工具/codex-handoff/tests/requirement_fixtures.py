"""Reusable inputs for the original offline workflow tests."""
import importlib.util
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROJECT = '0-学习与工具/fixture-service'


def seed(root, task):
    spec = importlib.util.spec_from_file_location('existing_lint_fixture', BASE.parent / 'test_工具-需求与变更包门禁lint.py')
    sample = importlib.util.module_from_spec(spec); spec.loader.exec_module(sample)
    sample.fixture_repo(root)
    (root / 'openspec/specs/sc1-core/spec.md').write_text(
        '# sc1-core Specification\n\n## Purpose\nExisting isolated fixture capability used to verify requirement workflow integration without changing business code.\n\n## Requirements\n', encoding='utf8')
    old = root / 'openspec/changes/sc1-new-feature'
    old.rename(root / 'openspec/changes' / task)
    index = root / 'docs/requirements/INDEX.md'
    index.write_text(index.read_text(encoding='utf8').replace('sc1-new-feature', task)
        .replace('feature | active_mvp', 'refinement | active_mvp')
        .replace('1/2', '0/2').replace('4-数字员工/采购部/SC1-example/tests/test_core.py', PROJECT + '/tests/test_calc.py'), encoding='utf8')
    service = root / PROJECT
    (service / 'tests').mkdir(parents=True)
    (service / 'calc.py').write_text('def answer():\n    return 0\n', encoding='utf8')
    (service / 'tests/test_calc.py').write_text('from calc import answer\ndef test_answer():\n    assert answer() == 0\n', encoding='utf8')
    change = root / 'openspec/changes' / task
    (change / 'tasks.md').write_text('- [ ] 1. 更新测试\n- [ ] 2. 实现\n', encoding='utf8')
    (change / '.openspec.yaml').write_text('schema: spec-driven\nmode: refinement\ncreated: 2026-11-14\n', encoding='utf8')
    (change / 'specs/sc1-core/spec.md').write_text(
        '## ADDED Requirements\n\n### Requirement: Fixture answer\nThe fixture SHALL return 42.\n\n'
        '#### Scenario: Read the result\n- **WHEN** answer is called\n- **THEN** it returns 42\n', encoding='utf8')
    return change


def acceptance_packet(root,task,current,execute):
    """Bind the fixture's real CI and actual function output, never fabricate success."""
    import json,hashlib,sys,xml.etree.ElementTree as ET
    def ref(path):
        return {'path':path.relative_to(root).as_posix(), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    change=root/'openspec/changes'/task
    target=current['ci_targets'][0]
    junit={'path':target['junit_path'],'sha256':target['junit_sha256']}
    case=next(ET.parse(junit['path']).getroot().iter('testcase'))
    result=execute([sys.executable,'-c','from calc import answer; print(answer())'],cwd=root/PROJECT,timeout=30)
    assert result['exit']==0 and result['stdout'].strip()=='42'
    functional=change/'acceptance-functional.json';functional.write_text(json.dumps(result),encoding='utf8')
    test=root/PROJECT/'tests/test_calc.py'
    packet={'task_id':task,'level':'mock','design':ref(change/'design.md'),
        'candidate':[ref(root/PROJECT/'calc.py'),ref(test)],
        'specs':[ref(change/'specs/sc1-core/spec.md')],
        'coverage':[{'scenario':'sc1-core::Fixture answer::Read the result','junit':junit,
            'classname':case.get('classname'),'testcase':case.get('name'),
            'test_source':ref(test),'functional':ref(functional)}]}
    (change/'acceptance.json').write_text(json.dumps(packet),encoding='utf8')
    return packet
