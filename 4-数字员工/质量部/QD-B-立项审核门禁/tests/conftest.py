"""测试夹具 —— 真实 A2.1 模板路径。

值抽取（已填样本）回归用陈忱黄金样本（data/golden/，收口-3）后补；
本批先用空白模板验证「锚点定位」与结构解析（解析探针 D4 的前半）。
"""
from pathlib import Path

import pytest

SCENE = Path(__file__).resolve().parent.parent
REAL_A21 = SCENE / "../../../7-外部文档/质量部/EQQR8082立项申请书（开发类）-A2.1.xlsx"
HUAFENG = SCENE / "data/golden/华丰天然气发动机EPA认证服务咨询项目立项申请书0616-测试专用2.1版本.xlsx"


@pytest.fixture(scope="session")
def real_a21_path() -> str:
    p = REAL_A21.resolve()
    if not p.exists():
        pytest.skip(f"真实 A2.1 空白模板不存在：{p}")
    return str(p)


@pytest.fixture(scope="session")
def huafeng_path() -> str:
    """华丰已填件（技术服务类黄金样本）。gitignore 不入库，缺失则跳过（同 SC8 real_frozen 纪律）。"""
    p = HUAFENG.resolve()
    if not p.exists():
        pytest.skip(f"华丰黄金样本不存在（本地脱敏样本，不入库）：{p}")
    return str(p)
