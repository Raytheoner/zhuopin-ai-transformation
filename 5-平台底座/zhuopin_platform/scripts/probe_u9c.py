"""U9C **测试环境**只读探测器（统一入口；联调一律走这里，物理隔离生产）。

约定（Paul 2026-06-30 定）：
  · 主线 Session / 生产代码读根目录 `.env`（生产 erp:4443，real）。
  · 一切库存/接口联调、探活，走本脚本——**只加载 `.env.test`（IT 测试库），并硬拦生产**。
凭据只从 `.env.test` 读、不打印；只读、绝不写 ERP（无 PO/审批等写端点调用）。

用法：
  python 5-平台底座/zhuopin_platform/scripts/probe_u9c.py            # 跑全部只读探测
  从其它探测脚本复用：from probe_u9c import load_test_profile, auth, post
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zhuopin_platform.env_anchor import resolve_anchor_dir  # noqa: E402

# 凭据锚点（队列 #354 收拢；实现见 `zhuopin_platform/env_anchor.py`）。
# 🔴 **原实现是 `REPO = Path(__file__).resolve().parents[3]`（硬数四层）**，两副面孔都占：
# 从 linked worktree 跑时算出的是**该 worktree 的根**（于是读到那份陈旧的 `.env`，不报错）；
# 部署到浅路径时 `parents[3]` 直接 `IndexError`。收拢后由 `--git-common-dir` 规范化到主工作区。
_ANCHOR_DIR, _ANCHOR_KIND = resolve_anchor_dir(__file__)
if _ANCHOR_DIR is None:                             # 既非 monorepo 也非扁平部署布局
    sys.exit("✗ 无法定位凭据锚点（既未找到 5-平台底座/zhuopin_platform 标记，也不在扁平部署根下）")
REPO = _ANCHOR_DIR                                  # …/企业AI转型（monorepo）或 C:/<svc>（扁平）
ENV_TEST = REPO / ".env.test"
ENV_PROD = REPO / ".env"

# ── 生产硬拦：只允许这些测试主机；命中生产或未知主机 → 直接退出 ───────────────────
ALLOWED_TEST_HOSTS = {"192.168.100.49", "testerp.equalitytec.com"}
FORBIDDEN_PROD_HOSTS = {"erp.equalitytec.com"}


def _parse_env(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if not path.exists():
        return cfg
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def load_test_profile() -> dict[str, str]:
    """加载 .env.test；做生产硬拦；测试密钥为空时回退试用生产密钥（仅判断是否同密钥）。"""
    if not ENV_TEST.exists():
        sys.exit(f"✗ 缺少测试探测档 {ENV_TEST}（见 .env.example / U9C 测试报告）")
    cfg = _parse_env(ENV_TEST)
    base = cfg.get("U9C_API_BASE", "").rstrip("/")
    host = (urlparse(base).hostname or "").lower()

    # —— 生产硬拦 ——
    if host in FORBIDDEN_PROD_HOSTS:
        sys.exit(f"✗ 拒绝：.env.test 指向生产主机 {host}。探测只允许测试库 {ALLOWED_TEST_HOSTS}。")
    if host not in ALLOWED_TEST_HOSTS:
        sys.exit(f"✗ 拒绝：未知主机 {host!r} 不在测试白名单 {ALLOWED_TEST_HOSTS}；如确属测试库请先加入白名单。")

    # 测试密钥缺失 → 回退试用生产密钥（一次性判断是否共用同一 ai 客户端密钥）
    if not cfg.get("U9C_CLIENT_SECRET"):
        prod = _parse_env(ENV_PROD)
        if prod.get("U9C_CLIENT_SECRET"):
            cfg["U9C_CLIENT_SECRET"] = prod["U9C_CLIENT_SECRET"]
            cfg["_SECRET_FROM"] = "生产 .env（试连，判断是否同密钥）"
        else:
            sys.exit("✗ .env.test 未填 U9C_CLIENT_SECRET，且生产 .env 也无可借用密钥。请向 IT 索取测试库 ai 客户端密钥。")
    else:
        cfg["_SECRET_FROM"] = ".env.test"
    return cfg


# LAN 测试库证书可能自签 → 只读探测不校验（生产对客路径另有 A1 强制校验，不走本脚本）
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def auth(cfg: dict[str, str]) -> str:
    now = datetime.now()
    params = urllib.parse.urlencode({
        "userCode": cfg["U9C_USER_CODE"], "entcode": cfg["U9C_ENT_CODE"],
        "orgcode": cfg["U9C_ORG_CODE"], "clientid": cfg["U9C_CLIENT_ID"],
        "clientsecret": cfg["U9C_CLIENT_SECRET"],
        "loginDate": f"{now.year}.{now.month}.{now.day}",
    })
    url = f"{cfg['U9C_API_BASE'].rstrip('/')}/U9C/webapi/OAuth2/AuthLogin?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if not resp.get("Success"):
        raise RuntimeError(f"AuthLogin 失败: {resp.get('ResMsg', resp)}")
    return resp.get("Data") or resp.get("data")


def post(cfg: dict[str, str], path: str, body: dict, token: str) -> tuple[int | None, str]:
    url = f"{cfg['U9C_API_BASE'].rstrip('/')}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "token": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return None, f"URLError: {e}"


def _brief(raw: str, n: int = 360) -> str:
    return raw[:n].replace("\n", " ")


def main() -> int:
    cfg = load_test_profile()
    host = urlparse(cfg["U9C_API_BASE"]).hostname
    print(f"探测目标（测试库）= {host}:{urlparse(cfg['U9C_API_BASE']).port}  密钥来源={cfg['_SECRET_FROM']}")

    print("\n=== 1) AuthLogin ===")
    try:
        tok = auth(cfg)
        print(f"OK  token 前 10 位 {str(tok)[:10]}…")
    except Exception as e:
        print(f"FAIL {e}")
        if cfg["_SECRET_FROM"].startswith("生产"):
            print("→ 生产密钥试连失败：测试库 ai 客户端密钥不同，请向 IT 索取并填入 .env.test。")
        return 1

    print("\n=== 2) CommonEntity/Query 可达性（测试库）===")
    st, raw = post(cfg, "/U9C/webapi/CommonEntity/Query",
                   {"PageSize": 1, "PageIndex": 0, "Orders": [], "Filters": [],
                    "EntityFullName": "UFIDA.U9.CBO.MD.Item.ItemMaster",
                    "ReturnFields": ["Code", "Name"]}, tok)
    print(f"  HTTP={st}  {_brief(raw)}")

    print("\n=== 3) QueryQohAndAvailable（确认 SQL bug 是否已在测试库修复）===")
    st, raw = post(cfg, "/U9C/webapi/Invtrans/QueryQohAndAvailable", {
        "QueryDTORDataList": [{
            "DataKey": "1",
            "QohInfo": {"Org": 1002107260020016,
                        "ItemInfo": {"ItemCode": "A08A.1415", "ItemName": "",
                                     "ItemGrade": -1, "ItemPotency": -1},
                        "ProductDate": "2025-07-11", "IsProdCancel": True},
            "DocDate": "2025-07-11"}],
        "IsIncludeCuurentDoc": True, "GroupByBizDate": True, "GroupFields": [2],
        "IsLotValid": True, "ProjectFilterMode": 0, "QtyFilterMode": 0,
        "TargetOrgCode": "Z", "WhList": [0], "WhStorageTypeList": [0]}, tok)
    print(f"  HTTP={st}  {_brief(raw, 500)}")

    print("\n=== 4) BOM/Query 冒烟（确认测试库 webapi 数据面可用）===")
    st, raw = post(cfg, "/U9C/webapi/BOM/Query", ["A08A.1415"], tok)
    print(f"  HTTP={st}  {_brief(raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
