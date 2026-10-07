from pathlib import Path
from html.parser import HTMLParser
import json
import shutil
import subprocess
ROOT = Path(__file__).resolve().parent.parent
class Elements(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []; self.links = []; self.buttons = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'id' in values: self.ids.append(values['id'])
        if tag in ('a', 'iframe'): self.links.append(values.get('href', values.get('src', '')))
        if tag == 'button': self.buttons.append(values)
def test_portal_keeps_business_entry_and_unique_ids():
    html = (ROOT / 'AI运营指挥中心-框架原型-v0.1.html').read_text(encoding='utf-8-sig')
    parser = Elements(); parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))
    for view in ('overview','apps','tasks','review','system','procurement','quality','finance','sales','operations','engineering'):
        assert 'view-' + view in parser.ids
    for url in ('http://192.168.100.51:8091/', 'http://192.168.100.51:8093/', 'http://192.168.100.51:8094/'):
        assert url in parser.links
    assert 'data/sales_dashboard_data.json' in html
    assert 'PORTAL_UI_MODEL_BEGIN' in html
def test_registry_preserves_old_and_known_entries_without_planned_actions():
    apps = json.loads((ROOT/'ui/apps.json').read_text(encoding='utf-8'))
    assert len({a['id'] for a in apps}) == len(apps)
    urls = {a['href'] for a in apps}
    for url in ('http://192.168.100.51:8091/', 'http://192.168.100.51:8091/cases', 'http://192.168.100.51:8093/', 'http://192.168.100.51:8094/', 'http://192.168.100.51:8096/procurement/sc2/', 'http://192.168.100.51:8097/', 'http://192.168.100.51:8098/', '#sales'):
        assert url in urls
    assert all(a['href'] is None for a in apps if a['stage']=='规划')
def test_unconnected_pages_do_not_offer_business_submission():
    html = (ROOT/'AI运营指挥中心-框架原型-v0.1.html').read_text(encoding='utf-8-sig')
    for view in ('tasks','review'):
        start = html.index('id="view-'+view+'"')
        section = html[start:html.index('</section>',start)]
        assert '尚未接入统一接口' in section
        assert '<form' not in section and 'type="submit"' not in section
    assert 'PORTAL_UI_THEME_BEGIN' in html
def test_single_file_build_is_repeatable_and_missing_marker_fails_closed(tmp_path):
    shutil.copytree(ROOT/'ui',tmp_path/'ui')
    (tmp_path/'scripts').mkdir()
    shutil.copy(ROOT/'scripts/inline-portal-ui.mjs',tmp_path/'scripts/inline-portal-ui.mjs')
    page=tmp_path/'AI运营指挥中心-框架原型-v0.1.html'
    shutil.copy(ROOT/page.name,page)
    command=['node',str(tmp_path/'scripts/inline-portal-ui.mjs')]
    first=subprocess.run(command,capture_output=True,text=True)
    assert first.returncode==0,first.stderr
    built=page.read_bytes()
    assert subprocess.run(command,capture_output=True).returncode==0
    assert page.read_bytes()==built
    bad=built.replace(b'<!-- PORTAL_UI_MODEL_BEGIN -->',b'<!-- INVALID -->',1)
    page.write_bytes(bad)
    assert subprocess.run(command,capture_output=True).returncode!=0
    assert page.read_bytes()==bad
def test_inline_script_has_no_business_write_or_external_runtime_source():
    html=(ROOT/'AI运营指挥中心-框架原型-v0.1.html').read_text(encoding='utf-8')
    assert '<script src=' not in html
    assert '<link rel="stylesheet"' not in html
    assert html.count("fetch('data/sales_dashboard_data.json'")==1
    assert "method:'POST'" not in html and "method:'PUT'" not in html and "method:'DELETE'" not in html
