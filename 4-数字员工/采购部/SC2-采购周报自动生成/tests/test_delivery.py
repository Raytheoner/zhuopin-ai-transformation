"""交付层单测（spec: sc2-report-delivery）。对应 tasks 7.1-7.6。"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

from sc2 import config, notify, outbox
from sc2.review import PublishState, ReviewStore, status_of
from sc2.webapp import GATEWAY_IDENTITY_HEADER, create_app, default_identity_resolver

BASE = date(2026, 8, 19)
PREFIX = "/procurement/sc2"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    yield


@pytest.fixture()
def client():
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    return app.test_client()


# ── 7.1 路由前缀 ────────────────────────────────────────────────────────────

def test_所有路由位于统一门户前缀之下():
    """design D2/D9：自首版即为目标态，网关落地后只改映射、不改场景代码。"""
    app = create_app(base_date=BASE, mode="mock")
    rules = [str(r) for r in app.url_map.iter_rules()
             if r.endpoint != "static" and not r.endpoint.startswith("_zp_gate")]
    assert rules
    for rule in rules:
        assert rule.startswith(PREFIX), f"路由 {rule} 未落在 {PREFIX} 前缀下"


def test_周报页可访问(client):
    r = client.get(f"{PREFIX}/")
    assert r.status_code == 200
    assert "采购周报" in r.get_data(as_text=True)


def test_ping在前缀下且可用(client):
    r = client.get(f"{PREFIX}/api/ping")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_页内链接与静态资源不使用根路径绝对引用(client):
    """spec 场景：页内引用须基于前缀，否则网关落地时会全部指错。"""
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    for href in re.findall(r'(?:href|action|src)="([^"]+)"', html):
        if href.startswith("/"):
            assert href.startswith(PREFIX), f"根路径绝对引用：{href}"


# ── 7.2 门禁与访问日志 ──────────────────────────────────────────────────────

def test_设置口令后无口令请求被拒且不返回业务数据(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().get(f"{PREFIX}/")
    assert r.status_code in (302, 401)
    body = r.get_data(as_text=True)
    assert "下单行数" not in body, "未通过门禁却泄露了业务数据"


def test_确认接口在门禁下也不得被未鉴权调用(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().post(f"{PREFIX}/api/confirm", json={"confirmed_by": "x"})
    assert r.status_code == 401


def test_访问被记录(client, tmp_path):
    client.get(f"{PREFIX}/")
    assert config.access_log_path().exists()


# ── 7.3 网关鉴权接入点 ──────────────────────────────────────────────────────

def test_默认接入点为空壳不阻断():
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context("/"):
        assert default_identity_resolver() is None


def test_替换接入点即可改变身份来源而不动业务路由():
    """网关落地后只换这一个实现，路由与页面代码不动。"""
    app = create_app(base_date=BASE, mode="mock",
                     identity_resolver=lambda: "gw:姚祖怡")
    app.config["TESTING"] = True
    c = app.test_client()
    c.post(f"{PREFIX}/api/confirm", json={})       # 不传 confirmed_by，走网关身份
    store = ReviewStore()
    period = c.get(f"{PREFIX}/api/report").get_json()["period"]
    entry = store.get(period)
    assert entry.confirmed_by == "gw:姚祖怡"


def test_网关身份头常量已定义():
    """接入点必须存在（过渡期可空壳，但不得缺席）。"""
    assert GATEWAY_IDENTITY_HEADER


# ── 7.4 确认发布按钮 ────────────────────────────────────────────────────────

def test_周报页含确认发布按钮(client):
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    assert "确认发布" in html


def test_确认接口把该期转为已确认(client):
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    assert status_of(ReviewStore(), period) == PublishState.PENDING
    r = client.post(f"{PREFIX}/api/confirm", json={"confirmed_by": "姚祖怡"})
    assert r.status_code == 200
    assert status_of(ReviewStore(), period) == PublishState.CONFIRMED


def test_确认人缺失且无网关身份时拒绝(client):
    r = client.post(f"{PREFIX}/api/confirm", json={})
    assert r.status_code == 400


def test_波动阈值与签认来源在页面上写明(client):
    """🔴 阈值 ±400% 已由姚祖怡 2026-08-21 判例回件显式签认。

    IATF：签认必须可追溯到人与时点——只翻一个"已确认"的布尔位而不写是谁签的，
    日后说不清这个数是哪来的。同时他限定了用途「仅作工作量参考」，页面必须写明
    它**不是异常告警、不触发任何自动推送**。
    """
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    assert "400%" in html
    assert "姚祖怡" in html and "2026-08-21" in html
    assert "不触发任何自动推送" in html


# ── 7.5 推送范围 ────────────────────────────────────────────────────────────

def test_推送对象仅采购部群与采购部AI专员():
    assert set(notify.RECIPIENTS) == {"采购部群", "姚祖怡"}


def test_推送范围不含管理层():
    joined = "".join(notify.RECIPIENTS)
    for banned in ("管理层", "总经理", "CEO", "VP"):
        assert banned not in joined


def test_推送不再要求先确认发布(client):
    """🔴 §四 #89 (a)：取消确认发布前置（Shao Peishen 2026-08-22 拍板）。

    姚祖怡要的是「周五晚 8 点自动给出本周的……同步推到群里」，原来那道人工确认门
    与之正面冲突。这里正是原 `test_未确认时推送被拒` 的**反向断言**：**未确认也发得出去**。
    """
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    assert status_of(ReviewStore(), period) == PublishState.PENDING
    assert notify.push(period, text="正文", store=ReviewStore()) is True


def test_推送一次且重复调用不再发(client):
    """幂等**没有**随确认门一并取消——它防的不是签认，是同一期发两遍。

    ⚠️ 取消前置后幂等比过去更要紧：过去还有人工确认这一步天然限流，
    现在到点即自动发，重跑/重启若不幂等就会连发。
    """
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    store = ReviewStore()
    assert notify.push(period, text="正文", store=store) is True
    assert notify.push(period, text="正文", store=store) is False
    assert outbox.pending() == 2, "一期写两条（群 + 私信），且只写一次"


def test_推送走aibot_outbox而非webhook(client):
    """🔴 队列 #282：不得新起 webhook，一律走智能机器人 chatid 通道。

    理由不是洁癖——**webhook 单向，群成员的回复进不到任何地方**，而姚祖怡恰恰是
    会在群里回话的那一位。以「推送层源码里不出现 webhook」反证通道没有走回头路。
    """
    import inspect

    src = inspect.getsource(notify)
    assert "webhook" not in src.lower().replace("outbox", "")

    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    notify.push(period, text="正文", store=ReviewStore())
    recs = [json.loads(l) for l in
            outbox.outbox_path().read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [r["channel"] for r in recs] == ["aibot_group_chatid", "aibot_direct"]
    assert recs[0]["department"] == "采购部"
    assert recs[1]["to_userid"] == "YaoZuYi"


def test_outbox不写死chatid只写部门名(client):
    """chatid 的权威映射在 aibot 侧那张 yaml 里；在这里抄一份就立刻有了第二份真相。"""
    import inspect

    from sc2 import outbox as ob

    assert "wrvDL_" not in inspect.getsource(ob), "不得把 chatid 抄进场景代码"


def test_部门键拼错当场上抛而不是静默跳过(client):
    """🔴 反直觉坑：中继侧「部门不在映射表」是 **fail-closed 静默跳过**——
    不报错、日志一切正常、消息就是没发出去（同 `PMC部` 那次）。
    故在入队这一侧就把它变成一次响亮的失败。"""
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    with pytest.raises(outbox.UnknownDepartmentError):
        outbox.enqueue(period=period, text="正文", department="PMC部")


def test_积压条数可见(client):
    """`#82` 那个形态的防线：机制天天在跑、一条都没真发出去，而没人察觉。"""
    assert outbox.pending() == 0
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    notify.push(period, text="正文", store=ReviewStore())
    assert outbox.pending() == 2


def test_扩大推送范围须显式变更而非运行时推断(monkeypatch):
    """spec：MUST NOT 由配置默认值或运行时推断实现。"""
    monkeypatch.setenv("SC2_EXTRA_RECIPIENTS", "管理层")
    import importlib
    importlib.reload(notify)
    assert set(notify.RECIPIENTS) == {"采购部群", "姚祖怡"}
    importlib.reload(notify)


# ── 7.6 服务入口路径引导 ────────────────────────────────────────────────────

def test_服务入口顶部含worktree路径引导():
    """队列 #300：入口脚本不得依赖全局 editable 指针指向谁。"""
    entry = config.SCENE_ROOT / "run_sc2.py"
    head = entry.read_text(encoding="utf-8")[:2000]
    assert "5-平台底座" in head and "sys.path.insert" in head


def test_端口默认为过渡期豁免端口():
    assert config.DEFAULT_PORT == 8096


def test_生成物均落reports目录(client, tmp_path):
    client.get(f"{PREFIX}/")
    client.post(f"{PREFIX}/api/confirm", json={"confirmed_by": "姚祖怡"})
    produced = list(tmp_path.iterdir())
    assert produced
    for p in produced:
        assert p.parent == tmp_path


# —— 页面表单确认路径（过渡期无网关身份，页面按钮走的就是这一路）——


def test_页面表单确认可完成确认发布(client):
    """🔴 复现 2026-08-18 部署前发现的缺陷：页面「确认发布」按钮提交的是表单、
    不是 JSON，而原实现只认 JSON body 与网关身份 ⇒ 过渡期必然 400。
    ⚠️ 2026-08-25 取消推送前置后，这一路记录的是**事后复核签认**、不再是发布闸门，
    但它仍是页面上唯一的人工动作，必须真能走通。"""
    r = client.post(f"{PREFIX}/api/confirm", data={"confirmed_by": "姚祖怡"})
    assert r.status_code == 200
    assert "已由 姚祖怡 复核签认" in r.get_data(as_text=True)


def test_页面表单未填确认人不得匿名放行(client):
    """没有主语的确认在 IATF 审核时等于没有确认——表单路径同样不得放行。"""
    r = client.post(f"{PREFIX}/api/confirm", data={})
    assert r.status_code == 400
    assert "请先填写确认人姓名" in r.get_data(as_text=True)


def test_健康检查端点在门禁下仍可达(monkeypatch):
    """🔴 复现 2026-08-18 部署前发现的缺陷：门禁缺省豁免是裸 `/api/ping`，
    而本场景 ping 在 `/procurement/sc2/api/ping` 之下 ⇒ 不显式传豁免路径就会被
    302 到登录页，部署脚本的健康检查与此后的存活探测会一律误判服务不健康。"""
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().get(f"{PREFIX}/api/ping")
    assert r.status_code == 200, "健康检查端点被门禁挡下"
    assert r.get_json()["ok"] is True



def test_服务端缺省不截断行级状态取数():
    """🔴 复现 2026-08-18 首次部署实测：窗口内料号 830 个，而 RealFeed 缺省上限
    200 ⇒ 630 个料号拿不到行级状态、按「状态未知」计入在途，在途类指标偏高。
    截断确实会写进周报取数说明（No silent caps），但那只是「诚实地报告一个次优数」，
    而页面上那些数正是要请姚祖怡判例批改的对象。故服务入口缺省 0（不限），
    慢的代价由 D21 承担：页面读快照，全量重算走独立的 POST /api/refresh。"""
    import run_sc2
    args = run_sc2.build_parser().parse_args(["serve"])
    assert args.max_status_materials == 0


# ── 周五 20:00 自动生成并推群（§四 #89）────────────────────────────────────

def test_autopush缺省真实模式():
    """🔴 唯一调用方是 `.51` 上的计划任务；缺省 mock 等于每周往群里发一份假数据。

    与 serve/report 缺省 mock 刻意不同——那两个是人手工跑的，跑错了当场就看见；
    这条没有人在看，缺省值错了要到姚祖怡在群里看见假数字才会发现。
    """
    import run_sc2

    assert run_sc2.build_parser().parse_args(["autopush"]).mode == "real"


def test_autopush缺省不截断行级状态取数():
    """与 serve 同口径：截断会让在途类指标偏高，而那正是要推给他看的数。"""
    import run_sc2

    assert run_sc2.build_parser().parse_args(["autopush"]).max_status_materials == 0


def test_autopush端到端生成并入outbox(monkeypatch, tmp_path):
    """mock 模式跑通全链：取数 → 落快照 → 写 outbox。"""
    import run_sc2

    assert run_sc2.main(["autopush", "--mode", "mock", "--base", "2026-08-19"]) == 0
    snapshots = list(tmp_path.glob("sc2_weekly_*.json"))
    assert snapshots, "未落快照，页面上就看不到本期"
    assert outbox.pending() == 2


def test_autopush重复跑不重复推送(monkeypatch):
    """计划任务重试、手工补跑都可能让它跑第二遍——不得连发两份。"""
    import run_sc2

    run_sc2.main(["autopush", "--mode", "mock", "--base", "2026-08-19"])
    run_sc2.main(["autopush", "--mode", "mock", "--base", "2026-08-19"])
    assert outbox.pending() == 2, "同一期被推送了两次"


def test_autopush的no_push只生成不推送(tmp_path):
    """首次上线演练用：先确认生成的东西对，再放开推送。"""
    import run_sc2

    assert run_sc2.main(
        ["autopush", "--mode", "mock", "--base", "2026-08-19", "--no-push"]) == 0
    assert list(tmp_path.glob("sc2_weekly_*.json"))
    assert outbox.pending() == 0


def test_周五基准日会带上本周窗口未走完的声明():
    """🔴 O-7：周五跑时本周只过了 5/7 天，而上周与上月同期都是完整 7 天
    ⇒「量」类指标的环比会系统性偏低。**那不是业务波动**。

    他要的就是「周五晚 8 点给出本周的」，所以这个偏差是设计上必然存在的；
    唯一的补救是**每期都把话说在明处**。这条断言防的是有人日后嫌它难看而删掉。
    """
    from sc2.report import build_report, render_text
    from sc2.sources import MockFeed
    from sc2.windows import build_windows

    friday = date(2026, 8, 21)
    assert friday.weekday() == 4, "基准日必须真的是周五，否则这条测试什么也没测"
    ws = build_windows(friday)
    text = render_text(build_report(MockFeed().fetch(ws), ws))
    assert "本周窗口尚未走完" in text
    assert "5/7 天" in text


def test_上限透传到取数层(monkeypatch):
    """create_app/CLI 传下来的上限必须真落到 RealFeed，而不是被中间层吞掉。"""
    from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector

    monkeypatch.setattr(ZpConnector, "from_env",
                        classmethod(lambda cls, **kw: object()))
    from sc2.sources import build_feed

    assert build_feed("real", 0).max_status_materials == 0      # 0 = 不限
    assert build_feed("real", 7).max_status_materials == 7
    assert build_feed("real").max_status_materials == 200       # 缺省仍是 RealFeed 的 200
