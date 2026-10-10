# 供审执行边界（根会话收敛）

本计划供审，不授权立即执行。已批准 design SHA 09B9083CD42F979D7BD912F0BC2ECBCCDA22DF15D7DAC2B55E26B6E29B18AA02 不变；本件新增的是精确实现/测试和隔离副作用审。

1. 起点固定主仓 HEAD `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。本聊天无可复用的合适托管树；历史 O3/门户树保留。
2. 获批后使用 app 原生 `create_worktree(allowAsync=true, name=sc4-source-evidence-1010, ref=28337c0ebb52afdbf61e955ecdbc22d151bcd185)` 创建并附着新候选。批准范围包括工具返回的仓库外新 checkout/必要 Git 元数据，实际绝对 workspace 路径创建后留证；只改正文八个产品/测试路径。Native 执行与显式 gpt-6-luna 沿用；不复制旧 dirty、不重置分支、不安装全局依赖。
3. 计划及批准的 OpenSpec 从主仓读取。候选实现、定向测试与审查在新树；根会话按共享锁维护正式 tasks/队列及批准/证据。候选最终 diff/SHA 留证，实际候选提交与 ff 另按治理收口，不在候选裸跑主仓 CommitSweep 或手动 commit。
4. 测试限定三个 SC4 文件：test_text_source.py、test_clause_extract.py、test_agent_audit.py；baseline 与实现后沿用同一清单。每次主仓 ignored `reports/sc4-source-evidence-1010/run-<uuid>/` 保存独立 basetemp（含合成 TXT/DOCX、保留 snapshot、JSONL/lock）、JUnit、stdout/stderr 和退出码。旧证据保留；可能无创建 symlink 权限时如实报告 skip，不假称已覆盖。
5. 唯一测试命令要求显式 `CandidateRoot`（原生工具真实返回路径）。真实合同/专业审核/业务签认/动作均各自保留前置；ff/push、真实取数、生产和外发另审。

---

# SC4 SourceEvidence 实施计划（供审）

## Goal

按已批准的 SC4 design A–E 与 §10，为 mock 阶段提供可执行的 SourceEvidence 实现路径：对注册的合成 TXT/DOCX 输入捕获一次原始字节，形成可追溯的文本证据与版本；保留原始半开区间偏移；强制写入真实 JSONL 审计；输入、解析或审计失败时 fail closed。该计划不启用真实合同、SRM、法律结论、审核动作或对外动作。

本轮仅保存计划。本计划所列实现、fixture 生成与测试命令均未执行。

## Architecture

1. 只有已注册的 synthetic SourceRef 可以进入 mock source adapter。TXT/MD 原始 bytes 读取一次，计算源 SHA-256 后严格 UTF-8 decode，不规范化 LF/CRLF。DOCX 原始 bytes 读取一次，保存到当前 run 新建的隔离 snapshot，再将 snapshot 路径交给共享 parser，显式 include_extra_parts=False；不得重新打开正式或原始 DOCX。
2. SourceEvidence 随 ContractDocument 传递，至少包含 artifact_id、source_version、source_sha256、canonical_text_sha256、text_view_id、text_view_version、offset_scheme。固定偏移协议为 `sc4-canonical-text-u32-half-open-v1`：Python Unicode codepoint 的 0-based 半开区间；事实原文必须等于 `source[start:end]`。展示文本可以 trim，但不能替代事实原文。
3. segmentation 不改变既有分类范围；无标题、歧义、无效输入等按已批准设计保留状态并 fail closed，不补推断事实。
4. 成功与可审计的输入失败都必须通过 AuditLogger.record 写入真实 JSONL sink。审计写失败时不得返回成功结果。事件只保存来源元数据、状态、覆盖数量、定位与阻塞标记，不保存合同原文或敏感路径。
5. 兼容保留既有 run_extraction(doc, lexicon, *, evaluator, audit=None) 合同与旧调用行为；新增完整 run_source_evidence/source-aware 入口才要求 SourceEvidence 与非空 AuditLogger。旧入口不计入六项来源证据验收。真实文档、专业审核、业务审批与动作执行保持关闭。

## Tech Stack

- Python 3.14 项目隔离环境；实现沿用 SC4 现有 Python 模块。
- DOCX mock fixture 使用 Python 标准库 zipfile 与 xml.etree.ElementTree 生成最小 OOXML 包；源解析使用已批准设计指定的共享 parser 公共接口。
- 持久审计使用平台 AuditLogger.jsonl(path) → AuditLogger.record(event) → JsonlSink.write(event)。禁止 noop/null sink。
- 测试使用 pytest 与 tmp_path；本轮不运行测试。

## Spec

- 权威设计：openspec/changes/sc4-contract-clause-extraction/design.md，用户已批准的 A–E 与 §10；批准证据 SHA-256：09B9083CD42F979D7BD912F0BC2ECBCCDA22DF15D7DAC2B55E26B6E29B18AA02。
- Stage A 为 synthetic mock；正式 OpenSpec spec/tasks 的 2M 阶段依赖已获批准更新，本计划按该依赖实施。已批准 design SHA 与本具体计划须逐项相符；不得从计划推导真实数据、专业签认、生产接入或对客权限。
- 文档台账及其他正式依据由主任务维护；本计划不变更任何正式 intent/design/spec/tasks/队列。

## Global Constraints

- 本计划仅授权准备实现路径，不授权执行实现或测试。
- 不改共享 parser 源码、平台审计实现、正式 OpenSpec 文件、队列、UI、connector、README/CLAUDE 或运行服务。
- 保留所有既有 dirty/untracked 修改；实现时只允许下列白名单文件。发现白名单外的必要改动，先停止并提交新的方案审阅。
- 只使用 synthetic 样本；禁止真实合同、供应商/OEM 技术附件、SRM/ERP 查询和外发。
- 不在测试中创建仓库 fixture 文件；所有临时源、snapshot 与 JSONL 写入 pytest tmp_path。未来计划中的 CLI 只可在获准实施后使用。
- DOCX snapshot 保留在本次新 UUID 隔离目录中，随测试 `tmp_path` 生命周期结束；不在实现步骤中 unlink/rmdir。不得递归删除、通配清理、清扫其他运行目录或删除 audit.jsonl。
- 审计 JSONL 必须持久化并可复核链；不能用空实现规避持久化依赖。审计写入失败即失败，不返回可用结果。

## Review Focus

1. 是否完整实现单次捕获与源哈希/文本哈希分离，且 TXT 换行不被隐式标准化。
2. DOCX 是否只解析同一份已捕获 bytes 的隔离 snapshot，并显式关闭额外 OOXML parts。
3. 来源证据、parser/profile 版本、offset scheme 是否进入结果与审计，原文是否严格等于半开区间切片。
4. 六个差异 case 与无效/缺失/审计失败的 fail-closed 行为是否覆盖，既有 run_extraction 兼容调用合同是否保持。
5. 审计是否走真实 JsonlSink；真实专业审核和动作仍是否保持关闭。
6. 路径白名单、正式闸依赖和隔离 snapshot 生命周期是否可审计。

## File Structure and Ownership

仅限以下文件；不得通过自动格式化顺带改其他路径。

- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/models.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/text_source.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/clause_extract.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/agent.py
- 新建：4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/sc4_evidence_fixtures.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_text_source.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_clause_extract.py
- 修改：4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_agent_audit.py

明确排除：共享 parser 实现、平台 AuditLogger/JsonlSink、正式 OpenSpec、队列、运行配置、真实连接器、UI、报告外的 fixtures、真实合同及 OEM 数据。计划本身位于被忽略的 reports 路径，不进入正式产品交付。

## Implementation Steps

### 0. 开始实施前的门禁

1. 重新核对批准 design 的 SHA-256 与本计划内容；若 design 已变化，暂停并重新审阅。
2. 正式 spec/tasks 已通过批准更新 Stage A 2M 依赖；本具体计划仍须按现流程供审批准后，才可执行实施。仅“文档就绪”不构成实施授权。
3. 记录当前工作树状态，不清理、不覆盖已有改动。确认白名单文件没有他人未提交改动；若有，先协调并在其基础上增量修改。
4. 读取共享 parser 的已批准公共接口/版本信息；不改 parser 源码。若接口与批准设计不一致，暂停，回到 design 评审。

### 1. 为来源与证据建模

1. 在 models.py 增加不可变 SourceRef 与 SourceEvidence 数据类。SourceRef 包含 artifact_id、version、relative_path；SourceEvidence 包含 artifact/version、source SHA-256、canonical text SHA-256、text view id/version 与固定 offset scheme。
2. ContractDocument 增加可选 source_evidence，保持纯 segmentation 单元测试构造兼容；真实 orchestration 对缺少 source_evidence 一律拒绝。
3. 明确 parser build/profile 作为文本视图版本字段，不能靠运行环境默认值隐式决定。
4. 覆盖 SHA 格式、空版本、offset scheme 不匹配等模型校验；错误输入不得构造可用来源证据。

### 2. 实现一次捕获的 mock source adapter

1. 限定输入为注册 SourceRef；将 relative_path 解析到调用方明确提供的 mock root 下。拒绝绝对路径、路径穿越、root 外解析结果、逃逸 symlink、未注册 artifact/version 与非支持后缀。
2. TXT/MD：以二进制方式打开并读取一次；对这些 bytes 计算 source_sha256；严格 UTF-8 decode，不做 newline translation、trim 或 Unicode normalization；对 decode 后的精确字符串计算 canonical_text_sha256。
3. DOCX：以二进制方式打开并读取一次；对捕获 bytes 计算 source_sha256；创建本次 run UUID 报告目录下 snapshots 子目录，并以 exclusive create 写入新 UUID 的 .docx snapshot。只将该 snapshot 交给共享 parser，调用必须显式 include_extra_parts=False；parser 返回的字符串是 canonical text，对其编码后计算 canonical_text_sha256。不得将原始 path 再交给 parser，也不得在计算哈希时重新读取源文件。
4. 将 parser build/profile 与 offset scheme 固定到 SourceEvidence；不支持 PDF/OCR、`.doc` 转换或 fallback parser。
5. DOCX 异常区分：无效 ZIP、缺少 word/document.xml、坏 XML 仍作为 DocxReadError；合法但无文本内容为 empty_text。不得将解析错误伪装成空合同。
6. 快照保留在本次新 UUID run 目录的 `snapshots` 下，供审计和复核；不执行 unlink/rmdir。测试目录由 pytest 的 `tmp_path` 生命周期管理。任何未来清理必须另有明确授权，本计划不包含删除步骤。

### 3. 保留原文位置并验证差异行为

1. 修改 clause_extract.py，使 ClauseSpan 的 start/end 均基于完整 canonical text 的 Python Unicode codepoint 索引，0-based 半开区间，scheme 固定为 `sc4-canonical-text-u32-half-open-v1`。
2. 不从 strip 后的局部字符串重算事实偏移；事实 text 必须是 canonical_text[start:end]。如需展示 trim 文本，新增独立 display_text 字段，禁止用 display_text 代替事实原文。
3. 保持已有分类/覆盖范围；歧义匹配归入 OTHER/unclassified；无章节标题状态为 no_clause_headings，空 span 列表，不推导缺失条款。
4. segmentation 继续使用既有分类输入和覆盖范围；source-aware entry 只增加来源证据，不将缺失推断为事实。

### 4. 接入必需 JSONL 审计并关闭无审计成功路径

1. 保持既有 run_extraction(doc, lexicon, *, evaluator, audit=None) 签名及 audit=None 兼容行为，不把旧入口计作来源证据验收。新增 run_source_evidence(source_ref, ..., evaluator, audit) 完整入口要求来源捕获、SourceEvidence 与非空 AuditLogger；省略 audit 由必填参数拒绝，显式 None 在读取/计算前拒绝。
2. 新完整入口先执行来源捕获，再调用 segmentation；成功和可审计的 typed source failure 都生成 AuditEvent。事件 data_sources 使用 dict[str, str]，至少保存 artifact/version、源哈希、文本哈希、text view id/version、offset scheme 与 lexicon 版本。
3. decision 记录 extraction 状态、coverage counts、review_status=待前置到位和标准化 blocked_by；不含合同正文、机密业务字段或本机绝对路径。content_hash 使用排序稳定的 JSON，纳入来源元数据、状态和每个 span 的类型/heading/start/end，不纳入原文正文。
4. 固定实际链路 AuditLogger.jsonl(path) → audit.record(event) → JsonlSink.write(event)。测试要断言文件存在、JSONL 可解析、链验证通过；禁止 mock/noop sink 作为成功证据。
5. sink 写失败时向调用方传播失败，且新完整入口不返回成功结果。source failure 的审计写入也失败时，传播审计异常并保留原异常上下文。
6. REVIEW 的三个现有函数继续抛出 PendingPrerequisiteError；不创建可执行人工审核动作。

### 5. 建立可重复 synthetic fixtures 与六个差异案例

1. 在 sc4_evidence_fixtures.py 提供六份确定性合成材料和 minimal DOCX builder；builder 仅用 stdlib zipfile/ElementTree 写最少 OOXML parts：[Content_Types].xml、_rels/.rels、word/document.xml。段落只含合成条款，不含真实供应商/OEM内容。
2. fixture 只在每个测试 tmp_path 下物化；不把生成的 DOCX/TXT 写入仓库或报告归档路径。
3. M01：同一逻辑合成合同分别 TXT 与 DOCX；比较抽取顺序、canonical text、offset、source/text hash、lexicon 与审计 manifest。TXT 与 DOCX 原始源哈希可以不同，但相同 canonical text 的 text hash 应相同。
4. M02：歧义标题命中两个 mock 类型；结果归 OTHER/unclassified，不作猜测。
5. M03：未分类标题仍保留原始位置与展示信息。
6. M04：无行首编号标题；行内“第三条”不算标题；输出空 spans 和 no_clause_headings，不推断 missing_types。
7. M05：CRLF、空白与非 ASCII 字符覆盖 codepoint 偏移；每项事实断言 text == source[start:end]，display_text 可单独 trim。
8. M06：同一 doc id 的 r1/r2 内容不同但 coverage 相同；来源哈希、canonical text 哈希、版本与 audit manifest 必须可区分，旧 JSONL 行保留。
9. 另覆盖无效 ZIP、缺失 OOXML 主文档、坏 XML、有效空 DOCX、unsupported `.pdf`/`.doc`、未注册来源、root 外路径、source evidence 缺失、JSONL 写失败与三项 review gate。每个失败都断言无成功结果。

### 5A. 实施代码基线（未来获批后按此接口落地）

以下代码块定义本次新增边界。实施时按白名单拆入对应模块；`run_extraction` 原函数不改签名/默认值。DOCX 生产路径固定导入 `zhuopin_platform.shared_tools.doc_parser.extract_text` 与 `DocxReadError`，只把一次捕获后保留的隔离 snapshot 路径传给该共享 parser，并显式传 `include_extra_parts=False`；不提供 parser/profile 注入入口，也不允许调用方替换原始 DOCX reader。parser 返回文本，解析失败保留共享 `DocxReadError` 类型并按失败路径审计。

#### models.py：来源类型与可选挂载

```python
from dataclasses import dataclass
import re

OFFSET_SCHEME = "sc4-canonical-text-u32-half-open-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SourceRef:
    artifact_id: str
    version: str
    relative_path: str

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.version.strip():
            raise ValueError("artifact_id 与 version 必填")
        if not self.relative_path.strip():
            raise ValueError("relative_path 必填")


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    artifact_id: str
    source_version: str
    source_sha256: str
    canonical_text_sha256: str
    text_view_id: str
    text_view_version: str
    offset_scheme: str = OFFSET_SCHEME

    def __post_init__(self) -> None:
        for value in (self.artifact_id, self.source_version,
                      self.text_view_id, self.text_view_version):
            if not value.strip():
                raise ValueError("SourceEvidence 标识与版本不得为空")
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 必须为小写 SHA-256")
        if not _SHA256.fullmatch(self.canonical_text_sha256):
            raise ValueError("canonical_text_sha256 必须为小写 SHA-256")
        if self.offset_scheme != OFFSET_SCHEME:
            raise ValueError("offset_scheme 不受支持")
```

给 `ContractDocument` 追加 `source_evidence: SourceEvidence | None = None`，不改原有必填字段及构造顺序；给 `ExtractionResult` 追加同名可选字段。旧构造调用保持有效，新完整入口在返回前必须确认该字段非空。`ClauseSpan.text` 改为未裁剪的原文切片；本计划不增添展示字段。

#### text_source.py：受注册约束的单次读取、DOCX 隔离快照

```python
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from .models import ContractDocument, SourceEvidence, SourceRef
from zhuopin_platform.shared_tools.doc_parser import DocxReadError, extract_text

OFFSET_SCHEME = "sc4-canonical-text-u32-half-open-v1"
TXT_TEXT_VIEW_ID = "utf-8-strict-direct-bytes;newline-preserved"
TXT_TEXT_VIEW_VERSION = "MOCK:sc4-utf8-source-profile-r1"
DOCX_TEXT_VIEW_ID = "zhuopin_platform.shared_tools.doc_parser.extract_text;include_extra_parts=False"
DOCX_TEXT_VIEW_VERSION = "MOCK:sc4-shared-doc-parser-profile-r1"


class SourceReadError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CapturedSource:
    document: ContractDocument
    evidence: SourceEvidence


def _under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class DocxTextSource:
    """DOCX 专用共享 parser adapter；PlainTextSource 仍只处理 TXT/MD。"""

    def load_snapshot(self, snapshot: Path) -> str:
        if snapshot.suffix.lower() != ".docx" or not snapshot.is_file():
            raise SourceReadError("docx_snapshot_invalid")
        text = extract_text(snapshot, include_extra_parts=False)
        if not isinstance(text, str):
            raise SourceReadError("docx_parser_returned_non_text")
        return text


def capture_registered_source(
    ref: SourceRef,
    *,
    mock_root: Path,
    run_dir: Path,
    registry: Mapping[tuple[str, str], str],
) -> CapturedSource:
    registered = registry.get((ref.artifact_id, ref.version))
    if registered is None or registered != ref.relative_path:
        raise SourceReadError("source_not_registered")
    try:
        root = mock_root.resolve(strict=True)
    except OSError as exc:
        raise SourceReadError("mock_root_unavailable") from exc
    relative = Path(ref.relative_path)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise SourceReadError("source_path_rejected")
    try:
        source = (root / relative).resolve(strict=True)
    except OSError as exc:
        raise SourceReadError("source_unavailable") from exc
    if not _under(source, root) or not source.is_file():
        raise SourceReadError("source_path_rejected")
    suffix = source.suffix.lower()
    if suffix not in {".txt", ".md", ".docx"}:
        raise SourceReadError("source_type_unsupported")

    try:
        raw = source.read_bytes()  # 本函数唯一一次读取注册源；后续只消费这份 bytes。
    except OSError as exc:
        raise SourceReadError("source_read_failed") from exc
    source_hash = sha256(raw).hexdigest()
    snapshot: Path | None = None
    snapshots_dir: Path | None = None
    try:
        if suffix in {".txt", ".md"}:
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SourceReadError("text_invalid_utf8") from exc
            text_view_id = TXT_TEXT_VIEW_ID
            text_view_version = TXT_TEXT_VIEW_VERSION
        else:
            try:
                run = run_dir.resolve(strict=True)
            except OSError as exc:
                raise SourceReadError("run_directory_unavailable") from exc
            run_id = run.name
            if not run_id.startswith("sc4-mock-"):
                raise SourceReadError("run_directory_not_isolated")
            snapshots_dir = run / "snapshots"
            try:
                snapshots_dir.mkdir(exist_ok=True)
            except OSError as exc:
                raise SourceReadError("snapshot_directory_failed") from exc
            try:
                snapshots_parent = snapshots_dir.resolve(strict=True).parent
            except OSError as exc:
                raise SourceReadError("snapshot_directory_invalid") from exc
            if snapshots_parent != run:
                raise SourceReadError("snapshot_parent_rejected")
            snapshot = snapshots_dir / f"{uuid4().hex}.docx"
            try:
                with snapshot.open("xb") as stream:
                    stream.write(raw)
            except OSError as exc:
                raise SourceReadError("snapshot_write_failed") from exc
            text = DocxTextSource().load_snapshot(snapshot)
            text_view_id = DOCX_TEXT_VIEW_ID
            text_view_version = DOCX_TEXT_VIEW_VERSION

        evidence = SourceEvidence(
            artifact_id=ref.artifact_id,
            source_version=ref.version,
            source_sha256=source_hash,
            canonical_text_sha256=sha256(text.encode("utf-8")).hexdigest(),
            text_view_id=text_view_id,
            text_view_version=text_view_version,
            offset_scheme=OFFSET_SCHEME,
        )
        document = ContractDocument(
            doc_id=ref.artifact_id,
            title=ref.artifact_id,
            text=text,
            source=f"synthetic:{ref.artifact_id}@{ref.version}",
            source_evidence=evidence,
        )
        return CapturedSource(document=document, evidence=evidence)
    finally:
        # 每个快照留在本次 UUID run 下供证据复核；不在本流程中删除。
        if snapshot is not None:
            try:
                resolved_snapshot = snapshot.resolve(strict=True)
                expected_parent = (run_dir.resolve(strict=True) / "snapshots").resolve(strict=True)
            except OSError as exc:
                raise SourceReadError("snapshot_validation_failed") from exc
            if resolved_snapshot.parent != expected_parent or resolved_snapshot.suffix != ".docx":
                raise SourceReadError("snapshot_path_invalid")
```

实施注：调用方只接受固定 mock root 下登记的 fixture；`run_dir` 由测试 `tmp_path` 下新 UUID 子目录创建，必须在进入本函数前存在。DOCX 只能调用上述确定导入的共享 `extract_text(snapshot, include_extra_parts=False)`，不允许注入替代 parser 或任意 text-view 版本。`DOCX_TEXT_VIEW_VERSION` 仅表示本合成 adapter 绑定的 profile，不能声称是实际部署 build；正式运行若无可验证 build metadata 必须 fail closed。TXT 与 DOCX 使用各自的固定 text-view ID/profile。隔离快照不删除，且其绝对路径不得写入审计。

#### clause_extract.py：原文半开位置

```python
_HEADING = re.compile(
    r"^[ \t]*(?:第\s*[一二三四五六七八九十百零〇\d]+\s*条|[一二三四五六七八九十]+\s*、|\d+(?:\.\d+)*[.、])\s*(?P<title>.*\S)?[ \t]*\r?$",
    re.MULTILINE,
)


def segment(doc: ContractDocument, lexicon: ClauseLexicon) -> ExtractionResult:
    matches = list(_HEADING.finditer(doc.text))
    spans: list[ClauseSpan] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(doc.text)
        heading = (match.group("title") or match.group(0)).strip()
        spans.append(ClauseSpan(
            clause_type=lexicon.classify(heading),
            heading=heading,
            text=doc.text[start:end],
            start=start,
            end=end,
        ))
    return ExtractionResult(
        doc_id=doc.doc_id, spans=spans, lexicon_id=lexicon.lexicon_id,
        source_evidence=doc.source_evidence,
    )
```

这个切片保留标题行前导空白、CRLF 与末尾换行；分类只消费已 trim 的 heading，不改变原文 span。既有 `summarize_coverage` 结构不变，不增加 missing_types 推断。

#### agent.py：新增强制来源与审计入口

```python
from pathlib import Path
from typing import Mapping

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.audit.sinks import JsonlSink
from .models import SourceRef
from .text_source import CapturedSource, DocxReadError, SourceReadError, capture_registered_source


def run_source_evidence(
    source_ref: SourceRef,
    lexicon: ClauseLexicon,
    *,
    mock_root: Path,
    run_dir: Path,
    registry: Mapping[tuple[str, str], str],
    evaluator: str,
    audit: AuditLogger,
) -> ExtractionResult:
    if not evaluator.strip():
        raise ValueError("evaluator 不可为空")
    if not isinstance(audit, AuditLogger) or not isinstance(audit.sink, JsonlSink):
        raise ValueError("来源证据入口要求真实 JSONL AuditLogger")
    try:
        captured = capture_registered_source(
            source_ref, mock_root=mock_root, run_dir=run_dir,
            registry=registry,
        )
    except (SourceReadError, DocxReadError) as exc:
        error_code = exc.code if isinstance(exc, SourceReadError) else "docx_read_error"
        payload = {
            "artifact_id": source_ref.artifact_id,
            "source_version": source_ref.version,
            "source_status": "read_failed",
            "extraction_status": "source_error",
            "error_code": error_code,
        }
        audit.record(AuditEvent(
            scenario=SCENARIO, action=ACTION, evaluator=evaluator,
            automation_level="L2", decision={
                **payload, "review_status": "待前置到位",
                "blocked_by": ["standard_clause_library", "risk_clause_criteria"],
            },
            data_sources={"source": f"synthetic:{source_ref.artifact_id}@{source_ref.version}",
                          "lexicon": lexicon.lexicon_id},
            content_hash=_content_hash(payload),
        ))
        raise

    result = clause_extract.segment(captured.document, lexicon)
    coverage = summarize_coverage(result)
    evidence = captured.evidence
    extraction_status = (
        "empty_text" if captured.document.text == ""
        else "no_clause_headings" if not result.spans
        else "extracted"
    )
    identity = {
        "artifact_id": evidence.artifact_id,
        "source_version": evidence.source_version,
        "source_sha256": evidence.source_sha256,
        "canonical_text_sha256": evidence.canonical_text_sha256,
        "text_view_id": evidence.text_view_id,
        "text_view_version": evidence.text_view_version,
        "offset_scheme": evidence.offset_scheme,
    }
    spans = [{"type": span.clause_type.value, "start": span.start, "end": span.end}
             for span in result.spans]
    audit_payload = {**identity, **coverage, "source_status": "captured",
                     "extraction_status": extraction_status,
                     "spans": spans}
    audit.record(AuditEvent(
        scenario=SCENARIO, action=ACTION, evaluator=evaluator,
        automation_level="L2", decision={
            **coverage, **identity, "source_status": "captured",
            "extraction_status": extraction_status,
            "review_status": "待前置到位",
            "blocked_by": ["standard_clause_library", "risk_clause_criteria"],
        },
        data_sources={"doc_id": captured.document.doc_id,
                      "source": captured.document.source,
                      "source_sha256": evidence.source_sha256,
                      "canonical_text_sha256": evidence.canonical_text_sha256,
                      "text_view": f"{evidence.text_view_id}@{evidence.text_view_version}",
                      "offset_scheme": evidence.offset_scheme,
                      "lexicon": lexicon.lexicon_id},
        content_hash=_content_hash(audit_payload),
    ))
    return result
```

该入口没有默认 `audit`，显式 `None` 或非 JSONL AuditLogger 在读取前拒绝；它写 `source_status`/`extraction_status`，并关联既有阻塞项，不创建 REVIEW 动作。成功、空文本、无标题、来源读取错误都各写清晰状态；任何 `audit.record` 异常向上传播，成功结果在记录返回前不会返回。既有 `run_extraction` 不被新入口调用或改写；它继续保留原来的 `audit=None` 兼容合同。

#### fixtures 与关键验收断言

```python
# tests/sc4_evidence_fixtures.py
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DOCX_PARTS = {
    "[Content_Types].xml": b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
    "_rels/.rels": b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
}


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    import xml.etree.ElementTree as ET
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = ET.Element(f"{{{ns}}}document")
    body = ET.SubElement(document, f"{{{ns}}}body")
    for paragraph in paragraphs:
        p = ET.SubElement(body, f"{{{ns}}}p")
        r = ET.SubElement(p, f"{{{ns}}}r")
        t = ET.SubElement(r, f"{{{ns}}}t")
        t.text = paragraph
    parts = dict(DOCX_PARTS)
    parts["word/document.xml"] = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, body_bytes in parts.items():
            archive.writestr(name, body_bytes)
    return path


def make_docx_parts(path: Path, parts: dict[str, bytes]) -> Path:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, body_bytes in parts.items():
            archive.writestr(name, body_bytes)
    return path


def synthetic_contract() -> str:
    return "前言\r\n第一条 价格\r\n含有非ASCII的¥字符\r\n第二条 交付\r\n按期交付。\r\n"
```

```python
# tests/test_agent_audit.py 新增的确定性输入 fixture
import pytest
from sc4_contract.models import SourceRef
from uuid import uuid4
from sc4_evidence_fixtures import DOCX_PARTS, make_docx, make_docx_parts, synthetic_contract


@pytest.fixture
def source_case(tmp_path):
    root = tmp_path / "mock"
    root.mkdir()
    text_r1 = synthetic_contract()
    text_r2 = text_r1.replace("按期交付。", "应于约定日期交付。")
    (root / "contract-r1.txt").write_bytes(text_r1.encode("utf-8"))
    (root / "contract-r2.txt").write_bytes(text_r2.encode("utf-8"))
    (root / "m02.txt").write_text("第一条 价格交付\n事实原文\n", encoding="utf-8")
    (root / "m03.txt").write_text("第一条 无匹配分类\r\n正文¥\r\n", encoding="utf-8")
    (root / "m05.txt").write_bytes("  第一条 价格  \r\n正文¥  \r\n\r\n第二条 交付 \r\n  交付\r\n".encode("utf-8"))
    (root / "no-headings.txt").write_text("正文引用第三条，但不是行首标题。\n", encoding="utf-8")
    (root / "empty.txt").write_bytes(b"")
    (root / "invalid-utf8.txt").write_bytes(b"\xff\xfe")
    make_docx(root / "empty.docx", [])
    make_docx_parts(root / "bad-xml.docx", {
        **DOCX_PARTS, "word/document.xml": b"<document>",
    })
    make_docx_parts(root / "missing-main.docx", DOCX_PARTS)
    (root / "invalid-zip.docx").write_bytes(b"not a zip archive")
    (root / "unsupported.pdf").write_bytes(b"synthetic placeholder")
    (root / "unsupported.doc").write_bytes(b"synthetic placeholder")
    m01_text = "\n".join([
        "第一条 价格", "金额为¥20", "第二条 交付", "按期交付",
        "第三条 质保", "提供质保", "第四条 违约", "按约处理",
    ])
    (root / "m01.txt").write_bytes(m01_text.encode("utf-8"))
    make_docx(root / "m01.docx", m01_text.split("\n"))
    refs = {
        "r1": SourceRef("SC4-MOCK-M06", "r1", "contract-r1.txt"),
        "r2": SourceRef("SC4-MOCK-M06", "r2", "contract-r2.txt"),
        "m01_txt": SourceRef("SC4-MOCK-M01", "r1", "m01.txt"),
        "m01_docx": SourceRef("SC4-MOCK-M01-DOCX", "r1", "m01.docx"),
        "m02": SourceRef("SC4-MOCK-M02", "r1", "m02.txt"),
        "m03": SourceRef("SC4-MOCK-M03", "r1", "m03.txt"),
        "m04": SourceRef("SC4-MOCK-M04", "r1", "no-headings.txt"),
        "m05": SourceRef("SC4-MOCK-M05", "r1", "m05.txt"),
        "empty": SourceRef("SC4-MOCK-EMPTY", "r1", "empty.txt"),
        "invalid_utf8": SourceRef("SC4-MOCK-INVALID-UTF8", "r1", "invalid-utf8.txt"),
        "empty_docx": SourceRef("SC4-MOCK-EMPTY-DOCX", "r1", "empty.docx"),
        "invalid_docx": SourceRef("SC4-MOCK-INVALID-DOCX", "r1", "invalid-zip.docx"),
        "missing_main": SourceRef("SC4-MOCK-MISSING-MAIN", "r1", "missing-main.docx"),
        "bad_xml": SourceRef("SC4-MOCK-BAD-XML", "r1", "bad-xml.docx"),
        "pdf": SourceRef("SC4-MOCK-PDF", "r1", "unsupported.pdf"),
        "doc": SourceRef("SC4-MOCK-DOC", "r1", "unsupported.doc"),
    }
    registry = {(ref.artifact_id, ref.version): ref.relative_path for ref in refs.values()}
    def kwargs():
        run_dir = tmp_path / f"sc4-mock-{uuid4().hex}"
        run_dir.mkdir()
        return {"mock_root": root, "run_dir": run_dir, "registry": registry}
    return {"root": root, "refs": refs, "registry": registry,
            "kwargs": kwargs, "text_r1": text_r1, "text_r2": text_r2,
            "m01_text": m01_text}
```

```python
# tests/test_agent_audit.py  imports
from pathlib import Path
import json
import pytest
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.doc_parser import DocxReadError
from sc4_contract.agent import ACTION, SCENARIO, run_extraction, run_source_evidence
from sc4_contract.clause_extract import segment, summarize_coverage
from sc4_contract.text_source import SourceReadError, capture_registered_source
from sc4_evidence_fixtures import synthetic_contract
```

未来测试至少逐项落成以下断言，不以 prose 代替测试：

```python
def test_m05_crlf_unicode_offsets_are_exact_slices(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    raw_source = (source_case["root"] / "m05.txt").read_bytes().decode("utf-8")
    result = run_source_evidence(
        source_case["refs"]["m05"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "m05.jsonl"),
    )
    for span in result.spans:
        assert 0 <= span.start <= span.end <= len(raw_source)
        assert span.text == raw_source[span.start:span.end]
    assert "\r\n" in result.spans[0].text
    assert "¥" in result.spans[0].text
    assert result.spans[0].text.startswith("  ")
    assert result.spans[0].text.endswith("\r\n\r\n")
    assert len(result.spans) == 2  # CRLF 标题仍识别，原始坐标不经换行归一化


def test_m01_txt_and_docx_capture_have_separate_source_and_text_hashes(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import ClauseType
    txt = capture_registered_source(
        source_case["refs"]["m01_txt"], **source_case["kwargs"]()
    )
    docx = capture_registered_source(
        source_case["refs"]["m01_docx"], **source_case["kwargs"]()
    )
    assert txt.document.text == docx.document.text == source_case["m01_text"]
    assert txt.evidence.canonical_text_sha256 == docx.evidence.canonical_text_sha256
    assert txt.evidence.source_sha256 != docx.evidence.source_sha256
    assert txt.evidence.text_view_id != docx.evidence.text_view_id
    assert txt.evidence.source_version == "r1"
    assert docx.evidence.offset_scheme == "sc4-canonical-text-u32-half-open-v1"
    expected = [ClauseType.PRICE, ClauseType.DELIVERY, ClauseType.WARRANTY, ClauseType.PENALTY]
    assert [span.clause_type for span in segment(txt.document, MOCK_LEXICON).spans] == expected
    assert [span.clause_type for span in segment(docx.document, MOCK_LEXICON).spans] == expected
    audit_path = tmp_path / "m01-audit.jsonl"
    txt_result = run_source_evidence(
        source_case["refs"]["m01_txt"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(audit_path),
    )
    docx_result = run_source_evidence(
        source_case["refs"]["m01_docx"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(audit_path),
    )
    txt_coverage = summarize_coverage(txt_result)
    docx_coverage = summarize_coverage(docx_result)
    assert {k: v for k, v in txt_coverage.items() if k != "doc_id"} == {
        k: v for k, v in docx_coverage.items() if k != "doc_id"
    }
    events = AuditLogger.jsonl(audit_path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(events) == 2
    assert [event["decision"]["extraction_status"] for event in events] == ["extracted", "extracted"]
    assert events[0]["decision"]["source_sha256"] != events[1]["decision"]["source_sha256"]
    assert events[0]["decision"]["canonical_text_sha256"] == events[1]["decision"]["canonical_text_sha256"]
    chain = AuditLogger.jsonl(audit_path).verify_chain()
    assert chain.ok is True and chain.total == 2


def test_m02_ambiguous_heading_is_other(source_case, tmp_path):
    from sc4_contract.clause_lexicon import ClauseLexicon
    from sc4_contract.models import ClauseType, ContractDocument
    ambiguous = ClauseLexicon("fixture-ambiguous-v1", {
        ClauseType.PRICE: ("价格交付",),
        ClauseType.DELIVERY: ("价格交付",),
    })
    result = run_source_evidence(
        source_case["refs"]["m02"], ambiguous, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "m02.jsonl"),
    )
    assert result.spans[0].clause_type is ClauseType.OTHER
    assert result.spans[0].text == "第一条 价格交付\n事实原文\n"
    assert AuditLogger.jsonl(tmp_path / "m02.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]["decision"]["extraction_status"] == "extracted"


def test_m03_unclassified_heading_keeps_full_source_span(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import ClauseType, ContractDocument
    result = run_source_evidence(
        source_case["refs"]["m03"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "m03.jsonl"),
    )
    source = result.source_evidence
    canonical = source_case["root"].joinpath("m03.txt").read_bytes().decode("utf-8")
    span = result.spans[0]
    assert span.clause_type is ClauseType.OTHER
    assert span.text == canonical[span.start:span.end] == canonical
    event = AuditLogger.jsonl(tmp_path / "m03.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["extraction_status"] == "extracted"
    assert "正文¥" not in json.dumps(event, ensure_ascii=False)


def test_m04_no_heading_returns_empty_without_missing_inference(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import ContractDocument
    result = run_source_evidence(
        source_case["refs"]["m04"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "m04.jsonl"),
    )
    assert result.spans == []
    coverage = summarize_coverage(result)
    assert coverage["span_count"] == 0
    assert "missing_types" not in coverage
    decision = AuditLogger.jsonl(tmp_path / "m04.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]["decision"]
    assert decision["extraction_status"] == "no_clause_headings"


def test_valid_empty_text_is_distinct_from_no_headings(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    result = run_source_evidence(
        source_case["refs"]["empty"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "empty.jsonl"),
    )
    assert result.source_evidence is not None
    assert result.spans == []
    event = AuditLogger.jsonl(tmp_path / "empty.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["extraction_status"] == "empty_text"


def test_valid_empty_docx_is_empty_text_not_parser_error(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    result = run_source_evidence(
        source_case["refs"]["empty_docx"], MOCK_LEXICON, **source_case["kwargs"](),
        evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "empty-docx.jsonl"),
    )
    assert result.spans == []
    event = AuditLogger.jsonl(tmp_path / "empty-docx.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["extraction_status"] == "empty_text"


def test_typed_source_error_is_audited_and_never_returns_result(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import SourceRef
    missing = SourceRef("SC4-MOCK-MISSING", "r1", "not-found.txt")
    registry = {**source_case["registry"], (missing.artifact_id, missing.version): missing.relative_path}
    with pytest.raises(SourceReadError, match="source_unavailable"):
        run_source_evidence(
            missing, MOCK_LEXICON, **{**source_case["kwargs"](), "registry": registry},
            evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "missing.jsonl"),
        )
    event = AuditLogger.jsonl(tmp_path / "missing.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["source_status"] == "read_failed"
    assert event["decision"]["extraction_status"] == "source_error"
    assert event["decision"]["error_code"] == "source_unavailable"


def test_invalid_utf8_is_typed_and_audited(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    with pytest.raises(SourceReadError, match="text_invalid_utf8"):
        run_source_evidence(
            source_case["refs"]["invalid_utf8"], MOCK_LEXICON, **source_case["kwargs"](),
            evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "bad-utf8.jsonl"),
        )
    event = AuditLogger.jsonl(tmp_path / "bad-utf8.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["extraction_status"] == "source_error"
    assert event["decision"]["error_code"] == "text_invalid_utf8"


def test_unregistered_and_traversal_refs_are_typed_and_audited(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import SourceRef
    outside = tmp_path / "outside.txt"
    outside.write_text("不得读取", encoding="utf-8")
    cases = [
        (SourceRef("SC4-MOCK-UNREGISTERED", "r1", "contract-r1.txt"), source_case["registry"], "unregistered.jsonl", "source_not_registered"),
        (SourceRef("SC4-MOCK-TRAVERSAL", "r1", "../outside.txt"),
         {**source_case["registry"], ("SC4-MOCK-TRAVERSAL", "r1"): "../outside.txt"},
         "traversal.jsonl", "source_path_rejected"),
    ]
    for ref, registry, filename, code in cases:
        with pytest.raises(SourceReadError, match=code):
            run_source_evidence(
                ref, MOCK_LEXICON,
                **{**source_case["kwargs"](), "registry": registry},
                evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / filename),
            )
        event = AuditLogger.jsonl(tmp_path / filename).query_by(scenario=SCENARIO, action=ACTION)[0]
        assert event["decision"]["error_code"] == code
        assert "outside.txt" not in json.dumps(event, ensure_ascii=False)


def test_symlink_escape_is_rejected(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    from sc4_contract.models import SourceRef
    outside = tmp_path / "outside-link-target.txt"
    outside.write_text("不得读取", encoding="utf-8")
    link = source_case["root"] / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("当前 Windows 测试进程无创建 symlink 的权限")
    ref = SourceRef("SC4-MOCK-SYMLINK", "r1", "escape.txt")
    registry = {**source_case["registry"], (ref.artifact_id, ref.version): ref.relative_path}
    with pytest.raises(SourceReadError, match="source_path_rejected"):
        run_source_evidence(
            ref, MOCK_LEXICON, **{**source_case["kwargs"](), "registry": registry},
            evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / "symlink.jsonl"),
        )


def test_source_evidence_rejects_bad_hash_and_offset_scheme():
    from sc4_contract.models import SourceEvidence
    values = {
        "artifact_id": "SC4-MOCK-X", "source_version": "r1",
        "source_sha256": "0" * 64, "canonical_text_sha256": "1" * 64,
        "text_view_id": "fixture", "text_view_version": "MOCK:r1",
    }
    with pytest.raises(ValueError, match="source_sha256"):
        SourceEvidence(**{**values, "source_sha256": "bad"})
    with pytest.raises(ValueError, match="offset_scheme"):
        SourceEvidence(**values, offset_scheme="other")


def test_explicit_none_audit_is_rejected_before_source_io(source_case):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    with pytest.raises(ValueError, match="JSONL AuditLogger"):
        run_source_evidence(
            source_case["refs"]["r1"], MOCK_LEXICON, **source_case["kwargs"](),
            evaluator="synthetic-test-operator", audit=None,
        )


@pytest.mark.parametrize("ref_key", ["pdf", "doc"])
def test_unsupported_formats_fail_closed(source_case, tmp_path, ref_key):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    with pytest.raises(SourceReadError, match="source_type_unsupported"):
        run_source_evidence(
            source_case["refs"][ref_key], MOCK_LEXICON, **source_case["kwargs"](),
            evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / f"{ref_key}.jsonl"),
        )


@pytest.mark.parametrize("ref_key", ["invalid_docx", "missing_main", "bad_xml"])
def test_invalid_docx_variants_preserve_docxreaderror(source_case, tmp_path, ref_key):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    with pytest.raises(DocxReadError):
        run_source_evidence(
            source_case["refs"][ref_key], MOCK_LEXICON, **source_case["kwargs"](),
            evaluator="synthetic-test-operator", audit=AuditLogger.jsonl(tmp_path / f"{ref_key}.jsonl"),
        )
    event = AuditLogger.jsonl(tmp_path / f"{ref_key}.jsonl").query_by(scenario=SCENARIO, action=ACTION)[0]
    assert event["decision"]["source_status"] == "read_failed"
    assert event["decision"]["extraction_status"] == "source_error"


def test_docx_uses_actual_shared_parser_on_snapshot_with_extra_parts_false(source_case, monkeypatch):
    import sc4_contract.text_source as source_module
    kwargs = source_case["kwargs"]()
    calls = []
    original_extract_text = source_module.extract_text
    def parser_spy(path, *, include_extra_parts):
        calls.append((Path(path), include_extra_parts))
        assert Path(path).is_file()
        return original_extract_text(path, include_extra_parts=include_extra_parts)
    monkeypatch.setattr(source_module, "extract_text", parser_spy)
    captured = capture_registered_source(
        source_case["refs"]["m01_docx"], mock_root=source_case["root"],
        run_dir=kwargs["run_dir"], registry=source_case["registry"],
    )
    assert len(calls) == 1 and calls[0][1] is False
    assert calls[0][0].parent.name == "snapshots"
    assert calls[0][0].is_file()  # 快照保留在本次隔离 run 内供复核
    assert calls[0][0].read_bytes() == (source_case["root"] / "m01.docx").read_bytes()
    assert captured.evidence.canonical_text_sha256


def test_registered_txt_and_docx_sources_are_read_once_and_parser_uses_snapshot(source_case, monkeypatch):
    import sc4_contract.text_source as source_module
    registered = {
        (source_case["root"] / "m01.txt").resolve(): 0,
        (source_case["root"] / "m01.docx").resolve(): 0,
    }
    original_read_bytes = Path.read_bytes
    original_extract_text = source_module.extract_text
    parser_paths = []

    def counted_read_bytes(path):
        resolved = Path(path).resolve()
        if resolved in registered:
            registered[resolved] += 1
        return original_read_bytes(path)

    def parser_spy(path, *, include_extra_parts):
        parser_paths.append(Path(path).resolve())
        return original_extract_text(path, include_extra_parts=include_extra_parts)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    monkeypatch.setattr(source_module, "extract_text", parser_spy)
    txt = capture_registered_source(
        source_case["refs"]["m01_txt"], **source_case["kwargs"]()
    )
    docx = capture_registered_source(
        source_case["refs"]["m01_docx"], **source_case["kwargs"]()
    )

    assert registered == {
        (source_case["root"] / "m01.txt").resolve(): 1,
        (source_case["root"] / "m01.docx").resolve(): 1,
    }
    assert txt.document.text == docx.document.text == source_case["m01_text"]
    assert len(parser_paths) == 1
    assert parser_paths[0] != (source_case["root"] / "m01.docx").resolve()
    assert parser_paths[0].parent.name == "snapshots"


def test_m06_version_change_keeps_old_jsonl_and_hashes_change(tmp_path, source_case):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    audit_path = tmp_path / "audit.jsonl"
    first = run_source_evidence(source_case["refs"]["r1"], MOCK_LEXICON,
                                **source_case["kwargs"](), audit=AuditLogger.jsonl(audit_path),
                                evaluator="synthetic-test-operator")
    second = run_source_evidence(source_case["refs"]["r2"], MOCK_LEXICON,
                                 **source_case["kwargs"](), audit=AuditLogger.jsonl(audit_path),
                                 evaluator="synthetic-test-operator")
    assert summarize_coverage(first) == summarize_coverage(second)
    assert first.source_evidence.source_sha256 != second.source_evidence.source_sha256
    assert first.source_evidence.canonical_text_sha256 != second.source_evidence.canonical_text_sha256
    assert first.source_evidence.source_version != second.source_evidence.source_version
    records = AuditLogger.jsonl(audit_path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(records) == 2
    for record, result in zip(records, (first, second), strict=True):
        assert record["evaluator"] == "synthetic-test-operator"
        assert record["automation_level"] == "L2"
        assert record["decision"]["extraction_status"] == "extracted"
        assert record["decision"]["review_status"] == "待前置到位"
        assert record["decision"]["blocked_by"] == ["standard_clause_library", "risk_clause_criteria"]
        assert record["decision"]["source_sha256"] == result.source_evidence.source_sha256
        assert record["decision"]["canonical_text_sha256"] == result.source_evidence.canonical_text_sha256
        assert record["data_sources"]["lexicon"] == "mock-v0"
        assert all(type(value) is str for value in record["data_sources"].values())
    assert records[0]["content_hash"] != records[1]["content_hash"]
    assert records[0]["decision"]["canonical_text_sha256"] != records[1]["decision"]["canonical_text_sha256"]
    chain = AuditLogger.jsonl(audit_path).verify_chain()
    assert chain.ok is True
    assert chain.total == 2


def test_real_jsonl_sink_failure_never_returns_success(source_case, tmp_path):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    blocked_path = tmp_path / "audit-is-directory.jsonl"
    blocked_path.mkdir()
    with pytest.raises(OSError):
        run_source_evidence(source_case["refs"]["r1"], MOCK_LEXICON,
                            **source_case["kwargs"](), audit=AuditLogger.jsonl(blocked_path),
                            evaluator="synthetic-test-operator")


def test_legacy_api_still_allows_omitted_audit(source_case):
    from sc4_contract.clause_lexicon import MOCK_LEXICON
    doc = capture_registered_source(source_case["refs"]["r1"], **source_case["kwargs"]()).document
    result = run_extraction(doc, MOCK_LEXICON, evaluator="synthetic-test-operator")
    assert result.doc_id == doc.doc_id
    assert result.source_evidence == doc.source_evidence
    # 尽管 document 已携带来源证明，legacy audit=None 仍只证明兼容可运行，不算完整来源审计验收。
```

上述可执行测试覆盖的失败矩阵为：未注册 ref、路径穿越、越界 symlink、`.pdf`/`.doc`、UTF-8 decode 错、无效 ZIP、缺 `word/document.xml`、坏 XML、显式 `audit=None`、真实 JSONL sink 写失败及 SourceEvidence 校验失败；每个 source failure 均断言抛出 typed error 且 JSONL 有 `source_status=read_failed`、`extraction_status=source_error`。有效空 DOCX 单独断言 `extraction_status=empty_text`，无标题非空输入断言 `no_clause_headings`。M01 由已导入的真实 `zhuopin_platform.shared_tools.doc_parser.extract_text` 端到端执行；spy 只包裹该真实函数，以验证隔离 snapshot 参数与 `include_extra_parts=False`，不替代真实 parser。

### 6. 更新测试并执行获批的定向验证

仅在实施获批后、从 SC4 子项目 cwd 执行以下 PowerShell 命令；本轮未运行。每次运行创建新的 ignored UUID 结果目录，JUnit 与合并 stdout/stderr 均留证；不在仓库根目录混跑：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc4ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc4CandidateHead = (& git -C $sc4ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc4CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') {
    throw 'SC4 candidate HEAD differs from the approved starting point'
}
$sc4RunId = [guid]::NewGuid().ToString('N')
$sc4RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc4-source-evidence-1010' "run-$sc4RunId"
New-Item -ItemType Directory -Path $sc4RunDir -ErrorAction Stop | Out-Null
$sc4ProjectDir = Join-Path $sc4ResolvedRoot '4-数字员工/采购部/SC4-合同条款自动提取与审核'
Push-Location $sc4ProjectDir
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_text_source.py' 'tests/test_clause_extract.py' 'tests/test_agent_audit.py' --basetemp (Join-Path $sc4RunDir 'basetemp') --junitxml (Join-Path $sc4RunDir 'junit.xml') 1> (Join-Path $sc4RunDir 'stdout.log') 2> (Join-Path $sc4RunDir 'stderr.log')
    $sc4TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc4RunDir 'exit-code.txt'), [string]$sc4TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc4TestExit -ne 0) { throw "SC4 targeted pytest failed with exit code $sc4TestExit; preserve $sc4RunDir" }
```

测试实现边界：TXT bytes 读取次数可通过隔离 fake file wrapper 计数；DOCX adapter 测试可用 spy 验证只传 snapshot path 与 include_extra_parts=False，而不替代真实共享 parser 的集成验证。所有 fixture snapshot 与 JSONL 审计落在 tmp_path；JUnit/命令输出落在上述新 UUID ignored 结果目录；不连接现网服务、不查询真实数据。

### 7. 复核与交付

1. 对照本白名单检查 diff，只包含允许的八个产品/测试文件；排除报告、正式 spec/tasks、共享 parser、队列、runtime、真实数据。
2. 回读实际 JSONL 样例，核对字段无敏感正文/绝对源路径，并验证 JSONL chain。
3. 汇总 M01–M06、错误矩阵、真实 sink 证据、未解决限制和测试结果；未通过则不宣称完成。
4. 首项 2M mock 来源证据实现与测试闭合后只回写该项证据；不得据此归档整个 SC4 场景。真实来源、专业 review、业务签认与后续任务仍按正式闸推进；合并或发布仍需针对该动作另行授权。

## Exit Criteria

- 正式 Stage A 依赖闸与本计划审批已齐全，且实现 diff 在文件白名单内。
- TXT/DOCX 从单次捕获内容得出 source hash 与 canonical text hash，DOCX 共享 parser 调用显式关闭 extra parts。
- 六差异案例、错误矩阵、u32 codepoint 半开偏移断言通过；缺来源证据、解析错误或审计失败均 fail closed。
- 每个成功结果都有真实 JSONL 审计行，sink 使用 JsonlSink，审计链验证通过。
- 三个 REVIEW 入口仍保持 PendingPrerequisiteError；真实合同、专业签认和动作没有被启用。
- 首项 2M 闭合只说明 synthetic source-evidence 代码与定向测试达到该项验收；不等于真实来源接入、专业/业务签认、全场景完工或归档。
- 本计划本身不证明实现已发生或验收已通过。
