"""单一授权 PPTX 的完整、可定位证据。失败不转成缺证或零分。"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import io
import os
import posixpath
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET
from .embedded_workbook import read_cached_cells

NS = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main', 'p':'http://schemas.openxmlformats.org/presentationml/2006/main', 'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentScope:
    oem_label: str
    source_version: str
    asil_level: str
    authorized_sha256: str


@dataclass(frozen=True)
class EvidenceRecord:
    ref: str
    page: int
    shape: str
    kind: str
    text: str


@dataclass(frozen=True)
class EvidenceBundle:
    scope: DocumentScope
    source_sha256: str
    sections: dict[str, str]
    records: tuple[EvidenceRecord, ...]
    assets: tuple[dict, ...]
    warnings: tuple[str, ...]
    paragraph_count: int
    page_count: int
    complete: bool
    scene: str | None
    read_state: str

    def to_dict(self):
        return asdict(self)


def _qda_reader():
    # 同一候选中的既有跨页分段；不使用另一工作树/共享 editable 指针。
    path = Path(__file__).resolve().parents[2] / 'QD-A-8D不良分析/qda_prefill/doc_reader.py'
    key = '_q2_qda_' + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def _xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise EvidenceError('XML entity declarations prohibited')
    return ET.fromstring(raw)


def _paragraph(p):
    return ''.join('\n' if n.tag == '{'+NS['a']+'}br' else (n.text or '') for n in p.iter() if n.tag in ('{'+NS['a']+'}t', '{'+NS['a']+'}br'))


def _preview(raw, target, original):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width * im.height > Image.MAX_IMAGE_PIXELS:
                raise EvidenceError('image pixel limit')
            im.load(); im.thumbnail((3200,3200)); im.convert('RGB').save(target, 'PNG')
    except Exception:
        if original.suffix.lower() == '.emf' and os.name == 'nt':
            # 固定命令，路径只经环境传递；不解释文档中的任何指令。
            script = "Add-Type -AssemblyName System.Drawing; $i=[System.Drawing.Image]::FromFile($env:Q2_EMF_SOURCE); try { $b=[System.Drawing.Bitmap]::new($i); try {$b.Save($env:Q2_EMF_TARGET,[System.Drawing.Imaging.ImageFormat]::Png)} finally {$b.Dispose()} } finally {$i.Dispose()}"
            env = dict(os.environ, Q2_EMF_SOURCE=str(original), Q2_EMF_TARGET=str(target))
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,check=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            raise


def read_pptx_evidence(path: Path, scope: DocumentScope) -> EvidenceBundle:
    if scope.asil_level.upper() not in ('QM', 'A', 'B') or not scope.oem_label or not scope.source_version:
        raise EvidenceError('scope/ASIL excluded')
    raw = path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    if source_hash != scope.authorized_sha256 or len(raw) > 20 * 1024 * 1024:
        raise EvidenceError('source SHA256 mismatch or input too large')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist(); names = z.namelist()
            if len(infos)>4096 or len(names)!=len(set(names)) or sum(x.file_size for x in infos)>128*1024*1024:
                raise EvidenceError('archive limits/duplicates')
            if any('\\' in n or PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or ':' in n for n in names):
                raise EvidenceError('unsafe archive path')
            rels = {e.attrib['Id']:e.attrib['Target'] for e in _xml(z.read('ppt/_rels/presentation.xml.rels'))}
            slides = [posixpath.normpath(posixpath.join('ppt', rels[e.attrib['{'+NS['r']+'}id']])) for e in _xml(z.read('ppt/presentation.xml')).findall('p:sldIdLst/p:sldId', NS)]
            if not slides or len(slides)>64:
                raise EvidenceError('slide count out of range')
            records=[]; paragraphs=0; expected=0; relation_pages={}; warnings=[]; assets=[]
            for page, part in enumerate(slides,1):
                root=_xml(z.read(part))
                expected += sum(bool(_paragraph(p).strip()) for p in root.findall('.//a:p',NS))
                relpart=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
                if relpart in names:
                    for rel in _xml(z.read(relpart)):
                        if rel.attrib.get('TargetMode')=='External':
                            continue  # 外链只作为原包内容保留，不访问。
                        dest=posixpath.normpath(posixpath.join(posixpath.dirname(part),rel.attrib['Target']))
                        relation_pages.setdefault(dest,[]).append(page)
                tree=root.find('p:cSld/p:spTree',NS)
                if tree is None: raise EvidenceError('slide shape tree missing')
                def visit(parent, prefix):
                    nonlocal paragraphs
                    for i, shape in enumerate(parent):
                        ident=f'{prefix}.{i+1}'
                        if shape.tag.endswith('}grpSp'):
                            visit(shape,ident); continue
                        for j, body in enumerate(shape.findall('p:txBody',NS)):
                            texts=[_paragraph(p) for p in body.findall('a:p',NS)]
                            paragraphs+=sum(bool(t.strip()) for t in texts)
                            records.append(EvidenceRecord(f'p{page}-s{ident}-t{j+1}',page,ident,'text','\n'.join(texts)))
                        for ri,row in enumerate(shape.findall('.//a:tbl/a:tr',NS),1):
                            for ci,cell in enumerate(row.findall('a:tc',NS),1):
                                texts=[_paragraph(p) for p in cell.findall('a:txBody/a:p',NS)]
                                paragraphs+=sum(bool(t.strip()) for t in texts)
                                text='\n'.join(texts)
                                records.append(EvidenceRecord(f'p{page}-s{ident}-r{ri}c{ci}',page,ident,'table_cell' if text else 'empty_table_cell',text))
                visit(tree,'0')
            if paragraphs != expected:
                raise EvidenceError(f'paragraph coverage mismatch: {paragraphs}/{expected}')
            assetdir=path.parent/'evidence-assets'; assetdir.mkdir(exist_ok=True)
            for part in names:
                if not part.startswith(('ppt/media/', 'ppt/embeddings/')) or part.endswith('/'):continue
                data=z.read(part); digest=hashlib.sha256(data).hexdigest()
                suffix=PurePosixPath(part).suffix.lower(); dest=assetdir/(digest+suffix)
                if dest.exists() and dest.read_bytes()!=data:raise EvidenceError('asset collision')
                if not dest.exists():dest.write_bytes(data)
                item={'ref':'asset-'+digest[:16],'part':part,'path':str(dest),'sha256':digest,'pages':sorted(set(relation_pages.get(part,[]))), 'read_state':'READ', 'kind':'media' if part.startswith('ppt/media/') else 'workbook'}
                try:
                    if item['kind']=='media':
                        preview=assetdir/(digest+'.preview.png')
                        _preview(data,preview,dest);item['preview']=str(preview)
                    else:
                        item['cells']=[asdict(c) for c in read_cached_cells(data,part)]
                except Exception as exc:
                    item['read_state']='READ_ERROR';item['error']=f'{type(exc).__name__}: {exc}';warnings.append(part+': '+item['error'])
                assets.append(item)
            text='\n'.join(r.text for r in records if r.text.strip())
            parsed=_qda_reader()._parse_sections(text,str(path))
            return EvidenceBundle(scope,source_hash,parsed.sections,tuple(records),tuple(assets),tuple(warnings),paragraphs,len(slides),not warnings,parsed.scene_checkbox.scene if parsed.scene_checkbox else None,'READ' if not warnings else 'READ_ERROR')
    except EvidenceError:raise
    except Exception as exc:
        raise EvidenceError(f'PPTX read failed: {type(exc).__name__}: {exc}') from exc
