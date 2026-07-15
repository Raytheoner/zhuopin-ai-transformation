"""企微智能机器人连接器测试（wecom_aibot.py）。

全程用 `AibotClientLike` 假实现替身，不依赖真实 SDK 已安装、不触真实企微端点
（对应 openspec/changes/wecom-aibot-channel/ 先 mock 后接真实的纪律）。
"""
import asyncio

import pytest

from zhuopin_platform.shared_tools.notifiers.wecom_aibot import (
    AibotConnector,
    UPLOAD_CHUNK_SIZE,
    UPLOAD_MAX_CHUNKS,
    CMD_UPLOAD_INIT,
    CMD_UPLOAD_CHUNK,
    CMD_UPLOAD_FINISH,
)


class _FakeClient:
    """`AibotClientLike` 的测试替身：记录所有调用，不接真实网络。"""

    def __init__(self, bot_id, secret, **options):
        self.bot_id = bot_id
        self.secret = secret
        self.options = options
        self.handlers: dict[str, list] = {}
        self.connected = False
        self.sent_messages: list[tuple[str, dict]] = []
        self.raw_frames: list[tuple[str, dict]] = []
        self.raw_frame_responses: dict[str, list] = {}
        self.downloads: list[tuple[str, str | None]] = []
        self.download_response: tuple[bytes, str | None] = (b"", None)

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    async def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    async def send_message(self, chatid, body):
        self.sent_messages.append((chatid, body))
        return {"errcode": 0}

    async def send_raw_frame(self, cmd, body):
        self.raw_frames.append((cmd, body))
        queue = self.raw_frame_responses.get(cmd, [])
        if queue:
            return queue.pop(0)
        return {"errcode": 0, "body": {}}

    async def download_file(self, url, aes_key=None):
        self.downloads.append((url, aes_key))
        return self.download_response

    @property
    def is_connected(self):
        return self.connected


def _factory(store: dict):
    """返回一个 client_factory，把创建出的唯一 _FakeClient 存进 store['client']。"""

    def factory(bot_id, secret, **options):
        client = _FakeClient(bot_id, secret, **options)
        store["client"] = client
        return client

    return factory


def test_bot_id_secret_required():
    with pytest.raises(ValueError):
        AibotConnector("", "secret", client_factory=_factory({}))
    with pytest.raises(ValueError):
        AibotConnector("bot", "", client_factory=_factory({}))


def test_event_handlers_wired_to_underlying_client():
    store: dict = {}
    seen = {"connected": 0, "authenticated": 0, "disconnected": [], "error": []}

    AibotConnector(
        "bot-1",
        "secret-1",
        client_factory=_factory(store),
        on_connected=lambda: seen.__setitem__("connected", seen["connected"] + 1),
        on_authenticated=lambda: seen.__setitem__("authenticated", seen["authenticated"] + 1),
        on_disconnected=lambda reason: seen["disconnected"].append(reason),
        on_error=lambda err: seen["error"].append(err),
    )

    client = store["client"]
    # 模拟底层 SDK 触发事件：直接调用注册的 handler
    client.handlers["connected"][0]()
    client.handlers["authenticated"][0]()
    client.handlers["disconnected"][0]("kicked or network error")
    client.handlers["error"][0](RuntimeError("boom"))

    assert seen["connected"] == 1
    assert seen["authenticated"] == 1
    assert seen["disconnected"] == ["kicked or network error"]
    assert len(seen["error"]) == 1


def test_connect_disconnect_and_is_connected_delegate():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))

    assert connector.is_connected is False
    asyncio.run(connector.connect())
    assert connector.is_connected is True
    connector.disconnect()
    assert connector.is_connected is False


def test_send_markdown_builds_correct_body():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))

    asyncio.run(connector.send_markdown("chat-1", "**hello**"))

    chatid, body = store["client"].sent_messages[0]
    assert chatid == "chat-1"
    assert body == {"msgtype": "markdown", "markdown": {"content": "**hello**"}}


def test_send_file_builds_correct_body():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))

    asyncio.run(connector.send_file("chat-1", "MEDIA_ID_123"))

    chatid, body = store["client"].sent_messages[0]
    assert chatid == "chat-1"
    assert body == {"msgtype": "file", "file": {"media_id": "MEDIA_ID_123"}}


def test_upload_media_single_chunk_happy_path():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))
    client = store["client"]
    client.raw_frame_responses[CMD_UPLOAD_INIT] = [{"body": {"upload_id": "U1"}}]
    client.raw_frame_responses[CMD_UPLOAD_FINISH] = [{"body": {"media_id": "M1"}}]

    result = asyncio.run(connector.upload_media(b"hello docx bytes", "followup.docx"))

    assert result.media_id == "M1"
    assert result.chunk_count == 1
    cmds = [cmd for cmd, _ in client.raw_frames]
    assert cmds == [CMD_UPLOAD_INIT, CMD_UPLOAD_CHUNK, CMD_UPLOAD_FINISH]
    init_body = client.raw_frames[0][1]
    assert init_body["type"] == "file"
    assert init_body["filename"] == "followup.docx"
    assert init_body["total_chunks"] == 1
    assert init_body["total_size"] == len(b"hello docx bytes")
    assert "md5" in init_body
    chunk_body = client.raw_frames[1][1]
    assert chunk_body["upload_id"] == "U1"
    assert chunk_body["chunk_index"] == 0
    assert "base64_data" in chunk_body


def test_upload_media_splits_into_multiple_chunks():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))
    client = store["client"]
    client.raw_frame_responses[CMD_UPLOAD_INIT] = [{"body": {"upload_id": "U2"}}]
    client.raw_frame_responses[CMD_UPLOAD_FINISH] = [{"body": {"media_id": "M2"}}]

    big = b"x" * (UPLOAD_CHUNK_SIZE * 2 + 10)  # 3 个分片
    result = asyncio.run(connector.upload_media(big, "big.docx"))

    assert result.chunk_count == 3
    chunk_frames = [f for cmd, f in client.raw_frames if cmd == CMD_UPLOAD_CHUNK]
    assert len(chunk_frames) == 3
    assert [f["chunk_index"] for f in chunk_frames] == [0, 1, 2]


def test_upload_media_rejects_over_max_chunks():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))

    too_big = b"x" * (UPLOAD_CHUNK_SIZE * (UPLOAD_MAX_CHUNKS + 1))
    with pytest.raises(ValueError, match="超过官方上限"):
        asyncio.run(connector.upload_media(too_big, "toobig.docx"))


def test_upload_media_raises_when_init_missing_upload_id():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))
    store_client_ref: dict = {}

    # 触发 factory 后修改其 init 响应为缺 upload_id
    client = store["client"]
    client.raw_frame_responses[CMD_UPLOAD_INIT] = [{"body": {}}]

    with pytest.raises(RuntimeError, match="upload_id"):
        asyncio.run(connector.upload_media(b"data", "f.docx"))


def test_download_file_delegates_to_client():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))
    store["client"].download_response = (b"file-bytes", "attachment.xlsx")

    data, filename = asyncio.run(connector.download_file("https://example/x", "AESKEY"))

    assert data == b"file-bytes"
    assert filename == "attachment.xlsx"
    assert store["client"].downloads == [("https://example/x", "AESKEY")]


def test_upload_media_raises_when_finish_missing_media_id():
    store: dict = {}
    connector = AibotConnector("bot-1", "secret-1", client_factory=_factory(store))
    client = store["client"]
    client.raw_frame_responses[CMD_UPLOAD_INIT] = [{"body": {"upload_id": "U3"}}]
    client.raw_frame_responses[CMD_UPLOAD_FINISH] = [{"body": {}}]

    with pytest.raises(RuntimeError, match="media_id"):
        asyncio.run(connector.upload_media(b"data", "f.docx"))
