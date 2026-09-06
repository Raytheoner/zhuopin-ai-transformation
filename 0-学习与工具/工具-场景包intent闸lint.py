"""新场景 openspec 包的 `intent.md` 前置闸 lint（队列 §一 `#436` ⑶① ／ `OP-0906-S`）。

## 这道闸守什么

Shao Peishen 2026-09-06 拍板 ③(a)：**新场景走 `/opsx:propose` 之前，场景目录必须已有
`intent.md` 且 frontmatter `status: 已确认`**（口径正本＝`.claude/rules/场景建造与合规.md`
§二 那条 🔴，承 `1-转型规划/0-全景路线图/端到端构建workflow优化-方案-2026-09-06.md` §四 W1）。
本脚本就是那条口径的机器守。

## 🔴 为什么落在 CI lint、而不是 openspec 自定义 validate 规则（实测坐实，不是选型偏好）

拍板原文写的是「闸落 openspec validate」。**实测证明 openspec 1.7.0 做不到硬拦**，故按
派单件 §一.2 的硬边界改走 CI lint：

- `openspec/config.yaml` 的 `rules.proposal` 是**喂给起草方的提示文本**，validate 不读它。
  实证：本仓库 8 份 `proposal.md`（`aibot-inbound-whitelist-li-jiaolong`／
  `aibot-receipt-route-by-source-group`／`batch-registration-precheck`／
  `fi1-warehouse-reconcile`／`lan-closeout-skill`／
  `open-pool-assigned-field-and-opener-env-filter`／`qd-b-cross-module-tier3`／
  `sc8-kit-date-rule1-start`）**都缺 config.yaml 点名 MANDATORY 的「知识资产三问」节**，
  而 `openspec validate --all --strict` 仍报 `169 passed, 0 failed`（2026-09-06 实测）。
- `openspec validate --help` 与 `openspec --help` 全表无任何自定义规则/插件挂载点。

⇒ **提示句不是闸，lint 才是。** `config.yaml` 里仍加了一条 MANDATORY 提示句，作用只是让两桌
起草时看得见这条要求；真正拦得住的是 `.github/workflows/ci.yml` 的 `scene-intent-gate-lint` job。

## 判据（三步，逐步收窄；宁可窄而准，不可宽到逼人不断加豁免）

**第 1 步 · 建场景索引**：扫 `4-数字员工/<部门>/<场景目录>/`，从目录名前缀取场景码
（`FI10-存货跌价智能分析` → `FI10`；`QD-B-立项审核门禁` → `QD-B`）。

**第 2 步 · 判包属于哪个场景**（信号 A 或 B 命中，且第 3 步「触碰」也成立才算场景类）：

- **信号 A**：包名以 `<场景码>-` 开头（`fi10-inventory-writedown-mvp` → FI10）。**长码优先**，
  故 `sc10-…` 不会被 `SC1` 抢走（`sc1` 之后是 `0` 不是 `-`，本就不匹配，长码优先是双保险）。
- **信号 B**：包内 `specs/<capability>/` 至少有一个 capability 名以 `<场景码>-` 开头
  （`fi2-recon-mvp` 的 `fi2-match-engine`）。
- **触碰**：`proposal.md`／`tasks.md` 正文出现该场景的目录路径
  `4-数字员工/<部门>/<场景目录>`。

🔴 **只写"触碰 `4-数字员工/` 即场景类"会误伤一大片机制类包**——实测 `env-anchor-collapse`／
`queue-domain-routing`／`coverage-point-ledger`／`sweep-ops-webhook-cutover`／
`oem-audit-fail-closed` 五个机制类包都在正文里引用了场景目录下的具体文件（作为受影响面或
举例），它们的 capability 全是 `platform-*`／`queue-*`／`sweep-*`，与任何场景码无关。故
**必须两侧都命中**：包的身份（名或 capability）属于该场景，且正文确实触碰该场景目录。
只命中一侧的包会进报告的「仅引用」「疑似」两个分栏——**可见但不判违规**，不静默。

**第 3 步 · 查 `intent.md`**：场景目录须存在 `intent.md`，其 YAML frontmatter 的
`status` 须为 `已确认`。缺文件／缺字段／值不对，三种都点名包名 ＋ 期望路径 ＋ 出路。

## 豁免三层（每层都写明来源与到期日；豁免不写理由，下一个人只能猜）

**第 ① 层 · 深化类（永久，结构性，闭集）**——grill 机制 2026-08-18 落地时的边界原文是
「**只对新场景开工前强制，深化类不用**」（`需求收敛第一道把关-grill机制融合方案-2026-08-18.md`
§六边界 ＋ G3(a)，队列归档 `#342` 拍板行）。名单＝**首次入库早于 2026-08-18 的场景**，
由下列命令实测得出（不是凭印象列的）：

    git log --diff-filter=A --format="COMMIT %ad" --date=short --name-only -- "4-数字员工"

实测结果（2026-09-06）：SC1 06-06／SC8 06-10／O2 06-10／SC3 06-10／SC5 06-11／QD-B 06-27／
FI1 06-29／QD-A 07-04／SC7 07-06／FI2 07-07 ⇒ 均早于 08-18；SC2 与 O1 恰在 08-18 当日；
八个新场景（FI5/FI6/FI8/FI9/FI10/SC4/SC10/SC11）均为 09-03。

🔑 **这一层是闭集、永不增长**：此后新建的场景首次入库日期必然晚于 2026-08-18，不可能落进
名单，所以写死不会变陈旧——**不需要任何人记得来维护它**。

🔴 **派单件原文的判据（「场景目录 `CLAUDE.md` 已有『部署状态』段」）作为附加自动信号保留**，
与名单取并集。保留而非替换，是因为实测它**只命中 FI2／QD-B／SC2 三个**——SC8 明明已部署到
`.51:8091`（有 `deploy-server.ps1`、`部署到长开服务器-保供看板.md`）却因为它的部署信息写在
`## 5. 状态时间线` 而不是叫「部署状态」的段里，就漏掉了。**单靠这个字面标记会把 SC8 的三个
深化包和 FI1 的建造包判成违规**（首跑实测 4 个），那正是"门禁上线第一天就是红的、然后被
习惯性忽略"的老路（同 `工具-引导样板lint.py` 头部那段判断）。

**第 ② 层 · 存量 8 包（包级，到期 2026-10-31）**——派单件点名冻结，逐包补完 grill
（`intent.md` 转 `已确认`）即从名单删；到期后一律硬拦。

**第 ③ 层 · SC2 历史件（场景级，到期 2026-10-31）**——SC2 的 grill 产出是
`需求grill产出-2026-08-18.md`（首个样本，早于定名），rules 明写「历史件不追改」。
（SC2 同时命中第 ① 层的「部署状态」信号，双保险。）

用法：
  python 0-学习与工具/工具-场景包intent闸lint.py             # 告警模式（退出码恒 0）
  python 0-学习与工具/工具-场景包intent闸lint.py --enforce    # 阻断模式（有违规即 1）
  python 0-学习与工具/工具-场景包intent闸lint.py --today 2026-11-01   # 试算到期后的效果
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SCENE_ROOT_NAME = "4-数字员工"
CHANGES_REL = "openspec/changes"

#: 场景目录名前缀 → 场景码。`QD-B-立项审核门禁` 这一族带一段字母后缀，故单列一支。
SCENE_CODE_RE = re.compile(r"^(QD-[A-Z]|[A-Z]{1,3}\d{1,3})-")

#: 豁免第 ②③ 层的统一到期日（派单件写死）。到期后这两层一律失效、硬拦。
EXEMPT_DEADLINE = _dt.date(2026, 10, 31)

#: 第 ① 层 · 深化类场景码（永久豁免，闭集）。来源与实测命令见模块 docstring。
LEGACY_SCENES: dict[str, str] = {
    "SC1": "2026-06-06 入库，早于 grill 机制生效日 2026-08-18",
    "SC3": "2026-06-10 入库（场景编号已退役，引擎并入 SC8）",
    "SC5": "2026-06-11 入库",
    "SC7": "2026-07-06 入库",
    "SC8": "2026-06-10 入库；已部署 `.51:8091`，部署信息写在「状态时间线」段故字面标记扫不到",
    "O2": "2026-06-10 入库",
    "QD-A": "2026-07-04 入库",
    "QD-B": "2026-06-27 入库（另命中「部署状态」段信号）",
    "FI1": "2026-06-29 入库；propose/design 已过、MVP 已落 master，2026-06-29 起 ⏸ 暂停",
    "FI2": "2026-07-07 入库（另命中「部署状态」段信号）",
}

#: 第 ② 层 · 存量包级豁免（到期 2026-10-31）。派单件 (ii).2 点名的 8 个。
EXEMPT_PACKAGES: dict[str, str] = {
    "sc4-contract-clause-extraction": "2026-09-03 批量 propose 的存量新场景包，待补 grill",
    "sc10-bom-review-material-governance": "同上",
    "sc11-inventory-transfer": "同上",
    "fi5-expense-audit-mvp": "同上",
    "fi6-anomaly-detect-mvp": "同上",
    "fi8-cashflow-forecast-mvp": "同上",
    "fi9-rd-cost-mvp": "同上",
    "fi10-inventory-writedown-mvp": "同上（首个补 grill 样本，见 OP-0906-V）",
}

#: 第 ③ 层 · 场景级存量豁免（到期 2026-10-31）。
EXEMPT_SCENES: dict[str, str] = {
    "SC2": "grill 首个样本，产出是 `需求grill产出-2026-08-18.md`（早于 `intent.md` 定名），"
           "rules/场景建造与合规 明写历史件不追改",
}

#: 附加自动信号：场景 CLAUDE.md 里有「部署状态」段 ⇒ 深化类（派单件原文判据，取并集）。
DEPLOY_SECTION_RE = re.compile(r"^#{1,6}\s*.*部署状态", re.M)

INTENT_FILENAME = "intent.md"
REQUIRED_STATUS = "已确认"

_FIX_HINT = (
    "出路：先跑 skill `zhuopin-requirement-grill` 做需求 grill，产出落 {expected}，"
    "三节固定（§一 M2 自查事实／§二 已定＝design Decisions／§三 待专员＝判例包待办），"
    "frontmatter 由 Shao Peishen 确认后写 `status: 已确认`；口径正本＝"
    "`.claude/rules/场景建造与合规.md` §二。"
)


@dataclass
class Scene:
    code: str
    dept: str
    dirname: str
    rel_dir: str
    has_deploy_section: bool = False


@dataclass
class Report:
    violations: list[str] = field(default_factory=list)
    exempted: list[str] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    mechanism_refs: list[str] = field(default_factory=list)
    name_only: list[str] = field(default_factory=list)
    scanned_packages: int = 0
    scenes: int = 0


# ── 第 1 步：建场景索引 ──────────────────────────────────────────────────────

def build_scene_index(root: Path) -> dict[str, Scene]:
    """扫 `4-数字员工/<部门>/<场景目录>/`，返回 {场景码: Scene}。"""
    scenes: dict[str, Scene] = {}
    base = root / SCENE_ROOT_NAME
    if not base.is_dir():
        return scenes
    for dept_dir in sorted(base.iterdir()):
        if not dept_dir.is_dir() or dept_dir.name == "档案":
            continue
        for scene_dir in sorted(dept_dir.iterdir()):
            if not scene_dir.is_dir():
                continue
            m = SCENE_CODE_RE.match(scene_dir.name)
            if not m:
                continue
            code = m.group(1).upper()
            claude_md = scene_dir / "CLAUDE.md"
            has_deploy = False
            if claude_md.is_file():
                has_deploy = bool(DEPLOY_SECTION_RE.search(
                    claude_md.read_text(encoding="utf-8", errors="replace")))
            scenes[code] = Scene(
                code=code,
                dept=dept_dir.name,
                dirname=scene_dir.name,
                rel_dir=f"{SCENE_ROOT_NAME}/{dept_dir.name}/{scene_dir.name}",
                has_deploy_section=has_deploy,
            )
    return scenes


# ── 第 2 步：判包属于哪个场景 ────────────────────────────────────────────────

def _codes_longest_first(scenes: dict[str, Scene]) -> list[str]:
    return sorted(scenes, key=lambda c: (-len(c), c))


def classify_package(pkg_dir: Path, scenes: dict[str, Scene]) -> tuple[str | None, str | None, list[str]]:
    """返回 (主场景码 or None, 命中信号说明 or None, 仅正文引用到的其它场景码)。

    主场景码非 None ⇒ 场景类包（信号 A/B 命中 **且** 正文触碰该场景目录）。
    """
    pkg_name = pkg_dir.name.lower()
    texts: list[str] = []
    for fname in ("proposal.md", "tasks.md"):
        f = pkg_dir / fname
        if f.is_file():
            texts.append(f.read_text(encoding="utf-8", errors="replace"))
    body = "\n".join(texts)

    caps: list[str] = []
    specs_dir = pkg_dir / "specs"
    if specs_dir.is_dir():
        caps = [d.name.lower() for d in specs_dir.iterdir() if d.is_dir()]

    touched = [c for c in _codes_longest_first(scenes) if scenes[c].rel_dir in body]

    for code in _codes_longest_first(scenes):
        prefix = code.lower() + "-"
        if pkg_name.startswith(prefix):
            signal = f"包名前缀 `{prefix}`"
        elif any(cap.startswith(prefix) for cap in caps):
            signal = f"spec capability 前缀 `{prefix}`"
        else:
            continue
        if code in touched:
            return code, signal, [c for c in touched if c != code]
        return None, f"疑似 {code}（{signal}），但 proposal/tasks 未引用 `{scenes[code].rel_dir}`", touched
    return None, None, touched


# ── 第 3 步：查 intent.md ────────────────────────────────────────────────────

def read_frontmatter_status(text: str) -> str | None:
    """取 YAML frontmatter 里的 `status` 值；无 frontmatter 或无该字段返回 None。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        m = re.match(r"^status\s*:\s*(.*)$", ln)
        if m:
            return m.group(1).strip().strip("\"'").strip()
    return None


def check_intent(root: Path, scene: Scene) -> str | None:
    """合规返回 None，否则返回问题描述（不含包名前缀）。"""
    expected = f"{scene.rel_dir}/{INTENT_FILENAME}"
    path = root / scene.rel_dir / INTENT_FILENAME
    if not path.is_file():
        return f"场景 {scene.code} 缺 `{expected}`"
    status = read_frontmatter_status(path.read_text(encoding="utf-8", errors="replace"))
    if status is None:
        return f"`{expected}` 的 frontmatter 无 `status:` 字段"
    if status != REQUIRED_STATUS:
        return f"`{expected}` 的 `status: {status}` 不是 `{REQUIRED_STATUS}`"
    return None


# ── 扫描主体 ────────────────────────────────────────────────────────────────

def exemption_for(pkg_name: str, scene: Scene, today: _dt.date) -> str | None:
    """返回豁免理由；无豁免返回 None。"""
    if scene.code in LEGACY_SCENES:
        return f"深化类·永久（{LEGACY_SCENES[scene.code]}）"
    if scene.has_deploy_section:
        return "深化类·永久（场景 CLAUDE.md 有「部署状态」段）"
    if today > EXEMPT_DEADLINE:
        return None
    if pkg_name in EXEMPT_PACKAGES:
        return f"存量包级·至 {EXEMPT_DEADLINE}（{EXEMPT_PACKAGES[pkg_name]}）"
    if scene.code in EXEMPT_SCENES:
        return f"存量场景级·至 {EXEMPT_DEADLINE}（{EXEMPT_SCENES[scene.code]}）"
    return None


def scan(root: Path = REPO_ROOT, today: _dt.date | None = None) -> Report:
    today = today or _dt.date.today()
    rep = Report()
    scenes = build_scene_index(root)
    rep.scenes = len(scenes)

    changes = root / CHANGES_REL
    if not changes.is_dir():
        return rep

    for pkg_dir in sorted(changes.iterdir()):
        if not pkg_dir.is_dir() or pkg_dir.name == "archive":
            continue
        rep.scanned_packages += 1
        code, signal, others = classify_package(pkg_dir, scenes)
        if code is None:
            if signal:                      # 疑似场景包但未触碰场景目录
                m = re.match(r"^疑似 (\S+)（", signal)
                sus = scenes.get(m.group(1)) if m else None
                reason = exemption_for(pkg_dir.name, sus, today) if sus else None
                if reason:
                    # 场景本就豁免 ⇒ 归豁免栏，不占「疑似」栏（少一行噪音，结论不变）
                    rep.exempted.append(
                        f"{pkg_dir.name} → {sus.code}：{reason}；另注：未引用场景目录")
                else:
                    rep.name_only.append(f"{pkg_dir.name}: {signal}")
            elif others:                    # 机制类包，只是正文引用了场景路径
                rep.mechanism_refs.append(
                    f"{pkg_dir.name}: 机制类（包名与 capability 均不属任何场景），"
                    f"正文引用 {'/'.join(others)}")
            continue

        scene = scenes[code]
        reason = exemption_for(pkg_dir.name, scene, today)
        if reason:
            rep.exempted.append(f"{pkg_dir.name} → {scene.code}：{reason}")
            continue
        problem = check_intent(root, scene)
        if problem:
            rep.violations.append(
                f"{pkg_dir.name}（场景类，{signal}）：{problem}。"
                + _FIX_HINT.format(expected=f"{scene.rel_dir}/{INTENT_FILENAME}"))
        else:
            rep.passed.append(f"{pkg_dir.name} → {scene.code}")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="新场景 openspec 包的 intent.md 前置闸 lint")
    ap.add_argument("--enforce", action="store_true",
                    help="有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    ap.add_argument("--root", default=str(REPO_ROOT), help="仓库根（默认＝本脚本上一级）")
    ap.add_argument("--today", default=None,
                    help="以该日期判豁免到期（YYYY-MM-DD），默认取本机今天")
    args = ap.parse_args(argv)

    today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()
    rep = scan(Path(args.root), today)

    print(f"场景包 intent 闸 lint：扫描 {rep.scanned_packages} 个在办变更包 / "
          f"{rep.scenes} 个场景目录（判豁免基准日 {today}）")
    if rep.passed:
        print(f"  ✓ 合规场景包 {len(rep.passed)}：{'、'.join(rep.passed)}")
    if rep.exempted:
        print(f"  ○ 豁免 {len(rep.exempted)}：")
        for line in rep.exempted:
            print(f"      - {line}")
    if rep.name_only:
        print(f"  ? 疑似场景包但未引用场景目录 {len(rep.name_only)}（可见不判违规）：")
        for line in rep.name_only:
            print(f"      - {line}")
    if rep.mechanism_refs:
        print(f"  · 机制类·仅引用场景路径 {len(rep.mechanism_refs)}（不适用本闸）：")
        for line in rep.mechanism_refs:
            print(f"      - {line}")

    if rep.violations:
        print(f"\n  ✗ 违规 {len(rep.violations)}：")
        for line in rep.violations:
            print(f"      - {line}")
        if args.enforce:
            return 1
        print("\n  （告警模式，退出码 0；加 --enforce 阻断）")
        return 0

    print("\n  ✓ 无违规。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
