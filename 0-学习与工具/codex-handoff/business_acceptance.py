"""Validate existing spec/test/audit acceptance evidence; no scoring or execution."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def scenarios(change):
    found = set()
    for spec in sorted((Path(change)/'specs').glob('*/spec.md')):
        requirement = None
        for line in spec.read_text(encoding='utf8').splitlines():
            if line.startswith('### Requirement: '):
                requirement = line.partition(': ')[2].strip()
            elif line.startswith('#### Scenario: ') and requirement:
                key = spec.parent.name+'::'+requirement+'::'+line.partition(': ')[2].strip()
                if key in found: raise ValueError('duplicate spec scenario')
                found.add(key)
    return found


def verify(root, task_id, packet, *, trusted_junit=None):
    root=Path(root).resolve()
    try:
        if not re.fullmatch(r'[a-z][a-z0-9-]{2,63}',task_id):raise ValueError('invalid task id')
        change=root/'openspec/changes'/task_id
        if packet.get('task_id')!=task_id or packet.get('level') not in ('mock','real-readonly'):
            raise ValueError('task or acceptance level mismatch; production is a separate gate')
        def checked(ref, *, junit=False):
            raw=Path(ref['path']); path=(root/raw) if not raw.is_absolute() else raw
            if path.is_symlink(): raise ValueError('symlink evidence rejected')
            path=path.resolve()
            trusted=trusted_junit is not None and any(
                Path(t['path']).resolve()==path and t['sha256']==ref.get('sha256') for t in trusted_junit)
            if (not path.is_relative_to(root) and not (junit and trusted)) or not path.is_file():
                raise ValueError('evidence path missing or outside allowed scope')
            if junit and trusted_junit is not None and not trusted:
                raise ValueError('JUnit is not original verified CI evidence')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=ref['sha256']:raise ValueError('evidence hash drift')
            return path,data
        design,_=checked(packet['design'])
        if design != (change/'design.md').resolve():raise ValueError('wrong design source')
        candidate={checked(r)[0] for r in packet['candidate']}
        if not candidate:raise ValueError('candidate files required')
        expected_files={p.resolve() for p in (change/'specs').glob('*/spec.md')}
        supplied={checked(r)[0] for r in packet['specs']}
        if not expected_files or supplied!=expected_files:raise ValueError('spec coverage missing or extra')
        required=scenarios(change)
        if not required:raise ValueError('no applicable business scenarios')
        coverage=packet['coverage']
        keys=[c['scenario'] for c in coverage]
        if set(keys)!=required or len(keys)!=len(required):raise ValueError('business scenario coverage mismatch')
        for item in coverage:
            test,_=checked(item['test_source'])
            if test not in candidate or not test.name.startswith('test_') or test.suffix!='.py':
                raise ValueError('pytest source must be part of candidate')
            _,raw=checked(item['junit'],junit=True)
            tree=ET.fromstring(raw)
            if tree.tag not in ('testsuite','testsuites'):raise ValueError('invalid JUnit')
            if any(int(s.get('failures','0')) or int(s.get('errors','0')) for s in tree.iter('testsuite')):
                raise ValueError('JUnit contains failures')
            if any(e.tag in ('failure','error') for e in tree.iter()):raise ValueError('JUnit contains failed case')
            cases=[c for c in tree.iter('testcase') if c.get('classname')==item['classname'] and c.get('name')==item['testcase']]
            if len(cases)!=1 or any(cases[0].find(tag) is not None for tag in ('failure','error','skipped')):
                raise ValueError('mapped test case is missing, ambiguous or not passed')
            _,functional=checked(item['functional'])
            if not functional.strip():raise ValueError('functional/audit evidence empty')
        return {'status':'accepted','scenarios':len(required),'level':packet['level'],
                'production_accepted':False,'professional_signoff':False}
    except (OSError,ValueError,KeyError,TypeError,AttributeError,ET.ParseError) as exc:
        return {'status':'blocked','reason':str(exc),'production_accepted':False}
