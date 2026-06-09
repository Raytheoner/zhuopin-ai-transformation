"""企业微信群机器人推送封装（收割自 supplychain src/notifiers/wecom.py）。

通用内部通知出口。webhook 地址由调用方注入（从环境变量读取，不硬编码）。

企业微信 Markdown 语法（群机器人子集）：**加粗** / <font color="warning">橙</font> /
> 引用块 / [链接](url) / --- 分割线。不支持 # 标题与表格，内容上限约 4096 字符。
"""
import json
import urllib.request


def send_markdown(webhook_url: str, content: str) -> None:
    """向企业微信群机器人推送 Markdown 消息（上限 4096 字符）。

    Raises:
        RuntimeError: 推送失败（errcode != 0）或网络错误。
    """
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode", 0) != 0:
        raise RuntimeError(
            f"企业微信推送失败 errcode={result.get('errcode')} errmsg={result.get('errmsg')}"
        )


def send_text(webhook_url: str, content: str) -> None:
    """向企业微信群机器人推送纯文本消息（用于错误告警等简单场景）。"""
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": content}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode", 0) != 0:
        raise RuntimeError(
            f"企业微信推送失败 errcode={result.get('errcode')} errmsg={result.get('errmsg')}"
        )
