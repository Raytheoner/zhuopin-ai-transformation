import tomllib
from pathlib import Path

import pytest

from aibot_service.gates import (
    FINALIZED_STATUS_MARKER,
    FORBIDDEN_BUSINESS_MODULE_SUBSTRINGS,
    assert_finalized,
    DeliveryNotFinalizedError,
)

SERVICE_ROOT = Path(__file__).resolve().parent.parent


def test_assert_finalized_accepts_marker():
    assert_finalized(FINALIZED_STATUS_MARKER)  # 不抛异常


@pytest.mark.parametrize(
    "status_value",
    ["", "✅ 已发", "⏳ 待 Paul 线下对齐新协同流程后发", "🆕 待发 ", "待发", "已推送"],
)
def test_assert_finalized_rejects_everything_else(status_value):
    if status_value.strip() == FINALIZED_STATUS_MARKER:
        pytest.skip("trimmed 后等于合法值，不属于本测试范围")
    with pytest.raises(DeliveryNotFinalizedError):
        assert_finalized(status_value)


def test_gate1_pyproject_excludes_business_connectors():
    """门禁①结构性核查：依赖清单不含 ERP/SRM/CRM 连接器（design.md D8）。"""
    pyproject_text = (SERVICE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    data = tomllib.loads(pyproject_text)
    deps = " ".join(data["project"]["dependencies"])
    for forbidden in FORBIDDEN_BUSINESS_MODULE_SUBSTRINGS:
        assert forbidden not in deps, f"依赖清单不得出现 {forbidden}：{deps}"


@pytest.mark.parametrize("module_name", ["intake", "forwarding", "group_notify"])
def test_gate1_inbound_modules_have_no_business_connector_imports(module_name):
    """静态核查 inbound 处理模块（intake.py 归档 / forwarding.py 转发 /
    group_notify.py 部门群通报）源码不 import erp_connector/srm_connector
    （AST 扫描）。group_notify.py 是 2026-07-14 新增的归档后部门群通报功能，
    同样受门禁①约束——inbound 触发的代码路径一律不得触达业务系统连接器。"""
    import ast
    import importlib

    mod = importlib.import_module(f"aibot_service.{module_name}")
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for forbidden in FORBIDDEN_BUSINESS_MODULE_SUBSTRINGS:
                assert forbidden not in module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in FORBIDDEN_BUSINESS_MODULE_SUBSTRINGS:
                    assert forbidden not in alias.name
