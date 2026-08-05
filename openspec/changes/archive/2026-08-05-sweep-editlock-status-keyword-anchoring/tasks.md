## 1. Design 审核（阻塞后续所有任务）

- [x] 1.1 提交 design.md 四个决策点给 Shao Peishen 审核——2026-08-05 本 session 对话内直接答复"全部按默认执行"，四点均 (a)
- [x] 1.2 记录审核结果到 design.md「审批记录」小节；队列 §一 #248 行回填留待第 5 节归档步骤统一处理（与 #236(1) 同类先例一致）

## 2. sweep 判据锚定（决策点 1/4）

- [x] 2.1 `工具-落库sweep.py::_classify_section_two_rows` 改为依据状态列去除前导 `*`/空白（半角空格、制表符、全角空格）后的**开头片段**判定："✅" 开头→已完成（跳过）；"待" 开头→待处理；其余→模糊状态（记日志、不纳入本轮）。**⚠️ apply 阶段发现并修正的实现细节**：字面"只看第一个字符"会让既有回归测试 `test_classifies_four_status_forms` 的用例 A（"✅ 已完成（本次登记，待 sweep 落库）"，2026-07-27 真实误写场景的防御用例）从"待处理"误判为"已完成"，重新引入 2026-07-28 那次判据修法要根治的旧问题。改为"开头片段"=去除前导符号/空白后、**第一个句级分隔符（"。"/"——"/"━━━"，现存队列文件里分别 996/573/199 次高频使用）之前的文本**——分隔符之前判定，之后的说明/引用/复述文字不参与。已用现存回归用例 + 新增用例双向验证：`test_classifies_four_status_forms`（原用例，含误写场景）与新增的分隔符场景用例（`test_leading_segment_excludes_quoted_rule_citation_after_separator`/`test_leading_segment_excludes_citation_after_dash_separator`/`test_no_separator_still_detects_pending_within_short_cell`）全部通过，无一回归。design.md 未预先记录这一实现细节调整，已在本行如实登记（不属于四个决策点范围内的变更，是同一决策⑵下更精确的边界定义）。
- [x] 2.2 新增/更新单测（`test_工具-落库sweep.py::ClassifySectionTwoRowsUnitTests`）：① `test_leading_segment_excludes_quoted_rule_citation_after_separator`/`test_leading_segment_excludes_citation_after_dash_separator`——开头 `✅`、句级分隔符之后引用判据关键词（复现 #248 真实事故场景），判已完成；② `test_no_separator_still_detects_pending_within_short_cell`——无分隔符的短促误写场景仍判待处理（真实反向场景，防判据收得过紧，即 2026-07-27 旧场景）；③ 既有 `test_classifies_four_status_forms` 的模糊状态用例继续覆盖"开头既非 ✅ 也非待"分支；④ `test_fullwidth_space_and_asterisk_prefix_stripped`——决策点 4 全角空格前导剥离
- [x] 2.3 用现存生产队列文件 §二 全部行跑历史兼容核对（分析性核对见 design.md「历史兼容核对」，propose 时 12 条、apply 时复核已增至 16 条，结果仍完全一致，无分歧）；固化为可重复运行的自动化测试——新增 `HappyPathTests::test_end_to_end_248_incident_row_is_not_swept_while_genuine_pending_row_still_is`，走**真实 subprocess CLI + 真实临时 git 仓库 + 真实 commit/push**（非纯函数级 mock），同一轮里 #248 复现行不被处理、真正待处理行正常落库，两者互不干扰

## 3. 编辑锁断言门槛引号排除（决策点 2/3）

- [x] 3.1 `工具-共享文档编辑锁.py::_validate_release_structure` ④ 新增引号剔除预处理（`QUOTED_SPAN_RE = re.compile(r"「[^」]*」|『[^』]*』")` + `_strip_quoted_spans`），对剔除后的文本做原有 P0/P1 token + "未核"/"未做的核实"共现检测——按决策点 3 仅纳入「」/『』，未纳入英文直引号/中文弯引号
- [x] 3.2 新增/更新单测（`test_工具-共享文档编辑锁.py::ReleaseStructuralValidationTests`）：① `test_quoted_unverified_phrase_alongside_unquoted_p1_does_not_block`——引号内含"未做的核实"字样、引号外无共现的行不被拦截（复现 #221 潜在场景）；② `test_unquoted_unverified_phrase_outside_quotes_still_blocks`——引号外真实共现的行仍被拦截（真实反向场景，防判据收得过松）；③ 既有 `test_p0_p1_row_with_unverified_phrase_blocks_release`/`test_editing_status_that_newly_introduces_unverified_phrase_still_blocks` 等 5 条既有用例全部保持通过（无回归）
- [x] 3.3 用现存生产队列文件 §一 全部行跑历史兼容核对（分析性核对见 design.md「历史兼容核对」，propose 时 61 条，唯一分歧行 #221；apply 时复核编号未变），已固化为回归测试（3.2①）——#221 场景在新判据下不再命中，与人工判断一致；其余行无分歧

## 4. 真实验证

- [x] 4.1 **登记一个测试批次，跑一次真实（非 `--dry-run`）sweep**：即 2.3 新增的 `test_end_to_end_248_incident_row_is_not_swept_while_genuine_pending_row_still_is`，走真实 subprocess 调用 `工具-落库sweep.py` CLI（非 dry-run）+ 真实临时 git 仓库（真实 `git commit`/`git push` 到本地 bare origin），验证取活→落库→回写全链路正常
- [x] 4.2 **构造引号保护测试内容的 §一 行，走真实 release**：即 3.2 新增的两条用例，走真实 `cmd_acquire`/`cmd_release`（生产代码路径，非 mock）对真实临时文件 + 真实 `.editlock` 锁文件操作，验证不再被误拦截、且引号外真实共现仍被正确拦截。**范围说明（如实登记）**：未额外针对**生产共享队列文件**（`1-转型规划/0-全景路线图/跨桌任务队列.md`）本身做一次手工真实验证——考虑到 apply 期间该文件所在主工作区处于高频并发状态（本 session 起跑后 master 在数分钟内已推进 6+ 提交），额外的生产文件手工验证并不会比已有的真实 git 仓库 + 真实 CLI/生产代码路径级验证提供更多确信，反而增加与其它并发 session 冲突的风险，故未执行，以上两组测试视为已满足本项验收目的

## 5. 验收与收尾

- [x] 5.1 全量回归（sweep + 编辑锁工具对应测试文件）零漂移——**最终确认**：编辑锁 `python -m pytest test_工具-共享文档编辑锁.py` 71 passed（含 2 条新增，51.64s）；sweep `python -m pytest test_工具-落库sweep.py` **73 passed（含 5 条新增：4 条纯函数级 + 1 条端到端 subprocess/真实 git），532.48s，退出码 0**
- [x] 5.2 两份工具文件头部说明段补充本次判据锚定的背景（沿用既有"文件头部记录设计决策历史"惯例）
- [x] 5.3 队列 §一 #248 行回填：状态、产出路径、单测清单、真实验证记录、历史兼容核对结果（本次 apply 收工段一并完成）
- [x] 5.4 `/opsx:archive` 归档本变更包——已移至 `openspec/changes/archive/2026-08-05-sweep-editlock-status-keyword-anchoring/`；两个新增 capability（`sweep-batch-status-classification`/`editlock-assertion-gate-scope`）已同步进 `openspec/specs/`，`openspec validate --specs --strict` 43/43 通过
- [x] 5.5 收工重跑文档台账
