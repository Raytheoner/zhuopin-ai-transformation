"""#592 第一批验收对照表：用 Q2 引擎对 10 份真实验收集样本逐份跑评审，对照陈忱 2026-09-14 原始判定。

🔴 真实 8D 原文一律不入 git（QD-A 红线 1）：本脚本只按绝对路径只读主仓 `7-外部文档/`，
不把原文抄进任何被跟踪文件；输出落 `reports/`（本目录 `.gitignore` 已排除）。

本脚本是**一次性校准工具**，不是档 2 生产接线——QD-A→Q2 的正式生产对接（含把
`SceneCheckbox.scene` 接进 webapp 请求路径）仍是 LAN 留步项，见 Q2 CLAUDE.md 时间线。

用法：python scripts/run_acceptance_calibration.py [--source-dir PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# —— 平台底座路径引导（唯一被允许的样板，见 5-平台底座/zhuopin_platform/bootstrap.py docstring）——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

# QD-A 前置抽取层是独立 Python 包（同一 monorepo 下的兄弟场景目录），非 pip 可装状态，
# 沿用 tests/conftest.py 同族做法显式挂路径。
_QDA_DIR = _HERE.parents[2] / "QD-A-8D不良分析"
if str(_QDA_DIR) not in sys.path:
    sys.path.insert(0, str(_QDA_DIR))

from zhuopin_platform.audit import AuditLogger, JsonlSink  # noqa: E402

from q2_8d_verdict import feed_source  # noqa: E402
from q2_8d_verdict.engine import AsilExcludedError, VerdictEngine  # noqa: E402
from q2_8d_verdict.models import Disposition, RedlineStatus  # noqa: E402
from qda_prefill import doc_reader  # noqa: E402

# 本机默认主仓绝对路径（worktree 不共享 gitignore 真实件，只能按绝对路径读主仓；
# 见队列 §一 #592 opener：「真实 8D 原件在主仓…worktree 内看不见,按绝对路径只读」）。
_DEFAULT_SOURCE_DIR = Path(r"C:\Dev\zhuopin-ai\7-外部文档\质量部\8D验收集-2026-09-10")

# 验收集全表（唯一来源＝Q2-8D验收集-标签与退回理由-2026-09-17.md §二，逐字对齐，不重新转录判据）。
GROUND_TRUTH: list[dict] = [
    {"short_id": "A", "subdir": "合格", "filename": "EQ20控制器漏贴标签问题8D报告.pptx",
     "group": "边界样本（原合格组）", "scene": "制造", "external": None, "reason": None},
    {"short_id": "B", "subdir": "合格", "filename": "EQ42-C2 元器件虚焊8D报告.pptx",
     "group": "合格", "scene": "制造", "external": None, "reason": None},
    {"short_id": "C", "subdir": "合格", "filename": "EQ42-C2电磁阀采集电流偏大问题8D报告.pptx",
     "group": "合格", "scene": "制造", "external": None, "reason": None},
    {"short_id": "1", "subdir": "不合格", "filename": "LEM800B-90(EQ07-3) K6针脚频率采集异常问题8D分析报告(2)(1).pptx",
     "group": "不合格", "scene": "制造", "external": "客户侧模板",
     "reason": "预防措施未固化到流程资产：D7完全未提及控制计划(CP)更新，也未提及FMEA/PFMEA更新，仅更新了作业规范和巡检表，触发红线。"},
    {"short_id": "2", "subdir": "不合格", "filename": "俄罗斯自动熄火8D报告.pptx",
     "group": "不合格", "scene": "研发", "external": None,
     "reason": "关键追溯信息缺失：研发场景缺失ECU型号/软硬件版本，触发红线。预防措施未固化到流程资产：D7未提及DFMEA更新、测试用例补充或设计规范更新，触发红线。"},
    {"short_id": "3", "subdir": "不合格", "filename": "保定TCU无法通讯8D分析报告.pptx",
     "group": "不合格", "scene": "制造 ※（见验收集正本§四，未决不得自行解释）", "external": None,
     "reason": "D7预防措施未固化到流程资产：D7完全未提及控制计划(CP)更新，也完全未提及FMEA/PFMEA更新，两者均未提及，触发红线。"},
    {"short_id": "4", "subdir": "不合格", "filename": "透气阀损坏分析报告.pptx",
     "group": "不合格", "scene": "制造", "external": None,
     "reason": "结构性缺段：七步法第五~七步全空；D4 无根因（仅「制造现场发生可能性较小」），根因未到底层（红线①）、D5永久措施内容完全空白（红线②）未验证（红线⑤）、D7 未固化（红线⑥）。"},
    {"short_id": "5", "subdir": "不合格", "filename": "EQ15-2 BGA开裂-8D报告.pptx",
     "group": "不合格", "scene": "制造", "external": "供应商编制",
     "reason": "根因未分析或分析未到底层：根因分析未到底层，最终根因停留在'外部应力导致BGA焊点开裂'，未进一步分析应力的具体来源（如工装设计缺陷、操作规范缺失等可对应具体预防措施的末端原因），且5Why仅追问到第3层即停止（红线①）；D4 根因未验证（红线⑤）。D7 固化表中 FMEA/CP 均填 N，未实际固化（按 J2 口径视同未提，红线⑥）。"},
    {"short_id": "6", "subdir": "不合格", "filename": "EQ15SY沙特不良分析8D报告.pptx",
     "group": "不合格", "scene": "制造", "external": None,
     "reason": "根因未分析或分析未到底层（红线①）；问题描述无任何客观数据（红线③）；D2 关键追溯信息缺失（型号/批次/时间缺两项以上，红线④）；根因未经验证（红线⑤）；D7 未固化（红线⑥）。"},
    {"short_id": "7", "subdir": "不合格", "filename": "EQ15不良分析报告.pptx",
     "group": "不合格", "scene": "制造", "external": None,
     "reason": "D2 追溯缺失（红线④）；D4 根因停留在「不小心撞击」表述，未下探到工艺/管理层（红线①）。"},
]

# 红线②③本批不验收（判例 11，J8 甲），此处仅作展示口径提醒，不参与准确率判断——见验收集正本 §三.3。
REDLINES_NOT_ACCEPTED_THIS_BATCH = (2, 3)

_REDLINE_DESC = {1: "①D4根因未到底层", 2: "②章节错位", 3: "③D2无客观数据",
                 4: "④关键追溯缺失", 5: "⑤D4根因未验证", 6: "⑥D7未固化"}


@dataclass
class SampleResult:
    short_id: str
    filename: str
    truth_group: str
    truth_reason: str | None
    extracted_d_keys: list[str]
    ai_scene: str | None
    scene_ambiguous: bool
    structural_return: bool
    structural_empty: tuple[str, ...]
    redlines_triggered: list[int]
    redlines_suspected: list[int]
    grade: str | None
    grade_range: tuple[str, str]
    disposition: str
    notes: tuple[str, ...]
    error: str | None = None
    redlines_all: tuple[tuple[int, str, str], ...] = ()   # (编号, 状态, 证据)，含 CLEAR/MANUAL_CHECK/NOT_ACCEPTED，供完整透明


def run_one(entry: dict, source_dir: Path, engine: VerdictEngine) -> SampleResult:
    path = source_dir / entry["subdir"] / entry["filename"]
    if not path.exists():
        return SampleResult(entry["short_id"], entry["filename"], entry["group"], entry["reason"],
                             [], None, False, False, (), [], [], None, ("", ""), "", (),
                             error=f"文件不存在：{path}")
    doc_sections = doc_reader.read(path)
    scene_cb = doc_sections.scene_checkbox
    ai_scene = scene_cb.scene if (scene_cb and not scene_cb.ambiguous) else None
    ai_doc = feed_source.from_qda(report_id=f"验收集-{entry['short_id']}", sections=doc_sections.sections,
                                   record=None, scene=ai_scene, template="标准8D")
    try:
        v = engine.evaluate(ai_doc)
    except AsilExcludedError as e:
        return SampleResult(entry["short_id"], entry["filename"], entry["group"], entry["reason"],
                             sorted(doc_sections.sections), ai_scene, bool(scene_cb and scene_cb.ambiguous),
                             False, (), [], [], None, ("", ""), "", (), error=str(e))
    return SampleResult(
        short_id=entry["short_id"], filename=entry["filename"], truth_group=entry["group"], truth_reason=entry["reason"],
        extracted_d_keys=sorted(doc_sections.sections), ai_scene=v.scene, scene_ambiguous=bool(scene_cb and scene_cb.ambiguous),
        structural_return=v.structural_return, structural_empty=v.structural_empty_sections,
        redlines_triggered=sorted(r.redline_no for r in v.redlines if r.status == RedlineStatus.TRIGGERED),
        redlines_suspected=sorted(r.redline_no for r in v.redlines if r.status == RedlineStatus.SUSPECTED),
        grade=v.grade, grade_range=v.grade_range, disposition=v.disposition.value, notes=v.notes,
        redlines_all=tuple((r.redline_no, r.status.value, r.evidence) for r in sorted(v.redlines, key=lambda x: x.redline_no)),
    )


def extraction_quality(keys: list[str]) -> str:
    if not keys:
        return "抽取完全未命中（0/7）——该份大概率用「一、二、三…」中文序号式模板，非「D1.」格式，doc_reader 现有 fallback 规则不覆盖"
    if len(keys) <= 2:
        return f"抽取仅命中 {len(keys)}/7 段，覆盖率过低，判定证据不足"
    if len(keys) < 7:
        return f"抽取命中 {len(keys)}/7 段，部分缺口"
    return "抽取命中 7/7 段，覆盖完整"


def consistency(r: SampleResult) -> tuple[str, str]:
    """粗判方向是否一致；不代替人工，只标方向。抽取命中率过低时不把「方向凑巧一致」算真验证。"""
    if r.error:
        return "⚠️ 异常", r.error
    # 样本 A 是「边界样本」，口径已由陈忱签认（验收集正本 §三.1）：红线⑥应按字面触发判 D，
    # 这不是误判，是标定 AI 对「勉强合格」容忍度的设计意图本身。
    if r.short_id == "A":
        if r.redlines_triggered == [6]:
            return "方向一致（口径预期）", "验收集正本 §三.1 已签认：A 应触发红线⑥判 D，用于标定 AI 对「勉强合格」的容忍度，AI 结果与该口径一致"
        return "方向不一致", f"口径预期 A 应触发红线⑥判 D，AI 实际红线触发={r.redlines_triggered}，与签认口径不符，需复核"
    truth_ok = r.truth_group.startswith("合格")
    ai_clean = (not r.structural_return) and (not r.redlines_triggered) and r.disposition != Disposition.STRUCTURAL_RETURN.value
    if truth_ok:
        if ai_clean:
            return "方向一致", "陈忱判合格，AI 未出结构退回或红线触发"
        return "方向不一致", f"陈忱判{r.truth_group}，AI 却出结构退回={r.structural_return}／红线触发={r.redlines_triggered}——需查是否解析取段有误"
    # 不合格组
    if not (r.structural_return or r.redlines_triggered):
        return "方向不一致（疑似漏判）", "AI 未触发任何红线也未结构退回，但陈忱当时判不合格——大概率是真实文档 D 段抽取未命中证据（QD-A 命中率实测 37.9%），不是判据本身有误"
    if len(r.extracted_d_keys) <= 2:
        return "方向表面一致·但证据不足（假阳性风险）", f"结构退回={r.structural_return} 与「不合格」方向一致，但 {extraction_quality(r.extracted_d_keys)}——退回判断是「抽取失败导致全段皆空」触发判例 9，不是真的识别到七步法缺段，不能当作本条判据的有效验证样本"
    return "方向一致", f"结构退回={r.structural_return}／红线触发={r.redlines_triggered}，与「不合格」方向一致，{extraction_quality(r.extracted_d_keys)}"


def render_report(results: list[SampleResult]) -> str:
    lines = [
        "# Q2 · 第一批验收对照表（草稿）",
        "",
        "> 数据来源：主仓 `7-外部文档/质量部/8D验收集-2026-09-10/`（真实 8D 原件，只读，不入 git）；",
        "> 判据对照来源：`4-数字员工/质量部/QD-A-8D不良分析/Q2-8D验收集-标签与退回理由-2026-09-17.md`（陈忱 2026-09-14 回件正本）。",
        "> 承接：队列 §一 `#592`；本表为草稿，供 10-16 前交陈忱，不代表已签认结论。",
        "",
        "## 使用前必读的六条已知缺口（本轮不掩盖）",
        "",
        "1. **安全相关字段未接**：本轮未跑 QD-A `field_extractor` 抽取 `safety_related`，"
        "`from_qda(record=None)` 恒为「未确认」（LOW），按判例 6，引擎对全部 10 份统一给出"
        "「转人工裁决」的**最终处置建议**——这是本轮已知的接线缺口，不能读成「AI 判定全部转人工＝没用」，"
        "比对应看下方**结构闸／红线触发／等级区间**这几列，不要只看「处置建议」列。",
        "2. **场景勾选行**：这 10 份是 2026-09-10 归集的历史 8D，多数早于 09-19 才定的 PPT D2 页"
        "「场景（必选）」勾选行模板改版，`extract_scene_checkbox` 大概率读不到、按 J7 兜底口径落"
        "「制造＋场景未标注」——样本 2（研发）与样本 3（※ 未决）尤其要核对下表 `AI场景` 列。",
        "3. **红线编号非逐字对应**：下表「AI 红线触发」用的是 Q2 canonical 编号"
        "（①D4根因未到底层／②章节错位／③D2无客观数据／④关键追溯缺失／⑤D4根因未验证／⑥D7未固化），"
        "陈忱回件原文里的「红线①②…」是她原始表述、编号含义**不保证与上面一一对应**"
        "（如样本 4 原文「D5永久措施空白（红线②）」，Q2 canon 的②是「章节错位」，两者字面不同）——"
        "本表**不代猜、不强行拉齐**，`陈忱当时退回理由（原文）` 一列照录原文，与 AI 判定并列展示，"
        "由人工判断是否指向同一处缺陷。",
        "4. **红线②③本批不验收**（判例 11，J8 甲）：这两条 Q2 恒返回「本批不验收·转人工」，"
        "不计入准确率，验收集正本 §三.3 已定。",
        "5. **样本 A 触发红线⑥判 D 不是误判**：验收集正本 §三.1 已签认——A 是「边界样本」，"
        "AI 按字面判 D 正是标定「AI 对勉强合格的容忍度」的设计意图，不应算作不一致。",
        "6. **本表新发现的抽取兼容缺口（本轮首次实测，此前从未跑过真实件）**：样本 1／3 用"
        "「一、二、三…」中文序号式模板（非「D1.」/「D1、」格式），`doc_reader` 现有规则"
        "0 命中；样本 4 仅命中 1/7 段。这几份的「结构退回」判断表面方向对，实际是抽取几乎"
        "全空触发判例 9 的**假阳性**，不能当作红线判据本身被验证——真正需要人核的是"
        "doc_reader 要不要新增「中文序号」标题识别（见逐份说明）。",
        "",
        "## 对照表",
        "",
        "| 短号 | 报告 | 陈忱当时判定 | AI 场景 | AI 结构闸 | AI 红线触发 | AI 红线疑似 | AI 等级/区间 | AI 处置建议 | 方向判断 |",
        "|:--:|---|---|---|:--:|---|---|:--:|---|---|",
    ]
    for r in results:
        if r.error:
            lines.append(f"| {r.short_id} | {r.filename} | {r.truth_group} | — | — | — | — | — | — | ⚠️ {r.error} |")
            continue
        scene_disp = r.ai_scene + ("（场景未标注，兜底）" if r.scene_ambiguous or r.ai_scene is None else "")
        g = r.grade or f"{r.grade_range[0]}–{r.grade_range[1]}"
        rl_trig = "、".join(str(n) for n in r.redlines_triggered) or "—"
        rl_susp = "、".join(str(n) for n in r.redlines_suspected) or "—"
        verdict, _ = consistency(r)
        lines.append(f"| {r.short_id} | {r.filename} | {r.truth_group} | {scene_disp} | "
                     f"{'退回' if r.structural_return else '过'} | {rl_trig} | {rl_susp} | {g} | {r.disposition} | {verdict} |")

    n_ok, n_fp_risk, n_miss, n_err = 0, 0, 0, 0
    for r in results:
        verdict, _ = consistency(r)
        if r.error:
            n_err += 1
        elif "假阳性风险" in verdict:
            n_fp_risk += 1
        elif "疑似漏判" in verdict or verdict == "方向不一致":
            n_miss += 1
        else:
            n_ok += 1
    lines += [
        "",
        "## 结论摘要（供陈忱快速判断，细节仍以逐份说明与原始 audit 为准）",
        "",
        f"- **可信验证且方向正确**：{n_ok}/10（含样本 A 的口径预期项）",
        f"- **表面方向对但因抽取失败无法算有效验证（假阳性风险）**：{n_fp_risk}/10——待排查 `doc_reader` 是否要扩展中文序号标题识别",
        f"- **真实漏判**（D 段抽取完整、但红线①③④未被触发/疑似）：{n_miss}/10——待排查是关键词预筛覆盖不足，还是要等语义层上线才能补",
        f"- **异常/文件缺失**：{n_err}/10",
        "",
        "## 逐份说明（不一致原因／需要人核对的点／全部红线状态）",
        "",
    ]
    for r in results:
        if r.error:
            lines.append(f"- **{r.short_id}**（{r.filename}）：⚠️ {r.error}")
            continue
        verdict, why = consistency(r)
        lines.append(f"- **{r.short_id}**（{r.filename}，D 段抽取命中 {r.extracted_d_keys or '无'}）："
                     f"{verdict}——{why}")
        if r.truth_reason:
            lines.append(f"  - 陈忱当时退回理由（原文）：{r.truth_reason}")
        if r.redlines_all:
            rl_line = "；".join(f"{_REDLINE_DESC.get(n, n)}={status}" for n, status, _ev in r.redlines_all)
            lines.append(f"  - 全部红线状态：{rl_line}")
        if r.notes:
            lines.append(f"  - AI notes：{'；'.join(r.notes)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", default=str(_DEFAULT_SOURCE_DIR))
    ap.add_argument("--out", default=str(_HERE.parent.parent / "reports"))
    a = ap.parse_args(argv)
    source_dir = Path(a.source_dir)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    engine = VerdictEngine(audit=AuditLogger(JsonlSink(out / "q2_acceptance_calibration_audit.jsonl")),
                           evaluator="Q2校准脚本-OP0923F")
    results = [run_one(entry, source_dir, engine) for entry in GROUND_TRUTH]
    report = render_report(results)
    report_path = out / "第一批验收对照表-草稿.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[已写入] {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
