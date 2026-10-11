# 五候选整合：Windows Git 路径与引用格式补充计划

状态：具体供审，未创建整合 auth/Native，未 pick 或测试。原 D5F 整合批准已收到，不重问该原范围。

## 1. 根因与既有批准

原完整计划 SHA D5F582F1291ABE3C978B9D7E3671ADEF57CCF92D522040ED679AC1A26ACBAADE、原 amendment 7C22C19CA088B27D27538672913D34C884588D7D87EA9118F92AE670BA90E043 与原 preflight 9583859E24D4F7462F1A31475457912DC2A59D0ED0821D483E78D33253F5DC39 保留原字节。本人本轮第1项A已批准固定base、五提交、41路径、六suite、隔离副作用及SC10/SC11精确例外；只读身份/mode准备已推进，未建立正式整合auth。

根两次固定Git只读 check-attr 均exit0：同一路径使用正斜杠时回显可按literal前缀比对，反斜杠时回显被引号/双反斜杠转义，原helper会误拒。证据：reports/four-approvals-1011/alignment-windows-path-probe-1011.json。Windows GetRelativePath 会将auth/registration相对路径传成反斜杠，故原正式前检不能按原文完成。另有静态一致性问题：准备采集逐路径status含-c core.quotepath=false，正式消费者未包含；未在config/filter/hooks门前跑status探针。

## 2. 请求的最小新批准

1. 新正式脚本目标 docs/superpowers/plans/five-candidates-alignment-1011/preflight_ee5_and_git.ps1：复制冻结958实现，仅修以下已核路径点：filter helper把Git pathspec转为`/`且prefix用同一规范化字符串；controls/auth两个GetRelativePath转`/`；两处主仓逐路径status加-c core.quotepath=false。响应path证据仍保留原业务字段，41集合/权限不变，config→filter→hooks→status门顺序不变。Native全树clean仍独立核，失败停止。
2. 新脚本self-path guard指向上述新正式路径；expected auth改为0-学习与工具/codex-handoff/五候选整合批准消费-2026-10-11.json。原完整计划身份仍读D5F文件，原amendment仍读7C文件；另在首次Git调用前读取本补充计划SHA，与新auth.windows_path_amendment_sha256精确比对。新auth继续绑定原D5F/7C/manifest/5summary和来源，只更新preflight script pin并新增本补件pin；不消费旧草稿或旧封存授权。新auth.windows_path_supplement_approval四字段为evidence_path/evidence_sha256/human_answer_path/human_answer_sha256；两个证据均在原ignored reports/candidate-integration-1010新UUID下。evidence的schema固定five-candidates-windows-path-supplement-approval/v1，approved=true、plan_sha256等于本补件、human_answer_sha256等于原答字节。首次Git前强制auth/registration各有且仅有四条对应control：本补件、新script、新批准evidence、新human-answer；SHA准确且expected_porcelain_v2已冻结为string（可为空），缺项/重复/null停止。按原config→filter→hooks→status顺序，四项均进入后续逐路径status门，推荐不等于授权。
3. 原D5F的第一个PowerShell执行模板只替换两个固定常量：`$AuthPath`改新1011消费件绝对路径，`$PreflightScript`改新脚本绝对路径；替换发生在任何读取/调用前。其余helper定义、四次官方查询/EE5 gate、五次ordinary cherry-pick、六suite完整测试block保持逐字节不变。修订后第一block SHA与未改第二/第三block SHA由根在新auth分别绑定；不原位改D5F。原test command text SHA保持第三block来源。
4. 为写新auth，根重新准备来源草稿与限定主仓观察：按当前真实人批/新补件/脚本/SC7完成/EE5闭环/SHA门后再config/filter/hooks再逐路径status；采集helper同样规范化Git pathspec及逐路径quotepath。精确控制集合包含原D5F、7C、958、manifest/5summary/旧封存批准/五原实现计划/原供审输入，以及新补件、新脚本和本次明确人批证据，逐项冻结SHA/status/读取时点。路径限定主仓；观察件是字段采集，不替代正式operation前检。不用旧20控制草稿直接消费。所有新增准备、registration、checkpoint、测试证据都限定原ignored reports/candidate-integration-1010新UUID；不写全局runtime/state。
5. 新auth仅在本补件明确A后由根正式登记，native.returned_root初值null；自SHA/status仍独立registration绑定。Native实际root/config/hooks/HEAD/branch/全树status创建后checkpoint绑定；SC10/SC11各pick/test仍各自官方468/469四查询与新脚本preflight。本次不改变已批Native名称、branch、允许根、固定base、五source OID/tree、41path/blob/mode、六suite/cwd/targets/runtime、campaign与失败停止/不abort约束。

原已批运行范围：新Native five-candidates-align-1010、branch codex/five-candidates-align-1010、FrozenBaseSHA310f54de71149b0cb0281749619ee3cd84f97bca；5 lane依SC2→SC4→SC10→SC11→O4。此补件不新增产品路径、commit或测试，不ff/push/生产/真实取数/专业签认/清理旧树。

## 3. 复核与正式冻结

ignored候选script/root-narrow-plan经根对照与独立静审后搬入上述正式新路径，正式成件仅供审、不代表执行批准。新script原始SHA、根补充计划正式SHA和两处模板替换后的block SHA均另由批准消费件冻结；独立审查须确认除路径/引用格式及对应身份门外无逻辑漂移。邻近plan-draft.md与plan-reference-sync.md均已标superseded，不进入审批包；唯一审批对象是本窄补件及匹配script/template-bindings。原D5F/958保留，原整合批准不因该新阻塞暂停其他独立范围。新补件推荐A：批准上述精确修订及在原整合范围内续跑；B：保留停止。无默认授权。

## 正式供审登记与精确绑定

2026-10-11T08:20:34.0783953+08:00（上海）。根按原字节搬入已独立静审的窄补件正文，上文输入SHA 68E23FF5ED78EF6F0C7D976DAF5F870CEBA3BC2DA942D4C19B3710406F4643F3。Luna独立审查：reports/candidate-integration-1010/windows-path-amendment-1011/independent-review-v2.json，SHA 27938302D9F44DD30CD1B186595C7B936573DF18FA56FD3ABF542EEFC0D57F66，passed/findings=[]；审查不含Parser或运行验证。

新正式script SHA E9300BD2476DBCB3C69D33104A0B8EEF2848420A568F7CF6409C79CA14508A54。模板静态绑定证据 reports/candidate-integration-1010/windows-path-amendment-1011/template-bindings.json，SHA 4D834600B7054AC1E62824885599DC35DE3E1DE5FB71BDF61EABB89C1845A660；第一block仅替换两路径常量后SHA 8C6F1557BA2B0F915462493154B8BF06E967FDBD3C058ED9836DDA1B6ADB80A0，第二block保持DEE8CE3FE7DAAE3E60612BA5763A7C82E6D96B57C6A4CB57A0C7D5B3BF2800AF，第三/test command保持E389B803BAE38A012B2FD18F68D644058AD0910755905288A4BE29A97A7C562E。所有block均未执行。

本登记仅使窄范围具体可审，原D5F批准已收到；本补件仍待Shao Peishen新的明确A，未auth/Native/pick/测试，不扩原批准。

审查边界：v1报告reports/candidate-integration-1010/windows-path-amendment-1011/independent-review.json SHA 274986FEAD1E09559047D9D0BEE5593242EF7BB97E1A759B0B47D853DAE18C2B保留；v2仅针对WPA-001/002修正作静态复核并关闭两项，模板SHA使用根旁证。根本次用精确Get-FileHash独立核新plan/script与v2报告，身份一致；未运行完整diff/Parser或执行验证。正式供审不表示已运行通过。
