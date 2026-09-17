"""数据源：`mock`（合成样本，可入库）／`qda`（接 QD-A 抽取层，置信度 fail-loud 标注）。

🔴 真实 8D 原文一律不入 git（QD-A 红线 1）。档 1 只用 `data/mock/samples.json` 的合成样本——它们按验收集
（`Q2-8D验收集-标签与退回理由-2026-09-17.md`）10 份的**场景标签与退回理由形态**仿写，**不含任何真实报告文字**；
7 条退回理由只作判据对照（`expected`），不是抽取输入。

`qda` 通道：输入 QD-A `DocumentSections.sections`（D 段全文＝正确承接点，评估件 §5.1）＋ `EightDRecord`
（只取 `safety_related` 与红线④追溯字段）。QD-A 总体命中率实测 37.9%、低于 60% MVP 门槛 ⇒ 本通道把每个
字段的置信度**原样带入**，`LOW`／`MED` 一律不当已确认输入（P2）；`safety_related` 非 HIGH ⇒ 引擎转人工。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config
from .models import Confidence, EightDInput, TraceField

_HERE = Path(__file__).resolve().parent
MOCK_PATH = _HERE.parent / "data" / "mock" / "samples.json"


def _to_doc(raw: dict[str, Any]) -> EightDInput:
    tf = tuple(TraceField(t["name"], t.get("value", ""), Confidence(t.get("confidence", "LOW"))) for t in raw.get("trace_fields", []))
    return EightDInput(
        report_id=raw["report_id"], sections=dict(raw["sections"]), scene=raw.get("scene"),
        template=raw.get("template", "标准8D"), safety_related=raw.get("safety_related"),
        safety_confidence=Confidence(raw.get("safety_confidence", "LOW")), asil_level=raw.get("asil_level", ""),
        trace_fields=tf, is_external=bool(raw.get("is_external", False)), meta={"source": "mock", **raw.get("meta", {})},
    )


def load_mock() -> list[tuple[EightDInput, dict[str, Any]]]:
    """返回 (输入, expected 对照) 列表；expected 只在测试里消费。"""
    data = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    return [(_to_doc(r), r.get("expected", {})) for r in data["samples"]]


def from_qda(report_id: str, sections: dict[str, str], record: Any | None, *, scene: str | None,
             template: str = "标准8D", oem: str = "") -> EightDInput:
    """QD-A 适配：`record` 为 `qda_prefill.field_extractor.EightDRecord`（可 None）。

    置信度按 QD-A 字面（HIGH/MED/LOW）原样带入；不做任何「MED 当 HIGH」的抬升。
    """
    safety, safety_conf = None, Confidence.LOW
    trace: list[TraceField] = []
    if record is not None:
        sr = record.safety_related
        safety_conf = Confidence(sr.confidence.value)
        safety = {"是": True, "否": False}.get(sr.value.strip(), None)
        # 追溯字段：QD-A 12 字段里没有「零件号／批次／发生时间」专字段，这里只能把 D2 交给引擎派生；
        # 派生结果的置信度由 redlines.derive_trace_fields 标（命中 HIGH／未命中 LOW），不在此处冒充 HIGH。
    return EightDInput(report_id=report_id, sections=dict(sections), scene=scene, template=template,
                       safety_related=safety, safety_confidence=safety_conf, trace_fields=tuple(trace),
                       meta={"source": "qda", "oem": oem, "qda_hit_rate_note": "QD-A 总体命中率实测 37.9%（<60% 门槛），字段不得当已确认输入"})


def load(source: str | None = None) -> list[tuple[EightDInput, dict[str, Any]]]:
    src = (source or config.DATA_SOURCE_DEFAULT).lower()
    if src == "mock":
        return load_mock()
    if src == "qda":
        raise RuntimeError("`qda` 通道须由调用方逐份传入 QD-A 解析结果（from_qda），不提供目录批量读取——真实 8D 不入库、不在此处落盘")
    raise ValueError(f"未知数据源 {src!r}（可选：mock／qda）")
