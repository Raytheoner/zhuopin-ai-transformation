"""测试夹具 —— 真实 A2.1 模板路径。

值抽取（已填样本）回归用陈忱黄金样本（data/golden/，收口-3）后补；
本批先用空白模板验证「锚点定位」与结构解析（解析探针 D4 的前半）。
"""
# —— worktree 隔离引导（队列 #300）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")

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
