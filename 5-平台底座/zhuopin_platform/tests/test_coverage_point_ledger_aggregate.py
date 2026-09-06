"""tasks §1.4 断言测试 —— **D3：跨域聚合只读、不产生任何合并落盘产物（含缓存）**。

主断言 ＝ `test_D3_跨域聚合只读不落盘_含缓存`：
在一份**五个域都有点**的 tmp 台账上调用 `aggregate()`，调用期间禁止一切写盘动作
（open 写模式／write_text／write_bytes／touch／mkdir，`io.open` 与 `builtins.open`
两条路都堵），调用前后对台账目录树与一个空的当前工作目录各做一次指纹比对
——两处指纹必须逐字节不变，且聚合确实读到了 ≥2 个域（防止「什么都没干」蒙混过关）。

🔴 本文件全部数据造在 `tmp_path`，**不碰仓库内那五份 0 字节 `.jsonl`**。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    chdir,
    create_event,
    make_store,
    no_disk_write_guard,
    transition_event,
    tree_fingerprint,
)

from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    Domain,
    Snapshot,
    Status,
    aggregate,
)


def _seed_all_domains(store):
    """五个域各造一个点（含一个已推进到 `在途` 的），返回 id 列表。"""
    ids = {
        Domain.PROCUREMENT: ("SC8-D19-01", "SC8"),
        Domain.FINANCE: ("FI2-D19-03", "FI2"),
        Domain.QUALITY: ("QD-B-D07-02", "QD-B"),
        Domain.SALES: ("S3-D04-01", "S3"),
        Domain.IT: ("IT5-D02-01", "IT5"),
    }
    for point_id, scene in ids.values():
        store.append(create_event(point_id, scene=scene))
    store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT, letters=("财务部#17",)))
    return ids


def test_D3_跨域聚合只读不落盘_含缓存(tmp_path):
    """**D3 主断言**：`aggregate()` 跨五个域聚合时，磁盘上不得多出、改动任何字节。

    断言四件事，缺一件这条测试就不成立：
      ⑴ 聚合期间任何写盘调用（含建目录、建空文件、缓存）立即抛 `WriteAttempted`；
      ⑵ 台账目录树指纹（路径 ＋ 字节数 ＋ sha256）调用前后完全一致；
      ⑶ 一个**空的当前工作目录**调用后仍为空 —— 抓写到相对路径的缓存产物；
      ⑷ 聚合确实读到了全部 5 个域 —— 否则「什么都没做」也能通过前三条。
    """
    store = make_store(tmp_path)
    _seed_all_domains(store)

    cwd_probe = tmp_path / "cwd探针"
    cwd_probe.mkdir()

    before_ledger = tree_fingerprint(store.ledger_dir)
    before_cwd = tree_fingerprint(cwd_probe)
    assert before_cwd == {}, "探针目录起始必须为空，否则 ⑶ 无意义"

    with chdir(cwd_probe):
        with no_disk_write_guard():
            snapshot = aggregate(store)

    # ⑷ 真的跨域了
    assert isinstance(snapshot, Snapshot)
    assert len(snapshot.domains_present) == 5, (
        f"聚合只覆盖到 {sorted(d.label for d in snapshot.domains_present)}，"
        f"未跨全部五个域——这条测试就没在测「跨域」"
    )
    assert len(snapshot.points) == 5

    # ⑵⑶ 磁盘逐字节不变
    assert tree_fingerprint(store.ledger_dir) == before_ledger, "台账目录被聚合改动了"
    assert tree_fingerprint(cwd_probe) == before_cwd, "聚合往当前工作目录落了产物（相对路径缓存）"


def test_D3_重复聚合不建缓存(tmp_path):
    """连续聚合两次仍然零写盘 —— 拦的是「第一次算完顺手缓存、第二次读缓存」那种写法。"""
    store = make_store(tmp_path)
    _seed_all_domains(store)
    before = tree_fingerprint(store.ledger_dir)

    with no_disk_write_guard():
        first = aggregate(store)
        second = aggregate(store)

    assert first.ids == second.ids
    assert tree_fingerprint(store.ledger_dir) == before


def test_D3_Snapshot无任何落盘方法():
    """`Snapshot`／`Point` 不得有 `save`／`dump`／`to_file`／`write_*` 之类的出口。

    🔑 D3 若只靠「调用方记得别调 save()」，就是又一条「靠人记得」的约束。
    这条断言保证那个方法**不存在**。
    """
    from zhuopin_platform.coverage_point_ledger import Point

    banned = ("save", "dump", "to_file", "write", "write_csv", "to_csv", "export", "flush")
    for cls in (Snapshot, Point):
        for name in dir(cls):
            assert not any(name.startswith(b) for b in banned), (
                f"{cls.__name__}.{name} 看起来是落盘出口；D3 禁止任何合并落盘产物（含缓存）"
            )


def test_守卫本身有效_写盘会被抓到(tmp_path):
    """**反向对照组**：守卫必须真能拦住写盘，否则上面三条全是假绿。

    🔑 一个从不失败的守卫和没有守卫是一回事，而两者在测试报告里长得一模一样。
    """
    from _coverage_point_ledger_helpers import WriteAttempted

    probe = tmp_path / "probe.txt"
    with pytest.raises(WriteAttempted):
        with no_disk_write_guard():
            probe.write_text("x", encoding="utf-8")

    with pytest.raises(WriteAttempted):
        with no_disk_write_guard():
            with open(tmp_path / "probe2.txt", "w", encoding="utf-8") as fh:
                fh.write("x")

    with pytest.raises(WriteAttempted):
        with no_disk_write_guard():
            (tmp_path / "cache").mkdir()

    # 守卫解除后写盘恢复正常（防止守卫泄漏污染后续测试）
    probe.write_text("ok", encoding="utf-8")
    assert probe.read_text(encoding="utf-8") == "ok"


def test_聚合结果可用于度量_事实日未知单列(tmp_path):
    """`事实日未知` 的点必须能被单独拎出来（SCHEMA §二）——不混入中位数的前提。"""
    from zhuopin_platform.coverage_point_ledger import FACT_DATE_UNKNOWN

    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    store.append(create_event("FI2-D19-04", scene="FI2", fact_date=FACT_DATE_UNKNOWN))

    snapshot = aggregate(store)
    unknown = snapshot.fact_date_unknown
    assert [p.id for p in unknown] == ["FI2-D19-04"]


def test_承接载体缺失可被扫出_价值指标基线(tmp_path):
    """tasks 6.3 质量型指标「承接载体缺失」数量必须可机器扫 —— 否则基线只能靠人数。"""
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    # tasks §2 回溯拆点里的历史点本来就可能没有承接载体 —— 那正是本包要度量的东西，
    # 故它必须**写得进去**（若写入期强制 ≥1，这个指标会结构性恒为 0）。
    store.append(create_event("FI2-D19-09", scene="FI2", carrier=()))

    snapshot = aggregate(store)
    assert [p.id for p in snapshot.missing_carrier] == ["FI2-D19-09"]
    assert snapshot.points["FI2-D19-03"].carriers == ("openspec:coverage-point-ledger",)
