"""判例包网页表单化（队列 #110 Feature B）。

背景：判例批改法（`6-人才与组织/部门AI专员跟进/需求确认方式升级-判例批改法与微会机制-2026-07-25.md`）
目前 100% 靠 Cowork 手写 md/docx 判例批改表发给专员、专员在 Word 真复选框控件里勾选或
回文字确认，机制侧没有任何结构化落库。本模块把"判例包"改造成 `.51` 上的一个网页：
**判例内容仍由 Cowork 起草**（现状判定/拟改判定是业务判断，不是本模块的职责），只是
改为写一份结构化 JSON 文件（下方"判例包定义"格式）而非 md 表格；专员打开企微里的
直达链接即可勾选提交，取代来回传 docx 附件。

判例包定义文件（Cowork 手写，UTF-8 JSON，放在 `case_review_dir` 目录下，
文件名 = ``<package_id>.json``）：

    {
      "package_id": "sc8-2026-08-06-example",
      "title": "批X · 议题标题",
      "recipient": "姚祖怡",
      "cases": [
        {"case_no": 1, "scenario": "真实场景描述…",
         "current_verdict": "现状判定…", "proposed_verdict": "拟改判定…"}
      ]
    }

🔴 2026-07-28 硬设计约束（队列 #143 加跑轮实证，务必保持，改动前先重读跨桌任务队列
`#110` 原文）：表单不得只做结构化三选一——① 每条判例的 ✏️ 自由文本与 ✅/❌ 独立记录
（✏️ 非空 ≠ 改判）；② 表单末尾必须有不受约束的自由补充区，汇总时与结构化选项同等
重视、不折叠；③ 支持一次提交内追加"新增问题"条目（编号可跳出既有判例编号体系）。

提交只落 JSONL（`case_review_store`，`feedback_store.JsonlAppendStore`），不经
`zhuopin_platform.audit`——专员打的 ✅/❌/✏️ 本身不改变任何判据，真正的口径变更仍须走
判例批改法 §1.1 第3条"规则条文反推确认"这一独立终局签认步骤（见队列 #110 调查结论）。
"""
from __future__ import annotations

import html as _html
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CaseItem:
    case_no: int
    scenario: str
    current_verdict: str
    proposed_verdict: str


@dataclass
class CaseReviewPackage:
    package_id: str
    title: str
    recipient: str
    cases: list[CaseItem] = field(default_factory=list)


def list_packages(case_review_dir: Path | str) -> list[CaseReviewPackage]:
    """列出目录下全部判例包定义（按文件名排序；损坏/不合规的 JSON 文件跳过不炸）。"""
    d = Path(case_review_dir)
    if not d.exists():
        return []
    out: list[CaseReviewPackage] = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(_parse_package(json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return out


def load_package(case_review_dir: Path | str, package_id: str) -> CaseReviewPackage:
    """按 package_id 加载单个判例包定义；不存在时抛 FileNotFoundError。"""
    path = Path(case_review_dir) / f"{package_id}.json"
    if not path.exists():
        raise FileNotFoundError(package_id)
    return _parse_package(json.loads(path.read_text(encoding="utf-8")))


def _parse_package(data: dict) -> CaseReviewPackage:
    cases = [
        CaseItem(case_no=c["case_no"], scenario=c["scenario"],
                 current_verdict=c["current_verdict"], proposed_verdict=c["proposed_verdict"])
        for c in data["cases"]
    ]
    return CaseReviewPackage(package_id=data["package_id"],
                             title=data.get("title", data["package_id"]),
                             recipient=data.get("recipient", ""), cases=cases)


def render_review_page(package: CaseReviewPackage) -> str:
    """渲染判例包网页表单（GET /cases/review/<package_id>）。"""
    rows = "".join(f"""
<div class="rv-case" data-case="{c.case_no}">
  <div class="rv-case-h">#{c.case_no}</div>
  <div class="rv-field"><b>真实场景</b>：{_html.escape(c.scenario)}</div>
  <div class="rv-field"><b>现状判定</b>：{_html.escape(c.current_verdict)}</div>
  <div class="rv-field"><b>拟改判定</b>：{_html.escape(c.proposed_verdict)}</div>
  <div class="rv-verdict">
    <label><input type="radio" name="verdict_{c.case_no}" value="agree"> ✅ 对</label>
    <label><input type="radio" name="verdict_{c.case_no}" value="disagree"> ❌ 错</label>
  </div>
  <label class="rv-note-label">✏️ 改判理由 / 备注（与上面勾选独立记录，非空不代表改判）</label>
  <textarea name="note_{c.case_no}" rows="2" placeholder="可选，写一句为什么"></textarea>
</div>""" for c in package.cases)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(package.title)} · 判例批改</title>
{_REVIEW_CSS}</head><body>
<div class="rv-wrap">
<h1>{_html.escape(package.title)}</h1>
<p class="rv-sub">收件人：{_html.escape(package.recipient)} · 共 {len(package.cases)} 项判例</p>
<p class="rv-hint">用法：每条画一个勾（✅对/❌错），改判理由为自由文本，与勾选独立记录，
未勾选也可以只写理由。全部答完后可在末尾自由补充其它想法，或追加新问题，一次提交即可。</p>
<form method="POST" id="rv-form">
<label class="rv-note-label">你的姓名</label>
<input type="text" name="respondent" placeholder="如：姚祖怡" required>
{rows}
<div class="rv-supplement">
  <label class="rv-note-label">自由补充（不受上面结构限制，任何想法都可以写在这里）</label>
  <textarea name="supplement" rows="4" placeholder="例如：推翻某条既有结论、夹带全新问题……都可以写在这里"></textarea>
</div>
<div class="rv-new-issues">
  <label class="rv-note-label">新增问题（可选，逐条追加，编号可跳出本次判例体系）</label>
  <div id="rv-new-issue-list"></div>
  <button type="button" id="rv-add-issue" class="rv-btn">+ 追加一条新问题</button>
</div>
<button type="submit" class="rv-btn rv-primary">提交</button>
</form>
</div>
<script>
document.getElementById('rv-add-issue').addEventListener('click', function(){{
  var wrap = document.createElement('div');
  wrap.style.marginTop = '8px';
  wrap.innerHTML = '<textarea name="new_issue" rows="2" placeholder="新问题描述"></textarea>';
  document.getElementById('rv-new-issue-list').appendChild(wrap);
}});
</script>
</body></html>"""


_REVIEW_CSS = """<style>
body{font-family:-apple-system,"Segoe UI",'Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}
.rv-wrap{max-width:720px;margin:0 auto}
h1{font-size:19px;margin:0 0 4px}
.rv-sub{color:#94a3b8;font-size:13px;margin:0 0 10px}
.rv-hint{background:#1e293b;border-left:3px solid #2563eb;padding:10px 14px;border-radius:4px;font-size:13px;color:#93c5fd;margin-bottom:18px}
.rv-case{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 16px;margin-bottom:12px}
.rv-case-h{font-weight:700;color:#93c5fd;margin-bottom:6px}
.rv-field{font-size:13px;margin:4px 0;line-height:1.5}
.rv-verdict{margin:8px 0;display:flex;gap:16px;font-size:14px}
.rv-note-label{display:block;font-size:12px;color:#94a3b8;margin:8px 0 4px}
textarea,input[type=text]{width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:8px;font-size:13px;box-sizing:border-box;font-family:inherit}
.rv-supplement,.rv-new-issues{background:#1e293b;border:1px dashed #475569;border-radius:8px;padding:14px 16px;margin:14px 0}
.rv-btn{background:#334155;color:#e2e8f0;border:0;border-radius:6px;padding:8px 16px;font-size:13px;cursor:pointer;margin-top:8px}
.rv-btn.rv-primary{background:#2563eb;color:#fff;font-weight:700;padding:10px 24px;margin-top:16px}
.rv-btn:hover{opacity:.9}
</style>"""
