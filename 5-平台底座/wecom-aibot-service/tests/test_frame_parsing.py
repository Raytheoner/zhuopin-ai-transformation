from aibot_service.frame_parsing import parse_inbound_frame


def test_parse_text_message_with_dict_from():
    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "姚祖怡"},
            "text": {"content": "收到，明天回复"},
        }
    }
    msg = parse_inbound_frame(frame)
    assert msg.sender == "姚祖怡"
    assert msg.msgtype == "text"
    assert msg.text_content == "收到，明天回复"


def test_parse_text_message_with_string_from():
    frame = {"body": {"msgtype": "text", "from": "唐燕萍", "text": {"content": "hi"}}}
    msg = parse_inbound_frame(frame)
    assert msg.sender == "唐燕萍"


def test_parse_file_message_extracts_url_and_aeskey():
    frame = {
        "body": {
            "msgtype": "file",
            "from": {"userid": "陈忱"},
            "file": {"url": "https://x/y", "aeskey": "AESKEY123", "filename": "权重表.xlsx"},
        }
    }
    msg = parse_inbound_frame(frame)
    assert msg.msgtype == "file"
    assert msg.file_url == "https://x/y"
    assert msg.file_aes_key == "AESKEY123"
    assert msg.file_name_hint == "权重表.xlsx"


def test_parse_message_missing_from_defaults_to_empty_sender():
    frame = {"body": {"msgtype": "text", "text": {"content": "no sender"}}}
    msg = parse_inbound_frame(frame)
    assert msg.sender == ""


def test_parse_message_missing_body_does_not_raise():
    msg = parse_inbound_frame({})
    assert msg.msgtype == ""
    assert msg.sender == ""


# ── 队列 #274：chatid/chattype 提取（此前从未进入 InboundMessage）───────────

def test_parse_group_message_extracts_chatid_and_chattype():
    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "ShaoPeiShen"},
            "text": {"content": "@邵总数字人🤖 财务测试短信"},
            "chatid": "wrkSFfCgAAxxxxxxxxxxxxxxxxxxxxx",
            "chattype": "group",
        }
    }
    msg = parse_inbound_frame(frame)
    assert msg.chatid == "wrkSFfCgAAxxxxxxxxxxxxxxxxxxxxx"
    assert msg.chattype == "group"


def test_parse_single_chat_message_chattype_single():
    frame = {
        "body": {
            "msgtype": "text",
            "from": {"userid": "YaoZuYi"},
            "text": {"content": "收到"},
            "chatid": "wrSingleChatIdXXXXXXXXXXXXXXXXX",
            "chattype": "single",
        }
    }
    msg = parse_inbound_frame(frame)
    assert msg.chatid == "wrSingleChatIdXXXXXXXXXXXXXXXXX"
    assert msg.chattype == "single"


def test_parse_message_missing_chatid_defaults_to_none():
    frame = {"body": {"msgtype": "text", "from": {"userid": "x"}, "text": {"content": "y"}}}
    msg = parse_inbound_frame(frame)
    assert msg.chatid is None
    assert msg.chattype is None
