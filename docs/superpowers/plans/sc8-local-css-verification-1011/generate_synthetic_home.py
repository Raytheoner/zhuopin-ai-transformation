"""Generate one script-free synthetic SC8 home shell for local CSS inspection.

This is a one-shot verification helper. It does not create a Flask app/client,
read a snapshot, start a service, or contact any endpoint.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid
from urllib.parse import urlsplit


REPO_ROOT = Path("C:/Dev/zhuopin-ai")
SC8_ROOT = REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺"
REPORT_ROOT = REPO_ROOT / "reports/sc8-live-readonly-1010"
WEBAPP_PATH = SC8_ROOT / "sc8/webapp.py"
BAOGUAN_PATH = SC8_ROOT / "sc8/baoguan.py"
EXPECTED_SHA256 = {
    "sc8/webapp.py": "1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E",
    "sc8/baoguan.py": "19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9",
}
IMPORT_CLOSURE = {
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/__init__.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/__init__.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/alert_dispatch.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/alert_dispatch.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan.py": BAOGUAN_PATH,
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan_service.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan_service.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_draft.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_draft.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_review.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_review.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_store.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_store.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/config.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/config.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/feedback_store.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/feedback_store.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/forecast.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/forecast.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/loaders.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/loaders.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/material_board.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/material_board.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/models.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/models.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/period_match.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/period_match.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/sources.py": REPO_ROOT / "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/sources.py",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/webapp.py": WEBAPP_PATH,
    "5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/agents/__init__.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/agents/__init__.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/agents/kit_engine.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/agents/kit_engine.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/access_log.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/access_log.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/simple_gate.py": REPO_ROOT / "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/simple_gate.py",
}
EXPECTED_IMPORT_CLOSURE_SHA256 = {
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/__init__.py": "EADE92315E89755BADE152D6AE068E4529E13D01706B708FD03AEF89A4BEFE39",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/alert_dispatch.py": "C3A1EFD3880929F6BDCBBB4783DF70E540A73F914DB76A593B618BAFE8A33DF0",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan.py": "19D443EA46BEA534FCC0469053D361883AE08D22FA802A75ACE8C4FBC0DCFBF9",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan_service.py": "996EA62447141807BDFF71D0DACD4ED2788B540B8131FA963D89F5647C10655C",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_draft.py": "6E9BE1CCD797C365A2B75E7C57D4F4E37564443FD1AFD5D3D44F133D853EB103",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_review.py": "441D73E79C64AF7DE07E6A197E7C8A584D4E3489CAC054F7A76D695B1A70FA73",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/case_store.py": "DF38AFC0DCEAC1C606DB3DF5CE6248DC1095983604B4507433109BFA72CC68C6",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/config.py": "94C3BB627733BE0635114484EA634D7841177443F8A6D53490E14FD6E71F8443",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/feedback_store.py": "60071115EBBC0B41756223F0112C1A1D971351625967F24239080B11A2724343",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/forecast.py": "4EF97B77F6D4F7F072413DFD014FC0B39AC7DF33E5112CED091CEA821B57A097",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/loaders.py": "112337EA62B7BD402ECB67D0ACFF974F910015ECEB0CC4927C975F9AEC716D15",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/material_board.py": "4F0FB3A9673CD7F128CECC59302EA46D2080189B9DACB188240E41511C7B42E2",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/models.py": "9F7397B68165FA2E8456140E8CC47F5896DA3CB16598EC27BE35757B77FB65DE",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/period_match.py": "24C96DDE2DF6E570568AAA561CB2A2BBA6A673D3FBE3AC1A21D1DF875D991063",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/sources.py": "228B333913BEABCB01D6315A48A3276B2D2787E8B1C7118028BC03B5F69154DE",
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/webapp.py": "1CB27E63F548B72A6D36A69CB4FCB50158FA2B04B2C5F83716AEE8856286240E",
    "5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py": "E7BA40C8B09F5839D2189DDF1EE6372E6FA7EB435DD1CA2C4E902082E9F86621",
    "5-平台底座/zhuopin_platform/zhuopin_platform/agents/__init__.py": "A2223541FE056551B69948945C13C37C21CCBF5EE3BF5D4296A4ABAD89D7BE86",
    "5-平台底座/zhuopin_platform/zhuopin_platform/agents/kit_engine.py": "1A265B6DD2FDD818BC0BC7682526EE8395A22E319F355EAFB2A127674EB5FC15",
    "5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py": "9F5853A630DAE9B75A52A811CD3CE1BD80A2B4751A4B6C87B993DA3C3ADB9C09",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py": "02F261359047CAE1E14C0ACBED5B52A11A955D3D745F328A15C95F78BCD7EB77",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/access_log.py": "28035D00FD9E5DDAF039F2825817282A9CCD11C57AD0B51B76D725DF7504BA6F",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py": "84D2FAA6E5FC8EB781A1411AE6F8E812844EF816F1DB0E7E12C642B9A5FA71A7",
    "5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/simple_gate.py": "100CAB8D8101F69A600679704481E40D5368DFED3C5BE92AB70AE1425BD53C5C",
}
SYNTHETIC_MARKER = "SYNTHETIC CSS CHECK — NO CUSTOMER OR SNAPSHOT DATA"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class MarkupChecks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.resource_tags: list[str] = []

    def _inspect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value or "" for name, value in attrs}
        for name, value in values.items():
            if re.fullmatch(r"on[a-z][a-z0-9_-]*", name):
                self.errors.append(f"event-handler attribute remains: {name}")
            if "javascript:" in value.casefold():
                self.errors.append(f"javascript URL remains in: {name}")
        if tag in {"script", "iframe", "img", "source", "video", "audio", "object", "embed", "link", "base"}:
            self.resource_tags.append(tag)
        for name in ("src", "href", "action", "formaction", "poster", "data"):
            value = values.get(name)
            if not value:
                continue
            parsed = urlsplit(value.strip())
            if parsed.scheme or parsed.netloc or value.strip().startswith("//"):
                self.errors.append(f"external URL remains in {tag}.{name}")
            if tag != "a" and name in {"src", "href", "poster", "data"}:
                self.errors.append(f"resource-bearing attribute remains: {tag}.{name}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="new UUID; output directory is fixed under reports/")
    args = parser.parse_args()
    try:
        run_id = str(uuid.UUID(args.run_id))
    except ValueError as exc:
        raise SystemExit(f"invalid UUID: {exc}") from exc
    if run_id != args.run_id.lower():
        raise SystemExit("run-id must use canonical UUID spelling")
    if Path.cwd().resolve() != SC8_ROOT.resolve():
        raise SystemExit(f"wrong cwd; expected exact SC8 root: {SC8_ROOT}")

    source_hashes = {
        "sc8/webapp.py": sha256(WEBAPP_PATH),
        "sc8/baoguan.py": sha256(BAOGUAN_PATH),
    }
    if source_hashes != EXPECTED_SHA256:
        raise SystemExit(f"pinned source SHA mismatch: {source_hashes}")
    import_closure_hashes = {
        relative: sha256(path) for relative, path in IMPORT_CLOSURE.items()
    }
    if import_closure_hashes != EXPECTED_IMPORT_CLOSURE_SHA256:
        raise SystemExit("pinned project import-closure SHA mismatch; stop before importing project modules")

    # Use the repository's approved bootstrap helper; do not depend on an
    # editable global package pointer from another checkout.
    _here = Path(__file__).resolve()
    for _parent in _here.parents:
        if (_parent / "5-平台底座" / "zhuopin_platform").is_dir():
            sys.path.insert(0, str(_parent / "5-平台底座" / "zhuopin_platform"))
            break
    from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402

    ensure_paths(__file__, SC8_ROOT, strict=True)
    from sc8 import webapp  # noqa: E402

    if Path(webapp.__file__).resolve() != WEBAPP_PATH.resolve():
        raise SystemExit(f"unexpected imported webapp path: {webapp.__file__}")

    # _shell_page only consumes these two values for the legend. Replace both
    # in this process with fixed synthetic values; no config or snapshot data is read.
    webapp.config.default_params = lambda: {"synthetic": True, "label": SYNTHETIC_MARKER}
    webapp.render_legend = lambda _params, *, include_version=False: (
        '<span class="synthetic-legend">' + SYNTHETIC_MARKER + "</span>"
    )
    page = webapp._shell_page()
    if not isinstance(page, str) or SYNTHETIC_MARKER not in page:
        raise SystemExit("synthetic marker missing from generated shell")

    css_parts = {
        "base": webapp._HTML_STYLE,
        "navigation": webapp._NAV_CSS,
        "portal": webapp._PORTAL_CSS,
    }
    if any(page.count(value) != 1 for value in css_parts.values()):
        raise SystemExit("expected each pinned CSS block exactly once")
    indices = {name: page.index(value) for name, value in css_parts.items()}
    if not indices["base"] < indices["navigation"] < indices["portal"]:
        raise SystemExit(f"CSS order mismatch: {indices}")

    portal = css_parts["portal"]
    checks = {
        "nav_overflow_x_auto": bool(re.search(r"\.bg-nav\s*\{[^}]*overflow-x\s*:\s*auto\s*;", portal, re.I | re.S)),
        "nav_white_space_nowrap": bool(re.search(r"\.bg-nav\s*\{[^}]*white-space\s*:\s*nowrap\s*(?:;|(?=\s*\}))", portal, re.I | re.S)),
        "mobile_breakpoint_600px": bool(re.search(r"@media\s*\(\s*max-width\s*:\s*600px\s*\)", portal, re.I)),
        "mobile_brand_hidden": bool(re.search(r"\.bg-nav\s+\.brand\s*\{[^}]*display\s*:\s*none\s*(?:;|(?=\s*\}))", portal, re.I | re.S)),
    }
    if not all(checks.values()):
        raise SystemExit(f"required portal CSS rule missing: {checks}")

    script_blocks = list(re.finditer(r"<script\b[^>]*>.*?</script\s*>", page, re.I | re.S))
    if len(script_blocks) != 1:
        raise SystemExit(f"expected exactly one inline script block; found {len(script_blocks)}")
    script_match = script_blocks[0]
    if re.search(r"\bsrc\s*=", script_match.group(0), re.I):
        raise SystemExit("script block unexpectedly references a source URL")
    safe_page = page[:script_match.start()] + page[script_match.end():]
    if re.search(r"<script\b", safe_page, re.I):
        raise SystemExit("script tag remains after single-block removal")
    if re.search(r"@import\b|url\(\s*[^)]", safe_page, re.I):
        raise SystemExit("CSS import or URL resource remains")
    markup = MarkupChecks()
    markup.feed(safe_page)
    markup.close()
    if markup.errors or markup.resource_tags:
        raise SystemExit(f"unsafe markup remains: errors={markup.errors}; resource_tags={markup.resource_tags}")

    output_dir = REPORT_ROOT / f"local-css-{run_id}"
    if output_dir.exists():
        raise SystemExit(f"output directory already exists; preserve and stop: {output_dir}")
    output_files = {
        "mock-home.html": safe_page.encode("utf-8"),
        "css-order-check.json": json.dumps({
            "synthetic_only": True,
            "page": "SC8 homepage shell; no service/client/snapshot",
            "source_sha256": source_hashes,
            "project_import_closure_sha256": import_closure_hashes,
            "css_order": ["base", "navigation", "portal"],
            "css_positions": indices,
            "css_sha256": {name: hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
                            for name, value in css_parts.items()},
            "portal_rules": checks,
            "removed_inline_script_count": 1,
            "residual_script_handlers_js_urls_external_resources": False,
        }, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    manifest = {
        "run_id": run_id,
        "synthetic_only": True,
        "cwd": str(SC8_ROOT),
        "source_sha256": source_hashes,
        "project_import_closure_sha256": import_closure_hashes,
        "outputs": {name: hashlib.sha256(content).hexdigest().upper()
                    for name, content in output_files.items()},
        "next_step_requires_separate_approval": "local Browser/CUA render at 320x844 and 390x844",
        "online_deployment_claim": False,
    }
    output_files["generator-manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ).encode("utf-8")

    # Create only after all source/CSS/HTML assertions pass. Any later write
    # failure leaves partial evidence in place; the operator must stop and preserve it.
    output_dir.mkdir(parents=False, exist_ok=False)
    for name, content in output_files.items():
        (output_dir / name).write_bytes(content)
    print(f"synthetic_generation=PASS output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
