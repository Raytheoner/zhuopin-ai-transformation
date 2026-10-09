"""Execute the real snapshot boot JavaScript against constructed input."""
import json
import re
import subprocess

import pytest
from sc8 import webapp


def run_boot(snapshot=None, *, status=200, previous=None, timeout=False):
    page = webapp._shell_page()
    script = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
    # Boot is deliberately independent from the existing card renderer.
    boot = script.split("const $=")[0]
    harness = r'''
const vm=require('node:vm');
let els={},calls=[];
function element(id){return els[id]||(els[id]={textContent:'',innerHTML:'',dataset:{}});}
const context={document:{getElementById:element},
 renderKpis(){},renderFbtns(){},render(){element('cards').innerHTML='original cards';},
 setTimeout(callback){if(TIMEOUT)queueMicrotask(callback);return 1;},clearTimeout(){},AbortController,
 fetch(url,opts){calls.push([url,opts&&opts.method||'GET']);
   if(TIMEOUT)return new Promise(()=>{});
   return Promise.resolve({ok:STATUS===200,status:STATUS,json(){return Promise.resolve(SNAP);}});}};
vm.createContext(context);vm.runInContext(BOOT,context);if(PREVIOUS)context.applySnap(PREVIOUS);
(async()=>{await context.loadSnap();await new Promise(setImmediate);
 console.log(JSON.stringify({els,calls,data:context.DATA,meta:context.META}));})();
'''
    code = ("const STATUS=" + str(status) + ";const SNAP=" + json.dumps(snapshot) +
            ";const PREVIOUS=" + json.dumps(previous) + ";const TIMEOUT=" + json.dumps(timeout) +
            ";const BOOT=" + json.dumps(boot) + ";" + harness)
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1000:]
    return json.loads(result.stdout)


def snapshot(**extra):
    return {"ok": True, "generated_at": "2026-10-08T18:00:00+08:00", "today": "2026-10-08",
            "param_version": "sc8-params-v1+rule1", "rows": [], **extra}


def test_snapshot_time_is_not_presented_as_source_time():
    result = run_boot(snapshot())
    text = result["els"]["ts"]["textContent"]
    assert "快照生成时间" in text
    assert "2026-10-08T18:00:00+08:00" in text
    assert "源更新时间：未提供" in text
    assert "sc8-params-v1+rule1" in text


def test_empty_snapshot_is_not_current_success():
    result = run_boot({"ok": False, "rows": [], "note": "尚未刷新"})
    assert "尚无快照" in result["els"]["ts"]["textContent"]
    assert "尚无快照" in result["els"]["cards"]["innerHTML"]


@pytest.mark.parametrize("status,label", [(403, "权限不足"), (503, "读取失败")])
def test_http_failure_is_distinct_from_empty_data(status, label):
    result = run_boot(snapshot(), status=status)
    assert label in result["els"]["ts"]["textContent"]
    assert "当次结果不可用" in result["els"]["ts"]["textContent"]
    assert result["data"] == []


def test_snapshot_note_and_version_are_text_and_no_business_write():
    result = run_boot(snapshot(param_version="<script>bad</script>", note="资料不足"))
    assert "<script>bad</script>" in result["els"]["ts"]["textContent"]
    assert result["calls"] == [["/api/baoguan", "GET"]]
    page = webapp._shell_page()
    assert "DOS：未提供" in page
    assert "D4/颜色专业签认待确认" in page


def test_materials_and_case_pages_keep_existing_navigation():
    page = webapp._materials_page()
    assert "同源" in page
    for path in ('/materials', '/cases', '/cases/review'):
        assert f'href="{path}"' in page
    assert "品牌" in page and "责任人" in page


def test_failure_retains_prior_snapshot_but_marks_it_not_current():
    previous = snapshot(rows=[{"id": "mock-item", "risk": "red"}])
    result = run_boot(status=503, previous=previous)
    assert result["data"] == previous["rows"]
    assert "非当次结果" in result["els"]["ts"]["textContent"]
    assert "2026-10-08T18:00:00+08:00" in result["els"]["ts"]["textContent"]


def test_timeout_reaches_unavailable_state():
    result = run_boot(timeout=True)
    assert "当次结果不可用" in result["els"]["ts"]["textContent"]
    assert "超时" in result["els"]["ts"]["textContent"]


def test_material_snapshot_labels_generation_and_permission_failure():
    page = webapp._materials_page()
    script = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
    functions = script[script.index('function applySnap(s){'):script.index('function exportExcel(){')]
    code = ("const vm=require('node:vm');let els={};const context={SNAP:{},ROWS:[],META:{},MONTHS:[],state:{},"
            "document:{getElementById(id){return els[id]||(els[id]={textContent:'',innerHTML:''});}},"
            "render(){},setTimeout(){return 1;},clearTimeout(){},fetch(){return Promise.resolve({ok:false,status:403});}};"
            "context.$=context.document.getElementById;vm.createContext(context);vm.runInContext(" + json.dumps(functions) + ",context);"
            "context.applySnap({ok:true,generated_at:'mock-time',today:'2026-10-08',rows:[],meta:{}});"
            "const first=els.ts.textContent;(async()=>{await context.loadSnap();await new Promise(setImmediate);"
            "console.log(JSON.stringify({first,last:els.ts.textContent}));})();")
    result = subprocess.run(['node','-e',code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1000:]
    text = json.loads(result.stdout)
    assert '快照生成时间' in text['first']
    assert '源更新时间：未提供' in text['first']
    assert '权限不足' in text['last']


def test_legend_uses_master_interface_and_labels_its_separate_provenance():
    page = webapp._shell_page()
    assert '图例来源：当前服务配置' in page
    assert '结果规则版本以快照来源栏为准' in page

def test_rule2_legend_hides_live_parameter_version(monkeypatch):
    calls = []
    def legend(params=None, *, include_version=True):
        calls.append(include_version)
        return '<p>legend sentinel</p>'
    monkeypatch.setattr(webapp, 'render_legend', legend)
    page = webapp._shell_page()
    assert calls == [False]
    assert '图例来源：当前服务配置' in page
    assert '结果规则版本以快照来源栏为准' in page
