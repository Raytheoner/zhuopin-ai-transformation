"""本客户单件作业：真实阶段、不可变产物、唯一 audit 后发布。"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,re,threading,uuid
from zhuopin_platform.audit import AuditEvent,AuditLogger
from zhuopin_platform.data_isolation_layer.router import OEMRouter
from . import config
from .ai_advice import make_request,validate_advice,canonical,digest,PROMPT_HASH,SCHEMA_HASH,MODEL,AdviceError,AdviceRequest
from .document_evidence import DocumentScope,read_pptx_evidence
from .engine import VerdictEngine
from .models import EightDInput
from .rules_loader import load

MAX_BYTES=20*1024*1024
FINAL=('complete','failed','interrupted')

class UploadError(RuntimeError):
    def __init__(self,code,message=''):
        self.code=code;super().__init__(message or code)

@dataclass(frozen=True)
class JobRef:
    object_id:str
    state:str

@dataclass(frozen=True)
class SavedDocumentReport:
    object_id:str
    state:str
    payload:dict|None=None
    receipt:dict|None=None
    error:str=''
    repair_available:bool=False

class DocumentUploadService:
    def __init__(self,root:Path,audit:AuditLogger,model,scope:DocumentScope):
        if scope.asil_level not in ('QM','A','B'):raise UploadError('scope_denied')
        self.root=Path(root).resolve();self.audit=audit;self.model=model;self.scope=scope
        self.instance=uuid.uuid4().hex;self._gate=threading.Lock();self._active=set()
        collection='oem_'+re.sub('[^a-z0-9_]','_',scope.oem_label.lower())+'_q2'
        self.router=OEMRouter(registered={scope.oem_label:collection},audit=audit)
        self.collection=self.router.resolve(scope.oem_label)
        self._guard(True)
        self._immutable(self.root/'scope.json',canonical(asdict(scope)).encode())

    def _guard(self,write=False):
        (self.router.guard_write if write else self.router.guard)(self.scope.oem_label,self.collection)

    def _immutable(self,path,raw):
        self._guard(True);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=raw:raise UploadError('storage_integrity','immutable content mismatch')
            return
        scratch=path.parent/(path.name+'.'+uuid.uuid4().hex+'.staged')
        with scratch.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if scratch.read_bytes()!=raw:raise UploadError('storage_integrity')
        try:os.link(scratch,path)
        except FileExistsError:pass
        if path.read_bytes()!=raw:raise UploadError('storage_integrity')

    def _job(self,object_id):
        if not isinstance(object_id,str) or not re.fullmatch('[a-f0-9]{32}',object_id):raise UploadError('not_found')
        return self.root/'objects'/object_id

    def _state(self,job,state,error=''):
        self._guard(True)
        # Windows 读句柄可能阻止替换。状态逐版原子发布，读者只看最后完整版本。
        versions=sorted((job/'states').glob('*.json'))
        seq=int(versions[-1].stem)+1 if versions else 1
        self._immutable(job/'states'/f'{seq:08d}.json',canonical({'state':state,'error':error,'instance':self.instance,'updated_at_utc':datetime.now(timezone.utc).isoformat()}).encode())

    def _actor(self,actor):
        if not isinstance(actor,str) or not re.fullmatch(r'local:[A-Za-z0-9_-]{1,64}',actor):raise UploadError('access_denied')

    def submit(self,raw:bytes,filename:str,actor:str)->JobRef:
        self._actor(actor);self._guard(True)
        if type(raw) is not bytes or len(raw)>MAX_BYTES:raise UploadError('input_too_large')
        if not filename or Path(filename).suffix.lower()!='.pptx' or hashlib.sha256(raw).hexdigest()!=self.scope.authorized_sha256:raise UploadError('scope_denied','仅允许本次已授权的同一PPTX与版本')
        rules=load()
        identity={'source':self.scope.authorized_sha256,'scope':asdict(self.scope),'actor':actor,'rules':digest(asdict(rules)),'rule_version':config.RULE_VERSION,'prompt':PROMPT_HASH,'schema':SCHEMA_HASH,'model':MODEL,'effort':'high'}
        operation=digest(identity);object_id=operation[:32];job=self._job(object_id)
        if (job/'owner.json').exists():
            saved=self.get(object_id,actor);return JobRef(object_id,saved.state)
        if not self._gate.acquire(blocking=False):raise UploadError('busy','本机已有一件业务评分在执行')
        handed=False
        try:
            job.mkdir(parents=True,exist_ok=False)
            self._immutable(job/'owner.json',canonical({'actor':actor,'scope':asdict(self.scope),'operation_id':operation,'identity':identity,'instance':self.instance}).encode())
            self._immutable(job/'source.pptx',raw);self._state(job,'receiving')
            self._active.add(object_id);self._start(object_id,rules);handed=True
            return JobRef(object_id,'receiving')
        except FileExistsError:
            raise UploadError('busy','对象已占用；保留现场，核验原作业')
        finally:
            if not handed:self._gate.release()

    def _start(self,object_id,rules,resume=False):
        threading.Thread(target=self._run,args=(object_id,rules,resume),name='q2-single-document',daemon=True).start()

    def _build_exports(self,report,bundle,dest):
        from .excel_report import build_exports
        return build_exports(report,bundle,dest).to_dict()

    def _check_model(self,response,req):
        if (response.requested_model!=MODEL or response.tool_calls or response.exit_code
                or response.prompt_hash!=PROMPT_HASH or response.schema_hash!=SCHEMA_HASH
                or response.request_sha256!=hashlib.sha256(req.prompt.encode()).hexdigest()
                or (response.observed_model is not None and response.observed_model!=MODEL and not response.observed_model.startswith(MODEL+'-'))):raise UploadError('model_integrity')

    def _run(self,object_id,rules,resume=False):
        job=self._job(object_id)
        try:
            self._guard(True);self._state(job,'extracting')
            bundle=read_pptx_evidence(job/'source.pptx',self.scope)
            self._immutable(job/'evidence.json',canonical(bundle.to_dict()).encode())
            baseline=VerdictEngine(ruleset=rules).evaluate(EightDInput(object_id,bundle.sections,bundle.scene,asil_level=self.scope.asil_level,meta={'source':'real-pptx','oem':self.scope.oem_label}))
            self._immutable(job/'baseline.json',canonical(baseline.to_dict()).encode())
            req=make_request(bundle,baseline,rules)
            self._state(job,'scoring')
            if resume:
                from .model_adapter import ModelResponse
                response=ModelResponse(**json.loads((job/'model-operation/response.json').read_bytes()))
            else:response=self.model.request(req,job/'model-operation')
            self._check_model(response,req)
            attempts=[{k:v for k,v in vars(response).items() if k!='payload'}];repair_reason=None
            try:advice=validate_advice(response.payload,bundle,baseline,rules)
            except AdviceError as exc:
                # 仅处理已读证据的引用结构错误；不重放传输/配额/权限/未知结果。
                if str(exc)!='quote not present in cited evidence':raise
                claimed=(job/'repair-once.json').exists()
                if claimed and (not resume or not (job/'model-repair-1/response.json').exists()):raise UploadError('repair_exhausted')
                repair_reason=str(exc)
                self._immutable(job/'repair-once.json',canonical({'reason':repair_reason,'original_response_sha256':digest(vars(response)),'max_repairs':1}).encode())
                original=response
                instruction='一次引用结构修正：原响应有quote未在其refs内出现。只调整refs/quote，使每个quote是一条真实ref中的连续原文（不得改写标点/空格/换行、不得拼接）。其他全部字段（分数、理由、整改建议、缺项、红线）必须逐字保持原值。不要重新评分。完整返回原schema JSON。'
                repair_prompt=req.prompt+'\n'+instruction+'\n原响应：'+canonical(response.payload)
                repaired_req=AdviceRequest(repair_prompt,req.schema,req.images,req.prompt_hash,req.schema_hash)
                if claimed:
                    from .model_adapter import ModelResponse
                    response=ModelResponse(**json.loads((job/'model-repair-1/response.json').read_bytes()))
                else:response=self.model.request(repaired_req,job/'model-repair-1')
                self._check_model(response,repaired_req)
                def decision(p):return {**p,'items':[{k:v for k,v in x.items() if k not in ('refs','quote')} for x in p['items']]}
                if decision(original.payload)!=decision(response.payload):raise UploadError('repair_changed_decision','引用修正改变了业务分数/理由，拒绝发布')
                advice=validate_advice(response.payload,bundle,baseline,rules)
                attempts.append({k:v for k,v in vars(response).items() if k!='payload'})
            self._immutable(job/'model-response.json',canonical(vars(response)).encode())
            self._immutable(job/'advice.json',canonical(advice.to_dict()).encode())
            self._state(job,'exporting')
            exports=self._build_exports(advice,bundle,job/'exports')
            artifacts={}
            for name in ('source.pptx','evidence.json','baseline.json','model-response.json','advice.json'):
                artifacts[name]={'path':name,'sha256':hashlib.sha256((job/name).read_bytes()).hexdigest()}
            for kind,entry in exports.items():
                path=Path(entry['path']).resolve()
                if not path.is_relative_to(job) or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise UploadError('storage_integrity')
                artifacts[kind]={'path':str(path.relative_to(job)),'sha256':entry['sha256']}
            for a in bundle.assets:
                for key in ('path','preview'):
                    if a.get(key):
                        p=Path(a[key]);artifacts[a['ref']+'-'+key]={'path':str(p.relative_to(job)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            owner=json.loads((job/'owner.json').read_bytes())
            payload={'object_id':object_id,'operation_id':owner['operation_id'],'actor':owner['actor'],'scope':asdict(self.scope),'advice':advice.to_dict(),'model':{**{k:v for k,v in vars(response).items() if k!='payload'},'attempts':attempts,'repair_reason':repair_reason},'artifacts':artifacts,'saved_at_utc':datetime.now(timezone.utc).isoformat()}
            self._immutable(job/'pending.json',canonical(payload).encode())
            receipt=self._receipt(payload,create=True)
            self._immutable(job/'result.json',canonical({'payload':payload,'receipt':receipt}).encode())
            self._verify(job,payload,receipt)
            self._state(job,'complete')
        except Exception as exc:
            self._state(job,'failed',f'{type(exc).__name__}: {exc}；现场已保留，结果未确认成功，需核验后恢复。')
        finally:
            self._active.discard(object_id);self._gate.release()

    def _event(self,payload):
        return AuditEvent(scenario='Q2',action='real_document_ai_advice',evaluator=payload['actor'],automation_level='L2',oem_context=self.scope.oem_label,
            timestamp=payload['saved_at_utc'],content_hash=digest(payload),data_sources={'source':self.scope.authorized_sha256,'rules':payload['advice']['rules_sha256'],'prompt':PROMPT_HASH,'schema':SCHEMA_HASH},
            decision={'operation_id':payload['operation_id'],'object_id':payload['object_id'],'kind':'ai_advice_unconfirmed','professional_signoff':False,'numeric_score':payload['advice']['total'],'numeric_grade':payload['advice']['numeric_grade'],'disposition':'转人工裁决'})

    def _receipt(self,payload,create=False):
        expected=self._event(payload).to_dict()
        matches=[e for e in self.audit.query_by(scenario='Q2',action='real_document_ai_advice') if e.get('decision',{}).get('operation_id')==payload['operation_id']]
        if not matches and create:
            self.audit.record(self._event(payload))
            matches=[e for e in self.audit.query_by(scenario='Q2',action='real_document_ai_advice') if e.get('decision',{}).get('operation_id')==payload['operation_id']]
        chain=self.audit.verify_chain()
        if len(matches)!=1 or not chain.ok or not chain.total or chain.error or {k:v for k,v in matches[0].items() if k!='prev_hash'}!=expected:raise UploadError('audit_integrity','audit unique receipt/chain verification failed')
        return {'event_sha256':digest(expected),'payload_sha256':digest(payload),'chain_verified':True,'professional_signoff':False}

    def _verify(self,job,payload,receipt):
        if payload['scope']!=asdict(self.scope) or payload['object_id']!=job.name or receipt!=self._receipt(payload):raise UploadError('storage_integrity')
        for artifact in payload['artifacts'].values():
            p=(job/artifact['path']).resolve()
            if not p.is_relative_to(job) or hashlib.sha256(p.read_bytes()).hexdigest()!=artifact['sha256']:raise UploadError('storage_integrity','artifact readback failed')

    def get(self,object_id:str,actor:str)->SavedDocumentReport:
        self._actor(actor);self._guard();job=self._job(object_id)
        try:
            owner=json.loads((job/'owner.json').read_bytes())
            if owner['actor']!=actor or owner['scope']!=asdict(self.scope):raise UploadError('access_denied')
            versions=sorted((job/'states').glob('*.json'))
            if not versions:raise UploadError('not_ready')
            state=json.loads(versions[-1].read_bytes())
            if state['state'] not in FINAL and object_id not in self._active:
                return SavedDocumentReport(object_id,'interrupted',error='原进程已中断；保全现场，未自动重放模型调用。')
            if state['state']!='complete':return SavedDocumentReport(object_id,state['state'],error=state.get('error',''),repair_available=state['state']=='failed' and (job/'model-operation/response.json').exists() and (('quote not present in cited evidence' in state.get('error','') and not (job/'repair-once.json').exists()) or ('AdviceError:' in state.get('error','') and (job/'model-repair-1/response.json').exists())))
            envelope=json.loads((job/'result.json').read_bytes());payload=envelope['payload'];receipt=envelope['receipt']
            self._verify(job,payload,receipt)
            return SavedDocumentReport(object_id,'complete',payload,receipt)
        except UploadError:raise
        except FileNotFoundError as exc:raise UploadError('not_found') from exc
        except Exception as exc:raise UploadError('storage_integrity') from exc

    def export(self,object_id,actor,kind)->Path:
        saved=self.get(object_id,actor)
        if saved.state!='complete' or kind not in ('xlsx','bundle'):raise UploadError('not_ready')
        return self._job(object_id)/saved.payload['artifacts'][kind]['path']

    def asset(self,object_id,actor,ref)->Path:
        saved=self.get(object_id,actor)
        key=ref+'-preview'
        if saved.state!='complete' or key not in saved.payload['artifacts']:raise UploadError('not_found')
        return self._job(object_id)/saved.payload['artifacts'][key]['path']

    def evidence(self,object_id,actor)->dict:
        saved=self.get(object_id,actor)
        if saved.state!='complete':raise UploadError('not_ready')
        return json.loads((self._job(object_id)/'evidence.json').read_bytes())

    def repair(self,object_id,actor)->JobRef:
        """操作者明确发起的同件单次引用修正；不清旧状态、不恢复旧Workflow。"""
        saved=self.get(object_id,actor);job=self._job(object_id)
        if not saved.repair_available:raise UploadError('repair_not_allowed')
        if not self._gate.acquire(blocking=False):raise UploadError('busy')
        try:
            self._state(job,'receiving','操作者明确启动引用核验；有已存修正响应时只读复用，不追加模型调用。')
            self._active.add(object_id);self._start(object_id,load(),resume=True)
        except Exception:
            self._active.discard(object_id);self._gate.release();raise
        return JobRef(object_id,'receiving')
