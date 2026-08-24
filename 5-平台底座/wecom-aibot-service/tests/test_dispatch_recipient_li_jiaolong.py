"""队列 #380：李姣龙（财务部）接入企微机器人可达白名单。

`dispatch.py::KNOWN_RECIPIENT_USERIDS` 此前实测仅 6 人、无李姣龙（§一 #372
⑥⑶ 已记该缺口）。她同时是三件事的执行人（每工作日 10:00 前投放税务导出
Excel／每日核对群通知判流程健康／按《核对通过明细表》手动在 ERP 立账），
我方已有多条动作需要直达她本人。

🔴 **本行是 §一 #379（年度提醒）的硬前置**：收件人就是她，白名单不通则提醒
发不出去，**且该通道 fail-closed 静默跳过、不报错** —— 失败形态是「什么也
没发生、命令行一切正常」。
"""
from aibot_service.dispatch import KNOWN_RECIPIENT_USERIDS


def test_li_jiaolong_is_reachable():
    assert KNOWN_RECIPIENT_USERIDS["李姣龙"] == "2025672"


def test_userid_is_the_numeric_staff_id_not_a_pinyin_guess():
    """🔴 `2025672` 是纯数字工号，不可推断（同 `陈承: 2023458`）。

    财务部六人里有两个是这种形态，任何"按拼音猜 userid"的做法在她们身上
    一定错，且错的形态是 fail-closed 静默跳过、命令行一切正常。本断言把
    「这是工号不是拼音」这条事实钉在测试里。
    """
    userid = KNOWN_RECIPIENT_USERIDS["李姣龙"]
    assert userid.isdigit()
    assert userid != "LiJiaoLong"


def test_existing_recipients_unchanged():
    """回归锁：本次只加一个键，既有六项一个不动。"""
    for name, userid in {
        "姚祖怡": "YaoZuYi",
        "唐燕萍": "tangyanping",
        "陈忱": "ChenChen",
        "王泓钦": "Hongqin.Wang",
        "泓钦": "Hongqin.Wang",
        "陈承": "2023458",
    }.items():
        assert KNOWN_RECIPIENT_USERIDS[name] == userid
