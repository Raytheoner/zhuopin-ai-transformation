"""FI10 · `fi10-inventory-intake` 采集层 —— `tasks.md` §3 的实现（本轮唯一开工节）。

**开工边界（design `D1`，2026-09-06 design 审已过）**：本模块只做采集 —— 库存账龄／在途采购／
BOM 用量／OEM 项目生命周期四类取数，**一律不读任何待签认口径**。§4（NRV 引擎）／§5（预警与
计提建议）**仍不得开工**，解除条件 ＝ `tasks 2.3` 关闭（四条口径经主笔唐燕萍签认、呆滞口径
另经姚祖怡会签）。

🔴 **本模块为什么可以先做**：采集层是本轮唯一能端到端真测的部分（不读口径 ⇒ 不是只有
fail-loud 分支可测），且它正好压着两条真前置 —— OEM 隔离（`D5`／`D11`）与 U9C／PLM 通道
核实 —— 先做它会把这两条从纸面逼成实测。

━━━ 三条落地形态（全部取自已过审的 design，不在此重新论证）━━━

**`D1` 前置风险**：U9C 库存通道与 PLM 取数通道**两条都未核实、且都无主**（design Open
Questions **B-1**，与 `#477` 同一条判词的第五次适用）。⇒ `real` 模式一律 fail-loud、
🔴 **不得回退 mock**（`tasks 3.1` 必测项）。

**`D5` OEM 隔离的机械形态**（直接借 FI9 `fi9-rd-cost-mvp/design.md` E2，不重新论证）：
  1. **guard 调在取数入口，不调在每一行** —— 散在每一行的 guard 漏掉一处不会有任何信号；
     入口只有一处，漏了整条路不通。⇒ `collect()` 在采集完当场建好归属索引。
  2. 🔴 **归属校验用 `OEMRouter.resolve()`，不用 `guard()`** —— 该步唯一要判定的是「这个
     项目自己声明的归属，是不是一个真实注册的 OEM」，没有「调用方 OEM 身份」这第二根轴，
     把 `resolve()` 的返回值再传回 `guard()` 做「自己与自己比」，该分支永远为真。
     ⚠️ **例外是 `read_phase_as()`／`isolated_view()`**：那里的第二根轴是**真的**（视图属主
     ≠ 数据属主），故照 `guard()` 的本意使用它，跨库拒绝与留痕都走平台既有路径。
  3. **`AuditEvent.oem_context` 填法** —— 逐项目事件填该项目 `oem_customer`；汇总类事件填
     本次覆盖到的已注册 OEM 显示名，字典序去重逗号连接（见 `audit_oem_context()`）。
  4. 规范 §3.3「`rag.retrieve()` 唯一入口」不卡本包 —— 该条射程是 Chroma/RAG 检索路径，
     FI10 走 U9C 关系型取数。

**`D11` 物料的 OEM 归属 ＝ 关联项目客户的集合，多值按最严**：物料↔项目是多对多，FI9 的
「项目→客户」一对一三态在此不够用。🔴 **`NO_LINKED_PROJECT`（无关联项目／通用料）与
`OWNERSHIP_UNJUDGED`（关联项目归属未判）两个哨兵不得合并** —— 合并即等于让「这个料谁都不
专属」和「压根没人看过这个料属于谁」变成同一件事，后者会被静默当通用料放行（与 FI9
`None` vs `NON_OEM_PROJECT` 同族错误，design 风险表第三行点名）。
⚠️ 「多值按最严」只解决**数据可见性**，**不解决跌价额在多项目间的分摊** —— 那是业务口径，
落 design Open Questions `FI10-G-05`，随 `tasks 2.3` 同批问主笔，**本模块不代拟**。
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer import OEMRouter

from . import config
from .models import BomUsage, InTransitPo, InventoryAging, OemProjectPhase

# ── 数据源模式 ────────────────────────────────────────────────────────────────
MODE_MOCK = "mock"
MODE_REAL = "real"
_MODES = (MODE_MOCK, MODE_REAL)

# ── 🔴 D11 两个哨兵：语义相反，**刻意不共用表示** ──────────────────────────────
#: 无关联项目（通用料）—— 走《OEM 数据隔离规范》§2.3 通用层，不是错误。
NO_LINKED_PROJECT = "__NO_LINKED_PROJECT__"
#: 关联项目的归属未判 —— fail-loud，**不得静默当通用料**。
OWNERSHIP_UNJUDGED = "__OWNERSHIP_UNJUDGED__"
#: 归属已判且属一个或多个已注册 OEM。
OWNERSHIP_OEM = "__OWNERSHIP_OEM__"

# ── mock 模式专用 OEM 注册表 ──────────────────────────────────────────────────
#: 🔴 **只为 mock 夹具而存在**，与平台 `REGISTERED_OEMS` 无交集（有用例守）。
#:
#: 成因是两条硬要求在 mock 模式下相撞：spec 场景「夹具不得含真实客户名」要求夹具用占位名
#: （夹具里放真名 ＝ 把隔离边界的第一道口子开在测试数据上），而 `D5` 要求归属校验必须过
#: `OEMRouter.resolve()`，占位名在平台注册表里必然未注册、一 resolve 就被拒。两者只能靠
#: 「mock 模式换一份注册表」同时满足。
#: ⚠️ **另两条路都更坏**：把占位名塞进平台 `REGISTERED_OEMS`，等于在生产注册表里凭空多出
#: 两个"客户"；mock 模式绕开 router，则 `D5`／`tasks 3.3` 在唯一能真跑的模式里失去覆盖。
#: 🔴 本表**不是口径**（不是待签认的业务口径，只是夹具的注册形态），故不进任何口径注册表。
MOCK_OEM_REGISTRY: dict[str, str] = {
    "OEM-占位甲": "mock_oem_placeholder_a",
    "OEM-占位乙": "mock_oem_placeholder_b",
    "OEM-占位丙": "mock_oem_placeholder_c",
}

#: 一个项目挂多个料时的分隔符 —— CSV 的 `,` 已被列分隔占用。
MATERIAL_ID_SEP = ";"

_DEFAULT_MOCK_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"

_FILES = {
    "inventory_aging": "inventory_aging.csv",
    "in_transit_po": "in_transit_po.csv",
    "bom_usage": "bom_usage.csv",
    "oem_project_phase": "oem_project_phase.csv",
}


class ChannelNotVerifiedError(RuntimeError):
    """真实源取数通道未核实时抛出（`tasks 3.1`）。

    🔴 fail-loud 且**不得回退 mock**：静默回退会把合成数据送进以为自己拿到真实账龄的调用方，
    而跌价计提是进财务报表的数——这一类错发现得最晚、代价最大。
    """


class OwnershipUnjudgedError(RuntimeError):
    """物料关联的项目归属未判时抛出（`D11`）。

    🔴 与「无关联项目」严格区分：后者是通用料、正常放行；本错误说的是**没人判过**，
    静默当通用料放行等于让未判的 OEM 明细流进通用层。
    """


def _resolve_mode(mode: Optional[str]) -> str:
    """默认模式取 `config.DATA_SOURCE_DEFAULT`，本层不自定第二个默认值（免得两处漂）。"""
    resolved = (mode or config.DATA_SOURCE_DEFAULT or "").strip().lower()
    if resolved not in _MODES:
        raise ValueError(
            f"未知数据源模式 {resolved!r}，只接受 {_MODES}。"
            "🔴 不兜底成 mock：把 'real' 拼错却静默拿到合成数据，与回退 mock 是同一类事故。"
        )
    return resolved


def build_router(mode: Optional[str] = None, audit: AuditLogger | None = None) -> OEMRouter:
    """按模式构造 OEM router：mock 模式用 `MOCK_OEM_REGISTRY`，real 模式用平台注册表。

    `audit` 不传时由 `OEMRouter` 自己内建平台默认审计器（拒绝必留痕，见其 docstring）。
    """
    resolved = _resolve_mode(mode)
    if resolved == MODE_MOCK:
        return OEMRouter(registered=dict(MOCK_OEM_REGISTRY), audit=audit)
    return OEMRouter(audit=audit)


# ══ OEM 归属：取数入口一次判定（D5-1／D5-2）════════════════════════════════════
def resolve_phase_owner(phase: OemProjectPhase, router: OEMRouter) -> str:
    """在取数入口对单个 OEM 项目解析一次归属，返回客户**显示名**。

    🔴 只读 `phase.oem_customer`，绝不检视 `project_id`／`phase`：从命名规则推导归属推错了
    不报错，而一错就是把 A 客户的物料记到 B 客户名下。

    · `oem_customer` 为空／空白 ⇒ 抛 `OwnershipUnjudgedError`（**未判 ≠ 通用料**）；
    · 非空但未注册（含拼写变体）⇒ `router.resolve()` 内部 fail-closed 并写审计，抛
      `CrossOEMAccessError`，本函数不吞；
    · 已注册 ⇒ 返回显示名（不是内部 collection key），与 `AuditEvent.oem_context` 的既有
      填法保持一致。
    """
    oem = (phase.oem_customer or "").strip()
    if not oem:
        raise OwnershipUnjudgedError(
            f"OEM 项目 {phase.project_id!r} 的 `oem_customer` 为空 ＝ 归属未判"
            f"（哨兵 {OWNERSHIP_UNJUDGED}）。🔴 不得当通用料放行——「没人判过」与"
            "「这个项目不专属任何客户」是两件事，共用一个表示就再也分不开。"
        )
    router.resolve(oem)  # 校验副作用：未注册/拼写变体在此 fail-closed 并留痕
    return oem


def read_phase_as(view_oem: str, phase: OemProjectPhase, router: OEMRouter) -> OemProjectPhase:
    """以 `view_oem` 的身份读一条 OEM 项目数据；跨客户即抛 `CrossOEMAccessError`（`tasks 3.3`）。

    ⚠️ **这里用 `guard()` 与 `D5-2`「不用 guard()」不矛盾**：`D5-2` 说的是归属校验那一步
    （`resolve_phase_owner`）没有第二根轴；本函数的第二根轴是真的 —— **视图属主 ≠ 数据属主**，
    正是 `guard()` 要判的那件事，且拒绝留痕直接走平台既有路径（规范 §3.2）。
    """
    target = router.resolve(resolve_phase_owner(phase, router))
    router.guard(oem=view_oem, collection=target)   # 跨客户在此抛 CrossOEMAccessError ＋ 留痕
    return phase


def isolated_view(view_oem: str, phases: Iterable[OemProjectPhase],
                  router: OEMRouter) -> tuple[OemProjectPhase, ...]:
    """某个 OEM 的隔离视图：只返回本客户的项目，**不靠调用方自己记得过滤**。

    🔴 `D11`「多值按最严」的可见性一半在此落地：共用料因为同时挂在多个客户的项目上，
    进**任一** OEM 的视图都会出现（明细逐客户拆行），不做「一料一主项目」的压缩。
    """
    own_collection = router.resolve(view_oem)
    kept: list[OemProjectPhase] = []
    for phase in phases:
        if router.resolve(resolve_phase_owner(phase, router)) == own_collection:
            kept.append(phase)
    return tuple(kept)


@dataclass(frozen=True)
class MaterialOwnership:
    """一个物料的 OEM 归属（`D11`）：状态 ＋ 客户集合。"""

    material_id: str
    state: str                       # NO_LINKED_PROJECT | OWNERSHIP_UNJUDGED | OWNERSHIP_OEM
    owners: tuple[str, ...] = ()     # 已注册 OEM 显示名，字典序去重
    project_ids: tuple[str, ...] = ()

    @property
    def is_general(self) -> bool:
        """是否走通用层 —— 🔴 只有「无关联项目」为真；「归属未判」恒为假。"""
        return self.state == NO_LINKED_PROJECT


def classify_material_ownership(material_id: str, phases: Iterable[OemProjectPhase],
                                router: OEMRouter) -> MaterialOwnership:
    """把一个物料的 OEM 归属判成三态之一（`D11`）。

    · 无任何关联项目 ⇒ `NO_LINKED_PROJECT`，`owners` 空集，走通用层；
    · **任一**关联项目归属未判 ⇒ `OWNERSHIP_UNJUDGED`（按最严：已判的那半不得把未判的那半
      盖过去，否则这个料看起来归属清楚，而未判的部分就此消失）；
    · 其余 ⇒ `OWNERSHIP_OEM`，`owners` ＝ 关联项目客户的**集合**（字典序去重，多值保留）。
    """
    linked = [p for p in phases if material_id in (p.material_ids or [])]
    if not linked:
        return MaterialOwnership(material_id=material_id, state=NO_LINKED_PROJECT)

    owners: set[str] = set()
    unjudged = False
    for phase in linked:
        try:
            owners.add(resolve_phase_owner(phase, router))
        except OwnershipUnjudgedError:
            unjudged = True     # 按最严：不 break，仍把其余项目走一遍（未注册名照样要被拒）
    project_ids = tuple(p.project_id for p in linked)
    if unjudged:
        return MaterialOwnership(material_id=material_id, state=OWNERSHIP_UNJUDGED,
                                 project_ids=project_ids)
    return MaterialOwnership(material_id=material_id, state=OWNERSHIP_OEM,
                             owners=tuple(sorted(owners)), project_ids=project_ids)


def require_owners(ownership: MaterialOwnership) -> tuple[str, ...]:
    """取归属客户集合；归属未判即 fail-loud（`D11`）。通用料返回空集，是正常态。"""
    if ownership.state == OWNERSHIP_UNJUDGED:
        raise OwnershipUnjudgedError(
            f"物料 {ownership.material_id!r} 的关联项目 {ownership.project_ids} 归属未判"
            f"（哨兵 {OWNERSHIP_UNJUDGED}）。🔴 不得静默当通用料"
            f"（那是另一个哨兵 {NO_LINKED_PROJECT}，语义相反）。"
        )
    return ownership.owners


def audit_oem_context(owners: Sequence[str]) -> str:
    """`AuditEvent.oem_context` 的填法（`D5-3`）：字典序去重逗号连接；空集填通用料哨兵。

    🔴 空集**不填空串** —— 空串在审计记录里读不出「这是通用料」还是「忘填了」。
    """
    unique = sorted({(o or "").strip() for o in owners if (o or "").strip()})
    return ",".join(unique) if unique else NO_LINKED_PROJECT


# ══ 在途量：与 kit_engine 同口径（tasks 3.2）════════════════════════════════════
def qty_in_transit_by_material(pos: Iterable[InTransitPo]) -> dict[str, float]:
    """按物料汇总在途量 ＝ Σ(已订 − 已收)。

    🔴 口径**刻意与 `zhuopin_platform.agents.kit_engine.calc_shortage` 对齐、不另立一套**
    （spec：同一个概念在两个场景里算出两个数，是最难查的一类不一致）。用例不是重抄一遍
    公式，而是拿 `calc_shortage` 真跑一次反解它眼里的在途量做交叉核对。
    """
    totals: dict[str, float] = {}
    for po in pos:
        totals[po.material_id] = totals.get(po.material_id, 0.0) + po.qty_in_transit
    return totals


# ══ 采集入口 ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class IntakeBundle:
    """一个测算基准日的采集结果 —— 三类输入齐备 ＋ 各带来源引用（spec 场景）。"""

    as_of_date: str
    mode: str
    aging: tuple[InventoryAging, ...]
    in_transit: tuple[InTransitPo, ...]
    bom_usage: tuple[BomUsage, ...]
    oem_phases: tuple[OemProjectPhase, ...]
    ownership: dict[str, MaterialOwnership] = field(default_factory=dict)
    #: 各输入的来源引用（spec「各带来源引用」）。形状与 `AuditEvent.data_sources` 一致，
    #: 可直接塞进审计事件 —— 不另造一套来源表示。
    data_sources: dict[str, str] = field(default_factory=dict)

    def qty_in_transit_by_material(self) -> dict[str, float]:
        return qty_in_transit_by_material(self.in_transit)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"mock 夹具缺失：{path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh)]


def _to_bool(raw: str) -> bool:
    """CSV 里的 `True/False` 是字符串 —— 直接 `bool("False")` 恒为真，是一处经典静默错。"""
    return (raw or "").strip().lower() in {"true", "1", "yes", "y"}


def collect(as_of_date: str, mode: Optional[str] = None, base_dir: Optional[Path] = None,
            audit: AuditLogger | None = None, router: OEMRouter | None = None) -> IntakeBundle:
    """采集某个测算基准日的四类输入，并在**取数入口**一次判完 OEM 归属（`D5-1`）。

    🔴 `mode="real"` ⇒ 抛 `ChannelNotVerifiedError`，**在读任何夹具之前**：U9C 库存通道与
    PLM 取数通道两条都未核实、且都无主（design Open Questions **B-1**，`tasks 3.1` 必测）。
    通道核实是待派发项，不是本层能自行解除的——故此处只 fail-loud，不留任何开关。

    🔴 源里出现归属未判的 OEM 项目 ⇒ 当场抛 `OwnershipUnjudgedError`，不带进下游
    （`D11`：不得静默当通用料）。
    """
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == MODE_REAL:
        raise ChannelNotVerifiedError(
            "FI10 采集层 real 模式不可用 —— 两条真实源通道均未核实、且都无主"
            "（design Open Questions B-1，待总线派发）：\n"
            f"  · U9C 库存通道：{config.U9C_INVENTORY_NOT_READY}\n"
            f"  · PLM 项目通道：{config.PLM_PROJECT_CHANNEL_NOT_READY}\n"
            "🔴 一律 fail-loud、不得回退 mock：静默回退会把合成数据送进以为自己拿到真实"
            "账龄的调用方，而跌价计提是进财务报表的数。"
        )

    mock_dir = Path(base_dir) if base_dir is not None else _DEFAULT_MOCK_DIR
    active_router = router if router is not None else build_router(resolved_mode, audit=audit)

    aging = tuple(
        InventoryAging(
            material_id=r["material_id"],
            material_name=r["material_name"],
            batch_no=r["batch_no"],
            qty=float(r["qty"]),
            unit_cost=float(r["unit_cost"]),
            aging_days=int(r["aging_days"]),
            warehouse=r.get("warehouse", ""),
            as_of_date=r.get("as_of_date", ""),
        )
        for r in _read_csv(mock_dir / _FILES["inventory_aging"])
    )
    in_transit = tuple(
        InTransitPo(
            po_no=r["po_no"],
            material_id=r["material_id"],
            qty_ordered=float(r["qty_ordered"]),
            qty_received=float(r["qty_received"]),
            unit_price=float(r["unit_price"]),
            eta=r.get("eta", ""),
        )
        for r in _read_csv(mock_dir / _FILES["in_transit_po"])
    )
    bom_usage = tuple(
        BomUsage(
            material_id=r["material_id"],
            product_id=r["product_id"],
            qty_per_unit=float(r["qty_per_unit"]),
            active=_to_bool(r.get("active", "")),
        )
        for r in _read_csv(mock_dir / _FILES["bom_usage"])
    )
    oem_phases = tuple(
        OemProjectPhase(
            project_id=r["project_id"],
            oem_customer=r["oem_customer"],      # 🔴 必填、无默认值：空即归属未判，下方入口炸
            phase=r["phase"],
            material_ids=[m.strip() for m in (r.get("material_ids") or "").split(MATERIAL_ID_SEP)
                          if m.strip()],
            phase_date=r.get("phase_date", ""),
        )
        for r in _read_csv(mock_dir / _FILES["oem_project_phase"])
    )

    # ── 🔴 D5-1：guard 就调这一次，在取数入口 ──
    for phase in oem_phases:
        resolve_phase_owner(phase, active_router)

    material_ids = {a.material_id for a in aging} | {p.material_id for p in in_transit} \
        | {b.material_id for b in bom_usage}
    for phase in oem_phases:
        material_ids |= set(phase.material_ids)
    ownership = {
        mid: classify_material_ownership(mid, oem_phases, active_router)
        for mid in sorted(material_ids)
    }

    data_sources = {
        key: f"mock:{(mock_dir / name).as_posix()}"
        for key, name in _FILES.items()
    }
    return IntakeBundle(
        as_of_date=as_of_date,
        mode=resolved_mode,
        aging=aging,
        in_transit=in_transit,
        bom_usage=bom_usage,
        oem_phases=oem_phases,
        ownership=ownership,
        data_sources=data_sources,
    )
