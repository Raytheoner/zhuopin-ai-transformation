# -*- coding: utf-8 -*-
"""#439 tasks §2.1 回溯拆点（黄金集）：14 封带 `决策点:` 且 ≥1 项的历史信 → 22 个口径点入台账。
经 LedgerStore.append_many 写入（唯一写盘入口），幂等：已存在的 id 跳过。
拆点来源＝各信 frontmatter `决策点:` 行（起草者当时的专家标注，非事后反推）；
`已签认` 只在 7-外部文档 存在以信名命名的回件落档件时写，evidence＝该件路径、fact_date＝件名日期（README 08-23 补转态日不作事实日）；
无名匹配回件件者停在 `在途`（fact_date=事实日未知），签认留 tasks 2.3 人工批改。
用法：python ledger_golden_backfill_0907.py [--dry-run]
"""
import sys, json, pathlib, datetime
ROOT = pathlib.Path(r"C:\Dev\zhuopin-ai")
sys.path.insert(0, str(ROOT / "5-平台底座/zhuopin_platform"))
from zhuopin_platform.coverage_point_ledger.store import LedgerStore
from zhuopin_platform.coverage_point_ledger.models import LedgerEvent, Event, Status, PointType, Domain

DRY = "--dry-run" in sys.argv
RAW = pathlib.Path(sys.argv[-1]) if sys.argv[-1].endswith(".json") else pathlib.Path(__file__).with_name("拆点原料-黄金集14信23点-2026-09-07.json")
BY = "OP-0907-AL"
now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
UNKNOWN = "事实日未知"
EXT = "7-外部文档/"

# file → (信编号 or None, 判例批次码, 域前缀场景码用于 id, 回件落档件相对路径 or None, 回件日期 or None, 备注)
META = {
    "IT部-陈承-跟进-2026-07-27-FO接口闭环确认与OCR最后期限.md":
        ("IT部#3", "I03", "IT", None, None, "README 主表：✅ 已推送 2026-07-27 07:49 UTC；无以信名命名的回件件（07-30 两条文本反馈未按信名归档），签认待 2.3"),
    "IT部-陈承-跟进-2026-07-28-两个接口缺行级状态字段请评估补齐.md":
        ("IT部#4", "I04", "IT", None, None, "README 归档件：📥 已回件并回灌（2026-08-23 补转态）；无以信名命名的回件件，签认待 2.3"),
    "财务部-唐燕萍-跟进-2026-07-27-FI2单价澄清与判例批改法切换.md":
        ("财务部#7", "F07", "FI2", EXT + "财务部/财务部-tangyanping-回复-2026-07-28-财务部-唐燕萍-跟进-2026-07-27-FI2单价澄清与判例批改法切换-回复-3f5a7f63260e4547281b2e4b8d62d4c8.docx", "2026-07-28", None),
    "财务部-唐燕萍-跟进-2026-07-28-FI2三单匹配Web服务上线请试用.md":
        ("财务部#8", "F08", "FI2", EXT + "财务部/财务部-tangyanping-回复-2026-07-31-财务部-唐燕萍-跟进-2026-07-28-FI2三单匹配Web服务上线请试用-回复-51efeabe343e2042b45126c70b120684.docx", "2026-07-31", None),
    "财务部-唐燕萍-跟进-2026-07-31-FI2v8面板改造上线请复核.md":
        ("财务部#9", "F09", "FI2", None, None, "README 归档件：📥 已回件并回灌（2026-08-23 补转态）；无以信名命名的回件件，签认待 2.3"),
    "财务部-唐燕萍-跟进-2026-08-03-FI2真实数据接入轮1请复核.md":
        ("财务部#10", "F10", "FI2", EXT + "财务部/财务部-tangyanping-回复-2026-08-04-财务部-唐燕萍-跟进-2026-08-03-FI2真实数据接入轮1请复核-回复-f922271d2c5ad5bf9e9192f29ed02fbc.docx", "2026-08-04", None),
    "财务部-唐燕萍-跟进-2026-08-05-FI2面板6项显示问题已修复请复核.md":
        ("财务部#11", "F11", "FI2", EXT + "财务部/财务部-tangyanping-回复-2026-08-06-财务部-唐燕萍-跟进-2026-08-05-FI2面板6项显示问题已修复请复核-回复-b01f0dd5ed0005b5ac01d9ccd9eb3006.docx", "2026-08-06", None),
    "质量部-陈忱-跟进-2026-07-28-QD-B新版上线请试用与两个数字.md":
        ("质量部#5", "Q05", "QD-B", None, None, "README 归档件：📥 已回件并回灌（2026-08-23 补转态）；无以信名命名的回件件（07-31 文本反馈未按信名归档），签认待 2.3"),
    "采购部-姚祖怡-跟进-2026-07-27-需求关闭判例批改.md":
        ("采购部#6", "P06", "SC8", EXT + "采购部/采购部-YaoZuYi-回复-2026-07-28-采购部-姚祖怡-跟进-2026-07-27-需求关闭判例批改-1e8f0afb364154e86292207dd4e7f768.docx", "2026-07-28", None),
    "采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用判例批改.md":
        (None, "P0729", "SC8", EXT + "采购部/采购部-YaoZuYi-回复-2026-08-06-采购部-姚祖怡-跟进-2026-07-29-批2上月未齐套跨月占用判例批改-1aa61300bdb89c97a92a53580ed436b0.docx", "2026-08-06",
         "README 归档件标「采购部（未发，不编号）／📥 已回件并回灌（闭环依据补记 2026-08-21）」，但 7-外部文档 存在以本信名命名的 08-06 回件件——两者矛盾，以落档件为事实、README 口径待 2.3 核"),
    "采购部-姚祖怡-跟进-2026-07-29-批2修复交付与18-19两条如实说明.md":
        ("采购部#7", "P07", "SC8", None, None, "编号按归档件日期序推定（#6=07-27、#8=07-29 徽标信），标 需复核；无以信名命名的回件件，签认待 2.3"),
    "采购部-姚祖怡-跟进-2026-08-05-答交口径v3已复现+替代料已建造请签字.md":
        ("采购部#11", "P11", "SC8", EXT + "采购部/采购部-YaoZuYi-回复-2026-08-06-采购部-姚祖怡-跟进-2026-08-05-答交口径v3已复现+替代料已建造请签字-044378b18b53b47240727a7e72bd498a.docx", "2026-08-06",
         "08-07 信（采购部#12）自述：08-06 回件未提黄金基准两份材料、改按默示接受——本行 evidence 是回件件存在的事实，是否构成对本点的签认待 2.3 逐点核"),
    "采购部-姚祖怡-跟进-2026-08-07-答交口径v4三态判据+替代料并列展示已修复请复核.md":
        ("采购部#12", "P12", "SC8", None, None, "信内自设「默示接受」——与判据类永不默认生效相抵，属历史违例，原样登记不改写；无以信名命名的回件件，签认待 2.3"),
    "采购部-姚祖怡-跟进-2026-08-10-可齐套套数两字段是否依赖判例批改.md":
        ("采购部#13", "P13", "SC8", EXT + "采购部/采购部-YaoZuYi-回复-2026-08-12-采购部-姚祖怡-跟进-2026-08-10-可齐套套数两字段是否依赖判例批改-6984a55ab3f8bbe59029d0f265143625.docx", "2026-08-12", None),
}
TYPE = {"判据类": PointType.CRITERION, "试用反馈": PointType.TRIAL_FEEDBACK, "材料索取": PointType.MATERIAL_REQUEST}

raw = json.loads(RAW.read_text(encoding="utf-8"))
store = LedgerStore(ROOT / "6-人才与组织/部门AI专员跟进/口径点台账")
existing = {}
for dom in Domain:
    for e in store.read_domain(dom):
        existing.setdefault(e.id, []).append(e)

events, skipped, summary = [], [], []
for letter in raw:
    fn = letter["file"]
    if fn not in META:
        raise SystemExit(f"META 缺 {fn}")
    num, batch, scene_id, ev_path, ev_date, meta_note = META[fn]
    if ev_path and not (ROOT / ev_path).exists():
        raise SystemExit(f"回件件不存在：{ev_path}")
    for p in letter["points"]:
        pid = f"{scene_id}-{batch}-{p['seq']:02d}"
        Domain.for_id(pid)  # 前缀合法性
        if pid in existing:
            skipped.append(pid); continue
        carrier = tuple(f"queue:§一{q} 需复核" for q in p.get("queue_refs", []))
        note_parts = [f"§2.1 黄金集回溯（源信 `{fn}`，frontmatter「{letter['决策点_frontmatter']}」）"]
        scene = letter["scene"]
        if scene_id == "IT":  # IT 域点：id 前缀须与 scene 一致，原信关联场景记入 note
            note_parts.append(f"IT 域点，关联场景 {scene}")
            scene = "IT"
        if letter.get("scene_guess"):
            note_parts.append("场景码为推定")
        if meta_note:
            note_parts.append(meta_note)
        letters = (num,) if num else ()
        events.append(LedgerEvent(id=pid, event=Event.CREATE, status=Status.ASKING, fact_date=letter["created"], recorded_on=now, by=BY,
                                  type=TYPE[p["type"]], scene=scene, proposer=letter["proposer"],
                                  case_text=p["case_text"], proposed_ruling=p["proposed_ruling"],
                                  carrier=carrier, letters=letters, due=None, note="；".join(note_parts)))
        # 在途：发出日在信文件与 README 归档件里均已不可考（08-23 补转态覆盖）→ 事实日未知
        events.append(LedgerEvent(id=pid, event=Event.TRANSITION, status=Status.IN_FLIGHT, fact_date=UNKNOWN, recorded_on=now, by=BY,
                                  letters=letters, note="回溯：发出日不可考（README 2026-08-23 补转态覆盖了真实日），不用补记日顶替"))
        if ev_path:
            events.append(LedgerEvent(id=pid, event=Event.TRANSITION, status=Status.SIGNED, fact_date=ev_date, recorded_on=now, by=BY,
                                      letters=letters, evidence=ev_path,
                                      note="回溯：以信名命名的回件落档件存在＝真实回件驱动；fact_date 取件名日期；逐点签认内容待 tasks 2.3 人工批改"))
        summary.append((pid, num, p["type"], "已签认" if ev_path else "在途"))

print(f"计划写入 {len(events)} 行（点 {len(summary)} 个），跳过已存在 {len(skipped)}：{skipped}")
for s in summary:
    print("  ", *s)
if DRY:
    print("dry-run，未写盘"); sys.exit(0)
paths = store.append_many(events)
print("appended", len(events), "->", sorted({p.name for p in paths}))
for dom in Domain:
    rows = store.read_domain(dom)
    if rows:
        print(dom.value, "rows now", len(rows))
