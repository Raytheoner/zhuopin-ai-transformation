# 五候选封存实施计划 · 2026-10-10

> 供审；未实施。记录：2026-10-10T20:04:56+08:00。唯一执行会话01a1229b-1106-7172-b5ed-b8b076448790。
> 这是一次精确范围的候选封存操作，须本人明确批准 `Sweep 不支持现有 Native detached 候选时的受控 Git 提交例外` 及候选／共同 Git 元数据写入。原实现计划只批准代码/定向测试/隔离副作用，未批准裸 commit；本件不把旧批准扩大为提交许可。

## 1. 目标与现时证据

五个技术首项已经各自按批准路径实现及核验；把每棵候选精确批准内容保存为一个带命名分支的本地 commit，形成可供后续对齐/整合审阅的稳定版本。SC2 144＋50passed、SC4 39passed/1Windows权限skip、SC10 56passed、SC11 30passed、O4 28passed。SC4原run缺独立command/exit文本的取证限制仍见其核验件，不伪造补档。

封存合同：只保存下表五棵现有 Native 候选、共41路径；每棵一新分支/一commit，父提交固定 `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。工作树内容仍须匹配其最终技术核验SHA，暂存和commit blob须匹配Git正常clean转换后的清单OID。

| 泳道 | 精确候选 | 路径数 | 新本地分支 |
|---|---|---:|---|
| SC2 | `C:/Users/Paul Shao/.codex/worktrees/sc2-biztype316-1010/zhuopin-ai` | 14 | `codex/candidate-sc2-1010` |
| SC4 | `C:/Users/Paul Shao/.codex/worktrees/sc4-source-evidence-1010/zhuopin-ai` | 8 | `codex/candidate-sc4-1010` |
| SC10 | `C:/Users/Paul Shao/.codex/worktrees/sc10-versioned-facts-1010/zhuopin-ai` | 4 | `codex/candidate-sc10-1010` |
| SC11 | `C:/Users/Paul Shao/.codex/worktrees/sc11-inventory-transfer-1010/zhuopin-ai` | 7 | `codex/candidate-sc11-1010` |
| O4 | `C:/Users/Paul Shao/.codex/worktrees/o4-stage0-evidence-1010/zhuopin-ai` | 8 | `codex/candidate-o4-1010` |

当前已存在的冻结源清单 `reports/candidate-integration-1010/seal-plan-preparation/manifest.json`，正式登记将逐字节复制到 `docs/superpowers/plans/five-candidates-seal-1010/manifest.json`；执行前两者SHA必须一致。清单 SHA `A4996E4758B4A36326D95D87524EAC63F02135AF57A126135CF2CBA5C51D12DB`。源采集并非跨树原子快照，执行前逐棵重核，不用旧snapshot代替前检。根已核41文件原字节SHA全部匹配最终独立技术证据；Git正常clean blob41/41与清单OID匹配，真实commit hooks不存在、未启用commit.gpgSign、无自定义clean filter，index为空、上述refs不存在。根证据 `reports/candidate-integration-1010/root-manifest-review-93b926fdb8d04df09d38e1efe44edcd0/root-review.json` 与 `reports/candidate-integration-1010/root-git-manifest-review-d2cd9dd75ac54c8889cbb4e7bc660ec5/root-review.json`。

主仓只读现时HEAD曾为 `75c1f76b791b1054f8a2e568fb7ba11162a8f693`，比共同基线+21提交，41路径无已提交/dirty交集。Sweep可能继续提交已登记文档，故记录当次main HEAD而不倒退主仓。主仓前进和无路径交集均不构成可直接ff的证明。

## 2. 已核支持路径与必要例外

现Sweep `_assert_not_a_linked_worktree`拒linked `.git`文件，`_check_preconditions`要求主仓master，CLI没有提交指定候选入口；不能在候选跑Sweep，也不能用fixture参数改变生产身份。旧泳道合入wrapper会fetch/rebase/ff/push及默认清理，超出本次。Workflow的implement入口要求干净同HEAD起点，不能封存这些dirty detached历史候选。

因此本件只申请以上五棵树的本地 `switch -c → 指定路径add → commit` 受控兜底例外，不修改这些工具或纪律，也不绕过hooks/权限。执行仍经正常Codex审批和Git配置。

## 3. 每棵执行前硬检查

1. 官方可查队列及原批准计划/最终核验件没有新撤销。官方查询器只支持§一/二/四，无法读取§三冻结标；不把§一状态当作无冻结证据。SC10/SC11本次只保存已核验字节，需本人明确批准 `completed_candidate_preservation_only` 精确例外；其余新场景建造仍服从冻结闸。根EE5作业在执行时必须未启动或已完成，若正在冻结闭环则串行等解冻后封存。当前没有新产品测试或真实调用。
2. 候选resolved root、Git dir/common dir与冻结清单一致；HEAD等于固定基线且detached，index为空；新ref不存在。路径/status集合恰等本棵白名单，无历史额外dirty。
3. 每个原字节SHA再次匹配最终核验，所有41清单路径全异；禁止候选中的链接文件/目录跨出该resolved root。每个 tracked mode保留清单基线100644，新文件100644；不提交symlink或submodule。
4. 重核真实Git commit hooks、自定义filter、signing和commit身份。仍无真实hook/filter且签名未启用、身份正常则继续；任何漂移/未知/错误停止该棵前检，不修改配置或禁用hook。记录完整只读命令和真实退出码。
5. main只读HEAD/branch及批准路径dirty交集现取；交集非空停止对应候选，保留现场。其余不受影响的泳道继续。

## 4. 精确写入、验证和副作用

按SC2→SC4→SC10→SC11→O4串行；每条Git命令独立，立即检查执行进程实际退出码。下文完整写入命令已固定，路径来自同一冻结清单；无 `add -A`、无全仓暂存。

- 创建该棵新 `codex/candidate-*-1010` 分支于现固定父提交：只改该棵HEAD/新ref，不做checkout到其他内容。
- 暂存该棵明列路径；核staged change path集合恰等批准集合、mode合法、每一staged OID恰等冻结清单 `candidate_git_blob_oid`、`diff --cached --check`为空；工作树原字节SHA再次匹配。Git换行转换是正常clean合同，不另改源字节。
- 仅在上述检查成立后normal commit；记录实际命令、stdout/stderr/退出码。commit父必须固定基线，`diff-tree parent..commit`路径集合/每文件blob与清单全等，commit后status/index为空、原字节SHA未漂移。
- 每一棵只成功commit一次；失败留新ref/index/原源码及证据，不reset、不删除/清理、不回退或自动改计划。成功的commit保留供审，依赖整合阶段等待后续方案。

可写副作用仅：五棵候选的HEAD/各自index及普通Git产生的管理锁/日志；主仓共同 `.git` 的五个新refs、对象库对应41路径内容blob及对应tree/五commit及普通Git reflog/管理锁；主仓ignored `reports/candidate-integration-1010/<新UUID>/` 原始命令/log/证据；正式治理登记由根会话另按既有锁流程进行，不在seal脚本执行写入范围内。共同Git路径以冻结清单为准，其中各worktree gitdir为 `.git/worktrees/zhuopin-ai`、`zhuopin-ai23`、`zhuopin-ai22`、`zhuopin-ai24`、`zhuopin-ai25`；不修改其它worktree/ref/index。

## 5. 后续闸和交付

本次没有新测试授权申请，也没有对齐/rebase/cherry-pick/合入/ff/push/PR/生产/ERP/邮件/真实取数/专业签认/归档或清理许可。正常Git封存前后不改变产品字节，复用明确最终核验SHA与上述已有结果；不声称这是新基线上的回归。五提交各自仍在旧基线旁支，主仓保持当前状态。

结果双件须逐棵记录真实ref/parent/commit/tree/OID、原SHA、status、退出码和受限范围，失败项明确写未封存；登记后继续准备对齐/整合具体计划及新基线定向验证供审，不把五个独立提交称成已合入或全景完工。

## 6. 完整41路径与最终身份

| 泳道 | 白名单路径 | 最终原字节SHA256 | Git正常clean blob OID |
|---|---|---|---|
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py` | `23B613859D7971EB9002A65B058F44C35D52A38AEB0DF1A2D268419047FCF25B` | `456abf077d3c1e61ebf5915b7740b08807ef6a18` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py` | `2D880A13AD060BE4C14BE8CFA47C4BE7E9AD3211E0A087C5B414314D9FE8AA7C` | `452adee2964e708c61b78cf1cac2c8cc89f5aa24` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py` | `4683D4DC4036F1F5B07484692F47D99C403BD1F4B9F441EE9DC88E7B57FCE541` | `188d0c2dc253652aa6be3a6e57650a0600b2d8a4` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py` | `2ACE616886C18BDD59336ED0A730E77D234A98ADADBDFD4A5E6DFCF92AF5E12E` | `cdf66e1b39ac82dab295588ee2ccd50ea9f7a367` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py` | `076DACB8B40F1116281FCC9E115301070E3DBBB43D7A167FB8CADBC6714140A4` | `349e0a373b0ec4fdd5704e8ddbb69d7683d7ffff` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py` | `C8EA00C5552A0444B90C143478A32058437D4FF95833CE1014596B7EC46D4BFE` | `50afe063c2642698b5dc274a29fab017b6d29743` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py` | `4B985F315B920AA37E7337B0200192A4C26D3D60B8662F39B11ADE14E16A86A4` | `1050c49db2382c1b7b2b62ddc583afe0e3880d0f` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_detail.py` | `5713E3248A7B04BB80C6A0F03DDE5ACB03B7610CBBB8D390FAC9AE4FD41B6B59` | `c48f9d15eb7bf52ef9963056bee4289ee4f086e6` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_metrics.py` | `575C45EBF5B3E9543BF0C1ED6A8976F563ABF395FDA25157AF682723F7681739` | `696330f3390add3b04d6ac82086d5eccaad68a0b` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_report.py` | `98CD41D73B7A150A329F2EB749E00544FBF5150AD3289D15728CE41AB7A6BB81` | `3576e97f2c8917adb40292662769674a14cb8e35` |
| SC2 | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_sources.py` | `BD64B1BEB0011A6F07AFA566B4A2BA2A2A0C2381F0CC966D10F10E2D7FB1BD3C` | `6d3114cc753666d55f04bdd3aab8408ee1fcb073` |
| SC2 | `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py` | `341DEAC3A17DA61B2B6C427CC70159733599FE586F52AF8E9E47B877228193C6` | `470efb13f5d61b34e42dfeb952b3f9e844e8b3bd` |
| SC2 | `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py` | `60130A8946724EA79A46E7010D03C10D8C6C837E7E8A45A4233B7FB4C2E7BED0` | `afd5c8cd362106231173ae1185a9a52a2148609f` |
| SC2 | `5-平台底座/zhuopin_platform/tests/test_erp_biztype316.py` | `6CEF2405445A9AC791547E5EA65C937E4632060699BEC86B069E6E3B0AD15A0E` | `4951bbba478f48ef174f8320a4b52d374c53f83a` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/models.py` | `5E19EE9A8C6860DE43761234318F9F8E6CFA5A14761E93E399FD33332E5962B6` | `596a22fd3b590e0a03197e39211026da587514ad` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/text_source.py` | `FF2F2818AF54FEC06986C0EEEF40BAA7FA54DC0F630525A1F7750272E87670E9` | `7483ecac8c36a72ba75b14556a27a088fb2beada` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/clause_extract.py` | `110BB03BEAC8F7043CD11DE36307F74F92A98A88E0A1DA3C13FFC0E39D5C7EB2` | `c812b1fa7e77832ad6973cdd2abf45215c97d0bd` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/agent.py` | `1AF0D6DDB2C0FEB6CFB289B38BC4479705967F2E4D4EE934D053D8588A955A75` | `13cb016fab3f037abd5b5d08f5f301c17aa5fe4a` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/sc4_evidence_fixtures.py` | `71D294E4772C7F9A185F9A54617B9012222446998AA53131547A765DD032B7D4` | `f74f472d60a51f6b84d59140fa10107258b1719a` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_text_source.py` | `4DB727DAB2DDAD6C2D6B4F88D7253E1EFAF43B5782C75977EEDF7B6EEB51552C` | `3f92445976dac1cdd2e875016f343e0e8e9c9506` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_clause_extract.py` | `9E7ED1627B52152733797B733D8B72CE6B8BE6F804071D2E11C06869EBD10707` | `6165a09ada5762a6ca9e336e4a3faf6b91d7bd40` |
| SC4 | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_agent_audit.py` | `8A1A4C7BE1F0AE3FE0EF41FD4845C2921D0EB27ECA30711B4260753BFBF5C7ED` | `21b9beb9519e0399c37940fa36522b7523942228` |
| SC10 | `4-数字员工/采购部/SC10-BOM评审与物料库管控/sc10_bom_review/evidence.py` | `64575FC610A4A8765A4146A3D89A840D52762A3749C254F9944D75ACAAC6E0A8` | `4594948f417119b8ab99477fc7943d65a806ada4` |
| SC10 | `4-数字员工/采购部/SC10-BOM评审与物料库管控/sc10_bom_review/agent.py` | `0195119AC00C491FF58922C1D4925927E4BB81BC7D676AC7F1CCD69F25EF03F9` | `f2062b879f091dc572e68fe950d72e51fd0eb14d` |
| SC10 | `4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_evidence.py` | `6EA0848B33E82D52023450222D75FCF53C83C0E7A03B28AC5420E773C6E297DF` | `36523f7afe2c45b8f167df8041ad682403a6fcdd` |
| SC10 | `4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_agent_audit.py` | `6472FC1776D4A4D3069CB92A9B3F52B887FB05ACF1F04B1EC3488F82A2937199` | `11185d2f62fc8e023a77ff05f5d4acbca8c9ba6a` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/models.py` | `D325EB931EBAA0D3C0C3CBCB1278F90B04CD915065AECC1377B5422356334CD4` | `ed56093caefc427ddf267c6f0db94faafe3c107b` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/routing.py` | `FF7C4398F629B4ECB959E8BEFB730E077EF7456CE6371C47FFD01D321C1C14BE` | `3463b196b6266f485854734f408e90b5529e5b12` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/agent.py` | `B0CCC9108FFCCED2349CA0BA742F14C44462CF6D8A0C11E5BE1B8BC52A612166` | `8710df4dc85c322da3371bc68000f6f61450e40b` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/gate.py` | `9C998B67B950F99D3FB6EC2C5046E79F3911BFDAF09ACC09AE42CB9F727A8790` | `c6d369974ab9ecfe8a65b9b439ec905f0a8ae0be` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/tests/test_shared_reservation.py` | `D2EF5EBA6CE12ED8DD7090CF500EB0C9390BEE950A8B8B9CBD83FDB30A0E61E8` | `30b1782310fc545700587971f79d176653d5b74e` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/tests/test_versioned_audit_gate.py` | `349861348617F41FC7D0BC76D1F0E44FD1AD1A213938F0E9F0941E5F21326604` | `4e5010656ced952ced5a08be02bdb1bb7043100e` |
| SC11 | `4-数字员工/采购部/SC11-库存智能调拨/tests/test_pmc_gate.py` | `00FD4A63483D3A7C7584E0700590AD26395D462E0BDD2FB5FFC57E0807897306` | `efbd77094b5f775da4ad5aed29f1321d6de40c77` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/__init__.py` | `EE74AF0B2032F6236DC04675E2534E7C3CBA73573E9167BDA6AB620821C90970` | `b87925770cc94d39e3b40add6fc28e7054d4c0a1` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/models.py` | `288805F6E63BCC4908403768B277C4EB108D3EA56006D6EBE8B39075B336D9A1` | `6d370106d90a54a5598700649bbacc364af2323b` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/canonical.py` | `B97F3AD9BE5315EA6B5EF997B389456BB5777693F6FE5805DA10C972D31861E4` | `05eb5bdad6eb3010eae2aa43e06e4a5bb4aa846d` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/checks.py` | `0B51B5499BDDAE585D87E0F2CEF041BB79FB7689BF52EDB72F5C8B03904FA99E` | `567fa2f0aa1a6ef570695bdad04b100776623667` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/agent.py` | `AD554FB37CF0507D35685C0C15CD295B055F64CB4528C1CF38F14D66A06B0FEF` | `024a2420518868a79c72874f49cf5812ebafc8df` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/tests/conftest.py` | `773A6681A37125A6C887717263A5BE40E2D4B9133C4CC8351962F772362E82FC` | `a3537599d79d098b8c0e2246dc42c10700754ceb` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/tests/o4_cases.py` | `DA215205659AB1AAF512B1C8AA7FDAF33E5993703F63DDE0B9852119A492B754` | `a561117de5dc7d9436515d1844d34cc4c8c1ceeb` |
| O4 | `4-数字员工/运营部/O4-设备预测性维护/tests/test_stage0.py` | `8DFFFD40455C6D3BAD05B30CD032D9A0F3284519FCA86C25C895A3E40D3A1999` | `4982257c4f139d514228130eaa8c8f8ba9d11427` |

## 7. 冻结可执行入口与真实停机行为

供审脚本 `docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py` SHA `6CAB74E0FA2E336C531E25FB62432D15C76A5998805D6818830EB6224D1A1277`；当前草稿源为同名reports副本，正式登记逐字节复制。只读默认/preflight与授权seal分支分开；reports副本永不能seal。脚本没有plan SHA常量，避免plan包含scriptSHA形成自引用；批准消费JSON按当次实际plan/script/manifest三SHA绑定。

前检不只写注释：实际核root/gitdir/commonDir、HEAD detached固定base、全index无cached变化、exact status分布、逐路径reparse/regular/mode/rawSHA、真实hooks/filter/signing与 `git var GIT_AUTHOR_IDENT`/`GIT_COMMITTER_IDENT`、main master/refHEAD和逐路径基线/dirty/normal-clean OID、新ref不存在。Git read进程使用GIT_OPTIONAL_LOCKS=0，先核filter再计算clean OID，不改配置。只读Git及官方查询的argv/stdout/stderr/真实returncode逐次写本次主仓新UUID；摘要不展开身份邮箱，原始身份输出只在本机ignored证据。

所有非空 GIT_* 控制环境变量（仅允许 OPTIONAL_LOCKS/TERMINAL_PROMPT/PAGER）在首个子进程前拒绝，仅记录变量名；每个 Git 命令经统一入口显式 `git --no-pager`，使工具环境的 GIT_PAGER 不会启动分页器。真实 core.fsmonitor 在 status/diff/hash 前检查，启用或自定义值则停止。所有 diff 禁止 ext-diff。commit 仅命令级 `-c maintenance.auto=false -c gc.auto=0` 避免另起自动维护；不改持久配置，不禁用正常 hooks/签名。首次只读前检因 GIT_PAGER 停在首个Git前；第二次因全局 filter.lfs 键停在status/hash前。两次Python退出2（未显式透传的PowerShell工具退出1），均未写候选/Git；原报告保留。

全局 filter.* 键存在不等于本次路径生效。脚本实际先枚举每棵候选及主仓全部tracked路径，与批准新路径合并，以64条分批 `check-attr -z filter` 严格核NUL三元组；仅 effective filter 为 unspecified/unset 才能到全仓status/diff/hash，未知/缺行/重复/错误都停止。原逐白名单属性/clean OID复核保留，不禁或删除LFS配置。独立Luna静态复审绑定6CAB脚本，已闭合以上入口与有效属性问题。

最终只读前检已执行，Python与显式透传PowerShell均exit0，五棵全部通过；报告 `reports/candidate-integration-1010/seal-evidence/4b8d06cc-2b17-4fde-a896-90b8b7788866/summary.json`，run-binding实际绑定6CAB脚本/A499manifest及当时草稿plan SHA。当前plan随后只补供审文字与以上实际证据；正式plan按最终字节另取SHA，并不称此后又跑一遍产品测试。SC10/SC11 freeze_check仍明确unverifiable_by_official_query，不称无冻结；seal需要§3/§8具体人批例外及EE5真实未启动/已闭状态。

seal每棵重跑前检与授权绑定后，normal `switch -c`、精确add；commit前全局cached delta path-set必须精确等本棵白名单，再核指定path stage mode=100644/OID、rawSHA、cached check；normal commit message为 `Seal <lane> candidate from frozen 28337c0ebb52 inventory`。commit后核恰一个父base、全局diff-tree path-set精确、tree每blob等清单、status/index干净且原SHA未漂。任何非预期exit/未知/失配即exit2，summary标失败并保存原始输出；不撤销已成功命令，不清index/ref/文件。

只读前检（可在供审阶段执行，无候选/Git写；只生成主仓报告）：

```powershell
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/reports/candidate-integration-1010/seal-plan-preparation/seal_candidates.py' --preflight
```

批准后唯一执行入口（每条独立立即核实际exit；根串行执行，失败保留且独立泳道照常）：

```powershell
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py' --seal --lane 'SC2' --authorization 'C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json'
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py' --seal --lane 'SC4' --authorization 'C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json'
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py' --seal --lane 'SC10' --authorization 'C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json'
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py' --seal --lane 'SC11' --authorization 'C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json'
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B 'C:/Dev/zhuopin-ai/docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py' --seal --lane 'O4' --authorization 'C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json'
```

## 8. 具体人审绑定与治理落点

正式消费唯一路径 `0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json`，schema=candidate-seal-approval/v1、decision=approve、approved_by=Shao Peishen、local_commit_exception=native_detached_candidate_commit_preservation；原题/原答证据指针及plan/script/manifest/base必须全部匹配，各lane精确ref/paths白名单匹配。JSON本身不创造授权，只有真实人类明确批准后根才登记；未答不得生成approve记录。

SC10/SC11还须逐lane freeze_scope_exception=completed_candidate_preservation_only、根ee5_root_operation_active=false；ee5_status_binding为status(not_started或completed)、固定绝对record_path `C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/EE5根作业状态-2026-10-10.json`、record_sha256。该JSON必须由根真实作业状态登记，字节SHA与解析status/inactive均匹配；它不证明§三全局无冻结，也不解除后续场景建造。EE5进入作业时根标active并停止SC10/11封存派令，完成解冻才改completed；旧hash授权会拒绝，需根按同一已批语义更新实际状态绑定而非伪造批准。

根普通治理登记精确落点：供审为 `docs/superpowers/plans/2026-10-10-five-candidates-seal.md`、其下固定子目录manifest/script、`0-学习与工具/codex-handoff/五候选本地提交计划供审绑定-2026-10-10.md/.json`、上述EE5根状态JSON、执行索引/R5/业务队列§二；批准后为同目录《五候选本地提交批准消费》md/json、实际《五候选本地提交结果》md/json、执行索引/R5、§一667/467/468/469/509及§二。所有普通正式写入仍acquire→写→官方edit/append→登记批次→release；seal脚本不触碰这些文档/队列。供审登记与批准消费是不同阶段，本计划未实施。
