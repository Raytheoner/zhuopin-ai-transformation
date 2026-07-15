"""测试替身：`AibotClientLike` 的假实现，供 delivery/intake/connection 测试复用。"""
from __future__ import annotations


class FakeAibotClient:
    def __init__(self, bot_id="bot", secret="secret", **options):
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


def fake_client_factory(store: dict):
    def factory(bot_id, secret, **options):
        client = FakeAibotClient(bot_id, secret, **options)
        store["client"] = client
        return client

    return factory
