"""未闭合产出扫描（队列 §一 `#398` 第 ⑷ 处，`OP-0826-U`，2026-08-26）。

**要治的病**：一份产出做完了一半，剩下半步等一个外部条件（回内网、等别的
任务收工、等签认），于是被登记为「留步」——**登记本身没问题，问题是这条
登记只有产生方、没有承接方**。没有任何机制会在条件满足时把它捞回来，也
没有任何机制会在它躺得太久时出声。

🔴 **本族有三种外形，只扫第一种会漏掉后两种**（`OP-0826-U` 派单件原文，
三个活样本均为 2026-08-26 当天实测所得）：

  **形态 1 · 队列行里写着「LAN 留步」** —— 最像样的那一种：有人负责任地
  登记了一行。样本＝队列两份真身共 19 处命中。

  **形态 2 · 留步项所依赖的代码卡在未合入分支上** —— 队列行状态看着是
  `[S:partial]` 正常在办，而行内让人去跑的那条命令**在主工作区根本不
  存在**。样本＝`#398` 的 `fb0d185`。

  **形态 3 · 产出连分支都没有** —— 只是某个 worktree 里未 commit 的改动。
  样本＝波次 A5（`#410`）以 `NO-SENTINEL` 结束，539 行新增只以 `modified`
  躺在 `.claude/worktrees/queue-410-editable-guard` 里，分支领先 master
  **0** 个提交；任何一次 worktree 清理都会让它消失。

🔑 **三者的共同点，也是本工具真正要防的东西：每一种在队列里看起来都正常，
没有任何一种会自己发出信号。**

--------------------------------------------------------------------------
🔴 三条反直觉判据（写在实现旁边，因为改实现的人一定会读到这里）
--------------------------------------------------------------------------

**⑴ 形态 2 绝不能用 ancestry 判「未合入」。** 直觉写法是
`git merge-base --is-ancestor <sha> master`，它对**每一个 rebase／
cherry-pick 落地的分支都会永久报红**。2026-08-26 当场实测：`#398` 的
`fb0d185` ancestry 判定为「未合入」，而它的内容早已在 `origin/master` 里
（`e024ead`）——两者 `git patch-id --stable` 完全相同（`db8ae53a…`）。
⇒ 本工具一律走 `git cherry <base> <branch>`：`+` 才是真·未上游，`-` 是
patch 等价已上游。**用 ancestry 会造出一个永远红着的告警，一周之内所有人
都会学会忽略它**（本项目已有三个这样的先例，见 `#398` 前三处）。

**⑵ off-LAN 下 `.51` 的 URL 照样返回 http_code。** 2026-08-25 实测
`:8093/api/ping` 返回 **502，且响应头带 `Proxy-Connection: keep-alive`**
——那个 502 是代理给的，不是服务给的。**只判「有没有状态码」会误报可达**
（同根 `CLAUDE.md` §5「工具静默回退」族：错误不产生任何信号）。故 on-LAN
判据取三项、缺一不算通：`ping` 通 ＋ 两个端口 `/api/ping` 返回 200 且
`Server` 头含 `waitress` ＋ 响应头**不含** `Proxy-Connection`。

**⑶ 判据必须能被「已补做／已合入／已 commit」关掉。** 每一项发现都有一个
稳定 key，落在状态文件里；key 消失即报一次「✅ 已解除」并从状态里删除。
🔴 **形态 1 曾在这一条上失守整整一天，修法见 `scan_form1` 文档**：它读的是
队列行，而队列行守「历史记录不追改」——补做方在行尾追加结论、原字样一个不
动 ⇒ 命中永不消失。2026-08-27 `OP-0827-E` 逐条核实完 11 条后重跑，**一条都
没减少**。现由 `--ack-form1`（带内容指纹的确认，同族＝
`工具-落库sweep.py --ack-stale-change`）关闭，**报告每轮把那条命令原样打出来**。
🔴 **key 里刻意不含任何会变的数字**（行数、提交数、字节数）——把会变的数
放进 key，每变一次就是一个新 key、天天被当成新问题重报，旧 key 还会被误判
为「已解除」（此判据抄自 `工具-落库sweep.py::_check_claude_md_carrier_size`
的同一处教训）。

--------------------------------------------------------------------------
边界（如实登记，不假装闭合）
--------------------------------------------------------------------------
- **只读**。不 commit、不合分支、不删 worktree、不改队列。处置一律由人或
  由 CC 看了报告后执行——与 `工具-孤儿worktree扫描.py` 的红线一致。
- **形态 3 不覆盖 gitignore 命中的内容**（`reports/`、`.env`、`*.db` 等）。
  那是 `工具-孤儿worktree扫描.py` 第三桶的职责（队列 `#267` 真实丢件事故
  就出在那里），此处不重复实现，避免两个工具对同一事实各报一份、口径还
  不一样。
- **形态 1 只认队列 §一／§四 的行**，§二 批次行**按解析结构天然排除**——
  §二 是已完成批次的历史叙述，把它算进来会让存量长期虚高（`OP-0826-U`
  原文：14 处里有 5 处属此类）。**被排除了几处会打印出来**，因为「剔掉了
  什么」本身是证据，不打印就没人知道判据在剔什么。
- **LAN 探针看的是这台机器**。放 CI 无意义（GitHub runner 出不了公司内网，
  在那里跑永远是「off-LAN」）——故 CI 场景请带 `--skip-lan-probe`。

用法：
  python 0-学习与工具/工具-未闭合产出扫描.py                  # 扫描 + 报告
  python 0-学习与工具/工具-未闭合产出扫描.py --skip-lan-probe # 不跑网络探针
  python 0-学习与工具/工具-未闭合产出扫描.py --wide           # 泛「留步」二级提示
  python 0-学习与工具/工具-未闭合产出扫描.py --json           # 机器可读
  python 0-学习与工具/工具-未闭合产出扫描.py --enforce        # 有发现即非零退出
  python 0-学习与工具/工具-未闭合产出扫描.py --repo-root <p>  # 仅测试用
  python 0-学习与工具/工具-未闭合产出扫描.py --ack-form1 <KEY> --note <依据>
                                                              # 形态 1 已核实闭合

退出码（🔴 不带 `--enforce` 时恒为 0，报告工具不该拦住调用它的那一轮）：
  0 = 干净（或未启用 enforce）
  1 = `--enforce` 且有未闭合产出
  2 = `--enforce` 且有判据不可用——**它比 1 更严重**：1 是「发现了问题」，
      2 是「这个守卫自己瞎了」，两者绝不合并成同一个码。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

_PLATFORM_PATH = Path(__file__).resolve().parents[1] / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))

# ============================================================
# 常量
# ============================================================

STATE_REL = "reports/unclosed-output-state.json"
# 报告里回显「怎么关掉这条告警」时用的自身路径。取仓库相对写法，与
# `工具-落库sweep.py::UNCLOSED_SCAN_SCRIPT_REL` 同一个字符串——两处不一致
# 会让人复制到一条跑不通的命令。
_SELF_REL = "0-学习与工具/工具-未闭合产出扫描.py"
# 形态 1 的「已核实闭合」确认状态（`#422` 护栏失效修复，`OP-0827-G`）。
# 🔴 **与 `STATE_REL` 必须是两份文件**：`STATE_REL` 每轮被整份重写（它记的是
# 「上一轮报过谁」），确认记录写进去会当轮即被冲掉。形态、目录、gitignore
# 归属与 `工具-落库sweep.py` 的 `reports/sweep-stale-change-ack.json` 一致
# ——本机状态、不入库（`.gitignore` 的 `**/reports/`）。
FORM1_ACK_STATE_REL = "reports/unclosed-output-form1-ack.json"
# 队列行的「结论段」分隔符（队列 #324 已确立的既有约定，见
# `工具-共享文档编辑锁.py::_leading_conclusion_segment`）。本文件只借它切段，
# **不借它判「哪一段是当前结论」**——那条判据依赖「新内容一律追加在末尾」，
# 而 2026-08-27 实测两种追加方向真的都有：`#422` 状态格是立行段在前、
# 「✅ 接线完成」追在末尾；`#340` 状态格反过来，08-21 段在第 1 段、08-18 段
# 在第 10 段、08-17 段在第 40 段，并用「以下为 …… 原登记」把更早的一段段
# 往后压。**靠段序判闭合会在其中一半的行上静默判反。**
CONCLUSION_SEGMENT_SEPARATOR = "━━━"

# 形态 1 的标记词。**默认口径刻意收窄到 LAN 一族**：队列里「留步」二字有
# 约 40 处用法（`发送留步`／`冒烟留步`／`整条留步`／`一律留步不发`…），
# 其中大多数是行文而非登记，全收会把这份报告变成噪音。泛口径由 `--wide`
# 单开一节、标为「仅提示」，不混进主清单。
LAN_MARKER_RE = re.compile(r"LAN\s*留步|回内网补做|回\s*LAN\s*(?:补|再|后)")
WIDE_MARKER_RE = re.compile(r"留步")

# 否定前缀。实测反例＝`#418` 行内原话「**故这不是 LAN 留步**，是『无人在场时
# 不自行执行需批准的生产写动作』」——纯字面匹配会把一条**明说了自己不是**
# 留步的行报成留步。判法：一行里的每一处命中，若紧邻左侧 4 字内出现否定词，
# 该处不算数；**一行里所有命中都被否定，这行才不进清单**（只要还剩一处真
# 命中就仍然报——宁可多报一条要人扫一眼的，不可因为同一行里有句否定就把
# 真的那处一起吞掉）。
NEGATION_WORDS = ("不是", "非", "不算", "不属", "并非")
NEGATION_LOOKBEHIND = 4

# 形态 1 分档（天）。阈值不是拍的：7 天＝`#312` 陈化催办已在用的那个数，
# 两处用同一个数，免得同一件事在两份报告里给出两种「算不算久」。
AGE_BUCKETS = ((7, "≥7 天"), (3, "3–6 天"))
AGE_BUCKET_FRESH = "<3 天"

# 形态 2：分支领先基准超过这个数就不再算 patch-id（`git cherry` 要对每个
# 提交算一次 patch-id，长分支上很慢）。超限的如实标注「未做 patch 等价
# 判定」，**不冒充成已判定**。
MAX_CHERRY_COMMITS = 200

# 形态 2 排除：备份分支按约定就是要长期领先的，报它没有任何行动含义。
FORM2_EXCLUDE_PREFIXES = ("backup/",)

# LAN 探针（判据 ⑵）
LAN_HOST = "192.168.100.51"
LAN_SERVICES = ((8091, "统一门户（SC8 等）"), (8093, "QD-B 立项审核门禁"))
EXPECTED_SERVER_TOKEN = "waitress"
PROXY_HEADER_LOWER = "proxy-connection"
HTTP_TIMEOUT_SECONDS = 6
PING_TIMEOUT_MS = 1000

# 落库 sweep 的计划任务名。形态 3 里「主工作区」那一条要用它的真实状态说话，
# 🔴 **不是拿它当假设**：本文件初版在主工作区那条上写死了一句「sweep 停用
# 期间它就是一堆没人收的产出」——**它根本没去查过 sweep 的状态**。2026-08-27
# 实测反例：`State=Ready`／`LastRun 11:17:02`／`Result=0x0`，一直在跑，而当时
# 3 个脏文件的 mtime 全部晚于那一轮 ⇒ 真因是「上一轮跑完之后才产生的正常
# 时间差」。**危害是复合的**：读到那句话的人会跟着断言 sweep 没在跑，于是
# 同一个未经验证的因果被下游当作事实转述一层。
SWEEP_TASK_NAME = "ZhuopinCommitSweep"
SWEEP_PROBE_TIMEOUT_SECONDS = 25
# 🔴 计划任务的 `LastRunTime`／`NextRunTime` 与文件 mtime **都是本机本地时间**
# （项目硬规则：mtime／`LastRunTime` 本地，审计 jsonl 与企微告警文案才是 UTC）
# ⇒ 两者同基准可直接比，报告里一律显式标「本地」。
LOCAL_TIME_FMT = "%Y-%m-%d %H:%M:%S"
# 主工作区脏文件的 mtime 清单进 JSON 时的上限。**只截显示、不截判定**：
# 「早于上一轮却仍未被收」是逐个文件算完再截的，不会因为截断而漏掉红旗。
SWEEP_MTIME_LIST_CAP = 20


# ============================================================
# 基础设施
# ============================================================

def _run_git(args: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=check,
    )


def _resolve_repo_root(override: str | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return Path(result.stdout.strip())


def _base_ref(repo_root: Path) -> str | None:
    """形态 2 的比较基准：优先 `origin/master`（权威备份就是它），退本地
    `master`。**返回值会被打进报告标题**——两个工具若用了不同基准，数字会
    对不上，而对不上的数字没有标注就是又一个静默陷阱（判据抄自
    `工具-孤儿worktree扫描.py::_behind_base`，此处顺序相反且是有意的：
    合没合入以远端为准，落没落后以本地为准）。"""
    for ref in ("origin/master", "master"):
        result = _run_git(["rev-parse", "--verify", "--quiet", ref], repo_root)
        if result.returncode == 0 and result.stdout.strip():
            return ref
    return None


def _parse_worktree_porcelain(text: str) -> list[dict]:
    entries: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current = {"path": line[len("worktree "):].strip(), "branch": None}
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):].strip().removeprefix("refs/heads/")
    if current:
        entries.append(current)
    return entries


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# 形态 1：队列行里的 LAN 留步登记
# ============================================================

_SECTION_HEADING_RE = re.compile(r"^## ([一二三四五六七八九十]+)、", re.MULTILINE)
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _split_sections(text: str) -> dict[str, str]:
    """把队列正文切成 `{分区序号: 正文}`。§二 由此天然被隔开——形态 1 只取
    §一／§四，不需要另写一条「跳过批次行」的规则（少一条规则，少一处会
    被改坏的地方）。"""
    sections: dict[str, str] = {}
    marks = list(_SECTION_HEADING_RE.finditer(text))
    for idx, mark in enumerate(marks):
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(text)
        sections[mark.group(1)] = text[mark.start():end]
    return sections


def _split_row_cells(line: str) -> list[str] | None:
    """切一行表格的单元格。优先用底座的反引号感知实现（反引号内的 `|` 不
    算列分隔符，见 `queue_table::_mask_backtick_spans`）；底座不可用时退
    朴素切列——**退化会让个别含反引号竖线的行列数对不上而被跳过，那是漏
    报，不是误报**，可接受；反过来（把它当成解析成功）才是不可接受的。"""
    try:
        from zhuopin_platform.shared_tools import queue_table  # noqa: PLC0415

        return queue_table.split_row_cells(line)
    except Exception:  # noqa: BLE001
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return None
        return [cell.strip() for cell in stripped[1:-1].split("|")]


def _iter_table_rows(section_text: str, expected_cols: int) -> list[list[str]]:
    """切出该分区的数据行。列数不符即跳过——与 `_parse_section_one` 同一套
    取舍，不为「解析得更全」而放宽（放宽会把正文里的表格也吃进来）。"""
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        cells = _split_row_cells(line)
        if cells is None or len(cells) != expected_cols:
            continue
        first = cells[0]
        if first in ("#", "批次", "") or set(first) <= {"-", " "}:
            continue
        rows.append(cells)
    return rows


def _age_days(registered: str | None, today: date) -> int | None:
    if not registered:
        return None
    match = _DATE_RE.search(registered)
    if match is None:
        return None
    try:
        stamp = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    return (today - stamp).days


def _bucket(age: int | None) -> str:
    if age is None:
        return "登记日未知"
    for threshold, label in AGE_BUCKETS:
        if age >= threshold:
            return label
    return AGE_BUCKET_FRESH


def _affirmative_hit(text: str, marker: re.Pattern[str]) -> re.Match[str] | None:
    """返回第一处**未被否定**的命中；全被否定则返回 `None`（见 `NEGATION_WORDS`）。"""
    for match in marker.finditer(text):
        left = text[max(0, match.start() - NEGATION_LOOKBEHIND):match.start()]
        if not any(word in left for word in NEGATION_WORDS):
            return match
    return None


def _hit_segments(cells: list[str], marker: re.Pattern[str]) -> list[str]:
    """本行里**真正登记了留步**的那些结论段（按 `━━━` 切，逐段判否定）。

    逐段判而不是把整行拼起来判，有一个实测理由：否定前瞻只看命中点左侧 4 字，
    拼行会让「上一格末尾的否定词」误伤「下一格开头的命中」——两格之间本来
    隔着一整个单元格边界，语义上不相干。
    """
    segments: list[str] = []
    for cell in cells:
        for segment in cell.split(CONCLUSION_SEGMENT_SEPARATOR):
            if _affirmative_hit(segment, marker) is not None:
                segments.append(segment.strip())
    return segments


def form1_fingerprint(segments: list[str]) -> str:
    """确认指纹 ＝ 该行**全部留步登记段**的内容哈希（`OP-0827-G`）。

    🔴 **指纹刻意只盖命中段，不盖整行**，这一条决定了这个机制会不会退化成
    噪音：队列行是只增不删的，一天之内被追加三五段是常态，指纹若盖整行，
    每追加一句无关的话就把已核实的条目重新捅红一次——那正是本次要治的病
    换个方向再犯一遍。

    盖住命中段则语义正好是「**我核过了这一行里登记的每一处留步**」：
    - 无关追加 ⇒ 指纹不变 ⇒ 保持静默；
    - **新登记一处留步** ⇒ 多一个命中段 ⇒ 指纹变 ⇒ 自动重新告警；
    - 改写了已核过的那一段 ⇒ 指纹变 ⇒ 自动重新告警。

    ⚠️ **已知代价，如实写在这里**：闭合结论句本身通常也含「LAN 留步」四个字
    （实测 `#340` 的「✅ 『LAN 留步』已补做完成」即是），所以它自己也是一个
    命中段 ⇒ **正确顺序是「先把结论写进队列行，再 ack」**；顺序反了会在下一
    轮因指纹变化重新报一次。这是 fail-loud 方向的代价，接受。
    """
    payload = "␞".join(segments)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _read_form1_acks(repo_root: Path) -> dict:
    path = repo_root / FORM1_ACK_STATE_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_form1_acks(repo_root: Path, acks: dict) -> None:
    path = repo_root / FORM1_ACK_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(acks, ensure_ascii=False, indent=2), encoding="utf-8")


def _excerpt(text: str, marker: re.Pattern[str], width: int = 60) -> str:
    match = marker.search(text)
    if match is None:
        return text[:width]
    start = max(0, match.start() - width // 2)
    return text[start:start + width].replace("\n", " ")


def scan_form1(repo_root: Path, today: date, wide: bool = False) -> dict:
    """扫两份队列真身的 §一／§四，找 LAN 留步登记。

    🔴 **两份逐份解析后合并，绝不拼接文本再解析一次**——`_split_sections`
    对同名分区只保留最后一个，拼接会静默丢掉第一份的整个 §一（同族坑已由
    `#312` 实测踩过一次并配了反例单测，见根 `CLAUDE.md` OP-0819-A ⑴）。

    ━━━ 🔴 **判据 ⑶ 在本形态上的落点（`#422` 护栏失效，`OP-0827-G` 修）** ━━━
    文件头判据 ⑶ 写着「判据必须能被『已补做／已合入／已 commit』关掉」。
    形态 2／3 天然做到了（分支合了、改动 commit 了，下一轮就不再命中）；
    **形态 1 做不到**——它读的是队列行，而队列行守「历史记录不追改」，补做
    方的写法是**在行尾追加结论、原字样一个不动** ⇒ 命中永不消失。2026-08-27
    实测：`OP-0827-E` 逐条核实完 11 条之后重跑，**一条都没减少**。

    **修法是指纹确认，不是识别中文**（三条路子比过，理由写在这里以免后人重选）：

    - **读行级 `[S:done]` 关掉** —— 不成立。`#340`／`#354` 整行仍是
      `[S:partial]`（各自还有别的未完项），而它们的 LAN 那半步确已闭合；
      用行级状态关，等于把「这一行做完了」和「这一行里的这半步做完了」
      当成同一件事。
    - **识别行内「已闭合／已补做」结论段** —— 本质是猜中文关键词。实测
      `#340` 写「✅『LAN 留步』已补做完成」、`#334` 写「本行 LAN 留步经核
      **仍成立**」，两句都含「LAN 留步」四字、只差一个措辞；而
      `工具-落库sweep.py` 的 `OBSERVATION_WINDOW_RE` 一节已把「关键词猜
      中文」明列为队列 #308 要根治的那一族，本文件不再造第二个。
    - **指纹确认（本实现）** —— 与 `工具-落库sweep.py::cmd_ack_stale_change`
      同族、**复用其形态而不是另造一套**：确认落在 `reports/` 下的 JSON、
      带 `--note` 判定依据、带内容指纹，指纹一变自动失效恢复告警。它不是
      白名单，是「我在 X 指纹下核过一次」。

    ⚠️ **它不是「机制守」，如实说清楚**：ack 这一步仍要人去跑一条命令。它比
    「在行内加个 `[LAN:closed]` 标记词」强的地方只有三点——① 确认带判定依据
    且落在机器读得到的地方；② 指纹会自己失效，确认不会烂在那里；③ 报告每轮
    把关闭它的那条命令原样打出来，**告警自己就是那份操作说明**。不夸大成
    「已机制化」。
    """
    try:
        from zhuopin_platform.shared_tools import queue_table  # noqa: PLC0415

        rels = queue_table.iter_queue_paths()
    except Exception as exc:  # noqa: BLE001
        # 🔴 底座包坏掉时不返回空清单——「没找到留步项」与「根本没去找」
        # 外观相同，正是本工具要治的那个病，不能在自己身上复发。
        return {"items": [], "wide_items": [], "excluded_section_two": None,
                "unavailable": f"取不到队列路径清单（{type(exc).__name__}: {exc}）"}

    acks = _read_form1_acks(repo_root)
    items: list[dict] = []
    suppressed: list[dict] = []
    wide_items: list[dict] = []
    excluded = 0
    missing: list[str] = []
    for rel in rels:
        path = repo_root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            missing.append(f"{rel}（{exc}）")
            continue
        sections = _split_sections(text)
        # §二 命中数只做统计与回显，不进清单。
        excluded += len(LAN_MARKER_RE.findall(sections.get("二", "")))
        for section, cols in (("一", 8), ("四", 4)):
            for cells in _iter_table_rows(sections.get(section, ""), cols):
                row_text = " ".join(cells)
                registered = cells[7] if section == "一" else cells[-1]
                age = _age_days(registered, today)
                record = {
                    "queue": rel, "section": section, "row_id": cells[0],
                    "registered": registered, "age_days": age, "bucket": _bucket(age),
                }
                segments = _hit_segments(cells, LAN_MARKER_RE)
                if segments:
                    key = f"form1:{rel}#{section}{cells[0]}"
                    fingerprint = form1_fingerprint(segments)
                    hit = {**record, "excerpt": _excerpt(row_text, LAN_MARKER_RE),
                           "key": key, "fingerprint": fingerprint,
                           "hit_segments": len(segments)}
                    ack = acks.get(key)
                    if isinstance(ack, dict) and ack.get("fingerprint") == fingerprint:
                        # 「已确认 ＋ 指纹未变」双条件才静默（同
                        # `_find_stale_in_flight_changes` 的 D2 语义）。
                        suppressed.append({**hit, "note": ack.get("note", ""),
                                           "acked_at": ack.get("acked_at", "")})
                    else:
                        items.append(hit)
                elif wide and WIDE_MARKER_RE.search(row_text):
                    wide_items.append({**record, "excerpt": _excerpt(row_text, WIDE_MARKER_RE)})

    # 🔴 确认记录对不上任何现存行时要说出来，不静默留着：行可能已归档、
    # 也可能编号变了；一条对不上的确认在文件里躺着，下次读的人会以为
    # 「那一处已经被核过」——而它核的是一个已经不存在的东西。
    live = {item["key"] for item in items} | {item["key"] for item in suppressed}
    stale_acks = sorted(key for key in acks if key not in live)

    return {
        "items": items, "wide_items": wide_items, "excluded_section_two": excluded,
        "suppressed": suppressed, "stale_acks": stale_acks,
        "unavailable": f"以下队列文件读不到：{'；'.join(missing)}" if missing else None,
    }


def cmd_ack_form1(repo_root: Path, key: str, note: str, today: date | None = None) -> int:
    """记一次「我核过了这一行登记的每一处 LAN 留步，它们确已闭合」。

    与 `工具-落库sweep.py::cmd_ack_stale_change` 逐条对齐：`--note` 不得为空
    （空确认等于没确认，还会伪装成已核）；算不出指纹就**拒绝记录**，不落一条
    没有指纹的确认——那种确认永远不会失效，正是本机制要避免的白名单。
    """
    if not note.strip():
        print("✗ --note 不能为空——须写明本次核的是什么、凭什么核的，"
              "不得留空确认（同 `--ack-stale-change` 的既有强制惯例）。")
        return 1
    result = scan_form1(repo_root, today or date.today())
    if result["unavailable"]:
        print(f"✗ 形态 1 判据本轮不可用（{result['unavailable']}），"
              "拒绝记录确认——算不出可信指纹。")
        return 1
    match = next((i for i in result["items"] if i["key"] == key), None)
    already = next((i for i in result["suppressed"] if i["key"] == key), None)
    if match is None and already is not None:
        print(f"· 无需重复确认：{key} 当前指纹 {already['fingerprint']} 与已有确认一致，"
              "本轮本就静默。")
        return 0
    if match is None:
        print(f"✗ 当前形态 1 命中里没有 `{key}`，拒绝记录确认——"
              "无法计算指纹，且一条确认不该指向一个不存在的命中。")
        print("  现存命中：" + ("；".join(i["key"] for i in result["items"]) or "（无）"))
        return 1
    acks = _read_form1_acks(repo_root)
    acks[key] = {
        "fingerprint": match["fingerprint"],
        "hit_segments": match["hit_segments"],
        "acked_at": _now_utc_str(),
        "note": note,
    }
    _write_form1_acks(repo_root, acks)
    print(f"✓ 已记录确认：{key}（指纹 {match['fingerprint']}，"
          f"覆盖 {match['hit_segments']} 个留步登记段）。")
    print("  指纹未变期间本行不再进形态 1 清单；该行**新登记一处留步、"
          "或改写了已核过的那一段**即自动失效、恢复告警。")
    print(f"  确认落在 `{FORM1_ACK_STATE_REL}`（本机状态、不入库）。")
    return 0


# ============================================================
# 形态 2：代码卡在未合入分支上
# ============================================================

def scan_form2(repo_root: Path, base: str | None) -> dict:
    """列出**真·未上游**的分支。判据＝`git cherry`（patch-id），不是 ancestry。

    `git cherry <base> <branch>` 逐个提交输出：`+ <sha>` 表示 base 上没有
    patch 等价的提交，`- <sha>` 表示已有。**只有 `+` 才算未合入**——理由与
    实测反例见模块文档判据 ⑴。
    """
    if base is None:
        return {"items": [], "unavailable": "仓库内既无 `origin/master` 也无 `master`，无从比对"}

    listed = _run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], repo_root)
    if listed.returncode != 0:
        return {"items": [], "unavailable": f"`git for-each-ref` 失败：{listed.stderr.strip()[:200]}"}

    worktree_of: dict[str, str] = {}
    wt_listed = _run_git(["worktree", "list", "--porcelain"], repo_root)
    if wt_listed.returncode == 0:
        for entry in _parse_worktree_porcelain(wt_listed.stdout):
            if entry.get("branch"):
                worktree_of[entry["branch"]] = entry["path"]

    items: list[dict] = []
    degraded: list[str] = []
    for branch in listed.stdout.split():
        # 🔴 **本地 `master` 刻意不排除。** 初版排除了它，结果本工具第一次
        # 真实运行就漏掉了当天最要紧的一条：本地 `master` 停在 `367b883`
        # （A3 的 `#394` outbox 中继，约 1,300 行）而 `origin/master` 早已
        # 走了另一条线，两边**已经分叉**——1 个本地独有 vs 6 个远端独有。
        # 那份代码 commit 了、没 push，`git push` 会被拒、`git pull` 会造出
        # 一个违反 ff-only 的 merge，而**队列里看不出任何异常**。
        # ⇒ 判据教训：**排除一个分支之前，先问「它出问题时谁会发现」**；
        # `master` 恰恰是最没有人替它兜底的那一个。
        if branch.startswith(FORM2_EXCLUDE_PREFIXES):
            continue
        counted = _run_git(["rev-list", "--count", f"{base}..{branch}"], repo_root)
        if counted.returncode != 0:
            continue
        try:
            ahead = int(counted.stdout.strip())
        except ValueError:
            continue
        if ahead == 0:
            continue
        if ahead > MAX_CHERRY_COMMITS:
            degraded.append(
                f"`{branch}` 领先 {ahead} 个提交，超过 {MAX_CHERRY_COMMITS}，未做 patch 等价判定")
            continue
        cherry = _run_git(["cherry", base, branch], repo_root)
        if cherry.returncode != 0:
            degraded.append(f"`{branch}` 的 `git cherry` 失败：{cherry.stderr.strip()[:120]}")
            continue
        unmerged = [line.split()[1] for line in cherry.stdout.splitlines() if line.startswith("+ ")]
        equivalent = sum(1 for line in cherry.stdout.splitlines() if line.startswith("- "))
        if not unmerged:
            # 🔴 全是 `-`：ancestry 会报红、patch-id 说已上游。这正是误报源，
            # 故不进清单。
            continue
        subjects = []
        for sha in unmerged[:3]:
            shown = _run_git(["log", "-1", "--format=%h %s", sha], repo_root)
            subjects.append(shown.stdout.strip() or sha[:12])
        # 分叉＝双向都有独有提交。普通分支分叉是常态（它就是拿来分叉的），
        # **本地 `master` 分叉不是**：ff-only 政策下它意味着 push 会被拒、
        # pull 会造出一个违规 merge，且两条路都不会有人主动去看。
        behind = _run_git(["rev-list", "--count", f"{branch}..{base}"], repo_root)
        behind_count = int(behind.stdout.strip()) if behind.stdout.strip().isdigit() else None
        items.append({
            "branch": branch, "worktree": worktree_of.get(branch),
            "unmerged": len(unmerged), "patch_equivalent": equivalent,
            "behind": behind_count, "is_local_master": branch == "master",
            "forked": bool(behind_count), "subjects": subjects, "key": f"form2:{branch}",
        })

    return {"items": items, "unavailable": "；".join(degraded) if degraded else None}


# ============================================================
# 形态 3：产出只是 worktree 里未 commit 的改动
# ============================================================

def _status_path(line: str) -> str:
    """从 `git status --porcelain` 一行里取出路径。

    重命名行形如 `R  旧名 -> 新名`：要看的是**新名**那一侧（旧名已不在盘上，
    对它 `stat` 只会得到一个「文件不存在」，把一条真改动记成无 mtime）。
    """
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def _collect_mtimes(root: Path, lines: list[str]) -> list[dict]:
    """逐个脏文件取本地 mtime。**全部取、不截断**——截断的是显示，不是判定。

    取不到（已删除／权限／路径异常）就如实记 `None`，🔴 **不回落成「现在」**：
    回落会让一个删除掉的文件永远显得「刚改过」，正好把真漏收藏起来。
    """
    collected: list[dict] = []
    for line in lines:
        name = _status_path(line)
        try:
            stamp = datetime.fromtimestamp((root / name).stat().st_mtime)
        except (OSError, ValueError):
            collected.append({"name": name, "mtime": None})
        else:
            collected.append({"name": name, "mtime": stamp.strftime(LOCAL_TIME_FMT)})
    return collected


def scan_form3(repo_root: Path) -> dict:
    """扫每个 worktree 的未提交改动。

    只看 tracked 改动与未跟踪文件；**gitignore 命中的内容有意不看**（边界
    见模块文档，那是 `工具-孤儿worktree扫描.py` 第三桶的职责）。
    """
    listed = _run_git(["worktree", "list", "--porcelain"], repo_root)
    if listed.returncode != 0:
        return {"items": [], "unavailable": f"`git worktree list` 失败：{listed.stderr.strip()[:200]}"}

    items: list[dict] = []
    unreadable: list[str] = []
    # `git worktree list` 的第一条永远是主工作区。它与 linked worktree 的
    # 风险不同：主工作区不会被 `worktree remove` 清掉，它的未提交改动本该
    # 由落库 sweep 每轮收走，救法也不同（人工 commit，而不是「先跑回归再
    # 合入」）。两者混在一起报，读的人会对最要紧的那几行用错处置。
    # 🔴 **「它只在 sweep 停用期间才是风险」这句话本文件曾写死在这里，是错的**：
    # sweep 在跑的时候主工作区照样会有脏文件——上一轮跑完之后新产生的改动就是。
    # 判「时间差」还是「真漏收」要的是证据（`LastRunTime` 与各文件 mtime 并排
    # 摆出来），不是一句断言，故此处只采集 mtime，结论留给 `format_report`。
    main_path = _parse_worktree_porcelain(listed.stdout)[0]["path"] if listed.stdout.strip() else None
    for entry in _parse_worktree_porcelain(listed.stdout):
        path = Path(entry["path"])
        if not path.is_dir():
            unreadable.append(f"`{entry['path']}` 目录不存在（worktree 记录未清理）")
            continue
        status = _run_git(["status", "--porcelain"], path)
        if status.returncode != 0:
            unreadable.append(f"`{entry['path']}` 的 `git status` 失败")
            continue
        lines = [ln for ln in status.stdout.splitlines() if ln.strip()]
        if not lines:
            continue
        untracked = sum(1 for ln in lines if ln.startswith("??"))
        tracked = len(lines) - untracked
        numstat = _run_git(["diff", "--numstat", "HEAD"], path)
        insertions = 0
        for ln in numstat.stdout.splitlines():
            head = ln.split("\t")[0]
            if head.isdigit():
                insertions += int(head)
        is_main = entry["path"] == main_path
        items.append({
            "worktree": entry["path"], "branch": entry.get("branch"),
            "is_main": is_main,
            "tracked_changes": tracked, "untracked": untracked,
            "insertions": insertions,
            "files": [ln[3:] for ln in lines[:5]],
            # mtime 只对主工作区采集——只有那一条的救法与 sweep 的轮次有关。
            "file_times": _collect_mtimes(path, lines) if is_main else [],
            # 🔴 key 只用 worktree 名，不含行数——行数每改一次就变，含它即
            # 每次都是新问题（判据 ⑶）。
            "key": f"form3:{path.name}",
        })

    return {"items": items, "unavailable": "；".join(unreadable) if unreadable else None}


# ============================================================
# 回 LAN 事件感知（判据 ⑵）
# ============================================================

def _probe_ping(host: str) -> dict:
    """🔴 判「通」不看退出码，看输出里有没有 `TTL=`。Windows `ping` 在
    「无法访问目标主机」时也可能给 0 退出码——那条回复来自本地路由器，
    不是目标主机。`TTL=` 是目标主机真的回了包才有的字段。"""
    try:
        result = subprocess.run(
            ["ping", "-n", "2", "-w", str(PING_TIMEOUT_MS), host],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"probe": f"ping {host}", "ok": False,
                "detail": f"调用失败：{type(exc).__name__}: {exc}"}
    ok = "TTL=" in result.stdout.upper()
    return {"probe": f"ping {host}", "ok": ok,
            "detail": "收到带 TTL 的回复" if ok else "无带 TTL 的回复（视为不可达）"}


def _probe_http(host: str, port: int, label: str) -> dict:
    """三项判据里的第二、三项合成一次请求：200 ＋ `Server: waitress` ＋
    响应头不含 `Proxy-Connection`。

    🔴 `HTTPError` **也要拆开看**，不能当成「off-LAN」一笔带过——08-25 那个
    502 正是从这里来的，它带着 `Proxy-Connection`，那才是判定「代理在答」
    的实据。把异常一律翻译成「不可达」等于把证据扔了。
    """
    url = f"http://{host}:{port}/api/ping"
    probe = {"probe": url, "ok": False, "status": None, "server": None, "proxy_header": None}
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            status, headers = response.status, response.headers
    except urllib.error.HTTPError as exc:
        status, headers = exc.code, exc.headers
    except Exception as exc:  # noqa: BLE001 —— URLError／超时／socket 错误
        probe["detail"] = f"{label}：请求失败（{type(exc).__name__}: {exc}）"
        return probe
    server = headers.get("Server") if headers else None
    proxy = None
    if headers:
        proxy = next((v for k, v in headers.items() if k.lower() == PROXY_HEADER_LOWER), None)
    probe.update(status=status, server=server, proxy_header=proxy)
    probe["ok"] = (status == 200 and server is not None
                   and EXPECTED_SERVER_TOKEN in server.lower() and proxy is None)
    probe["detail"] = f"{label}：HTTP {status}｜Server={server!r}｜Proxy-Connection={proxy!r}"
    return probe


def probe_lan(host: str = LAN_HOST) -> dict:
    """三项齐备才算 on-LAN。**任一项不过即 off**，不做「两项过了就算通」的
    宽容——宽容一次，这个判据就退化成 08-25 那个会骗人的判据。"""
    probes = [_probe_ping(host)]
    probes.extend(_probe_http(host, port, label) for port, label in LAN_SERVICES)
    return {"on_lan": all(probe["ok"] for probe in probes), "probes": probes}


# ============================================================
# 落库 sweep 的真实状态（形态 3 · 主工作区那条的证据来源）
# ============================================================

_SWEEP_PS = (
    "$ErrorActionPreference='Stop';"
    "$t=Get-ScheduledTask -TaskName '__TASK__';"
    "$i=Get-ScheduledTaskInfo -TaskName '__TASK__';"
    "$o=[ordered]@{state=[string]$t.State;last_result=$i.LastTaskResult};"
    "$o.last_run=$(if($i.LastRunTime){$i.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss')});"
    "$o.next_run=$(if($i.NextRunTime){$i.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss')});"
    "[pscustomobject]$o|ConvertTo-Json -Compress"
)

# `State` 取这两个值才算「它在跑」。**其余一律不算**，且不猜：`Disabled` 是
# 停用，取不到是取不到，两者在报告里必须能被分辨——把「取不到」写成「停用」
# 就是本函数存在的那个原始缺陷换了个方向再犯一次。
SWEEP_LIVE_STATES = ("Ready", "Running")


def probe_sweep_task(task_name: str = SWEEP_TASK_NAME) -> dict:
    """只读查一次落库 sweep 计划任务的 `State`／`LastRunTime`／`NextRunTime`。

    🔴 **三态而非两态**：在跑／已停用／**取不到**。取不到（非 Windows、没有
    这个任务、`powershell` 不在 PATH、超时）**绝不能被渲染成「停用」**——
    「我查了，它是停的」与「我没查到」是两句完全不同的话，而前者会让读的人
    去做一次并不需要的 `Enable-ScheduledTask`。
    """
    result: dict = {"task": task_name, "available": False, "state": None,
                    "last_run": None, "next_run": None, "last_result": None,
                    "detail": None}
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             _SWEEP_PS.replace("__TASK__", task_name)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=SWEEP_PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        result["detail"] = "本机找不到 `powershell`（非 Windows 或不在 PATH）"
        return result
    except (OSError, subprocess.SubprocessError) as exc:
        result["detail"] = f"调用失败：{type(exc).__name__}: {exc}"
        return result

    if completed.returncode != 0:
        reason = (completed.stderr or completed.stdout).strip().splitlines()
        result["detail"] = (f"`Get-ScheduledTask -TaskName {task_name}` 非零退出"
                            f"（{reason[0][:160] if reason else '无输出'}）")
        return result
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        result["detail"] = f"输出不是 JSON（前 120 字：{completed.stdout.strip()[:120]!r}）"
        return result

    result.update(available=True, state=payload.get("state"),
                  last_run=payload.get("last_run"), next_run=payload.get("next_run"),
                  last_result=payload.get("last_result"))
    result["detail"] = (f"State={result['state']}｜LastRun={result['last_run']}"
                        f"｜NextRun={result['next_run']}｜LastTaskResult={result['last_result']}")
    return result


def _sweep_is_live(sweep: dict | None) -> bool:
    return bool(sweep and sweep.get("available") and sweep.get("state") in SWEEP_LIVE_STATES)


def _parse_local(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, LOCAL_TIME_FMT)
    except ValueError:
        return None


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def track_lan_flip(state: dict, lan: dict | None) -> dict:
    """把本轮探针结果与上轮比，返回 `{flip, previous, since}`。

    **只有 off→on 那一次翻转才是事件**（`OP-0826-U`：不是每轮都报）。首轮
    没有历史 ⇒ `flip=None`，不把「第一次看见 on」当成翻转——那会在装上的
    当天凭空发一条提醒，而什么都没发生。
    """
    previous = state.get("lan", {}).get("on_lan")
    if lan is None:
        return {"flip": None, "previous": previous, "since": None}
    flip = None
    if previous is False and lan["on_lan"] is True:
        flip = "off→on"
    elif previous is True and lan["on_lan"] is False:
        flip = "on→off"
    return {"flip": flip, "previous": previous,
            "since": state.get("lan", {}).get("last_change_utc")}


# ============================================================
# 汇总
# ============================================================

def scan(repo_root: Path, *, lan: bool = True, wide: bool = False,
         state_path: Path | None = None, today: date | None = None,
         sweep_probe: bool | None = None) -> dict:
    """`sweep_probe=None` ＝ 跟随 `lan`：`--skip-lan-probe`（CI／离线／单测）
    连同 sweep 任务查询一起跳过，两者都是「问外部环境」而非「读仓库」。"""
    # 🔴 日期取本机本地日（项目硬规则：写入/比对日期一律用本机，不用 UTC）。
    today = today or date.today()
    state_file = state_path or (repo_root / STATE_REL)
    state = _load_state(state_file)
    base = _base_ref(repo_root)

    form1 = scan_form1(repo_root, today, wide=wide)
    form2 = scan_form2(repo_root, base)
    form3 = scan_form3(repo_root)
    lan_result = probe_lan() if lan else None
    flip = track_lan_flip(state, lan_result)
    # 只在真有主工作区脏文件时才去查——没有那一条时，这次查询的结果不会被
    # 用到，白花一次 `Get-ScheduledTask` 的时间。
    want_sweep = lan if sweep_probe is None else sweep_probe
    sweep = (probe_sweep_task()
             if want_sweep and any(item.get("is_main") for item in form3["items"])
             else None)

    current_keys = {item["key"] for group in (form1["items"], form2["items"], form3["items"])
                    for item in group}
    previous_keys = set(state.get("alerted", {}))
    resolved = sorted(previous_keys - current_keys)

    return {
        "base_ref": base, "today": today.isoformat(), "form1": form1, "form2": form2,
        "form3": form3, "lan": lan_result, "lan_flip": flip, "sweep_task": sweep,
        "resolved": resolved,
        "state_path": str(state_file),
        "unavailable": [reason for reason in
                        (form1["unavailable"], form2["unavailable"], form3["unavailable"])
                        if reason],
    }


def write_state(findings: dict, state_path: Path) -> None:
    """把本轮 key 与 LAN 状态落盘。**已解除的 key 写完这一轮就消失**——
    「✅ 已解除」只报一次，报完即静音，这是判据 ⑶ 的落点。"""
    state = _load_state(state_path)
    now = _now_utc_str()
    alerted = state.get("alerted", {})
    fresh: dict[str, dict] = {}
    for group in ("form1", "form2", "form3"):
        for item in findings[group]["items"]:
            key = item["key"]
            fresh[key] = {"first_seen_utc": alerted.get(key, {}).get("first_seen_utc", now),
                          "last_seen_utc": now}
    lan_state = state.get("lan", {})
    if findings["lan"] is not None:
        changed = lan_state.get("on_lan") != findings["lan"]["on_lan"]
        lan_state = {
            "on_lan": findings["lan"]["on_lan"], "observed_utc": now,
            "last_change_utc": now if changed else lan_state.get("last_change_utc"),
        }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"alerted": fresh, "lan": lan_state}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _format_main_workspace_verdict(item: dict, sweep: dict | None) -> list[str]:
    """主工作区那一条的结论。**有条件、且自带证据**——这一段的全部价值就在于
    把 `LastRunTime` 与各文件 mtime 摆在一起，让人一眼分清「正常时间差」与
    「真漏收」；只删掉「停用期间」四个字会让它退化成一句没有诊断力的话。
    """
    rows = item.get("file_times") or []
    dirty = item["tracked_changes"] + item["untracked"]
    out: list[str] = []

    if not _sweep_is_live(sweep):
        # 停用／取不到：保留原救法文案，但把「我凭什么这么说」一并写出来。
        if sweep and sweep.get("available"):
            basis = f"已实测其 `State={sweep.get('state')}`（LastRun `{sweep.get('last_run')}` 本地）"
        elif sweep:
            basis = (f"⚠️ **取不到任务状态，故本条无法断言 sweep 是否在跑**"
                     f"（{sweep.get('detail')}）")
        else:
            basis = "⚠️ **本轮未查 sweep 状态**（`--skip-lan-probe`）——**不据此判断它在不在跑**"
        out.append("      ⇒ 主工作区的改动本该由落库 sweep 每轮收走；**sweep 停用期间**"
                   "它就是一堆没人收的产出，需人工 commit（不适用下面那条救法）。")
        out.append(f"        {basis}")
        return out

    last_run = _parse_local(sweep.get("last_run"))
    shown = rows[:SWEEP_MTIME_LIST_CAP]
    stale = [r for r in rows if (mt := _parse_local(r["mtime"])) and last_run and mt < last_run]
    unknown = [r for r in rows if r["mtime"] is None]

    out.append(f"      ⇒ 主工作区 {dirty} 个改动未收；落库 sweep **在跑**"
               f"（`State={sweep.get('state')}`｜上一轮 `{sweep.get('last_run')}` 本地"
               f"｜`LastTaskResult={sweep.get('last_result')}`）。")
    out.extend(f"        · `{r['name']}` mtime `{r['mtime'] or '取不到'}`（本地）" for r in shown)
    if len(rows) > len(shown):
        out.append(f"        · 另有 {len(rows) - len(shown)} 个未列出（判定已含它们）")
    if stale:
        out.append(f"      ⇒ 🔴 **其中 {len(stale)} 个文件 mtime 早于上一轮却仍未被收 —— "
                   f"这不是时间差，是真漏收**（多半是没登记 §二 批次）："
                   + "、".join(f"`{r['name']}`" for r in stale[:SWEEP_MTIME_LIST_CAP]))
    if unknown:
        out.append(f"      ⇒ ⚠️ {len(unknown)} 个文件取不到 mtime，**这几个既没被判成时间差、"
                   f"也没被判成漏收**，须人工看一眼："
                   + "、".join(f"`{r['name']}`" for r in unknown[:SWEEP_MTIME_LIST_CAP]))
    if not stale and not unknown:
        out.append(f"      ⇒ 全部晚于上一轮，**属正常时间差、不是漏收**；下一轮 "
                   f"`{sweep.get('next_run') or '（取不到）'}`（本地）会收走。")
    return out


def format_report(findings: dict) -> str:
    lines = [f"# 未闭合产出扫描 · {findings['today']}（只读，不做任何处置）",
             f"比较基准：`{findings['base_ref'] or '（无）'}`"]

    lan = findings["lan"]
    if lan is None:
        lines.append("\n## 回 LAN 感知：本轮已跳过（`--skip-lan-probe`）")
    else:
        flip = findings["lan_flip"]["flip"]
        head = "✅ on-LAN（三项齐备）" if lan["on_lan"] else "⛔ off-LAN（三项未齐）"
        lines.append(f"\n## 回 LAN 感知：{head}")
        if flip == "off→on":
            lines.append("🔔 **本轮由 off 翻到 on —— 下面的 LAN 留步项现在可以补做了。**")
        elif flip == "on→off":
            lines.append("· 本轮由 on 翻到 off（记录在案，不是提醒）。")
        for probe in lan["probes"]:
            mark = "✅" if probe["ok"] else "❌"
            lines.append(f"  {mark} `{probe['probe']}` —— {probe.get('detail', '')}")

    form1 = findings["form1"]
    lines.append(f"\n## 形态 1 · 队列里的 LAN 留步登记：{len(form1['items'])} 处")
    if form1["excluded_section_two"]:
        lines.append(f"（已剔除 §二 批次行里的历史叙述 {form1['excluded_section_two']} 处——"
                     "那些是已完成批次的记述，不是待办）")
    for item in sorted(form1["items"], key=lambda i: -(i["age_days"] or 0)):
        age = f"{item['age_days']} 天" if item["age_days"] is not None else "登记日未知"
        lines.append(f"  · §{item['section']} #{item['row_id']}（{item['queue'].split('/')[-1]}）"
                     f"｜{item['bucket']}／{age}｜`{item['key']}`｜指纹 {item['fingerprint']}"
                     f"｜…{item['excerpt']}…")
    if form1["items"]:
        lines.append("  ⇒ 怎么救：on-LAN 后按行内已写死的补法执行，做完回写该行并销号。")
        # 🔴 这三行是判据 ⑶ 在形态 1 上的全部落点，**不得因为「报告太长」而删**：
        # 关掉一条告警的办法必须印在告警自己身上，否则它就是一条关不掉的告警
        # （`#422` 原缺陷：11 条逐条核实完，重跑一条没减少）。
        lines.append("  ⇒ 🔴 **已核实其中某一处其实早已闭合**（补做方守「历史记录不追改」、"
                     "原字样必然保留，所以它不会自己消失）：先把核实结论写进该队列行，"
                     "再跑——")
        lines.append(f"       python {_SELF_REL} --ack-form1 '<上面那个 key>' "
                     "--note '<你核的是什么、凭什么核的>'")
        lines.append("       指纹只盖该行的留步登记段：无关追加不重开；**新登记一处留步、"
                     "或改写已核过的那一段，自动失效重新告警**。")
    if form1.get("suppressed"):
        # 不做成完全静默（`--ack-stale-change` 的 D2 是完全静默）。理由：一个
        # 只会变长、从不回显的抑制清单，正是本工具要防的「看起来干净」。
        # 只回显条数与 key，不回显详情——详情在 ack 文件里。
        keys = "、".join(i["key"].split("#")[-1] for i in form1["suppressed"])
        lines.append(f"  （另有 {len(form1['suppressed'])} 处**已核实闭合、指纹未变**，"
                     f"本轮静默：{keys}；判定依据见 `{FORM1_ACK_STATE_REL}`）")
    if form1.get("stale_acks"):
        lines.append(f"  ⚠ {len(form1['stale_acks'])} 条确认记录已对不上任何现存行"
                     f"（行归档／编号变／留步字样被整段改写）："
                     + "、".join(form1["stale_acks"]))
    for item in form1.get("wide_items", []):
        lines.append(f"  （宽口径·仅提示）§{item['section']} #{item['row_id']}：…{item['excerpt']}…")

    form2 = findings["form2"]
    lines.append(f"\n## 形态 2 · 代码卡在未合入分支上：{len(form2['items'])} 条分支")
    for item in sorted(form2["items"], key=lambda i: not i.get("is_local_master")):
        where = f"｜worktree `{item['worktree']}`" if item["worktree"] else "｜无 worktree"
        equiv = (f"（另有 {item['patch_equivalent']} 个提交已 patch 等价上游）"
                 if item["patch_equivalent"] else "")
        head = "🔴 **本地 master 已分叉** " if item.get("is_local_master") and item.get("forked") else ""
        behind = f"，落后 {item['behind']} 个" if item.get("behind") else ""
        lines.append(f"  · {head}`{item['branch']}`：{item['unmerged']} 个真·未上游提交"
                     f"{behind}{equiv}{where}")
        lines.extend(f"      {subject}" for subject in item["subjects"])
        if item.get("is_local_master") and item.get("forked"):
            lines.append("      ⇒ 🔴 **不得 `git pull`（会造出违反 ff-only 的 merge）、"
                         "也不得 `push -f`**：把本地独有提交 rebase 到 `origin/master` "
                         "之上再 ff push，或确认它已由别的分支带上去后 ff 对齐本地。")
    if form2["items"]:
        lines.append("  ⇒ 怎么救：先验一眼，再 ff 合入 master（`git rebase origin/master` 后 ff push）；"
                     "验不过则如实登记，不得直接丢弃。")

    form3 = findings["form3"]
    lines.append(f"\n## 形态 3 · 产出只是 worktree 里未 commit 的改动：{len(form3['items'])} 处")
    for item in sorted(form3["items"], key=lambda i: i.get("is_main", False)):
        tag = "（主工作区）" if item.get("is_main") else ""
        lines.append(f"  · `{item['worktree']}`{tag}（分支 `{item['branch'] or 'detached'}`）："
                     f"{item['tracked_changes']} 个已跟踪改动 ＋ {item['untracked']} 个未跟踪"
                     f"，共 {item['insertions']} 行新增")
        lines.extend(f"      {name}" for name in item["files"])
        if item.get("is_main"):
            lines.extend(_format_main_workspace_verdict(item, findings.get("sweep_task")))
    if any(not item.get("is_main") for item in form3["items"]):
        lines.append("  ⇒ 怎么救（linked worktree）：先跑该改动所属子项目的回归，绿则 commit 到"
                     "本分支再合入；🔴 不得丢弃、不得替它改判。任何一次 worktree 清理都会让"
                     "这些行消失。")

    if findings["resolved"]:
        lines.append(f"\n## ✅ 已解除（上一轮报过、本轮不再命中）：{len(findings['resolved'])} 项")
        lines.extend(f"  · `{key}`" for key in findings["resolved"])

    if findings["unavailable"]:
        lines.append("\n## ⚠ 判据不可用（**不据此判为干净**）")
        lines.extend(f"  · {reason}" for reason in findings["unavailable"])

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="未闭合产出扫描（三形态 ＋ 回 LAN 感知），只读")
    parser.add_argument("--repo-root", default=None, help="仓库根（仅测试用）")
    parser.add_argument("--skip-lan-probe", action="store_true",
                        help="不问外部环境（LAN 三项探针 ＋ sweep 任务状态）（CI／离线）")
    parser.add_argument("--wide", action="store_true", help="附带泛「留步」二级提示")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--enforce", action="store_true", help="有发现即非零退出")
    parser.add_argument("--no-write-state", action="store_true", help="不落状态文件")
    parser.add_argument("--state", default=None, help="状态文件路径（仅测试用）")
    parser.add_argument(
        "--ack-form1", default=None, metavar="KEY",
        help="记一次形态 1 的「已核实闭合」确认（key 取自报告行），"
             "带指纹、可自动失效；须配 --note。不扫描、只记录。")
    parser.add_argument(
        "--note", default="",
        help="--ack-form1 配套：本次核的是什么、凭什么核的，必填。")
    args = parser.parse_args(argv)

    repo_root = _resolve_repo_root(args.repo_root)
    if args.ack_form1 is not None:
        return cmd_ack_form1(repo_root, args.ack_form1, args.note)
    state_path = Path(args.state) if args.state else repo_root / STATE_REL
    findings = scan(repo_root, lan=not args.skip_lan_probe, wide=args.wide, state_path=state_path)

    print(json.dumps(findings, ensure_ascii=False, indent=2) if args.json
          else format_report(findings))

    if not args.no_write_state:
        write_state(findings, state_path)

    if not args.enforce:
        return 0
    if findings["unavailable"]:
        return 2
    total = sum(len(findings[form]["items"]) for form in ("form1", "form2", "form3"))
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
