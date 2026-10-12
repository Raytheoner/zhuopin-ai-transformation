"""Synthetic API responses only; catch failures that used to look successful."""
import importlib.util
from pathlib import Path

import dotenv
import pytest


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.payload = payload if payload is not None else {"code": 200, "result": {"records": []}}
        self.text = "response-body-canary-do-not-log"

    def json(self):
        return self.payload


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    path = Path(__file__).resolve().parents[1] / "xiaoshouyi_data_sync_fixed.py"
    spec = importlib.util.spec_from_file_location("sales_source_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.requests, "get", lambda *a, **k: pytest.fail("unmocked API request"))
    return module


def client(source):
    return source.XiaoshouyiAPI("fixture.invalid", "synthetic-token")


def test_401_is_failure_not_empty_page(source, monkeypatch, caplog):
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(401))
    with pytest.raises(Exception, match="401"):
        client(source)._query_sql("select id from lead")
    assert "response-body-canary" not in caplog.text


def test_later_page_failure_cannot_return_partial_success(source, monkeypatch):
    def request(url, *, params, **kwargs):
        if "limit 0," in params["q"]:
            return Response(payload={"code": 200, "result": {"records": [{"id": 1}, {"id": 2}]}})
        return Response(503)
    monkeypatch.setattr(source.requests, "get", request)
    with pytest.raises(Exception):
        client(source)._query_all("select id from lead", page_size=2)


@pytest.mark.parametrize("payload", [
    {"code": 200, "result": {}},
    {"code": 200, "result": {"records": "not-a-list"}},
    {"code": 200, "result": {"records": [None]}},
    {"code": 500, "msg": "body-canary"},
])
def test_invalid_response_cannot_be_successful_empty_page(source, monkeypatch, payload):
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(payload=payload))
    with pytest.raises(Exception):
        client(source)._query_sql("select id from lead")


def test_duplicate_ids_stop_pagination(source, monkeypatch):
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(
        payload={"code": 200, "result": {"records": [{"id": 1}, {"id": 1}]}}))
    with pytest.raises(Exception, match="duplicate"):
        client(source)._query_all("select id from lead", max_records=3)


def test_missing_id_stops_pagination(source, monkeypatch):
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(
        payload={"code": 200, "result": {"records": [{"phone": "synthetic"}]}}))
    with pytest.raises(Exception, match="id"):
        client(source)._query_all("select id from lead", max_records=3)


def test_record_limit_cannot_report_truncated_success(source, monkeypatch):
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(
        payload={"code": 200, "result": {"records": [{"id": 1}, {"id": 2}]}}))
    with pytest.raises(Exception):
        client(source)._query_all("select id from lead", max_records=1)


def test_main_auth_failure_returns_nonzero_and_preserves_snapshot(source, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("XIAOSHOUYI_API_DOMAIN", "fixture.invalid")
    monkeypatch.setenv("XIAOSHOUYI_ACCESS_TOKEN", "synthetic-token")
    monkeypatch.setattr(source.requests, "get", lambda *a, **k: Response(401))
    directory = tmp_path / "crm_data"
    directory.mkdir()
    old = directory / "dashboard_data.json"
    old.write_bytes(b'{"sync_time":"2026-06-25T18:08:53"}')
    result = source.main()
    assert result != 0 and result is not None
    assert old.read_bytes() == b'{"sync_time":"2026-06-25T18:08:53"}'


def test_import_does_not_load_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: calls.append(True))
    path = Path(__file__).resolve().parents[1] / "xiaoshouyi_data_sync_fixed.py"
    spec = importlib.util.spec_from_file_location("sales_import_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert calls == []


def test_short_page_is_not_assumed_to_be_the_end(source, monkeypatch):
    requests_seen = []
    pages = iter([[{'id': 1}, {'id': 2}], [{'id': 3}], [{'id': 4}], []])
    def query(sql):
        requests_seen.append(sql)
        return next(pages)
    api = client(source)
    monkeypatch.setattr(api, '_query_sql', query)
    assert [row['id'] for row in api._query_all('select id from lead', page_size=500)] == [1, 2, 3, 4]
    assert requests_seen[-1] == 'select id from lead order by id asc limit 4, 500'
