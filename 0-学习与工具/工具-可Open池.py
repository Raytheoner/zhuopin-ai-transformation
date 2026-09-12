#!/usr/bin/env python3
"""可 Open 池——只读 CLI 薄壳（队列 #312，2026-09-02 裁定「两侧共用同一判定函数」）。

判据**不在本文件**，在 `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/
open_pool.py`（唯一权威实现）。本文件只做两件事：把仓库根喂给它、把结果按调用方
要的形状打印出来。两个消费方：
  · 看板数据层 `工具-项目状态卡数据层.ps1` —— `--json-b64`，取 `@@POOL64@@` 前缀那一行
    （内容＝UTF-8 JSON 的 base64，**stdout 纯 ASCII**：PowerShell 解码子进程 stdout 走
    `[Console]::OutputEncoding`，在 Windows-MCP 等无控制台宿主里不可控，中文 `机／业` 一旦
    被按 GBK 解就整卡分组失效且不报错——base64 把编码问题从通道上拿掉）；
  · 其它程序消费 —— `--json`，取 `@@POOL@@` 前缀那一行（明文 UTF-8 JSON）；
  · 人／值周巡检 —— 不带 `--json`，打印可读清单（编号｜字段｜任务首段），含
    被排除单列（poolEx）与字段缺失（poolDeg）两段，便于反查。
企微推送器 `aibot_service/open_pool_reminder.py` 不经本文件，直接 import 权威模块。

🔴 任一份队列文件读不到 ⇒ exit 2 且 `errors` 非空——**残缺的结果不当作完整的池**
（`#312` 缺口一形态：读侧只跟一份、池看起来正常、实际少一半）。
纯只读：不改文件、不触发动作、不发通知。
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# 同 `工具-队列查询.py`／`工具-共享文档编辑锁.py` 既有引导：按本脚本所在 checkout
# 的本地路径找 zhuopin_platform，import 结果与全局 editable 安装指向谁无关（队列 #306）。
_SEARCH_ROOT = Path(__file__).resolve().parents[1]
_PLATFORM_PATH = _SEARCH_ROOT / "5-平台底座" / "zhuopin_platform"
if str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools.open_pool import (  # noqa: E402
    VERDICT_DEGRADED,
    VERDICT_EXCLUDED,
    compute_open_pool,
    snapshot_to_kanban_payload,
)

JSON_PREFIX = "@@POOL@@"
JSON_B64_PREFIX = "@@POOL64@@"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="可 Open 池只读查询（判据在 shared_tools/open_pool.py）")
    parser.add_argument(
        "--repo-root", default=str(_SEARCH_ROOT),
        help="仓库根（默认＝本脚本所在 checkout；看板 ps1 显式传 $root）",
    )
    parser.add_argument("--json", action="store_true", help="输出一行 @@POOL@@ + 压缩 JSON（明文 UTF-8）")
    parser.add_argument(
        "--json-b64", action="store_true",
        help="输出一行 @@POOL64@@ + base64(UTF-8 JSON)（看板数据层契约，stdout 纯 ASCII）",
    )
    args = parser.parse_args(argv)

    snapshot = compute_open_pool(Path(args.repo_root))
    payload = snapshot_to_kanban_payload(snapshot)
    if args.json or args.json_b64:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if args.json_b64:
            sys.stdout.write(JSON_B64_PREFIX + base64.b64encode(compact.encode("utf-8")).decode("ascii") + "\n")
        else:
            sys.stdout.write(JSON_PREFIX + compact + "\n")
    else:
        pool = sorted(snapshot.pool, key=lambda rv: int(rv[1].row_id) if rv[1].row_id.isdigit() else 0)
        by_dom = {"机": [], "业": []}
        for _rel, v in pool:
            by_dom.setdefault(v.domain or "?", []).append(v)
        print(f"可 Open 池 {len(pool)} 行（机 {len(by_dom['机'])}／业 {len(by_dom['业'])}）")
        for dom in ("机", "业"):
            for v in by_dom[dom]:
                flag = f"　⚠️ {v.flag}" if v.flag else ""
                print(f"  #{v.row_id} ｜ [S:{v.status}][D:{dom}] ｜ {v.lead_task}{flag}")
        ex = snapshot.of(VERDICT_EXCLUDED)
        if ex:
            print(f"排除单列（{len(ex)}）：" + "，".join(f"#{v.row_id}（{v.why}）" for _r, v in ex))
        deg = snapshot.of(VERDICT_DEGRADED)
        if deg:
            print(f"字段缺失/无法判定（{len(deg)}）：" + "，".join(f"#{v.row_id}（{v.why}）" for _r, v in deg))
        if payload["skipped"]:
            print("列数不符未纳入判定：" + "，".join(f"#{n}" for n in payload["skipped"]))
        for err in payload["errors"]:
            print(f"🔴 读取失败：{err['file']} — {err['why']}")
    return 2 if snapshot.errors else 0


if __name__ == "__main__":
    sys.exit(main())
