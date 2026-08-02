import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

from aibot_service.connection import build_connector, BOTID_KEY, SECRET_KEY
from aibot_service.constants import PAUL_USERID
from aibot_service.queue_lock_pending import read_deferred_appends

from fakes import fake_client_factory

# 真实编辑锁工具源文件——用于队列 #168 的真实子进程集成测试（不用 fake，
# 因为要验证的正是"真实持锁期间机器人确实不会写盘"这件事本身）。
_EDIT_LOCK_TOOL_SOURCE = (
    Path(__file__).resolve().parents[3] / "0-学习与工具" / "工具-共享文档编辑锁.py"
)

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 既有任务 | CC | p | e | 待领 | — | 07-09 |
"""


def _secrets(bot_id="BOT1", secret="SECRET1", **extra):
    return EnvSecretsProvider(override={BOTID_KEY: bot_id, SECRET_KEY: secret, **extra})


def test_missing_credentials_raise_keyerror(tmp_path):
    secrets = EnvSecretsProvider(override={})
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    with pytest.raises(KeyError):
        build_connector(
            secrets=secrets,
            audit=audit,
            external_docs_root=tmp_path / "7-外部文档",
            queue_path=tmp_path / "queue.md",
            client_factory=fake_client_factory({}),
        )


def test_build_connector_wires_credentials_into_client(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    connector = build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )

    assert connector is not None
    assert store["client"].bot_id == "BOT1"
    assert store["client"].secret == "SECRET1"
    # design.md D2/D3 应用层保守重连预算
    assert store["client"].options["max_reconnect_attempts"] == 6
    assert store["client"].options["reconnect_interval"] == 2000


def test_connection_lifecycle_events_are_audited(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    client.handlers["connected"][0]()
    client.handlers["authenticated"][0]()
    client.handlers["disconnected"][0]("network glitch")
    client.handlers["reconnecting"][0](1)
    client.handlers["error"][0](RuntimeError("boom"))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == [
        "connection_established",
        "authenticated",
        "disconnected",
        "reconnecting",
        "connection_error",
    ]


def test_unrecoverable_error_triggers_fatal_disconnect_callback(tmp_path):
    """07-16 P0 事故根因：SDK 重连预算耗尽后只报 on_error，不主动退出进程，
    `_run_forever` 的 `await asyncio.Event().wait()` 于是永久挂起（僵尸存活，
    外层 start-aibot-service-dev.ps1 的三级退避重启永远等不到进程退出）。
    修复：`on_error` 识别 SDK "Max reconnect attempts exceeded" 信号，调用
    `on_fatal_disconnect` 回调，交由调用方主动退出进程。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    fatal_calls: list = []

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
        on_fatal_disconnect=lambda: fatal_calls.append(True),
    )
    client = store["client"]

    client.handlers["error"][0](RuntimeError("Max reconnect attempts exceeded"))

    assert fatal_calls == [True]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["connection_error", "fatal_disconnect_detected"]


def test_transient_error_does_not_trigger_fatal_disconnect_callback(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    fatal_calls: list = []

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
        on_fatal_disconnect=lambda: fatal_calls.append(True),
    )
    client = store["client"]

    client.handlers["error"][0](RuntimeError("[WinError 64] 指定的网络名不再可用。"))

    assert fatal_calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["connection_error"]


def test_fatal_disconnect_without_callback_is_a_noop(tmp_path):
    """`on_fatal_disconnect` 未传（如既有调用方未升级）时不应报错。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    client.handlers["error"][0](RuntimeError("Max reconnect attempts exceeded"))


def test_on_message_dispatches_to_archive_and_appends_queue(tmp_path):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "YaoZuYi"},  # 姚祖怡，真实 userid（2026-07-13 联调确认）
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "已收到，稍后回复"

    new_queue = (tmp_path / "queue.md").read_text(encoding="utf-8")
    assert "采购专线" in new_queue


def test_on_message_also_forwards_to_paul(tmp_path):
    """Paul 2026-07-13 拍板：进件除归档外一律同步转发给 Paul。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "chattype": "single",
            "from": {"userid": "YaoZuYi"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    forwarded = [m for m in client.sent_messages if m[0] == PAUL_USERID]
    assert len(forwarded) == 1
    assert "发件人：YaoZuYi" in forwarded[0][1]["markdown"]["content"]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "inbound_forwarded_to_paul" in actions


def test_on_message_forward_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("转发模拟失败")

    monkeypatch.setattr(connection_mod, "forward_inbound_to_paul", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出，也不影响归档已成功
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "forward_dispatch_failed" in actions
    assert "archived" in actions


def test_on_message_notifies_department_group_when_configured(tmp_path, monkeypatch):
    """Paul 2026-07-12 拍板/2026-07-15 落地：归档成功后回部门群 webhook 发一条通报。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    group_mapping_path = tmp_path / "group_mapping.yaml"
    group_mapping_path.write_text("采购部: WECOM_WEBHOOK_URL_PROCUREMENT\n", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    build_connector(
        secrets=_secrets(WECOM_WEBHOOK_URL_PROCUREMENT="https://example/webhook?key=P"),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        group_mapping_path=group_mapping_path,
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "YaoZuYi"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    assert len(calls) == 1
    assert calls[0][0] == "https://example/webhook?key=P"
    assert "已归档" in calls[0][1]
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notified" in actions


def test_on_message_skips_group_notify_when_unconfigured_by_default(tmp_path, monkeypatch):
    """默认 yaml 不含销售部——不应误发。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    calls = []
    monkeypatch.setattr(
        "aibot_service.group_notify.wecom.send_markdown",
        lambda url, content: calls.append((url, content)),
    )

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "Hongqin.Wang"},
            "text": {"content": "已收到，稍后回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    assert calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_skipped" in actions
    assert "group_notified" not in actions


def test_on_message_group_notify_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    group_mapping_path = tmp_path / "group_mapping.yaml"
    group_mapping_path.write_text("采购部: WECOM_WEBHOOK_URL_PROCUREMENT\n", encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(WECOM_WEBHOOK_URL_PROCUREMENT="https://example/webhook?key=P"),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        group_mapping_path=group_mapping_path,
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("通报模拟失败")

    monkeypatch.setattr(connection_mod, "notify_department_group", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出，也不影响归档已成功
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "采购部").glob("*.md"))
    assert len(archived) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "group_notify_dispatch_failed" in actions
    assert "archived" in actions


def test_on_message_rejects_non_whitelisted_sender_with_polite_reply(tmp_path):
    """Paul 2026-07-16 口头需求（队列 #35）：白名单外发送人只收礼貌回复，
    不落档/不转发/不占用队列行/不发群通报。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "random_colleague"},
            "text": {"content": "问一下别的项目的事"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    # 没有任何归档产物
    assert not (tmp_path / "7-外部文档").exists() or not any(
        (tmp_path / "7-外部文档").rglob("*.md")
    )
    # 队列没被追加
    assert (tmp_path / "queue.md").read_text(encoding="utf-8") == QUEUE_TEXT
    # 没有转发给 Paul、没有正常发送
    assert not any(m[0] == PAUL_USERID for m in client.sent_messages)
    # 唯一一条发出的消息是回给发送人本人的礼貌回复
    assert len(client.sent_messages) == 1
    assert client.sent_messages[0][0] == "random_colleague"

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["whitelist_rejected"]
    assert "archived" not in actions
    assert "inbound_forwarded_to_paul" not in actions
    assert "group_notified" not in actions


def test_on_message_routes_it_sender_to_it_department(tmp_path):
    """陈承（userid=2023458，IT）在白名单里；2026-07-22（队列 #70）起
    `department_mapping.yaml` 已补入陈承→IT 映射，不再落"待分拣"——
    直接归档进 `7-外部文档/IT/`（三路径其余部分不变）。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "2023458"},
            "text": {"content": "IT 侧的回复"},
        }
    }
    asyncio.run(client.handlers["message"][0](frame))

    archived = list((tmp_path / "7-外部文档" / "IT").glob("*.md"))
    assert len(archived) == 1
    assert list((tmp_path / "7-外部文档" / "待分拣").glob("*.md")) == []

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "whitelist_rejected" not in actions
    assert "mapping_unmatched" not in actions
    assert "archived" in actions
    assert "inbound_forwarded_to_paul" in actions


def test_on_message_dispatch_failure_is_audited_not_raised(tmp_path, monkeypatch):
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    import aibot_service.connection as connection_mod

    async def _boom(**kwargs):
        raise RuntimeError("归档模拟失败")

    monkeypatch.setattr(connection_mod, "archive_inbound_message", _boom)

    frame = {"body": {"msgtype": "text", "from": {"userid": "YaoZuYi"}, "text": {"content": "x"}}}
    # 不应向上抛出——门禁①要求归档失败也要留痕而不是让服务崩溃
    asyncio.run(client.handlers["message"][0](frame))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "message_dispatch_failed" in actions


# ── 队列 #126：`repo_root` 接入的队列 git 同步全链集成测试 ──────────────
#
# 此前 `build_connector(repo_root=...)` 这条路径从未在集成层面被测试过
# （只有 queue_git_sync.py 自己的单测覆盖了 git 层逻辑）——本节补齐，同时
# 验证：① 归档→追加→git 同步全链只产生一行（不因 queue_git_sync 内部重复
# 调用 append_pending_task 而重复追加，此前的隐藏 bug）；② 即便传入的
# repo_root 与队列文件实际所在 checkout 不一致，也能动态解析恢复（#126
# 核心场景）。


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )


def _init_git_repo_with_queue(tmp_path: Path, queue_text: str) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "-b", "master")

    seed = tmp_path / "_seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "master")
    _git(seed, "config", "user.email", "seed@example.com")
    _git(seed, "config", "user.name", "Seed")
    (seed / "queue.md").write_text(queue_text, encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "init")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "master")

    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "config", "user.email", "bot@example.com")
    _git(repo, "config", "user.name", "Test Bot")
    return origin, repo


def _message_frame(sender: str = "YaoZuYi", content: str = "已收到，稍后回复") -> dict:
    return {
        "body": {
            "msgtype": "text",
            "from": {"userid": sender},
            "text": {"content": content},
        }
    }


def test_on_message_with_repo_root_appends_exactly_one_row_and_pushes(tmp_path):
    """归档+队列追加+git 同步全链只应产生一行，不得因 queue_git_sync 内部
    再次调用 append_pending_task 而重复追加同一条消息。"""
    origin, repo = _init_git_repo_with_queue(tmp_path, QUEUE_TEXT)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=repo / "7-外部文档",
        queue_path=repo / "queue.md",
        client_factory=fake_client_factory(store),
        repo_root=repo,
    )
    client = store["client"]

    asyncio.run(client.handlers["message"][0](_message_frame()))

    new_queue = (repo / "queue.md").read_text(encoding="utf-8")
    occurrences = new_queue.count("采购专线")
    assert occurrences == 1, f"应只追加一行，实际出现 {occurrences} 次：\n{new_queue}"

    pushed_content = subprocess.run(
        ["git", "--git-dir", str(origin), "show", "master:queue.md"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    assert "采购专线" in pushed_content, "本地追加+提交后必须真正推送到远端"

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_appended" in actions
    assert "queue_sync_pushed" in actions
    assert "queue_sync_degraded" not in actions


def test_on_message_with_mismatched_repo_root_still_syncs_via_dynamic_resolution(tmp_path):
    """队列 #126 核心场景复现：`build_connector` 传入的 `repo_root` 不是
    `queue_path` 实际所属的 checkout（服务常驻 ops worktree、队列文件在
    主工作区的真实故障模式简化版）。修复前会在 `_relative_to_repo` 处直接
    抛异常、整条同步降级；修复后应动态解析出 queue_path 真正所属的仓库
    根，正常推送成功。"""
    origin, repo = _init_git_repo_with_queue(tmp_path, QUEUE_TEXT)
    wrong_repo_root = tmp_path / "unrelated_checkout"
    _git(tmp_path, "init", "-q", "-b", "master", str(wrong_repo_root))
    _git(wrong_repo_root, "config", "user.email", "x@example.com")
    _git(wrong_repo_root, "config", "user.name", "X")

    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=repo / "7-外部文档",
        queue_path=repo / "queue.md",
        client_factory=fake_client_factory(store),
        repo_root=wrong_repo_root,  # 故意传错——模拟 #126 的 checkout 不一致
    )
    client = store["client"]

    asyncio.run(client.handlers["message"][0](_message_frame()))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_sync_pushed" in actions, f"应动态解析出正确 repo 根并成功推送，实际 actions={actions}"
    assert "queue_sync_degraded" not in actions

    pushed_content = subprocess.run(
        ["git", "--git-dir", str(origin), "show", "master:queue.md"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    assert "采购专线" in pushed_content

    new_queue = (repo / "queue.md").read_text(encoding="utf-8")
    assert new_queue.count("采购专线") == 1


# ── 队列 #168：编辑锁真实集成（真实子进程，不用 fake）─────────────────────
#
# 复现分析件 §一 的核心场景："持锁方读入 → 机器人追加 → 持锁方写回"——
# 用真实的共享编辑锁 CLI 工具模拟一个人类会话持锁编辑，验证机器人在这段
# 窗口期内确实不会写盘（而不是被动指望"写前核验"侥幸不覆盖），消息改为
# 推迟补录；锁释放后下一条消息到达时自动补录成功，两条消息最终都完整出现
# 在队列文件与远端，没有任何一条消息丢失或被覆盖。


def _human_acquire_lock(repo: Path, queue_path: Path, who: str = "TestHuman") -> None:
    result = subprocess.run(
        [sys.executable, str(repo / "0-学习与工具" / "工具-共享文档编辑锁.py"),
         "--file", str(queue_path), "acquire", "--who", who],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _human_release_lock(repo: Path, queue_path: Path, who: str = "TestHuman") -> None:
    result = subprocess.run(
        [sys.executable, str(repo / "0-学习与工具" / "工具-共享文档编辑锁.py"),
         "--file", str(queue_path), "release", "--who", who],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_on_message_defers_when_human_holds_edit_lock_then_flushes_after_release(tmp_path):
    origin, repo = _init_git_repo_with_queue(tmp_path, QUEUE_TEXT)
    (repo / "0-学习与工具").mkdir()
    (repo / "0-学习与工具" / "工具-共享文档编辑锁.py").write_text(
        _EDIT_LOCK_TOOL_SOURCE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    pending_lock_path = tmp_path / "pending_lock.jsonl"
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=repo / "7-外部文档",
        queue_path=repo / "queue.md",
        client_factory=fake_client_factory(store),
        repo_root=repo,
        enable_queue_edit_lock=True,
        pending_lock_path=pending_lock_path,
    )
    client = store["client"]

    # 模拟人类会话正在编辑队列文件——此时机器人若绕锁直接写盘，稍后人类
    # 把内存里那份（不含机器人新增行）整文件写回时会静默覆盖掉它。
    _human_acquire_lock(repo, repo / "queue.md")

    asyncio.run(client.handlers["message"][0](_message_frame(content="锁占用期间的第一条消息")))

    # 归档本体不受影响；队列文件本身一个字节都不该变（机器人从未写盘）。
    assert (repo / "7-外部文档" / "采购部").exists()
    assert (repo / "queue.md").read_text(encoding="utf-8") == QUEUE_TEXT
    pending = read_deferred_appends(pending_lock_path)
    assert len(pending) == 1

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_append_deferred_lock_busy" in actions
    assert "queue_appended" not in actions
    assert "queue_sync_pushed" not in actions

    # 人类"写回"（模拟真实场景：持锁期间只是占位，真正的覆盖风险发生在
    # release 之后——这里直接 release，验证释放后下一条消息能自动补录）。
    _human_release_lock(repo, repo / "queue.md")

    asyncio.run(client.handlers["message"][0](_message_frame(content="锁释放后的第二条消息")))

    final_queue = (repo / "queue.md").read_text(encoding="utf-8")
    # 两条消息都必须完整出现，一条不多一条不少——第一条是补录的，第二条
    # 是正常路径追加的。
    assert final_queue.count("采购专线") == 2
    assert read_deferred_appends(pending_lock_path) == []

    pushed_content = subprocess.run(
        ["git", "--git-dir", str(origin), "show", "master:queue.md"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    assert pushed_content.count("采购专线") == 2, "补录的一行也必须真正推送到远端，不能只留在本地"

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_append_pending_flushed" in actions
    assert actions.count("queue_sync_pushed") == 2  # 补录一次 + 第二条消息正常追加一次


def test_on_message_with_lock_disabled_by_default_behaves_exactly_as_before(tmp_path):
    """`enable_queue_edit_lock` 默认 False——不传时行为与加这个功能前完全
    一致（不产生任何锁相关的子进程调用/审计事件）。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    asyncio.run(client.handlers["message"][0](_message_frame()))

    new_queue = (tmp_path / "queue.md").read_text(encoding="utf-8")
    assert "采购专线" in new_queue
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "queue_append_deferred_lock_busy" not in actions


# ── 队列 #193：断连"进行中"提示接线 ──────────────────────────────────────

def test_disconnect_alert_disabled_by_default_lifecycle_events_work_outside_event_loop(tmp_path):
    """`disconnect_alert_fallback_send` 默认 None——不传时必须零副作用，
    连接生命周期回调（既有测试大量在无运行中事件循环的同步上下文里直接
    调用这些 handler）不应因新增本特性而报
    `RuntimeError: no running event loop`（回归本次改动引入的潜在缺陷）。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    client = store["client"]

    # 无 asyncio.run 包裹，纯同步调用——不传 disconnect_alert_fallback_send
    # 时这里不应抛出。
    client.handlers["disconnected"][0]("network glitch")
    client.handlers["reconnecting"][0](1)
    client.handlers["authenticated"][0]()

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["disconnected", "reconnecting", "authenticated"]


def test_disconnect_alert_enabled_wires_lifecycle_without_firing_within_short_test_window(tmp_path):
    """启用本特性（传入 fallback）时，断连→（在阈值内）恢复的完整生命周期
    须能在真实事件循环里跑通、不抛异常、不产生未取消的悬空任务；默认阈值
    75 秒远大于本测试实际耗时，故不应触发提示（提示逻辑本身的判据已在
    test_disconnect_inprogress_alert.py 用可控假 _sleep 精确覆盖，此处只
    验证接线本身）。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    fallback_calls: list = []

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
        disconnect_alert_fallback_send=fallback_calls.append,
    )
    client = store["client"]

    async def scenario():
        client.handlers["disconnected"][0]("network glitch")
        client.handlers["reconnecting"][0](1)
        await asyncio.sleep(0)  # 让计时任务真正启动
        client.handlers["authenticated"][0]()  # 阈值内恢复，取消计时任务
        await asyncio.sleep(0)  # 让取消传播完成

    asyncio.run(scenario())

    assert fallback_calls == []
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["disconnected", "reconnecting", "authenticated"]
    assert "pending_lock_flush_dispatch_failed" not in actions
