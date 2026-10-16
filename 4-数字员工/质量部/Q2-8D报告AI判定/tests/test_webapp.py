"""Q2 门户页 `/quality/q2`（队列 §一 `#612` tasks 5.1）：路由前缀／mock 标注／网关接入点空壳三件。"""
from __future__ import annotations

from q2_8d_verdict import config
from q2_8d_verdict.webapp import GATEWAY_IDENTITY_HEADER, create_app, default_identity_resolver
import io
import json
import re

import pytest
from q2_8d_verdict.mock_upload import example_input

UPLOAD = config.ROUTE_PREFIX + "/mock-upload"


def demo_client(tmp_path, **overrides):
    kw = dict(mock_upload_enabled=True, mock_upload_root=tmp_path / "store",
              mock_upload_actor=lambda: "synthetic:tester", mock_upload_access=lambda action, actor: True)
    kw.update(overrides)
    return create_app(audit_path=tmp_path / "audit.jsonl", **kw).test_client()


def csrf(client):
    response = client.get(UPLOAD)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def submit_json(client, source=None):
    return client.post(UPLOAD, data=source or example_input("1"), content_type="application/json",
        headers={"X-CSRF-Token": csrf(client), "Origin": "http://localhost"})


@pytest.mark.parametrize("path", [UPLOAD, UPLOAD + "/example/1", config.ROUTE_PREFIX + "/mock-results/" + "a" * 32])
def test_new_operations_disabled_by_default(tmp_path, path):
    c = create_app(audit_path=tmp_path / "audit").test_client()
    assert c.get(path, headers={GATEWAY_IDENTITY_HEADER: "admin"}).status_code == 404


def test_explicit_enable_without_trusted_hooks_cannot_self_authorize(tmp_path):
    c = demo_client(tmp_path, mock_upload_access=None)
    assert c.get(UPLOAD, headers={GATEWAY_IDENTITY_HEADER: "admin"}).status_code == 403
    c = demo_client(tmp_path, mock_upload_actor=lambda: "real-user")
    assert c.get(UPLOAD).status_code == 403


def test_complete_file_form_redirect_report_export_and_no_store(tmp_path):
    c = demo_client(tmp_path)
    example = c.get(UPLOAD + "/example/1")
    assert example.status_code == 200 and "attachment" in example.headers["Content-Disposition"]
    response = c.post(UPLOAD, data={"csrf_token": csrf(c), "file": (io.BytesIO(example.data), "synthetic.json")},
                      headers={"Origin": "http://localhost"})
    assert response.status_code == 303 and response.mimetype == "text/html"
    page = c.get(response.location)
    assert page.status_code == 200 and "单份合成报告" in page.text
    assert "单份审计标识未接入" not in page.text
    for text in ("源时点", "未提供", "输入SHA256", "规则版本", "审计回执", "质量工程师", "待人工"):
        assert text in page.text
    export = c.get(response.location + "/export")
    assert export.status_code == 200 and "attachment" in export.headers["Content-Disposition"]
    data = export.get_json()
    assert data["payload"]["object_id"] in page.text
    assert data["receipt"]["event_sha256"] in page.text
    for r in (example, response, page, export):
        assert r.headers["Cache-Control"] == "no-store"


def test_pasted_json_and_explicit_api_share_idempotent_object(tmp_path):
    c = demo_client(tmp_path)
    first = submit_json(c)
    assert first.status_code == 201 and first.is_json
    again = c.post(UPLOAD, data={"csrf_token": csrf(c), "input_json": example_input("1").decode()},
                   headers={"Origin": "http://localhost"})
    assert again.status_code == 303 and again.location == first.headers["Location"]


def test_csrf_same_origin_and_ambiguous_inputs_rejected(tmp_path):
    c = demo_client(tmp_path)
    assert c.post(UPLOAD, json={}).status_code == 403
    token = csrf(c)
    assert c.post(UPLOAD, json={}, headers={"X-CSRF-Token": token, "Origin": "https://elsewhere"}).status_code == 403
    assert c.post(UPLOAD, json={}, headers={"X-CSRF-Token": token}).status_code == 403
    assert c.post(UPLOAD, data={"csrf_token": token, "input_json": "{}", "file": (io.BytesIO(b"{}"), "x")},
                  headers={"Origin": "http://localhost"}).status_code == 400


def test_malformed_oversize_and_asil_safe_errors(tmp_path):
    c = demo_client(tmp_path)
    assert submit_json(c, b"{").status_code == 400
    assert submit_json(c, b" " * (2 * 1024 * 1024 + 1)).status_code == 413
    data = json.loads(example_input("1"))
    data["report"]["asil_level"] = "D"
    response = submit_json(c, json.dumps(data).encode())
    assert response.status_code == 422 and response.get_json()["error"] == "asil_excluded"


def test_uploaded_markup_escaped_and_permissions_cover_view_export(tmp_path):
    allowed = {"view": True, "export": True}
    c = demo_client(tmp_path, mock_upload_access=lambda action, actor: allowed.get(action, True))
    data = json.loads(example_input("1"))
    data["report"]["report_id"] = "<script>alert('test')</script>"
    result = submit_json(c, json.dumps(data).encode())
    url = result.headers["Location"]
    page = c.get(url)
    assert "<script>" not in page.text and "&lt;script&gt;" in page.text
    allowed["view"] = False
    assert c.get(url).status_code == 403
    allowed["export"] = False
    assert c.get(url + "/export").status_code == 403


def test_storage_failure_is_503_not_empty_success(tmp_path, monkeypatch):
    from q2_8d_verdict.mock_upload import MockUploadService, MockUploadError
    def fail(*a, **k):
        raise MockUploadError("storage_unavailable")
    monkeypatch.setattr(MockUploadService, "submit", fail)
    response = submit_json(demo_client(tmp_path))
    assert response.status_code == 503
    assert response.get_json()["error"] == "storage_unavailable"


def test_paste_supports_declared_limit_and_actor_is_resolved_once_per_request(tmp_path):
    calls = []
    def actor():
        calls.append(1)
        return "synthetic:tester"
    c = demo_client(tmp_path, mock_upload_actor=actor)
    token = csrf(c)
    calls.clear()
    data = json.loads(example_input("1"))
    data["report"]["sections"]["D8"] = " " * 700_000
    response = c.post(UPLOAD, data={"csrf_token": token, "input_json": json.dumps(data)},
                      headers={"Origin": "http://localhost"})
    assert response.status_code == 303
    assert calls == [1]


def _client(**kw):
    app = create_app(audit_path="reports/test_q2_web_audit.jsonl", **kw)
    return app.test_client()


def test_ping_is_exempt_and_prefixed():
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/api/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "service": config.SERVICE_NAME}


def test_index_renders_mock_banner_and_summary_tables():
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "mock" in body
    assert "并非真实 8D 评审结论" in body
    assert config.SERVICE_NAME in body
    assert "七维得分" in body
    assert "分级分布" in body
    assert "D1" in body and "D7" in body


def test_root_without_prefix_is_404():
    client = _client()
    assert client.get("/").status_code == 404
    assert client.get("/api/ping").status_code == 404


def test_default_identity_resolver_reads_gateway_header():
    app = create_app(audit_path="reports/test_q2_web_audit.jsonl")
    with app.test_request_context("/", headers={GATEWAY_IDENTITY_HEADER: "ShaoPeiShen"}):
        assert default_identity_resolver() == "ShaoPeiShen"
    with app.test_request_context("/"):
        assert default_identity_resolver() is None


def test_identity_resolver_is_injectable_and_does_not_block_readonly_page():
    calls = []

    def _resolver():
        calls.append(1)
        return None

    client = _client(identity_resolver=_resolver)
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 200
    assert calls == [1]


def test_gate_is_noop_without_env_var(monkeypatch):
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    client = _client()
    assert client.get(f"{config.ROUTE_PREFIX}/").status_code == 200


def test_gate_activates_when_env_var_set(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "test-secret")
    client = _client()
    resp = client.get(f"{config.ROUTE_PREFIX}/")
    assert resp.status_code == 302  # 未带 cookie/token，被门禁重定向到登录页
    assert client.get(f"{config.ROUTE_PREFIX}/api/ping").status_code == 200  # 健康检查仍豁免


REAL='/quality/q2/review'

def real_client(tmp_path,service,**kw):
    args=dict(real_upload_enabled=True,real_upload_service=service,real_upload_actor=lambda:'local:test',real_upload_access=lambda action,actor:True)
    args.update(kw)
    return create_app(audit_path=tmp_path/'web-audit.jsonl',**args).test_client()

def real_token(client):
    r=client.get(REAL);assert r.status_code==200
    return re.search(r'name="csrf_token" value="([^"]+)"',r.text).group(1)

def test_real_default_closed_and_cannot_trust_identity_header(tmp_path):
    c=create_app(audit_path=tmp_path/'a').test_client()
    assert c.get(REAL).status_code==404
    c=real_client(tmp_path,object(),real_upload_actor=None)
    assert c.get(REAL,headers={'X-Zp-Identity':'admin'}).status_code==403

def test_real_multipart_complete_download_and_escape(tmp_path,monkeypatch):
    from test_document_upload import upload_fixture,wait_job
    raw,m,a,s=upload_fixture(tmp_path);c=real_client(tmp_path,s)
    token=real_token(c)
    assert c.post(REAL,data={'csrf_token':token,'file':(io.BytesIO(raw),'a.pptx')},headers={'Origin':'http://other'}).status_code==403
    r=c.post(REAL,data={'csrf_token':token,'file':(io.BytesIO(raw),'a.pptx')},headers={'Origin':'http://localhost'})
    assert r.status_code==303
    from q2_8d_verdict.document_upload import JobRef
    saved=wait_job(s,JobRef(r.location.rsplit('/',1)[1],'receiving'))
    assert saved.state=='complete',saved.error
    page=c.get(r.location)
    assert page.status_code==200 and '未专业签认' in page.text and '整改建议' in page.text and '原文依据' in page.text
    x=c.get(r.location+'/excel');assert x.status_code==200 and x.data[:2]==b'PK'
    assert 'attachment' in x.headers['Content-Disposition'] and x.headers['Cache-Control']=='no-store'
    assert c.get(r.location+'/bundle').status_code==200
    denied=real_client(tmp_path,s,real_upload_access=lambda action,actor:action!='export')
    assert denied.get(r.location+'/excel').status_code==403

def test_real_csrf_input_errors_and_failed_job_no_download(tmp_path):
    from test_document_upload import upload_fixture,wait_job
    raw,m,a,s=upload_fixture(tmp_path);c=real_client(tmp_path,s)
    assert c.post(REAL).status_code==403
    token=real_token(c)
    assert c.post(REAL,data={'csrf_token':token},headers={'Origin':'http://localhost'}).status_code==400
    assert c.post(REAL,data={'csrf_token':token,'file':(io.BytesIO(b'bad'),'a.pptx')},headers={'Origin':'http://localhost'}).status_code==422
    m.request=lambda *args:(_ for _ in ()).throw(RuntimeError('<script>denied</script>'))
    r=c.post(REAL,data={'csrf_token':token,'file':(io.BytesIO(raw),'a.pptx')},headers={'Origin':'http://localhost'})
    from q2_8d_verdict.document_upload import JobRef
    wait_job(s,JobRef(r.location.rsplit('/',1)[1],'receiving'))
    page=c.get(r.location);assert '&lt;script&gt;denied' in page.text and '<script>denied' not in page.text
    assert c.get(r.location+'/excel').status_code==409

def test_real_file_larger_than_parser_chunk_within_20mib(tmp_path):
    import zipfile,hashlib
    from test_document_upload import upload_fixture,wait_job
    from q2_8d_verdict.document_evidence import DocumentScope
    from q2_8d_verdict.document_upload import DocumentUploadService,JobRef
    raw,m,a,s=upload_fixture(tmp_path)
    blob=io.BytesIO(raw)
    with zipfile.ZipFile(blob,'a') as z:z.writestr('synthetic-padding.bin',b'x'*1024*1024)
    raw=blob.getvalue();scope=DocumentScope('SYNTHETIC-A','T1','B',hashlib.sha256(raw).hexdigest())
    s=DocumentUploadService(tmp_path/'large-store',a,m,scope);c=real_client(tmp_path,s)
    r=c.post(REAL,data={'csrf_token':real_token(c),'file':(io.BytesIO(raw),'large.pptx')},headers={'Origin':'http://localhost'})
    assert r.status_code==303
    assert wait_job(s,JobRef(r.location.rsplit('/',1)[1],'receiving')).state=='complete'
