"""测试替身：`AibotClientLike` 的假实现，供 delivery/intake/connection 测试复用。"""
from __future__ import annotations

from aibot_service.queue_edit_lock import QueueLockBusy


class FakeQueueEditLock:
    """`queue_appender.QueueEditLock` 契约的可控测试替身（队列 #168）——
    不起子进程/不依赖真实仓库，`busy` 控制 `try_acquire` 是否抛
    `QueueLockBusy`，并记录调用次数供断言。"""

    def __init__(self, busy: bool = False):
        self.busy = busy
        self.acquire_calls = 0
        self.release_calls = 0

    def try_acquire(self) -> None:
        self.acquire_calls += 1
        if self.busy:
            raise QueueLockBusy("测试替身：模拟锁占用中")

    def release(self) -> None:
        self.release_calls += 1


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
