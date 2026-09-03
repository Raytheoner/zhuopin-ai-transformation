"""判据签认 —— 跨场景公共模块（Shao Peishen 2026-09-03 拍板 EE-1=(a) 收进底座）。

## 一句话语义

**未签认的判据一律为 ``None``，任何读取未签认判据的调用必须 fail-loud；
本模块不提供、也不接受任何「给个默认值」的旁路。**

## 为什么收进底座

rule-of-three 已触发（**5 > 3**）：FI5／FI6／FI8／FI9／FI10 五个财务场景各需一套
「判据签认」逻辑，此前是**五份各自手抄的本地实现**。五份手抄必然各自漂移——
本项目在 `#345`（35 份路径引导手抄副本）上已经吃过一次同形状的亏。

## 收进来的 ＝ 五份实现里真正共通的四件事

  1. 一条判据有**身份**（key）、有**要定什么**（question）、有**该谁签**（owner）；
  2. 未签认 ⇒ 值为 ``None``；**读它必抛**，不回退默认（`CriterionNotSignedOffError`）；
  3. 签认是一条**可追溯记录**：实名 ＋ 日期 ＋ 落档凭据 ＋ 规则版本，四项全必填（`Signoff`）；
  4. 场景把判据登记进一张**注册表**，据此可整体查缺（`CriteriaRegistry`）、
     并校验 ``RULE_VERSION`` 与签认状态是否一致（五份实现各写了一遍的那条 assert）。

## 🔴 刻意**没有**收进来的（防止底座反过来绑死场景）

  · 具体判据名、值的形状、领域文案 —— 那是场景数据，进了底座就成了底座在替场景定业务；
  · **权限缺口**（FI8 银行余额取数授权，须 CFO 办公室）、**存在性未核实**（FI9 工时系统）、
    **前置未满足**（FI10 芯片价格 API，队列 `#475`）—— 三者机械形状虽像判据，
    但**各只出现 1 次，rule-of-three 未触发**，且五个场景包明确要求「三处缺口性质各不相同、
    分别立牌不合并」。✅ **Shao Peishen 2026-09-03 拍板 G-2 ＝ (a) 不收**，三条原样留在各自场景包；
  · L2 默认侧（``needs_manual_review=True``）、``disclaimer`` 必填、``confirmed_by`` 无默认
    —— 虽 5/5 命中，但属**模型层**纪律、不属判据签认，出圈不收。
    ✅ **G-4 ＝ (b) 另立队列行 `#476`、不排期**（触发条件＝至少两个财务引擎落地，🛑 未满足前不得认领）；
  · 与 `AuditLogger` 的联动 —— 五份本地实现都没有，本模块不凭空加。
    ✅ **G-5 ＝ (a) 不接**，保本模块**零内部依赖**；改**反向依赖**：由各场景引擎在
    ``record(AuditEvent)`` 时把当时的 ``RULE_VERSION`` 写进 ``decision``
    —— **审计日志指向判据版本，不是判据模块去写日志**（实施归 A4，见 `tasks.md` 4.7）。

## 用法

    from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion, Signoff

    CRITERIA = CriteriaRegistry("FI5", [
        Criterion("L2_BUDGET_BLOCK_PCT",
                  question="占用预算余额超过百分之几即拦截并通知上级",
                  owner="财务侧"),
    ])
    RULE_VERSION = "fi5-skeleton-unsigned-2026-09-03"
    CRITERIA.assert_rule_version(RULE_VERSION)

    CRITERIA.value_of("L2_BUDGET_BLOCK_PCT")   # ⇒ 抛 CriterionNotSignedOffError

签认落地（三步齐了才动，缺一步都不要动）::

    Criterion(...).signed(
        0.9,
        Signoff(signed_by="某某某", signed_on="2026-10-11",
                evidence="3-治理与合规/报销政策判据表-2026-10-11.md",
                rule_version="fi5-signed-2026-10-11"),
    )

✅ **状态**：openspec 变更包 `criteria-signoff-platform` **design 审已于 2026-09-03 通过**
（Shao Peishen 逐条拍板 `G-1`…`G-7`，见看护批 `B-0903_50` §一与 `design.md` §定夺项）。
🔴 五个场景包的迁移是 **A4 段**的事，本模块所在的收口段**不改任何场景包**；
A4 须把 FI10 的 ``SLOW_MOVING_CRITERIA`` 一并登记进注册表（`G-3`，`tasks.md` 4.1a），
迁移前后未签认判据数恒为 **18**。
"""

from .errors import (
    CriteriaSignoffError,
    CriterionContractError,
    CriterionNotSignedOffError,
    UnknownCriterionError,
)
from .models import Criterion, Signoff
from .registry import UNSIGNED_VERSION_TAG, CriteriaRegistry

__all__ = [
    "CriteriaRegistry",
    "Criterion",
    "Signoff",
    "CriteriaSignoffError",
    "CriterionNotSignedOffError",
    "CriterionContractError",
    "UnknownCriterionError",
    "UNSIGNED_VERSION_TAG",
]
