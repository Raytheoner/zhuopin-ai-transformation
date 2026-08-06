"""两道硬门禁的共享常量/断言（design.md D8，写死代码结构，非配置开关）。"""
from __future__ import annotations

# 门禁②：README「发送状态」列的"已定稿待推送"标记（README 既有约定值）。
# 只有此值才允许推送；其余任何取值（含空/已发/待对齐/队列 #294 新增的
# `readme_table.PAUSED_STATUS` "⏸ 暂缓"等）一律拒绝——本门禁按等值断言
# 实现（非排除名单），新增状态天然被结构性排除，无需在此逐一列举。
FINALIZED_STATUS_MARKER = "🆕 待发"


class DeliveryNotFinalizedError(RuntimeError):
    """门禁②拒绝：目标行「发送状态」列不是约定的待发标记。"""


def assert_finalized(status_value: str) -> None:
    if status_value.strip() != FINALIZED_STATUS_MARKER:
        raise DeliveryNotFinalizedError(
            f'门禁②拒绝发送：当前状态 "{status_value.strip()}" 非约定的待发标记 '
            f'"{FINALIZED_STATUS_MARKER}"'
        )


# 门禁①（结构性，非本文件运行时断言）：intake.py 的归档动作只允许三类代码
# 路径——写文件归档 / 追加队列行 / 发确认收讫回执。不依赖任何 ERP/SRM/CRM
# 连接器；pyproject.toml 依赖清单里刻意不含 zhuopin_platform 的
# erp_connector/srm_connector，见 tests/test_gate1_no_business_system_access.py
# 的静态核查（导入 AST 扫描 + 依赖清单文本扫描双重校验）。
FORBIDDEN_BUSINESS_MODULE_SUBSTRINGS = ("erp_connector", "srm_connector")
