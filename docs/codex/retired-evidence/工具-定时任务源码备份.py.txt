"""定时任务 prompt 自动回镜（队列 #169）。

背景：`Claude\\Scheduled\\<taskId>\\SKILL.md` 是值周巡检/拆件巡逻等自动化机制的
全部实现，此前无任何版本保护。2026-07-30 已建立人工兜底镜像
（`0-学习与工具/定时任务源码/<taskId>.SKILL.md`，见该目录 README.md），但回镜
第 3 步（"回镜到本目录"）此前全靠人记得。本脚本把这一步自动化。

方向严格单向：真身（`Claude\\Scheduled\\`）→ 镜像（本目录 `定时任务源码/`）。
本脚本只从真身读、只往镜像写，结构上不提供任何反向路径——同 README.md 强调的
"改镜像不生效"是同一类陷阱，勿写反。

白名单：与 `定时任务源码/README.md`「镜像范围」表严格同步（见 WHITELIST 常量）。
扩大范围需同时改这里与该表，不做成自动发现全部任务——README 已注明"刻意不镜"
Paul 个人投资类扫描与已废弃/一次性任务，自动发现会把这些也镜进公司项目仓库。

凭据扫描 fail-closed：回镜前逐任务扫描，命中任一模式即拒绝写入该任务的镜像
（不静默入库），不影响其余任务的正常回镜。扫描类别取自 README.md「安全前置」
小节既有判据：webhook URL（`qyapi.weixin`/`webhook/send?key=`）、apiKey/secret/
token 实值、`ZP_GATE_PASSWORD` 等口令、长随机串、`sa` 账号口令。

用法：
  python 0-学习与工具/工具-定时任务源码备份.py
  python 0-学习与工具/工具-定时任务源码备份.py --source-dir <path> --mirror-dir <path>   # 仅测试用

退出码：0=全部任务已处理（含 unchanged/updated/missing_source）；1=至少一个任务
因命中凭据扫描被拒绝写入，需人工核实真身内容后再决定如何处理（脚本不提供绕过
开关，绕过需要人工直接确认后手动复制，不应由脚本自动完成）。
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

WHITELIST = (
    "huijian-chaijian-patrol",
    "weekly-status-update",
    "check-skill-plugin-updates",
    # 2026-09-10 补两条（`OP-0910-A`）：跑本脚本时报出「只认得 3 条」，
    # 而 `mcp__scheduled-tasks__list_scheduled_tasks` 现取实有 6 条 ⇒
    # 白名单是**写死的清单**，新任务建好不会自己进来（同族＝队列 §一
    # `#535` 夹具硬编码／`#537` 锚点数写死）。
    "zhuopin-lan-closeout-reminder",  # 项目机制，此前一直漏镜、非刻意排除
    "poll-opener-batch",              # 承接 `#551`／`UPS5:7` 的机器守本体
    # 🔴 仍**刻意不镜** `claude-force-close-verify-0905`：其自述「出结论即
    #    请求关停」＝一次性任务，属 README「不镜的」第二类。
)

# 🔴 **黑名单：刻意不镜、且已确认过的目录**（Shao Peishen 2026-09-10 答 `2c`）。
# 与 WHITELIST 合起来构成「已分类集合」；**任何在册目录两表皆无 ⇒ 告警**。
#
# **为什么保白名单而不是改成自动发现（他 2026-09-10 裁 (c) 的理由）**：
# 自动发现＋黑名单排除，漏一个只是多镜一份；但**新建的个人任务会默认进公司
# 仓库**，那是泄漏面。⇒ 方向不变，改为**双列 + 未分类即告警**：既不会静默
# 漏镜（今天 `zhuopin-lan-closeout-reminder` 就是这么漏了多日），也不会把
# 他的个人扫描自动搬进来。
#
# 🔴 **分类依据是注册表，不是猜名字**：2026-09-10 现取
# `mcp__scheduled-tasks__list_scheduled_tasks` **实有 6 条在册**，而本目录下
# 有 12 个任务目录 ⇒ **另外 6 个是注册表里已经没有的孤儿目录**（任务删了、
# 目录留着）。孤儿不是「待镜候选」，归黑名单。
BLACKLIST = (
    # —— 注册表已无（孤儿目录，2026-09-10 现取坐实）——
    "migration-observation-daily-check",
    "restore-commit-sweep-reminder",
    "wave-0826-watch",
    "morning-briefing",
    "obsidian-localize-clipping-images",
    "sanhuan-300408-weekly-scan",
    # —— 在册但刻意不镜 ——
    "claude-force-close-verify-0905",  # 自述「出结论即请求关停」＝一次性
    # —— 非任务目录 ——
    "_backup-20260813",
)

#: 目录名以此开头的一律不当任务看（工具自建的备份/临时目录）。
NON_TASK_PREFIXES = ("_", ".")

DEFAULT_SOURCE_DIR = Path.home() / "Claude" / "Scheduled"
DEFAULT_MIRROR_DIR = Path(__file__).resolve().with_name("定时任务源码")

# 凭据扫描模式：命中任一即 fail-closed。宁可误报（人工看一眼即可排除），
# 不可漏报（漏报即凭据入库，明文暴露即吊销+轮换，代价远高于误报的复核成本）。
_CREDENTIAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"qyapi\.weixin\.qq\.com/cgi-bin/webhook/send\?key="), "企微 webhook URL 含 key 参数"),
    (re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"), "疑似 API key/secret/token 实值"),
    (re.compile(r"ZP_GATE_PASSWORD\s*=\s*\S+"), "ZP_GATE_PASSWORD 明文口令"),
    (re.compile(r"(?i)\bsa\b[^\n]{0,20}(password|口令|密码)\s*[:=]"), "sa 账号口令"),
    (re.compile(r"[A-Za-z0-9+/]{64,}={0,2}"), "疑似长随机串/base64 密钥（64+ 字符，高于 git SHA 40 位长度以降误报）"),
)


@dataclass
class MirrorResult:
    task_id: str
    status: str  # "updated" | "unchanged" | "missing_source" | "credential_blocked"
    detail: str = ""


def scan_for_credentials(content: str) -> list[str]:
    """返回命中的凭据类别标签列表；空列表＝未命中，可安全回镜。"""
    return [label for pattern, label in _CREDENTIAL_PATTERNS if pattern.search(content)]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mirror_one_task(source_dir: Path, mirror_dir: Path, task_id: str) -> MirrorResult:
    """单个任务的回镜判定与执行。只读 source_dir、只写 mirror_dir——方向单向。"""
    real_path = source_dir / task_id / "SKILL.md"
    if not real_path.exists():
        return MirrorResult(task_id, "missing_source", f"真身不存在：{real_path}")

    content = real_path.read_text(encoding="utf-8")
    hits = scan_for_credentials(content)
    if hits:
        return MirrorResult(task_id, "credential_blocked", "；".join(hits))

    mirror_path = mirror_dir / f"{task_id}.SKILL.md"
    if mirror_path.exists():
        existing = mirror_path.read_text(encoding="utf-8")
        if _sha256(existing) == _sha256(content):
            return MirrorResult(task_id, "unchanged")

    mirror_dir.mkdir(parents=True, exist_ok=True)
    mirror_path.write_text(content, encoding="utf-8")
    return MirrorResult(task_id, "updated")


def run_backup(
    source_dir: Path, mirror_dir: Path, whitelist: tuple[str, ...] = WHITELIST
) -> list[MirrorResult]:
    return [mirror_one_task(source_dir, mirror_dir, task_id) for task_id in whitelist]


_STATUS_LABEL = {
    "updated": "✓ 已更新镜像",
    "unchanged": "· 无变化",
    "missing_source": "⚠ 真身不存在（任务可能已被删除/改名）",
    "credential_blocked": "🔴 命中凭据扫描·已拒绝写入",
}


def format_report(results: list[MirrorResult]) -> str:
    lines = ["=== 定时任务 prompt 回镜报告（单向：真身 → 镜像，勿写反） ==="]
    for r in results:
        line = f"  {r.task_id}: {_STATUS_LABEL[r.status]}"
        if r.detail:
            line += f"（{r.detail}）"
        lines.append(line)

    blocked = [r for r in results if r.status == "credential_blocked"]
    if blocked:
        lines.append(
            f"\n⚠️ {len(blocked)} 个任务因命中凭据扫描被拒绝写入镜像。"
            "本脚本不提供绕过开关——需人工打开真身文件核实是否为误报，"
            "确认无凭据后手动复制到镜像目录，不应自动强行写入。"
        )
    return "\n".join(lines)


def find_unclassified(source_dir: Path | None = None) -> list[str]:
    """列出**既不在白名单、也不在黑名单**的任务目录（Shao Peishen 2026-09-10 答 `2c`）。

    🔴 **这是本文件从「人守」变成「机器守」的那一步。** 在它之前，白名单漏了
    一个任务，表现是**什么都不发生**——`zhuopin-lan-closeout-reminder` 就这样
    无版本保护地裸奔了多日，直到 2026-09-10 有人偶然跑了一次脚本、数了数
    「怎么只有 3 条」才发现。🔑 **一个只在「有事」时出声、而漏项恰好表现为
    「没事」的机制，等于没有。**

    ⚠️ **本函数只看目录，看不见注册表**：脚本跑在本机 Python 里，拿不到
    `mcp__scheduled-tasks__*`。⇒ 任务被删除后**目录仍在**，本函数看不出来；
    这类孤儿一律靠 `BLACKLIST` 显式排除（现有 6 个已排）。**新建任务一定会
    新建目录，所以「漏镜」这个方向是守得住的**——守不住的只有反方向（已删
    任务仍留在白名单），代价仅为多镜一份陈旧文本，可接受。
    """
    source_dir = source_dir or DEFAULT_SOURCE_DIR
    if not source_dir.exists():
        return []
    known = set(WHITELIST) | set(BLACKLIST)
    out = []
    for d in sorted(source_dir.iterdir()):
        if not d.is_dir() or d.name in known:
            continue
        if d.name.startswith(NON_TASK_PREFIXES):
            continue
        out.append(d.name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--source-dir", default=None, help="仅测试用：覆盖真身目录（默认 ~/Claude/Scheduled）")
    parser.add_argument("--mirror-dir", default=None, help="仅测试用：覆盖镜像目录（默认本文件同目录下 定时任务源码/）")
    args = parser.parse_args()

    source_dir = Path(args.source_dir) if args.source_dir else DEFAULT_SOURCE_DIR
    mirror_dir = Path(args.mirror_dir) if args.mirror_dir else DEFAULT_MIRROR_DIR

    results = run_backup(source_dir, mirror_dir)
    print(format_report(results))

    # 🔴 零命中也回显（同 sweep 第 4/6/7/9 类惯例）：一个从来不出声的检查，
    #    没人能判断它是「没问题」还是「没跑」。
    unclassified = find_unclassified(source_dir)
    if unclassified:
        print(
            f"\n🔴 **{len(unclassified)} 个在册任务目录既不在白名单也不在黑名单**"
            f"——它们**不会被镜像、也不会有人发现**：\n  - "
            + "\n  - ".join(f"`{n}`" for n in unclassified)
            + "\n  ⇒ 逐个判定后写进 WHITELIST（项目机制）或 BLACKLIST（个人/一次性/孤儿），"
              "并同步 `定时任务源码/README.md`「镜像范围」表。"
        )
    else:
        print(f"\n✅ 任务目录分类完备：白名单 {len(WHITELIST)} ＋ 黑名单 {len(BLACKLIST)}，无未分类。")

    return 1 if any(r.status == "credential_blocked" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
