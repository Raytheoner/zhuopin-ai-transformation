"""企业微信「智能机器人」双向通道连接器（WebSocket 长连接）。

与同目录 `wecom.py`（webhook 群机器人，只发不收）并存、互不依赖。本模块只封装
连接/收发的协议细节，不含任何业务逻辑（业务编排在 `wecom-aibot-service` 独立
服务目录，见 openspec/changes/wecom-aibot-channel/design.md D1）。

底层复用官方 SDK `wecom-aibot-python-sdk`（可选依赖，见 pyproject.toml `[aibot]`
extra）——本模块顶层 **不** import 该 SDK，只在 `default_client_factory()` 内部
懒加载，未安装该 extra 的场景 `pip install -e` 平台包时不受影响。

官方 SDK 未覆盖 outbound 素材上传（`aibot_upload_media_init`/`_chunk`/`_finish`
三个 WS cmd，详见企微官方文档），本模块在 `_SdkClientAdapter.send_raw_frame()`
里补上，复用 SDK 内部 `_ws_manager.send_reply()` 这个"发帧+等 ACK"通用原语
（与 SDK 自身 `send_message()` 实现模式一致）。
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

# 单分片上限（Base64 编码前），官方文档：512KB / 分片，最多 100 分片。
UPLOAD_CHUNK_SIZE = 512 * 1024
UPLOAD_MAX_CHUNKS = 100

CMD_UPLOAD_INIT = "aibot_upload_media_init"
CMD_UPLOAD_CHUNK = "aibot_upload_media_chunk"
CMD_UPLOAD_FINISH = "aibot_upload_media_finish"


@runtime_checkable
class AibotClientLike(Protocol):
    """连接器依赖的最小客户端接口——真实 SDK 与测试替身均实现此接口。"""

    def on(self, event: str, handler: Callable[..., Any]) -> Any: ...
    async def connect(self) -> Any: ...
    def disconnect(self) -> None: ...
    async def send_message(self, chatid: str, body: dict) -> dict: ...
    async def send_raw_frame(self, cmd: str, body: dict) -> dict: ...
    async def download_file(
        self, url: str, aes_key: str | None = None
    ) -> tuple[bytes, str | None]: ...
    @property
    def is_connected(self) -> bool: ...


class _SdkClientAdapter:
    """把官方 SDK 的 `WSClient` 适配为 `AibotClientLike`（补 send_raw_frame）。"""

    def __init__(self, ws_client: Any) -> None:
        self._client = ws_client

    def on(self, event: str, handler: Callable[..., Any]) -> Any:
        return self._client.on(event, handler)

    async def connect(self) -> Any:
        return await self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    async def send_message(self, chatid: str, body: dict) -> dict:
        return await self._client.send_message(chatid, body)

    async def send_raw_frame(self, cmd: str, body: dict) -> dict:
        """SDK 未公开封装的 cmd（如素材上传三步）经内部 ack 队列原语发送。"""
        from aibot.utils import generate_req_id  # 懒加载

        req_id = generate_req_id(cmd)
        # WSClient 内部 _ws_manager.send_reply(req_id, body, cmd) 是与官方
        # send_message() 相同的"发帧 + 排队等待对方按 req_id 回 ACK"原语。
        return await self._client._ws_manager.send_reply(req_id, body, cmd)

    async def download_file(
        self, url: str, aes_key: str | None = None
    ) -> tuple[bytes, str | None]:
        return await self._client.download_file(url, aes_key)

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected


def default_client_factory(bot_id: str, secret: str, **options: Any) -> AibotClientLike:
    """默认客户端工厂：懒加载官方 SDK，构造并适配为 `AibotClientLike`。"""
    import aibot  # 懒加载，未装 [aibot] extra 时不影响本模块的其余导入

    ws_options = aibot.WSClientOptions(bot_id=bot_id, secret=secret, **options)
    return _SdkClientAdapter(aibot.WSClient(ws_options))


@dataclass
class UploadResult:
    media_id: str
    chunk_count: int


class AibotConnector:
    """企微智能机器人长连接封装：订阅/心跳/重连由底层 SDK 负责；本类只做
    事件→回调转接 + outbound 发送/素材上传的薄封装。不含任何业务判断。
    """

    def __init__(
        self,
        bot_id: str,
        secret: str,
        *,
        client_factory: Callable[..., AibotClientLike] = default_client_factory,
        max_reconnect_attempts: int = 6,
        heartbeat_interval_ms: int = 30_000,
        reconnect_base_delay_ms: int = 5_000,
        ws_url: str | None = None,
        on_connected: Callable[[], None] | None = None,
        on_authenticated: Callable[[], None] | None = None,
        on_disconnected: Callable[[str], None] | None = None,
        on_reconnecting: Callable[[int], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_message: Callable[[dict], None] | None = None,
    ) -> None:
        if not bot_id:
            raise ValueError("bot_id 不能为空")
        if not secret:
            raise ValueError("secret 不能为空")

        factory_kwargs: dict[str, Any] = {
            "max_reconnect_attempts": max_reconnect_attempts,
            "heartbeat_interval": heartbeat_interval_ms,
            "reconnect_interval": reconnect_base_delay_ms,
        }
        if ws_url:
            factory_kwargs["ws_url"] = ws_url

        self._client = client_factory(bot_id, secret, **factory_kwargs)

        if on_connected:
            self._client.on("connected", on_connected)
        if on_authenticated:
            self._client.on("authenticated", on_authenticated)
        if on_disconnected:
            self._client.on("disconnected", on_disconnected)
        if on_reconnecting:
            self._client.on("reconnecting", on_reconnecting)
        if on_error:
            self._client.on("error", on_error)
        if on_message:
            self._client.on("message", on_message)

    async def connect(self) -> None:
        await self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    async def send_markdown(self, chatid: str, content: str) -> dict:
        """推送 markdown 正文到指定会话（对应 `aibot_send_msg`）。"""
        return await self._client.send_message(
            chatid, {"msgtype": "markdown", "markdown": {"content": content}}
        )

    async def send_file(self, chatid: str, media_id: str) -> dict:
        """推送已上传素材（如 docx）到指定会话，`media_id` 来自 `upload_media`。"""
        return await self._client.send_message(
            chatid, {"msgtype": "file", "file": {"media_id": media_id}}
        )

    async def download_file(
        self, url: str, aes_key: str | None = None
    ) -> tuple[bytes, str | None]:
        """下载并解密 inbound 文件消息（场景②用），`aes_key` 取自消息体
        `file.aeskey`/`image.aeskey`。返回 (文件字节, 文件名)。"""
        return await self._client.download_file(url, aes_key)

    async def upload_media(
        self, file_bytes: bytes, filename: str, media_type: str = "file"
    ) -> UploadResult:
        """临时素材三步分片上传（官方文档：单分片 ≤512KB，最多 100 分片，
        初始化后 30 分钟内传完，素材 3 天有效）。返回可供 `send_file` 引用的
        `media_id`。`media_type` 取官方枚举 file/image/voice/video，本服务
        只用附件场景，默认 "file"。**请求体字段名 2026-07-13 已用真实凭据
        核实修正**（`type`/`total_chunks`/`base64_data`，早期实现按不准确的
        网页摘要猜的字段名 `chunk_count`/`data`，被真实企微 API 拒绝
        `errcode=40058 body.type missing`，现按官方文档原文字段改正）。
        """
        chunks = [
            file_bytes[i : i + UPLOAD_CHUNK_SIZE]
            for i in range(0, len(file_bytes), UPLOAD_CHUNK_SIZE)
        ] or [b""]
        if len(chunks) > UPLOAD_MAX_CHUNKS:
            raise ValueError(
                f"文件过大：{len(chunks)} 分片超过官方上限 {UPLOAD_MAX_CHUNKS}"
                f"（单分片 {UPLOAD_CHUNK_SIZE} 字节）"
            )

        init_resp = await self._client.send_raw_frame(
            CMD_UPLOAD_INIT,
            {
                "type": media_type,
                "filename": filename,
                "total_size": len(file_bytes),
                "total_chunks": len(chunks),
                "md5": hashlib.md5(file_bytes).hexdigest(),
            },
        )
        upload_id = init_resp.get("body", {}).get("upload_id") or init_resp.get("upload_id")
        if not upload_id:
            raise RuntimeError(f"素材上传初始化未返回 upload_id：{init_resp!r}")

        for index, chunk in enumerate(chunks):
            await self._client.send_raw_frame(
                CMD_UPLOAD_CHUNK,
                {
                    "upload_id": upload_id,
                    "chunk_index": index,
                    "base64_data": base64.b64encode(chunk).decode("ascii"),
                },
            )

        finish_resp = await self._client.send_raw_frame(
            CMD_UPLOAD_FINISH, {"upload_id": upload_id}
        )
        media_id = finish_resp.get("body", {}).get("media_id") or finish_resp.get("media_id")
        if not media_id:
            raise RuntimeError(f"素材上传完成未返回 media_id：{finish_resp!r}")

        return UploadResult(media_id=media_id, chunk_count=len(chunks))
