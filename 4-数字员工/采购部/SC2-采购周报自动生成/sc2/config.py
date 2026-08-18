"""SC2 配置 —— 路径、路由前缀、推送范围。

🔴 **所有自动生成物一律落在场景 `reports/` 下**（spec sc2-weekly-report）。
该目录已被仓库 `.gitignore` 的 `**/reports/` 规则覆盖（`git check-ignore -v`
实测命中 `.gitignore:28`）。散落到场景根目录的生成物会被落库 sweep 判为孤儿
脏文件并持续告警——#322 的编辑锁 `.mutex.stale` 就是这么响了 17.1 小时。
"""
from __future__ import annotations

import os
from pathlib import Path

#: 场景根目录（本文件的上一级）。
SCENE_ROOT = Path(__file__).resolve().parent.parent

#: 统一门户路由前缀（design D2/D9）。**自首版即为目标态**，网关落地后只改映射、
#: 不改场景代码。
ROUTE_PREFIX = "/procurement/sc2"

#: 过渡期服务端口。**8096**，Shao Peishen 2026-08-18 部署当日改判。
#: 🔴 design 审 ④(a) 原定 8095，其依据「顺延现网 8091-8094」是**错的**——部署前
#: 实测 `.51` 上 8090（UnifiedPortalGateway）与 8095（ZhuopinRecruitAgent，
#: uvicorn，计划任务已注册且 Running）**均已被占用**，当初那次端口普查漏了两个。
#: ⚠️ 这是对「新场景一律不新起端口对外」硬约束的**显式豁免**，已获 Shao Peishen
#: 认可；注销条件＝统一门户网关落地后收编。详见场景 CLAUDE.md「部署状态」段。
DEFAULT_PORT = 8096

SERVICE_NAME = "SC2 采购周报"


def reports_dir() -> Path:
    """生成物目录。可用 `SC2_REPORTS_DIR` 覆盖（测试用），缺省为场景 `reports/`。"""
    override = os.environ.get("SC2_REPORTS_DIR", "").strip()
    path = Path(override) if override else SCENE_ROOT / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_path(period: str) -> Path:
    """某期周报快照。`period` 为 ISO 周标签，如 ``2026-W34``。"""
    return reports_dir() / f"sc2_weekly_{period}.json"


def publish_state_path() -> Path:
    """发布确认状态（跨进程持久化，spec sc2-anomaly-review）。"""
    return reports_dir() / "sc2_publish_state.json"


def audit_path() -> Path:
    """场景审计 JSONL（平台 `audit` 的 sink）。"""
    return reports_dir() / "sc2_audit.jsonl"


def connector_trace_path() -> Path:
    """连接器访问痕迹（与合规 audit 物理分离，见底座 connector_audit 说明）。"""
    return reports_dir() / "sc2_connector_trace.jsonl"


def access_log_path() -> Path:
    return reports_dir() / "sc2_access.jsonl"


def wecom_webhook() -> str:
    """采购部群 webhook。凭据只进 `.env`，不进任何会被同步的 settings。"""
    return os.environ.get("SC2_WECOM_WEBHOOK_URL", "").strip()
