"""测试夹具 —— 真实 A2.1 模板路径。

值抽取（已填样本）回归用陈忱黄金样本（data/golden/，收口-3）后补；
本批先用空白模板验证「锚点定位」与结构解析（解析探针 D4 的前半）。
"""
import sys
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent, strict=True)  # noqa: E402

import pytest

SCENE = Path(__file__).resolve().parent.parent
# 7-外部文档/质量部 2026-07 由质量专线重组：空白模板移入「产品类立项申请书及评审报告」子夹
REAL_A21 = (SCENE / "../../../7-外部文档/质量部/产品类立项申请书及评审报告/"
            "EQQR8082立项申请书（开发类）-A2.1.xlsx")
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
