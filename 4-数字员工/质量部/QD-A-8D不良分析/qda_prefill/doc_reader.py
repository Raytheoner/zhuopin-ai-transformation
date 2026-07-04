"""文档读取器 — docx/pdf → DocumentSections。

接口与未来平台 shared_tools/doc_parser.py 同构（rule-of-three触发时零改平移）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# D1-D8 段落标头的识别模式（宽松匹配多种格式）
_SECTION_PATTERNS = [
    # "D1:", "D1：", "D1 团队成员"
    re.compile(r"^[Dd][1-8]\s*[:：\s]", re.MULTILINE),
    # "第一步：", "第二步："
    re.compile(r"^第[一二三四五六七八]步\s*[:：]", re.MULTILINE),
    # "1.", "2." — only when at line start with space after dot
    re.compile(r"^\d\.\s+\S", re.MULTILINE),
    # "Step 1:", "Step1:"
    re.compile(r"^Step\s*\d\s*[:：]", re.MULTILINE | re.IGNORECASE),
]

_D_NUM_RE = re.compile(r"[Dd]([1-8])")


@dataclass
class DocumentSections:
    """解析后的文档结构。"""
    full_text: str
    # 按 D 编号索引的段落内容，key="D1"..."D8"
    sections: dict[str, str] = field(default_factory=dict)
    # 文档的前 500 字（标题/摘要区）
    header_text: str = ""
    source_path: str = ""


def read(path: Path | str) -> DocumentSections:
    """统一入口，按扩展名路由到 docx/pdf 读取器。"""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".docx", ".doc"):
        return _read_docx(p)
    elif suffix == ".pdf":
        return _read_pdf(p)
    else:
        raise ValueError(f"不支持的文件格式：{suffix}（支持 .docx/.pdf）")


def _read_docx(path: Path) -> DocumentSections:
    try:
        from docx import Document  # type: ignore
    except ImportError as e:
        raise ImportError("需要 python-docx：pip install python-docx") from e

    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    return _parse_sections(full_text, str(path))


def _read_pdf(path: Path) -> DocumentSections:
    try:
        import pdfplumber  # type: ignore
    except ImportError as e:
        raise ImportError("需要 pdfplumber：pip install pdfplumber") from e

    lines = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
    full_text = "\n".join(line.strip() for line in lines if line.strip())
    return _parse_sections(full_text, str(path))


def _parse_sections(full_text: str, source_path: str) -> DocumentSections:
    """从全文提取 D1–D8 段落。"""
    sections: dict[str, str] = {}
    header_text = full_text[:500]

    lines = full_text.splitlines()
    current_key: str | None = None
    current_lines: list[str] = []

    for line in lines:
        d_match = _D_NUM_RE.match(line.strip())
        # 宽松判定：行以 D\d 开头（含标点或空格紧跟）
        is_section_header = bool(
            d_match and re.match(r"^[Dd][1-8]\s*[:：\s，,]", line.strip())
        )
        if is_section_header and d_match:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = f"D{d_match.group(1)}"
            # 把本行剩余内容（冒号后）作为段落起始
            rest = re.sub(r"^[Dd][1-8]\s*[:：\s，,]\s*", "", line.strip())
            current_lines = [rest] if rest else []
        else:
            if current_key is not None:
                current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return DocumentSections(
        full_text=full_text,
        sections=sections,
        header_text=header_text,
        source_path=source_path,
    )
