"""仓库外活载体扫描脚本（队列 #227②）。

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

只读扫描，不做任何改动；某一类载体路径不存在/网络请求失败，均降级为
"跳过并说明原因"，不视为脚本失败（这些路径本机专属，或依赖内网可达性，
独立于 git 仓库状态——sweep 之外的独立小工具，不需要 sweep 那套"账面
对不上就整体不动"的严格安全门）。

用法：
  python 0-学习与工具/工具-仓库外载体扫描.py "PT1H"
  python 0-学习与工具/工具-仓库外载体扫描.py "PT1H" --skip-http   # 不联网检查 .51 页面
"""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path

ARTIFACTS_DIR = Path(r"C:\Users\Paul Shao\Claude\Artifacts")
SCHEDULED_DIR = Path(r"C:\Users\Paul Shao\Claude\Scheduled")
SKILLS_DIR = Path(r"C:\Users\Paul Shao\.claude\skills")

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


def scan_cowork_artifacts(keyword: str, artifacts_dir: Path = ARTIFACTS_DIR) -> list[dict]:
    return _scan_directory_for_keyword(artifacts_dir, keyword)


def scan_scheduled_tasks(keyword: str, scheduled_dir: Path = SCHEDULED_DIR) -> list[dict]:
    return _scan_directory_for_keyword(scheduled_dir, keyword)


def scan_installed_skills(keyword: str, skills_dir: Path = SKILLS_DIR) -> list[dict]:
    return _scan_directory_for_keyword(skills_dir, keyword)


def scan_51_services(
    keyword: str, service_urls: tuple[str, ...] = SERVICE_URLS,
    timeout: float = HTTP_TIMEOUT_SECONDS,
) -> tuple[list[dict], list[dict]]:
    """HTTP GET 每个 `.51` 服务页面并原文查找 `keyword`。

    返回 (hits, unreachable)：unreachable 记录连接失败的 URL 与原因
    （内网不可达/超时/非 200 等）——不视为脚本失败，只是"这一处这次没扫到"。
    """
    hits: list[dict] = []
    unreachable: list[dict] = []
    for url in service_urls:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            unreachable.append({"url": url, "reason": str(exc)})
            continue
        for line_no, line in enumerate(body.splitlines(), 1):
            if keyword in line:
                hits.append({"path": url, "line_no": line_no, "line": line.strip()})
    return hits, unreachable


def _print_section(title: str, hits: list[dict]) -> None:
    print(f"\n【{title}】命中 {len(hits)} 处")
    for hit in hits:
        print(f"  {hit['path']}:{hit['line_no']}: {hit['line']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keyword", help="要查找的关键词（纯子串匹配，非正则）")
    parser.add_argument("--skip-http", action="store_true", help="不联网检查 .51 四服务页面")
    parser.add_argument("--artifacts-dir", default=None, help="仅测试用：覆盖 Cowork artifacts 目录")
    parser.add_argument("--scheduled-dir", default=None, help="仅测试用：覆盖定时任务真身目录")
    parser.add_argument("--skills-dir", default=None, help="仅测试用：覆盖已安装版 skill 目录")
    parser.add_argument(
        "--service-urls", default=None,
        help="仅测试用：逗号分隔覆盖 .51 四服务 URL",
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else ARTIFACTS_DIR
    scheduled_dir = Path(args.scheduled_dir) if args.scheduled_dir else SCHEDULED_DIR
    skills_dir = Path(args.skills_dir) if args.skills_dir else SKILLS_DIR
    service_urls = (
        tuple(args.service_urls.split(",")) if args.service_urls else SERVICE_URLS
    )

    print(f"扫描关键词：{args.keyword!r}")

    for label, base_dir, scan_fn in (
        ("① Cowork artifacts", artifacts_dir, scan_cowork_artifacts),
        ("④ 定时任务真身", scheduled_dir, scan_scheduled_tasks),
        ("③ 已安装版 skill", skills_dir, scan_installed_skills),
    ):
        if not base_dir.exists():
            print(f"\n【{label}】目录不存在，跳过：{base_dir}")
            continue
        hits = scan_fn(args.keyword, base_dir)
        _print_section(label, hits)

    if args.skip_http:
        print("\n【② .51 四服务页面】已按 --skip-http 跳过联网检查")
    else:
        hits, unreachable = scan_51_services(args.keyword, service_urls)
        _print_section("② .51 四服务页面", hits)
        if unreachable:
            print(f"  ⚠ {len(unreachable)} 个服务不可达（内网不通/超时属正常，不视为脚本失败）：")
            for item in unreachable:
                print(f"    - {item['url']}：{item['reason']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
