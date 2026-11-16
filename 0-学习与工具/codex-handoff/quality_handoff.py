"""接力资料本地维护；无网络、模型、Git写入或业务状态推断。

原队列仍是任务/执行归属正本；本模块仅保存接力记录并生成有界索引。
正式写卡由invoke的R5Card复用原登记/单文件锁；此处锁保护合作维护进程。
"""
from contextlib import contextmanager
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

BASE = 'docs/handoff/quality'
ENTRY = '0-学习与工具/codex-handoff/质量域-R5接力-2026-10-20.md'
DOMAINS = {
    'quality': {'base': BASE, 'entry': ENTRY, 'label': '质量', 'prefix': 'QH', 'date': '20261020'},
    'procurement': {'base': 'docs/handoff/procurement', 'entry': '0-学习与工具/codex-handoff/1020采购七场景真实数据接续-2026-10-20.md', 'label': '采购', 'prefix': 'PH', 'date': '20261020'},
    'finance': {'base': 'docs/handoff/finance', 'entry': '0-学习与工具/codex-handoff/1019财务业务补齐转场接力-2026-10-19.md', 'label': '财务', 'prefix': 'FH', 'date': '20261019'},
    'phase1': {'base': 'docs/handoff/phase1', 'entry': '1-转型规划/0-全景路线图/session接力-Phase1收口.md', 'label': 'Phase1', 'prefix': 'P1H', 'date': '20261030'},
}
R5_SECTIONS = ('目标', '已批范围', '完成／停点', '证据', '下一步', '待审批')
STATUSES = ('open', 'review', 'closed', 'reference')


class HandoffError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


class Store:
    def __init__(self, root, base=BASE, entry=ENTRY, *, domain='quality'):
        if domain not in DOMAINS:
            raise HandoffError('unknown domain')
        self.domain = domain
        self.profile = DOMAINS[domain]
        self.root = Path(root).resolve()
        self.base_rel, self.entry_rel = base, entry
        self.base = self.resolve(base)

    def resolve(self, rel):
        if not isinstance(rel, str) or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise HandoffError('unsafe relative path')
        p = self.root / rel
        if not p.resolve().is_relative_to(self.root):
            raise HandoffError('path escapes repository')
        return p

    def path(self, rel):
        return self.resolve(self.base_rel + '/' + rel)

    def rel(self, path):
        return str(path.relative_to(self.root)).replace('\\', '/')

    def read_json(self, rel):
        try:
            return json.loads(self.path(rel).read_bytes())
        except (OSError, ValueError) as exc:
            raise HandoffError('invalid or missing ' + rel) from exc

    def item_path(self, item_id):
        if not re.fullmatch(self.profile['prefix'] + r'-[A-Za-z0-9-]+', item_id):
            raise HandoffError('invalid permanent id')
        return self.path('items/' + item_id + '.json')

    @contextmanager
    def lock(self):
        self.base.mkdir(parents=True, exist_ok=True)
        with self.path('.maintain.lock').open('a+b') as f:
            if f.tell() == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise HandoffError('maintenance busy') from exc
            try:
                yield
            finally:
                f.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(f, fcntl.LOCK_UN)

    @staticmethod
    def immutable(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('xb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
        except FileExistsError:
            if path.read_bytes() != data:
                raise HandoffError('immutable hash conflict: ' + str(path))

    @staticmethod
    def current_hash(path):
        return digest(path.read_bytes()) if path.is_file() else None

    @staticmethod
    def atomic(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
        with temp.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)

    def record(self, item_id, title, text, sources, topic=None, owner='原任务Owner；执行状态待核'):
        return {'id': item_id, 'topic': topic or self.profile['label'], 'title': title, 'owner': owner,
                'status': 'review', 'done_when': '核对应原任务现时证据与剩余判据后确认；不得仅凭历史标题关闭',
                'risk': '遗失将丢失历史授权、未完条件或证据定位', 'sources': sources,
                'completion_evidence': [], 'original_text': text, 'notes': '',
                'legacy_ids': sorted(set(re.findall(r'#\d+', text)))}

    @staticmethod
    def identity(record):
        return {'sources': record['sources'], 'original_sha256': digest(record['original_text'].encode()),
                'legacy_ids': record['legacy_ids']}

    def initialize(self, seed):
        with self.lock():
            if self.path('catalog.json').exists() or self.path('.pending.json').exists():
                raise HandoffError('already initialized or recovery required')
            source = self.resolve(self.entry_rel); original = source.read_bytes()
            original.decode('utf-8-sig', errors='strict')
            snapshot_rel = 'archive/' + digest(original) + '.bin'
            self.immutable(self.path(snapshot_rel), original)
            lines = original.splitlines(keepends=True); mapping = []; records = {}
            frontmatter = set()
            if lines and lines[0].decode('utf-8-sig').strip() == '---':
                end = next((n for n in range(1, len(lines)) if lines[n].decode('utf-8-sig').strip() == '---'), None)
                if end is None:
                    raise HandoffError('unterminated frontmatter')
                frontmatter = set(range(1, end + 2))
            for i, line in enumerate(lines, 1):
                text = line.decode('utf-8-sig')
                structural = i in frontmatter or not text.strip() or text.strip() == '>' or bool(re.match(r'^#{1,6}(?:\s|$)', text.lstrip()))
                if structural:
                    mapping.append({'line': i, 'kind': 'structure', 'sha256': digest(line)})
                    continue
                if i not in seed:
                    raise HandoffError('missing semantic seed for source line ' + str(i))
                item_id = f"{self.profile['prefix']}-{self.profile['date']}-L{i:03}"
                sources = [{'path': self.rel(self.path(snapshot_rel)), 'sha256': digest(original), 'start': i, 'end': i}]
                record = self.record(item_id, seed[i]['title'], text, sources, seed[i].get('topic'))
                for field in ('owner', 'done_when', 'risk', 'notes', 'r5_section', 'entry_summary'):
                    if field in seed[i]: record[field] = seed[i][field]
                records[item_id] = record
                mapping.append({'line': i, 'kind': 'item', 'id': item_id, 'sha256': digest(line)})
            if set(seed) != {x['line'] for x in mapping if x['kind'] == 'item'}:
                raise HandoffError('seed source ranges differ')
            migration = {'source': self.entry_rel, 'snapshot': snapshot_rel, 'source_sha256': digest(original), 'lines': mapping}
            self.immutable(self.path('migration.json'), encode(migration))
            for item_id, record in records.items():
                self.immutable(self.item_path(item_id), encode(record))
            catalog = {'schema': 1, 'entry': self.entry_rel, 'migration_sha256': digest(encode(migration)),
                       'known': {}, 'revisions': {}, 'generated': {}}
            if self.domain != 'quality':
                catalog['domain'] = self.domain
            published = self._apply(catalog, records, initialize_hash=digest(original))
            self._check()
            return published

    def _catalog(self):
        catalog = self.read_json('catalog.json')
        raw = self.path('catalog.json').read_bytes()
        archived = self.path('archive/catalog-' + digest(raw) + '.json')
        if not archived.is_file() or archived.read_bytes() != raw:
            raise HandoffError('catalog manually changed or hash damaged')
        if catalog.get('entry') != self.entry_rel:
            raise HandoffError('entry identity rebound')
        if catalog.get('domain', 'quality') != self.domain:
            raise HandoffError('domain identity rebound')
        return catalog

    def _records(self, catalog):
        records = {}
        for p in self.path('items').glob('*.json'):
            try:
                raw = p.read_bytes(); record = json.loads(raw)
                item_id = record['id']
                if self.item_path(item_id) != p:
                    raise HandoffError('id path rebound')
                for key in ('topic', 'title', 'owner', 'status', 'done_when', 'risk', 'sources', 'completion_evidence', 'original_text', 'notes', 'legacy_ids'):
                    if key not in record:
                        raise HandoffError('missing item field: ' + key)
                if record['status'] not in STATUSES or not all(isinstance(record[k], str) and record[k].strip() for k in ('topic', 'title', 'owner', 'done_when', 'risk')):
                    raise HandoffError('invalid record fields')
                if record['status'] in ('closed', 'reference'):
                    evidence = record['completion_evidence']
                    required = 'completion' if record['status'] == 'closed' else 'reference'
                    if not evidence or not any(e.get('kind') == required for e in evidence):
                        raise HandoffError('closed/reference requires evidence')
                    for e in evidence:
                        if self.current_hash(self.resolve(e['path'])) != e['sha256']:
                            raise HandoffError('completion/reference evidence hash mismatch')
                if item_id in catalog['known'] and self.identity(record) != catalog['known'][item_id]:
                    raise HandoffError('source or original text rebound: ' + item_id)
                records[item_id] = record
            except (KeyError, TypeError, ValueError, OSError) as exc:
                raise HandoffError('invalid item: ' + str(p)) from exc
        if not set(catalog['known']).issubset(records):
            raise HandoffError('known permanent id missing')
        for item_id, versions in catalog['revisions'].items():
            if not versions:
                raise HandoffError('missing revision lineage')
            for h in versions:
                if self.current_hash(self.path(f'revisions/{item_id}/{h}.json')) != h:
                    raise HandoffError('immutable revision hash damaged')
        migration = self.read_json('migration.json')
        if self.current_hash(self.path('migration.json')) != catalog['migration_sha256']:
            raise HandoffError('migration hash damaged')
        original = self.path(migration['snapshot']).read_bytes()
        if digest(original) != migration['source_sha256']:
            raise HandoffError('source snapshot hash damaged')
        lines = original.splitlines(keepends=True)
        if [x['line'] for x in migration['lines']] != list(range(1, len(lines) + 1)):
            raise HandoffError('source line coverage missing')
        for entry, raw in zip(migration['lines'], lines):
            if digest(raw) != entry['sha256']:
                raise HandoffError('source line hash damaged')
            if entry['kind'] == 'item':
                record = records.get(entry['id'])
                if not record or record['original_text'] != raw.decode('utf-8-sig'):
                    raise HandoffError('source content coverage missing')
        return records

    def _render(self, records):
        outputs = {}; page_links = []; counts = {s: 0 for s in STATUSES}
        for status in STATUSES:
            entries = [r for _, r in sorted(records.items()) if r['status'] == status]
            counts[status] = len(entries)
            page = 1; heading = f"# {self.profile['label']}资料 · {status}\n\n"; text = heading
            for r in entries:
                title = r['title'].replace('\n', ' ')[:140]
                line = f"- [{r['id']} · {title}](../items/{r['id']}.json)\n"
                if len((text + line).encode()) > 8192:
                    rel = f'views/{status}-{page:03}.md'; outputs[self.rel(self.path(rel))] = text.encode(); page_links.append((status, rel)); page += 1; text = heading
                text += line
            if entries:
                rel = f'views/{status}-{page:03}.md'; outputs[self.rel(self.path(rel))] = text.encode(); page_links.append((status, rel))
        if self.domain == 'phase1':
            return self._render_r5(outputs, records, counts, page_links)
        text = f"# [Win]1030 {self.profile['label']}域资料索引（自动生成）\n\n"
        text += '已按§四352转为专题资料索引。此页不代表旧业务写方已停止或新会话已接管。任务状态/归属仍查原队列；只读所需分组和单项，不默认整读历史。\n\n'
        text += '## 分组\n\n' + '；'.join(f'{s}：{counts[s]}' for s in STATUSES) + f'。共{len(records)}项。\n\n'
        parent = self.resolve(self.entry_rel).parent
        for status, rel in page_links:
            link = os.path.relpath(self.path(rel), parent).replace('\\', '/')
            text += f'- [{status} · {Path(rel).stem}]({link})\n'
        manual = os.path.relpath(self.root / 'docs/handoff/quality-maintenance.md', parent).replace('\\', '/')
        apply_entry = 'R5Card apply' if self.domain == 'quality' else f'--domain {self.domain} --apply'
        text += f'\n## 阅读与更新\n\n[维护说明]({manual})。新增/修改只进入单项JSON，再走{apply_entry}；首页/分页禁止手工追加。所有旧段均原字节保全，目录与来源映射由本地程序核验。\n\n'
        text += '## 执行边界\n\n普通建造由已确认唯一写方的主会话串行推进。泳道看护完整保留，按任务显式选择；不因本迁移恢复旧批、清锁或扩大生产/真实源/外发权限。历史记录均待核，不将旧成功/待批自动当作今天状态。\n'
        if len(text.encode()) > 4096:
            raise HandoffError('entry exceeds 4096 bytes')
        outputs[self.entry_rel] = text.encode()
        return outputs, counts

    def _render_r5(self, outputs, records, counts, page_links):
        slots = {}
        for record in records.values():
            section = record.get('r5_section')
            if section is None:
                continue
            summary = record.get('entry_summary')
            if section not in R5_SECTIONS or section in slots or not isinstance(summary, str) or not summary.strip() or len(summary.encode()) > 512:
                raise HandoffError('invalid or duplicate R5 section/summary')
            slots[section] = record
        if set(slots) != set(R5_SECTIONS):
            raise HandoffError('R5 requires all six section records')
        parent = self.resolve(self.entry_rel).parent
        link = lambda p: os.path.relpath(p, parent).replace('\\', '/')
        text = '# [Win]1030 · Phase1 接力（自动生成）\n\n'
        text += '本轮仅接手资料维护，原业务执行归属保留。只读相关完整记录；新增/修改进入单项真源，禁止向首页追加。'
        text += f'共{len(records)}条资料；' + '、'.join(f'{s} {counts[s]}' for s in STATUSES) + '。\n'
        for section in R5_SECTIONS:
            record = slots[section]
            text += f"\n## {section}\n{record['entry_summary']} [完整记录]({link(self.item_path(record['id']))})\n"
            if section == '证据':
                text += ' '.join(f'[{status}分组]({link(self.path(rel))})' for status, rel in page_links)
                text += f" · [维护说明]({link(self.root/'docs/handoff/quality-maintenance.md')})\n"
        if len(text.encode()) > 4096:
            raise HandoffError('entry exceeds 4096 bytes')
        outputs[self.entry_rel] = text.encode()
        return outputs, counts

    def _capture(self, path, raw):
        h = digest(raw); self.immutable(self.path('conflicts/' + h + '.bin'), raw)
        record = self.record(self.profile['prefix'] + '-MANUAL-' + h[:20], '人工编辑生成页待核：' + self.rel(path), raw.decode('utf-8-sig'),
                             [{'path': self.rel(self.path('conflicts/' + h + '.bin')), 'sha256': h, 'start': 1, 'end': len(raw.splitlines())}])
        self.immutable(self.item_path(record['id']), encode(record))

    def _apply(self, catalog, records=None, initialize_hash=None, accept_drift=(), fault=None):
        if self.path('.pending.json').exists():
            raise HandoffError('recovery required; use explicit recover')
        records = records if records is not None else self._records(catalog)
        for rel, expected in catalog['generated'].items():
            p = self.resolve(rel)
            if self.current_hash(p) != expected:
                if not p.is_file():
                    raise HandoffError('generated page missing')
                raw = p.read_bytes(); self._capture(p, raw)
                if digest(raw) not in accept_drift:
                    raise HandoffError('manual generated edit preserved as independent review record; explicit accept required')
        if accept_drift:
            records = self._records(catalog)
        for item_id, record in records.items():
            raw = encode(record); h = digest(raw)
            self.immutable(self.path(f'revisions/{item_id}/{h}.json'), raw)
            catalog['known'].setdefault(item_id, self.identity(record))
            versions = catalog['revisions'].setdefault(item_id, [])
            if h not in versions: versions.append(h)
        outputs, counts = self._render(records)
        # 旧页保留可审计空索引，禁止遗留旧内容继续充当活动展示。
        for rel in catalog['generated']:
            if rel not in outputs:
                outputs[rel] = b'# Archived generated page\n\nUse the current entry.\n'
        catalog['generated'] = {p: digest(b) for p, b in outputs.items()}
        catalog_raw = encode(catalog)
        self.immutable(self.path('archive/catalog-' + digest(catalog_raw) + '.json'), catalog_raw)
        outputs[self.rel(self.path('catalog.json'))] = catalog_raw
        inputs = {self.rel(self.item_path(i)): self.current_hash(self.item_path(i)) for i in records}
        inputs[self.rel(self.path('migration.json'))] = self.current_hash(self.path('migration.json'))
        changed = {rel: raw for rel, raw in outputs.items() if self.current_hash(self.resolve(rel)) != digest(raw)}
        if initialize_hash is not None and self.current_hash(self.resolve(self.entry_rel)) != initialize_hash:
            raise HandoffError('author edit during initialization')
        if not changed:
            return {'changed': False, 'paths': [], 'items': len(records), 'entry_bytes': len(outputs[self.entry_rel]), 'counts': counts, 'recovery': 'none'}
        # 未变化的生成页也是事务读取集；恢复期间作者修改它们同样必须阻断。
        inputs.update({rel: self.current_hash(self.resolve(rel)) for rel in outputs if rel not in changed})
        operations = []
        for rel, raw in changed.items():
            h = digest(raw); self.immutable(self.path('transaction-data/' + h + '.bin'), raw)
            operations.append({'path': rel, 'before': self.current_hash(self.resolve(rel)), 'after': h})
        journal = {'operations': operations, 'inputs': inputs}
        self.immutable(self.path('.pending.json'), encode(journal))
        self._finish(journal, fault)
        return {'changed': True, 'paths': list(changed), 'items': len(records), 'entry_bytes': len(outputs[self.entry_rel]), 'counts': counts, 'recovery': 'none'}

    def _finish(self, journal, fault=None):
        def guard():
            for rel, h in journal['inputs'].items():
                if self.current_hash(self.resolve(rel)) != h:
                    raise HandoffError('author input conflict during recovery')
            for op in journal['operations']:
                rel = op['path']
                allowed = rel == self.entry_rel or rel == self.rel(self.path('catalog.json')) or rel.startswith(self.base_rel + '/views/')
                if not allowed or self.current_hash(self.resolve(rel)) not in (op['before'], op['after']):
                    raise HandoffError('author output conflict during recovery')
                if self.current_hash(self.path('transaction-data/' + op['after'] + '.bin')) != op['after']:
                    raise HandoffError('transaction payload hash damaged')
        guard()  # 全量预检，发生冲突时连第一个输出也不覆盖。
        for i, op in enumerate(journal['operations']):
            guard()
            p = self.resolve(op['path'])
            if self.current_hash(p) != op['after']:
                self.atomic(p, self.path('transaction-data/' + op['after'] + '.bin').read_bytes())
            if fault: fault(i)
        guard()
        raw = encode(journal)
        self.immutable(self.path('transactions/' + digest(raw) + '.json'), raw)
        self.path('.pending.json').unlink()  # 仅删除已核验完成的自身事务，不删锁。

    def apply(self, accept_drift=(), fault=None):
        with self.lock():
            return self._apply(self._catalog(), accept_drift=accept_drift, fault=fault)

    def recover(self):
        with self.lock():
            if not self.path('.pending.json').exists():
                return {'changed': False, 'paths': [], 'recovery': 'none'}
            journal = self.read_json('.pending.json')
            self._finish(journal)
            result = self._check(); result.update(recovery='completed', changed=True, paths=[x['path'] for x in journal['operations']])
            return result

    def _check(self):
        if self.path('.pending.json').exists():
            raise HandoffError('recovery required')
        catalog = self._catalog(); records = self._records(catalog)
        for i, r in records.items():
            if i not in catalog['known'] or digest(encode(r)) != catalog['revisions'][i][-1]:
                raise HandoffError('unpublished item revision; explicit apply required')
        expected, counts = self._render(records)
        for rel, h in catalog['generated'].items():
            raw = self.resolve(rel).read_bytes()
            if digest(raw) != h or (rel in expected and raw != expected[rel]):
                raise HandoffError('generated consistency mismatch')
            if rel.startswith(self.base_rel + '/views/') and len(raw) > 8192:
                raise HandoffError('page exceeds 8192 bytes')
        if not set(expected).issubset(catalog['generated']):
            raise HandoffError('generated page missing from catalog')
        return {'items': len(records), 'counts': counts, 'entry_bytes': len(expected[self.entry_rel]), 'changed': False, 'paths': [], 'recovery': 'none'}

    def check(self):
        # 只读check不创建锁/目录；与写方并发时返回未知/失败，不修改输出。
        return self._check()

    def add_record(self, item_id, title, text):
        with self.lock():
            if item_id in self._catalog()['known'] or self.item_path(item_id).exists():
                raise HandoffError('permanent id cannot be reused')
            self.immutable(self.item_path(item_id), encode(self.record(item_id, title, text, [])))


def domain_store(root, domain):
    profile = DOMAINS[domain]
    return Store(root, profile['base'], profile['entry'], domain=domain)


def check_all(root):
    results = {domain: domain_store(root, domain).check() for domain in DOMAINS}
    return {'domains': results, 'items': sum(r['items'] for r in results.values()),
            'changed': False, 'paths': [], 'recovery': 'none'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument('--domain', choices=(*DOMAINS, 'all'), default='quality')
    group = parser.add_mutually_exclusive_group(required=True)
    for flag in ('check', 'apply', 'recover'):
        group.add_argument('--' + flag, action='store_true')
    parser.add_argument('--accept-drift-sha', action='append', default=[])
    parser.add_argument('--who', help='write actions require the existing official single-file lock owner')
    args = parser.parse_args(argv)
    try:
        if args.domain == 'all':
            if not args.check:
                raise HandoffError('all-domain entry is read-only; apply/recover one domain under its official lock')
            print(json.dumps(check_all(args.root), ensure_ascii=False)); return 0
        s = domain_store(args.root, args.domain)
        if not args.check:
            lock = s.resolve(s.entry_rel + '.editlock')
            try:
                owner = json.loads(lock.read_bytes())
            except (OSError, ValueError) as exc:
                raise HandoffError('official card lock required') from exc
            if not args.who or owner.get('released') or owner.get('who') != args.who:
                raise HandoffError('official card lock owner mismatch')
        result = s.check() if args.check else s.recover() if args.recover else s.apply(accept_drift=set(args.accept_drift_sha))
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (HandoffError, OSError, ValueError) as exc:
        print(json.dumps({'changed': False, 'error': str(exc), 'recovery': 'inspect-preserved-material'}, ensure_ascii=False)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
