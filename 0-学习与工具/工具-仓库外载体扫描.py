"""仓库外活载体扫描脚本（队列 #227②；队列 #398⑵ 修两类结构性假零）。

背景：协议〇.8"批次变更参数须已复检"的复检手段全部是全库 grep，而以下
四类活载体在 git 仓库之外，任何全库 grep 都不可能命中（#227 实测：sweep
周期 4h→1h 后，Cowork artifact `zhuopin-project-status` 内嵌的 mermaid
流程图仍写着"每 4h"，3 天无人发现——根因就是这四类载体结构性地不在任何
grep 域内）：
  ① Cowork artifacts（本机 `C:\\Users\\Paul Shao\\Claude\\Artifacts\\`）
  ② `.51` 四个服务的页面内嵌文案（保供看板 8091／命令中心 8092／
     QD-B 8093／FI2 8094）
  ③ 已安装版 skill（本机 `C:\\Users\\Paul Shao\\.claude\\skills\\`，
     源码在库、安装版只读）
  ④ 定时任务真身（本机 `C:\\Users\\Paul Shao\\Claude\\Scheduled\\`，
     库内仅镜像）

本脚本把这四类路径纳入同一次可搜索的范围，供"已复检"时逐项过一遍——
不是全库 grep 的替代品，是它结构性覆盖不到的那一块的补充。

🔴 **零命中不等于已核验（队列 #398⑵，2026-08-24 环境体检 §4.2/§4.3 实测
坐实后入法）**——原实现只会输出「命中 N 处」，于是两类**结构上已经扫不到
任何东西**的载体，输出与「真的扫了、真的没有」完全一样：

  · ② `.51` 四服务：四个服务已加访问口令门，HTTP GET 仍返回 **200**，
    但回的是 **1.6 KB 的登录页**、不是看板正文 ⇒ 此后永远命中 0，
    **与页面里写了什么无关**。
  · ③ 已安装版 skill：扫描根 `~/.claude/skills` 下**根本没有本项目的
    skill**（6 个 `zhuopin-*` 安装在 Cowork/claude.ai 侧，不落本机磁盘；
    本机只有源码 `0-学习与工具/skills源码/`）⇒ 此后永远命中 0。
    该类恰是高危载体（`zhuopin-queue-audit` 等若留旧指针，后果同 ④）。

故每一类都必须先过**阳性对照**（这一类此刻究竟还扫不扫得到东西），
过不了就输出「🔴 本类无法核验：<原因>」而**不是**「命中 0 处」，并在
结尾总表里点名。判据没坏、目标变了，而判据不知道目标变了——这一条是
本工具存在的前提，不是可选优化。

只读扫描，不做任何改动；某一类载体路径不存在/网络请求失败，均降级为
"跳过并说明原因"，不视为脚本失败（这些路径本机专属，或依赖内网可达性，
独立于 git 仓库状态——sweep 之外的独立小工具，不需要 sweep 那套"账面
对不上就整体不动"的严格安全门）。

用法：
  python 0-学习与工具/工具-仓库外载体扫描.py "PT1H"
  python 0-学习与工具/工具-仓库外载体扫描.py "PT1H" --skip-http   # 不联网检查 .51 页面
  python 0-学习与工具/工具-仓库外载体扫描.py "PT1H" --strict      # 有类无法核验即退出码 2

退出码：0 ＝ 全部类别均已核验（命中数可信）；2 ＝ 有类别无法核验且传了
`--strict`。默认不传 `--strict` 时恒为 0，以免改变既有调用方的语义；
供机器消费（如月度体检 §九 第 3 项复测）时请显式传 `--strict`。
"""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path

ARTIFACTS_DIR = Path(r"C:\Users\Paul Shao\Claude\Artifacts")
SCHEDULED_DIR = Path(r"C:\Users\Paul Shao\Claude\Scheduled")
SKILLS_DIR = Path(r"C:\Users\Paul Shao\.claude\skills")
# ③ 类阳性对照的参照物：本项目 skill 的**源码**目录（在库内，恒可得）。
# 安装版是否真的覆盖了这些名字，就是"这一类还扫不扫得到本项目的东西"。
SKILL_SOURCE_DIR = Path(__file__).resolve().with_name("skills源码")

# 命令中心/保供看板/QD-B/FI2 四服务，见 CLAUDE.md §5 端口约定。
SERVICE_URLS = (
    "http://192.168.100.51:8091/",
    "http://192.168.100.51:8092/",
    "http://192.168.100.51:8093/",
    "http://192.168.100.51:8094/",
)

HTTP_TIMEOUT_SECONDS = 5
# 只扫描这些文本类扩展名——目录里可能混有图片/字体等二进制文件，读取会
# 抛 UnicodeDecodeError，扫描脚本对此降级跳过该文件，不视为失败。
TEXT_FILE_SUFFIXES = {
    ".html", ".htm", ".md", ".txt", ".json", ".js", ".ts", ".py", ".ps1",
    ".yaml", ".yml", ".xml", ".css",
}

# ② 类阳性对照的判据：命中任一即认定"这是一道门禁页，不是看板正文"。
# 用**门禁自身的特征**判定，不用页面大小之类的启发式——大小会随改版漂移，
# 而"页面里有个密码输入框"这件事，只要门还在就一直成立。
AUTH_GATE_MARKERS = (
    'type="password"',
    "type='password'",
    "访问口令",
    "请输入口令",
    "请输入密码",
)


def _scan_directory_for_keyword(base_dir: Path, keyword: str) -> list[dict]:
    """遍历 `base_dir` 下所有文本类文件，逐行查找 `keyword`（纯子串匹配，
    非正则）。目录不存在时返回空列表（由调用方决定是否单独提示"已跳过"）。
    """
    if not base_dir.exists():
        return []
    hits = []
    for path in sorted(base_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if keyword in line:
                hits.append({
                    "path": str(path),
                    "line_no": line_no,
                    "line": line.strip(),
                })
    return hits


def count_scannable_files(base_dir: Path) -> int:
    """`base_dir` 下本工具**真的会去读**的文本文件数。

    ①④ 两类的阳性对照：目录还在、但里面一个可扫文件都没有（被搬走／
    改了扩展名／换了根路径），此时零命中同样不构成"已复检"。
    """
    if not base_dir.exists():
        return 0
    return sum(
        1 for p in base_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_FILE_SUFFIXES
    )


def scan_cowork_artifacts(keyword: str, artifacts_dir: Path = ARTIFACTS_DIR) -> list[dict]:
    return _scan_directory_for_keyword(artifacts_dir, keyword)


def scan_scheduled_tasks(keyword: str, scheduled_dir: Path = SCHEDULED_DIR) -> list[dict]:
    return _scan_directory_for_keyword(scheduled_dir, keyword)


def scan_installed_skills(keyword: str, skills_dir: Path = SKILLS_DIR) -> list[dict]:
    return _scan_directory_for_keyword(skills_dir, keyword)


def project_skill_names(source_dir: Path = SKILL_SOURCE_DIR) -> set[str]:
    """本项目自有 skill 的名字集合，取自库内源码目录的子目录名。

    源码目录不存在时返回空集——调用方据此判定"参照物缺失"，同样属于
    无法核验，不得退化成"没有本项目 skill，所以零命中正常"。
    """
    if not source_dir.is_dir():
        return set()
    return {p.name for p in source_dir.iterdir() if p.is_dir()}


def installed_project_skills(
    skills_dir: Path = SKILLS_DIR, source_dir: Path = SKILL_SOURCE_DIR,
) -> tuple[set[str], set[str]]:
    """③ 类阳性对照：返回 (已安装的本项目 skill 名, 未安装的本项目 skill 名)。

    判据是"扫描根下是否真的存在本项目的 skill"，不是"扫描根下有没有东西"
    ——`~/.claude/skills` 一直有 2 个与本项目无关的第三方 skill，正是它们
    让这一类看上去"扫了"。
    """
    expected = project_skill_names(source_dir)
    if not skills_dir.is_dir():
        return set(), expected
    present = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    return expected & present, expected - present


def looks_like_auth_gate(body: str) -> bool:
    """页面正文是否是一道访问口令门（而不是看板正文）。"""
    lowered = body.lower()
    return any(marker.lower() in lowered for marker in AUTH_GATE_MARKERS)


def scan_51_services(
    keyword: str, service_urls: tuple[str, ...] = SERVICE_URLS,
    timeout: float = HTTP_TIMEOUT_SECONDS,
) -> tuple[list[dict], list[dict], list[dict]]:
    """HTTP GET 每个 `.51` 服务页面并原文查找 `keyword`。

    返回 (hits, unreachable, gated)：
      · unreachable —— 连接失败的 URL 与原因（内网不可达/超时/非 200 等）；
        不视为脚本失败，只是"这一处这次没扫到"。
      · gated —— **返回了 200、但正文是访问口令门**的 URL。🔴 这一类
        必须与 unreachable 分开报：它在网络层完全正常，只有内容层是错的，
        原实现把它计入"扫过了、零命中"，正是队列 #398⑵ 要修的假零。

    ⚠️ 返回值由 2 元组扩为 3 元组（#398⑵）——旧签名结构上无法表达"扫到了
    但扫的是门"，调用方必须显式处理 gated，不能再靠 hits 为空蒙混过关。
    """
    hits: list[dict] = []
    unreachable: list[dict] = []
    gated: list[dict] = []
    for url in service_urls:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            unreachable.append({"url": url, "reason": str(exc)})
            continue
        if looks_like_auth_gate(body):
            gated.append({
                "url": url,
                "reason": f"返回 200 但正文是访问口令登录页（{len(body)} 字节），非看板正文",
            })
            continue
        for line_no, line in enumerate(body.splitlines(), 1):
            if keyword in line:
                hits.append({"path": url, "line_no": line_no, "line": line.strip()})
    return hits, unreachable, gated


def _print_hits(title: str, hits: list[dict]) -> None:
    print(f"\n【{title}】命中 {len(hits)} 处")
    for hit in hits:
        print(f"  {hit['path']}:{hit['line_no']}: {hit['line']}")


def _print_unverifiable(title: str, reason: str) -> None:
    print(f"\n【{title}】🔴 本类无法核验：{reason}")
    print("  ⇒ 本类**没有**零命中结论可用；不得据此做任何「已复检」声明。")


def _print_summary(statuses: list[tuple[str, bool, str]]) -> int:
    """打印核验状态总表，返回无法核验的类别数。"""
    unverifiable = [s for s in statuses if not s[1]]
    print("\n" + "=" * 60)
    print("核验状态总表（零命中是否可信，逐类）")
    for label, ok, detail in statuses:
        mark = "✅ 已核验" if ok else "🔴 无法核验"
        print(f"  {mark}  {label}　{detail}")
    if unverifiable:
        print(
            f"\n🔴 本次 {len(unverifiable)}/{len(statuses)} 类无法核验："
            + "、".join(s[0] for s in unverifiable)
        )
        print("   这些类别的「零命中」不构成证据，复检结论只能覆盖已核验的类别。")
    else:
        print("\n✅ 四类全部已核验，本次命中数可作为「已复检」的依据。")
    print("=" * 60)
    return len(unverifiable)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keyword", help="要查找的关键词（纯子串匹配，非正则）")
    parser.add_argument("--skip-http", action="store_true", help="不联网检查 .51 四服务页面")
    parser.add_argument(
        "--strict", action="store_true",
        help="有类别无法核验即以退出码 2 结束（供机器消费，如月度体检复测）",
    )
    parser.add_argument("--artifacts-dir", default=None, help="仅测试用：覆盖 Cowork artifacts 目录")
    parser.add_argument("--scheduled-dir", default=None, help="仅测试用：覆盖定时任务真身目录")
    parser.add_argument("--skills-dir", default=None, help="仅测试用：覆盖已安装版 skill 目录")
    parser.add_argument("--skill-source-dir", default=None, help="仅测试用：覆盖 skill 源码目录")
    parser.add_argument(
        "--service-urls", default=None,
        help="仅测试用：逗号分隔覆盖 .51 四服务 URL",
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else ARTIFACTS_DIR
    scheduled_dir = Path(args.scheduled_dir) if args.scheduled_dir else SCHEDULED_DIR
    skills_dir = Path(args.skills_dir) if args.skills_dir else SKILLS_DIR
    skill_source_dir = (
        Path(args.skill_source_dir) if args.skill_source_dir else SKILL_SOURCE_DIR
    )
    service_urls = (
        tuple(args.service_urls.split(",")) if args.service_urls else SERVICE_URLS
    )

    print(f"扫描关键词：{args.keyword!r}")
    statuses: list[tuple[str, bool, str]] = []

    # ①④：阳性对照 ＝ 目录存在，且下面真的有本工具会读的文本文件。
    for label, base_dir, scan_fn in (
        ("① Cowork artifacts", artifacts_dir, scan_cowork_artifacts),
        ("④ 定时任务真身", scheduled_dir, scan_scheduled_tasks),
    ):
        if not base_dir.exists():
            _print_unverifiable(label, f"扫描根目录不存在：{base_dir}")
            statuses.append((label, False, f"目录不存在 {base_dir}"))
            continue
        scannable = count_scannable_files(base_dir)
        if scannable == 0:
            _print_unverifiable(
                label, f"目录存在但其下 0 个可扫文本文件：{base_dir}（是否已被搬走／改扩展名？）",
            )
            statuses.append((label, False, "目录下 0 个可扫文件"))
            continue
        hits = scan_fn(args.keyword, base_dir)
        _print_hits(label, hits)
        statuses.append((label, True, f"扫过 {scannable} 个文件，命中 {len(hits)} 处"))

    # ③：阳性对照 ＝ 扫描根下真的存在**本项目**的 skill（不是随便有东西）。
    label = "③ 已安装版 skill"
    expected = project_skill_names(skill_source_dir)
    installed, missing = installed_project_skills(skills_dir, skill_source_dir)
    if not expected:
        _print_unverifiable(
            label, f"参照物缺失——skill 源码目录不存在或为空：{skill_source_dir}",
        )
        statuses.append((label, False, "无参照物，无法判断覆盖面"))
    elif not installed:
        _print_unverifiable(
            label,
            f"扫描根 {skills_dir} 下不存在任何本项目 skill"
            f"（本项目 {len(expected)} 个：{'／'.join(sorted(expected))}）"
            "——已安装版在 Cowork/claude.ai 侧，不落本机磁盘，本机永远扫不到",
        )
        statuses.append((label, False, f"本项目 {len(expected)} 个 skill 一个都不在扫描根下"))
    else:
        hits = scan_installed_skills(args.keyword, skills_dir)
        _print_hits(label, hits)
        if missing:
            print(
                f"  ⚠ 部分覆盖：本项目 {len(expected)} 个 skill 中 {len(missing)} 个不在扫描根下"
                f"（{'／'.join(sorted(missing))}），这些未被核验"
            )
        statuses.append((
            label, True,
            f"覆盖本项目 {len(installed)}/{len(expected)} 个 skill，命中 {len(hits)} 处",
        ))

    # ②：阳性对照 ＝ 取回的正文是看板正文，而不是访问口令门。
    label = "② .51 四服务页面"
    if args.skip_http:
        print(f"\n【{label}】已按 --skip-http 跳过联网检查")
        _print_unverifiable(label, "本次按 --skip-http 未联网，本类未扫")
        statuses.append((label, False, "--skip-http 未扫"))
    else:
        hits, unreachable, gated = scan_51_services(args.keyword, service_urls)
        reachable_count = len(service_urls) - len(unreachable) - len(gated)
        if reachable_count == 0:
            reason_parts = []
            if gated:
                reason_parts.append(f"{len(gated)} 个返回 200 但正文是访问口令登录页")
            if unreachable:
                reason_parts.append(f"{len(unreachable)} 个不可达（内网不通/超时）")
            _print_unverifiable(label, "；".join(reason_parts) + "——无一取到看板正文")
            for item in gated + unreachable:
                print(f"    - {item['url']}：{item['reason']}")
            statuses.append((label, False, f"0/{len(service_urls)} 个服务取到正文"))
        else:
            _print_hits(label, hits)
            for item in gated:
                print(f"  🔴 口令门（本页未核验）：{item['url']}：{item['reason']}")
            for item in unreachable:
                print(f"  ⚠ 不可达（本页未核验）：{item['url']}：{item['reason']}")
            detail = f"{reachable_count}/{len(service_urls)} 个服务取到正文，命中 {len(hits)} 处"
            statuses.append((label, not (gated or unreachable), detail))

    unverifiable_count = _print_summary(statuses)
    if args.strict and unverifiable_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
