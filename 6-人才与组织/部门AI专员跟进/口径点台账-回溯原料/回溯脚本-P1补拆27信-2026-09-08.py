# -*- coding: utf-8 -*-
"""#439 tasks §2.2 回溯拆点（P1 补拆）：其余 27 封已闭环跟进信 → 口径点入台账。

与 §2.1《回溯脚本-黄金集23点-2026-09-07.py》同一套写入路径与同一套状态判据，
只有「拆点来源」和「回件件命名判据」两处不同，逐条写在下面：

⑴ **拆点来源** —— §2.1 吃的是各信 frontmatter `决策点:`（起草者当时的专家标注）；
   本轮这 27 封**没有**该字段（覆盖率 2026-08-11 起为 0%，成因见 design 审前置件 §2.1），
   故按 **P1 判别式**补拆：「专员只答这一条、完全不答其他条，这一条能否成立？」
   ＋ P2（判例行是点的证据不是点本身，三行结构算 1 点）＋ P4（三类型分流）。
   🔴 **信内自陈优先**：`开放点:`／`开放点计数:`／`闭环形态:`／正文「本封要你定 N 件事」
   一律以自陈为准，自陈原文抄进每个点的 note。**拆点结果属待批改品，交 tasks 2.3 由
   Shao Peishen 逐点核**（§2.1 那 23 点是专家标注、可当黄金集；本轮 27 封不是）。

⑵ **回件件命名判据扩展（如实登记）** —— §2.1 只认「件名含信名全名」一种。
   实测 8 月下旬起企微落档改用第二种命名 `…-回复-<部门#N>-<日期>-<主题>-<hash>.docx`，
   `质量部#10`／`采购部#21` **只有**这一种，按 §2.1 的判据会被判成「无回件」而停在途——
   与 README 明写的「📥 已回件并回灌」直接矛盾。⇒ 本轮两种命名都认，
   命中方式逐点写进 note（`信名式`／`编号式`／两者皆是）。

⑶ **发出日一律 `事实日未知`**（同 §2.1）：README 主表对已闭环信只留「回灌日」、
   不留推送时刻；`跟进信行日志/` 各件是「主要事项列」外置、也无推送时刻；
   发送侧审计在 `.51`，本泳道不碰。🔴 **不用回灌日顶替发出日**（tasks 3.3）。

用法：python 回溯脚本-P1补拆27信-2026-09-08.py [--dry-run] [<原料.json>]
"""
import sys, json, pathlib, datetime, re

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "5-平台底座/zhuopin_platform"))
from zhuopin_platform.coverage_point_ledger.store import LedgerStore
from zhuopin_platform.coverage_point_ledger.models import (
    LedgerEvent, Event, Status, PointType, Domain,
)

DRY = "--dry-run" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
RAW = pathlib.Path(args[0]) if args else pathlib.Path(__file__).with_name(
    "拆点原料-P1补拆27信-2026-09-08.json")
BY = "OP-0908-H"
NOW = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
UNKNOWN = "事实日未知"

TYPE = {
    "判据类": PointType.CRITERION,
    "试用反馈": PointType.TRIAL_FEEDBACK,
    "材料索取": PointType.MATERIAL_REQUEST,
}
# 编号 → 判例批次码（与 §2.1 同构：`财务部#13`→`F13`、`采购部#7`→`P07`、`质量部#5`→`Q05`、`IT部#3`→`I03`）
DEPT_LETTER = {"财务部": "F", "采购部": "P", "质量部": "Q", "IT部": "I", "销售部": "S"}


def batch_code(number: str) -> str:
    m = re.fullmatch(r"(\S+?)#(\d+)", number)
    if not m:
        raise SystemExit(f"编号形态不认识：{number!r}（应形如 `采购部#14`）")
    dept, n = m.group(1), int(m.group(2))
    if dept not in DEPT_LETTER:
        raise SystemExit(f"部门 {dept!r} 不在册")
    return f"{DEPT_LETTER[dept]}{n:02d}"


def main() -> None:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    ev_map = json.loads(
        pathlib.Path(__file__).with_name("回件落档件命中-P1补拆27信-2026-09-08.json")
        .read_text(encoding="utf-8"))

    store = LedgerStore(ROOT / "6-人才与组织/部门AI专员跟进/口径点台账")
    existing = set()
    for dom in Domain:
        for e in store.read_domain(dom):
            existing.add(e.id)

    events, skipped, summary, zero = [], [], [], []
    for letter in raw:
        num = letter["编号"]
        batch = batch_code(num)
        scene = letter["scene"]
        hits = ev_map.get(num) or []
        if len(hits) > 1:
            raise SystemExit(f"{num} 命中多份回件件，需人工裁：{[h['path'] for h in hits]}")
        hit = hits[0] if hits else None
        if hit:
            if not (ROOT / hit["path"]).exists():
                # 7-外部文档/ 被 .gitignore 忽略、只存在于主 checkout；worktree 内取不到时
                # 退到主 checkout 校验存在性，路径本身仍写仓库根相对路径。
                if not (pathlib.Path(r"C:\Dev\zhuopin-ai") / hit["path"]).exists():
                    raise SystemExit(f"回件件不存在：{hit['path']}")
            if not hit.get("date"):
                raise SystemExit(f"{num} 的回件件件名里取不到日期：{hit['path']}")

        if not letter["points"]:
            zero.append((num, letter.get("拆点依据", "")))
            continue

        for p in letter["points"]:
            pid = f"{scene}-{batch}-{p['seq']:02d}"
            Domain.for_id(pid)  # 前缀合法性；不合法当场抛
            if pid in existing:
                skipped.append(pid)
                continue
            note_parts = [
                f"§2.2 P1 补拆（源信 `{letter['file']}`）",
                f"拆点依据：{letter['拆点依据']}",
            ]
            if letter.get("自陈原文"):
                note_parts.append(f"信内自陈：{letter['自陈原文']}")
            if letter.get("scene_guess"):
                note_parts.append("场景码为推定")
            note_parts.append("🔴 本点属 P1 补拆结果、非专家标注，待 tasks 2.3 由 Shao Peishen 批改")
            carrier = tuple(f"queue:§一{q} 需复核" if q.startswith("#") else f"queue:{q} 需复核"
                            for q in p.get("queue_refs", []))
            events.append(LedgerEvent(
                id=pid, event=Event.CREATE, status=Status.ASKING,
                fact_date=letter["created"], recorded_on=NOW, by=BY,
                type=TYPE[p["type"]], scene=scene, proposer=letter["proposer"],
                case_text=p["case_text"], proposed_ruling=p["proposed_ruling"],
                carrier=carrier, letters=(num,), due=None,
                default_after_h=p.get("default_after_h"),
                note="；".join(note_parts)))
            events.append(LedgerEvent(
                id=pid, event=Event.TRANSITION, status=Status.IN_FLIGHT,
                fact_date=UNKNOWN, recorded_on=NOW, by=BY, letters=(num,),
                note="回溯：发出日不可考（README 主表只留回灌日、行日志无推送时刻、"
                     "发送侧审计在 .51 不取），按 SCHEMA 写 `事实日未知`，不用回灌日顶替"))
            if hit:
                events.append(LedgerEvent(
                    id=pid, event=Event.TRANSITION, status=Status.SIGNED,
                    fact_date=hit["date"], recorded_on=NOW, by=BY, letters=(num,),
                    evidence=hit["path"],
                    note=f"回溯：可归属本信的回件落档件存在＝真实回件驱动（命名判据：{hit['match']}）；"
                         f"fact_date 取件名日期；逐点签认内容待 tasks 2.3 人工批改"))
            summary.append((pid, num, p["type"], "已签认" if hit else "在途"))

    print(f"计划写入 {len(events)} 行（点 {len(summary)} 个），"
          f"零建点信 {len(zero)} 封，跳过已存在 {len(skipped)}：{skipped}")
    for s in summary:
        print("  ", *s)
    print("零建点信：")
    for num, why in zero:
        print(f"   {num}｜{why[:110]}")
    if DRY:
        print("dry-run，未写盘")
        return
    paths = store.append_many(events)
    print("appended", len(events), "->", sorted({p.name for p in paths}))
    for dom in Domain:
        rows = store.read_domain(dom)
        if rows:
            print(dom.value, "rows now", len(rows))


if __name__ == "__main__":
    main()
