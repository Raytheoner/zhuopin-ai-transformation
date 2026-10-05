# O3 发布准备 A Implementation Plan

> 状态：待 Shao Peishen 审阅；未授权执行。方法拟继续 Native 父会话 inline；不派实施子代理。此件补的是主仓整合前置，原 O3 intent、设计、实施批准继续有效。不是 ff 或真实切换申请。

> For agentic workers：获准后使用 executing-plans 按任务顺序 Native 执行，沿用原生机械捕获及逐项目验证；纯数字步骤遵从项目编号约定。唯一新增子代理是本计划明确申请的一次只读 Luna review。

**Goal:** 将已验证 O3 实现及其已批准输入链按原字节移到现时主仓的独立基线上，取得新 HEAD 的真实 CLI、逐项目零新增回归和独立审阅，然后另呈 ff 审批。

**Architecture:** 在两棵新 managed worktree 中分别冻结纯主仓基线与 O3 重放版本。产品沿用既有六模块、16组静态合成案例和平台 audit，没有新增业务功能、判据、依赖、API、后台或恢复 fixture。旧实现树、纯 b7 基线树及全部失败原件保留。

**Tech Stack:** Git、PowerShell、现有隔离 Python/pytest、原 CI 发现工具、原 OpenSpec 与 intent/bootstrap lint、原生 collaboration 只读 reviewer。

**验证成本:** 原 b7 根项目纯基线实际4599.98秒、b6完整根项目5023.70秒；新基线需要两侧真实验证，不能假定很快。时间以实际日志为准。没有批准本计划就不发生这些新增运行或模型费用。

**Spec:** 已批准 b7b0e416 的 `openspec/changes/o3-logistics-evidence/{proposal.md,design.md,specs/o3-transport-evidence/spec.md}`、`4-数字员工/运营部/O3-物流异常检测与追踪/intent.md` 及 `docs/superpowers/plans/2026-10-05-o3-transport-evidence.md`。

## 现时事实与权限增量

2026-10-05 12:38:29 UTC 只读预检：main=`f58f0b797703492eab4c1d5e53e5bab64057c62d`，实现=`5acd24332245c8003ac62955cb16e5bef4b50464`；merge-base=`391e317ff441fe1f067d2845533dc422097be1f3`，不能直接 ff。18产品路径在 main 相对原批准 b7 基线均未变化。完整 intent 在两边字节相同，另6件已批准输入文档尚未进入 main。主仓72条历史未提交记录保留，不能为整合而清理或混入它们。本次只读 CI 发现实际为27项目；新树预计只增加 O3 一项，仍以当场发现结果核验。本快照仅说明发布准备原因，执行Task1必须重新冻结当场main。

原通道例外 A 只允许既有 O3 隔离树、原18产品路径及一名 Luna reviewer。新的 A 申请增加：两棵新的隔离验证树；最多24明确路径的原字节重放；新 HEAD 一次新的独立、无父历史、只读 `gpt-6-luna/xhigh` reviewer。没有实施子代理，也没有恢复机制模型调用额度。未批准前只允许读侧准备。

## Global Constraints

1. 源固定 `5acd24332245c8003ac62955cb16e5bef4b50464`；原业务设计不改，source18件逐字节复用，三件静态夹具不重算或重写。
2. 原 fixture SHA256 `10fc191d5f34bf94d92e2790a5abc5fa2af6d9b789dbb8a0727901c54fdf0ba6`；expected `2a68c3f8368a3da74ac5d2c818ddaec45044fa58dfb33ad6d473b9754ef42ad6`；mapping `b374429f67f1ac8229973543999e4c654d0f7aa70a0ab0ac5f96b55a21d1bc57`。保留 LF 原字节，不改共享 Git 配置。
3. O3-G-01至G-06保持专业待判；operator仍是未认证的调用者声明；没有责任判断、严重度、处置或 Owner/backup 代签。
4. 原#658批准及恢复失败批原位保留；财务/销售/研发暂停状态不因回归测试改变。ff、activation、.51、外发及L2仍逐项另审。
5. 新 worktree 只 checkout/验证，不启动或克隆 Windows 业务服务，不重装共享 editable 平台指针；运行 Python 固定 `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`。
6. 总测试并发不超过2；根项目超时7200秒、其他项目1800秒。超时/进程非零保留真实退出和原始输出，不删失败、不改断言、不新增 skip。
7. 新基线从执行时现时 main 冻结；记录实际 SHA 及 dirty 清单，旧主仓未提交资料不带入。若24路径或 O3 所用平台源码相对批准输入出现内容冲突，停并呈具体差异，不能顺便改模块或扩大白名单。
8. 新证据明确标新 HEAD，不把 `5acd` 的测试或旧 Luna 结论冒作新 HEAD 结论。证据本地保全与正式留存接收分别报告；没有接收/backup 确认不声称3年留存闭合。
9. 最终准备结果先在 ignore 的 reports 保全；官方登记批次标“待ff审”，不先作为“待sweep”推进 master；不修改调度器、不跨 session 持队列锁。若其他工作推进 main，ff只读预检必须报告新分叉，不自动 rebase/合入。

## 明确路径（最多24件）

S=`4-数字员工/运营部/O3-物流异常检测与追踪`。产品18件与原实施白名单完全相同：

1. S/pyproject.toml
2. S/o3_transport_evidence/__init__.py
3. S/o3_transport_evidence/contracts.py
4. S/tests/conftest.py
5. S/tests/test_contracts.py
6. S/tests/fixtures/o3-evidence-r1.json
7. S/tests/fixtures/o3-expected-r1.json
8. S/tests/fixtures/mapping.md
9. S/o3_transport_evidence/evidence.py
10. S/tests/test_evidence_versions.py
11. S/tests/test_evidence_deltas.py
12. S/o3_transport_evidence/report.py
13. S/tests/test_report.py
14. S/o3_transport_evidence/cli.py
15. S/o3_transport_evidence/__main__.py
16. S/tests/test_cli.py
17. S/README.md
18. S/CLAUDE.md

补齐已批准输入6件；其字节及SHA均取原 b7，不更新旧审批 frontmatter 或任务勾选：

| 路径 | 原批准 SHA256 |
|---|---|
| openspec/changes/o3-logistics-evidence/proposal.md | ea8d9276f63da8381bbca4d1693c6bbbc9688619a894b0e8edbc31002252a8dc |
| openspec/changes/o3-logistics-evidence/design.md | 7aebe3e42cdaab35f4119a4315d3af8dfb36641e556914ecdf2e12178fe7a9ff |
| openspec/changes/o3-logistics-evidence/specs/o3-transport-evidence/spec.md | ab1496b352e18b36d266132cb595a09ad63c5e0200c65b09e0fc59ea8323e924 |
| openspec/changes/o3-logistics-evidence/tasks.md | 4e985cba15b8899a946dd6f4b0b70dd9493e28af5a1679a614618e1b5fbf3d9d |
| openspec/changes/o3-logistics-evidence/approval.md | fd88f2ee947b913b3d27691c700513aa1a90993b9bd075403fdae4ea7b2b9906 |
| docs/superpowers/plans/2026-10-05-o3-transport-evidence.md | cb25a12c7b7ec8b158616319ef277ae1efd47f4ccd453c1f88f4025b407b66a0 |

intent既有且相同（a13f5f9103b6f4541bf9659d55949ffdfac64b1aacd8ef85048b2ee6b5273b60），只核验，不写第25件。新增本计划与交付登记是主仓看护文档，不混入产品重放提交。

## Review Focus

1. 原字节24件和新基线 diff严格一致；没有顺带旧分支的其它提交、历史主仓 WIP 或第25产品路径。
2. 三件静态夹具与更正/未知/候选规则完全相同；不能用更新 expected 消除差异。
3. CLI起始/持久化前的 clean HEAD guard、实际新 HEAD、原子输出与真实 audit 链仍可验证；Git状态失败不留 passed。
4. 新纯基线和实现使用相同逐项目 cwd/argv/环境，失败节点逐条对照；旧 b7 测试不能充当新纯主仓基线。
5. 一次新 Luna reviewer 可读实际新树和完整 hash 包；final必须等完整验证，不能把旧审阅或“待ff审”当 Guardian成功、ff许可或留存接收。

## Task 1：绑定与两棵隔离树

**Files:** 只在主仓看护件登记实际新批准；审批原文/plan SHA保存在独立本机 approvals；树内 `reports/o3-publication-preparation-1005` 记录 binding/progress，均为ignore。

**Interfaces:** Produces `main_snapshot_sha`、`pure_baseline_tree`、`replay_tree`；均取真实工具回传，不猜路径。

1. 取得本计划明确批准，保存原文并核实 scope/method/reviewer额度。原A不能默认为新A。
2. 当场读取现时main HEAD与status，不改主仓。只读检查24路径、原intent和平台依赖；与输入不一致则停止。
3. native managed `create_worktree` 顺序创建 `o3-publication-baseline-1005`、`o3-publication-1005`，两者ref均是同一现时 `main_snapshot_sha`；按真实 operationId 等待并附着。
4. Probe新树，确认两个HEAD与snapshot一致、Git状态clean、同一隔离Python和checkout平台；源码基线树此后不改。

**Expected:** 新批准、两棵纯相同基线树、真实绑定记录齐全；未启动服务、未修改共享配置、原树未动。

## Task 2：受控原字节重放与本地提交

**Files:** 上列24件；产品所有模块职责/接口仍按原已批计划，不实现新功能。

**Interfaces:** Consumes三棵实际树与snapshot；Produces每件源/目标SHA、实际changed_paths及clean新HEAD。

使用原 `implementation.json`（SHA bf7c94f1790b2d1843654e38c3487178a64fe0591bcef929caf2450f4c2d4430）的18路径，加上本计划6明确输入路径；读源Git blob，逐件校验、复制和记录。下面是待执行helper的完整复制逻辑；只接受本计划新建树和实际snapshot参数：

```python
from pathlib import Path
import argparse, hashlib, json, re, subprocess
p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--base',required=True)
a=p.parse_args();target=Path(a.tree).resolve(strict=True)
root=Path(r'C:\Users\Paul Shao\.codex\worktrees').resolve(strict=True)
source=Path(r'C:\Users\Paul Shao\.codex\worktrees\o3-evidence-design-1005\zhuopin-ai')
head='5acd24332245c8003ac62955cb16e5bef4b50464'
if not target.is_relative_to(root) or target.parent.name!='o3-publication-1005' or target.name!='zhuopin-ai':
    raise SystemExit('not the newly authorized replay tree')
if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',a.base):raise SystemExit('invalid snapshot')
def git(tree,*args):
    return subprocess.run(['git','-c','core.fsmonitor=false','-C',str(tree),*args],capture_output=True,check=True).stdout
if git(target,'rev-parse','HEAD').decode().strip()!=a.base or git(target,'status','--porcelain','--untracked-files=all'):
    raise SystemExit('target must be the clean frozen snapshot')
auth=Path(r'C:\Dev\Codex\runtimes\zhuopin-ai\approvals\o3-logistics-evidence-1005\implementation.json').read_bytes()
if hashlib.sha256(auth).hexdigest()!='bf7c94f1790b2d1843654e38c3487178a64fe0591bcef929caf2450f4c2d4430':
    raise SystemExit('original authority changed')
paths=json.loads(auth.decode('utf-8-sig'))['allowed_paths']
extra=['openspec/changes/o3-logistics-evidence/'+s for s in
       ('proposal.md','design.md','specs/o3-transport-evidence/spec.md','tasks.md','approval.md')]
extra+=['docs/superpowers/plans/2026-10-05-o3-transport-evidence.md']
if len(paths)!=18 or len(set(paths+extra))!=24:raise SystemExit('path fence mismatch')
records=[]
for rel in paths+extra:
    data=git(source,'show',head+':'+rel)
    dest=target.joinpath(*rel.split('/'));resolved=dest.resolve()
    if not resolved.is_relative_to(target) or dest.is_symlink():raise SystemExit('unsafe destination')
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    digest=hashlib.sha256(data).hexdigest()
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise SystemExit('copy mismatch')
    records.append({'path':rel,'sha256':digest,'bytes':len(data)})
out=target/'reports/o3-publication-preparation-1005/copy';out.mkdir(parents=True,exist_ok=False)
(out/'copy-receipt.json').write_text(json.dumps({'source_head':head,'base':a.base,'files':records},
    ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_head':head,'base':a.base,'copied_paths':len(records)},ensure_ascii=False))
```

1. 执行前另核6文档SHA与上表、intentSHA、平台runtime源码一致性；helper只复制，不替代审批/前置检查。
2. Native执行上段后逐件核源与目标24件相等、三fixture哈希相等；实际diff是同一24集合的子集，所有遗漏仅能是基线已有同字节文件。任何表外diff停止。
3. 用copy receipt中的路径数组显式`git add --`，读取cached diff/`git diff --cached --check`，只在新树本地提交。命令路径一律引号，禁止add整个仓库。
4. 记录新HEAD与clean状态；不能修改原 `5acd` 或原 b6。

**Expected:** 最多24件原字节、清洁新HEAD、无功能变化；CLI运行前必须已有clean提交。

## Task 3：新基线与同HEAD真实验证

**Files:** 两棵树各自专属ignore reports，仅验证原件；所有测试源码只读。

**Interfaces:** Consumes新HEAD/snapshot与24复制记录；Produces原始argv/cwd/env/start/end/exit/stdout/stderr/hash、CLI/JUnit、失败节点对照及manifest。

1. 两树分别执行 `工具-CI矩阵发现.py`；应只新增O3测试项目。使用各项目真实cwd，逐项目统一命令为：

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -m pytest -q --tb=short
```

2. 复用已实际跑通的Native捕获方式：Popen显式argv/cwd；stdout/stderr落独占文件；原被执行进程退出码；根7200秒/其他1800秒；总并发≤2。纯主仓27项目与实现28项目各保留原始summary，不继承旧b7失败清单。超时或进程错误必须保留并阻断通过。
3. 新O3项目cwd分别执行真实CLI与JUnit，下列路径参数由binding/copy receipt提供实际绝对路径；输入仍是树中原byte fixture，run_id为新UUID，输出目录首次创建：

```powershell
# $o3ReplayTree与$o3PlanReports取Task1 binding的实际新树/专属reports根。
$o3ScenePath = Join-Path "$o3ReplayTree" '4-数字员工/运营部/O3-物流异常检测与追踪'
$o3InputPath = Join-Path "$o3ScenePath" 'tests/fixtures/o3-evidence-r1.json'
$o3ExpectedPath = Join-Path "$o3ScenePath" 'tests/fixtures/o3-expected-r1.json'
$o3RunOutput = Join-Path "$o3PlanReports" 'run-output'
$o3JUnitPath = Join-Path "$o3PlanReports" 'o3-junit.xml'
$o3RunId = [guid]::NewGuid().ToString('N')
Push-Location -LiteralPath "$o3ScenePath"
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -m o3_transport_evidence --input "$o3InputPath" --expected "$o3ExpectedPath" --operator Native-1005-O3 --run-id "$o3RunId" --output-root "$o3RunOutput"
$o3CliExit = $LASTEXITCODE
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -m pytest -q --tb=short --junit-xml "$o3JUnitPath"
$o3JUnitExit = $LASTEXITCODE
Pop-Location
```

前两变量是Task1/2的实际输出绑定，不允许猜值或遗漏参数；命令的stdout/stderr仍按本任务第2步原生捕获，不能丢弃实际非零退出。

4. 两个repo根各执行 `openspec validate o3-logistics-evidence --strict`（纯基线没有该包时记录“不存在”，不伪造pass）；`工具-场景包intent闸lint.py --enforce --verbose`；`工具-引导样板lint.py --enforce --verbose`；`git -c core.fsmonitor=false diff --check`。既有工具红必须两侧同命令实测比较。
5. 按project及完整FAILED/ERROR节点逐条比较；新O3项目必须exit0，其余任何新节点/新非零/超时均阻断。两侧失败退出类型与完整结束summary也须实核，exit1变exit2/3/进程异常不能只凭节点集合称零新增。新平台源码若与原批准基线不同，按Task1停点，不做表外修复。
6. 全部完成后确认两HEAD未变化及clean，逐文件重算字节数/SHA，保留真实audit chain及CLI manifest。只报告“零新增回归”，不把基线红宣称全绿。

**Expected:** 新CLI complete/matched/passed；O3现有149测试通过、仅原link权限skip；完整矩阵与纯主仓逐节点零新增；工具闸原始结果齐全。无法满足时保留失败，本计划没有新功能修复授权。

## Task 4：新独立审阅与可审的ff停点

**Files:** plan-owned reviewer brief、原始final文本、dispatch记录、原始/最终hash manifest及本地copy receipt；主仓只写看护/官方登记。

**Interfaces:** Consumes完整新HEAD/hash包；Produces新Luna实际结论、所有裁决/延期Minor、新ff只读预检和下一审批件。

1. 当前父会话只在新批准额度下，通过native collaboration一次显式`gpt-6-luna`、`xhigh`、`fork_turns:none`派只读reviewer；使用已有code-reviewer模板、原intent/spec/plan及本计划。原reviewer与原稿继续保留，不充当新同HEADreview。
2. 等完整CI与hash后才取得final；记录它实际做/没做的测试和hash核验。Critical/Important未闭合不能呈可ff，不能默默二次派审阅者或扩代码范围；Minor只登记延期。新replay没有预授权产品修复。
3. 本地hash保全原件及新manifest，记录正式留存owner/backup是否收到；缺回执就保持留存未闭合。
4. 官方锁acquire→写/登记#508与批次“待ff审”→K2核验→release；六项报告压缩为范围、版本、验证、审阅、证据、下一闸。不跨验证过程持锁，不提前标Guardian delivery_accepted或场景done。
5. 当场只读核main是否仍为新HEAD祖先、24路径冲突/主仓WIP及origin状态。不能ff则呈具体新差异，禁止自动改基线；可以ff也只给确切源/目标SHA和diff的审批件，等待针对ff的明确授权。真实切换/.51/外发/L2仍另审。

**Expected:** 一份可核验的新基线发布准备包和具体ff审批件；执行本计划本身没有ff、push、生产或对外动作。若不批准本计划，保持已验证 `5acd` 及其全部批准/证据即可，不回滚、不退役、不重派。

## 自核

本计划只重放已批准功能；没有新增接口/业务判据、没有模型fallback、没有产品第25路径。Task1树/基线→Task2原字节/cleanHEAD→Task3同版本原始验证→Task4实际独立审阅/ff前置顺序明确。真实source/目标路径和UUID只能来自前置任务输出；没有假定未来测试结果，也没有借原审批扩大新树、新输入链与新审阅额度。
