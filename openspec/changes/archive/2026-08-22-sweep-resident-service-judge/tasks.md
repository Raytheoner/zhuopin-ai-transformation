## 0. design 审门禁（阻塞后续全部任务）

- [x] 0.1 Shao Peishen 过目 `design.md`，特别是 §Decisions D1 末尾那处「与派单件字面的差异」：本设计把 `-AppFiles` 当**输入之一**而非唯一真值（＝定夺 1(a)），派单件字面写的是「用 `-AppFiles` 清单作判据」（近 1(b)）。**确认走 (a) 还是回退 (b)**——两者产出不同判据，选错要重做，故列为硬门禁。
- [x] 0.2 确认 D3「`register-*.ps1` 与 `run-*.vbs` 文案分开」是否保留（保留＝多一条分支；不保留＝两类印同一句「同步并重启」，对注册脚本是错处置）。
- [x] 0.3 确认 §Risks 第 3 条的登记方式：本次不覆盖 `.51` 四个部署目标（FI2/QD-B/SC2/SC8），须在队列 §四 #87 显式写明，避免下一轮误以为已覆盖。

## 1. 判据实现（`0-学习与工具/工具-落库sweep.py`）

- [x] 1.1 删除 `RESIDENT_SERVICE_PATH_PREFIXES`（L484）——**整体退休，不留兜底分支**（proposal §退休哪一个守卫）。
- [x] 1.2 新增 sync 脚本解析器：读 aibot 那份 `sync-to-server.ps1`，取 `-AppFiles` 条目与 `-LocalPlatformDir`。严格照 design §D4 四条契约：`utf-8-sig` 读取／反斜杠转正斜杠（**常量用 r-string**）／`-AppFiles @(...)` 跨行 `DOTALL` 匹配／解析失败从低取值。
- [x] 1.3 新增运行体集合构造：①`-AppFiles`（目录→前缀、文件→精确，按仓库内实际是否为目录判定）∪ ②`zhuopin_platform/` 除 `tests/` ∪ ③计划任务执行入口常量（`run-*.vbs`、`register-*.ps1`）。③ 处注释写明取自 `Get-ScheduledTask` 直读、并写明复核方式。
- [x] 1.4 重写 `_touches_resident_service`（L1177）：由返回 `bool` 改为返回**命中明细**（路径 + 命中来源 + 处置类别）；无命中返回空。
- [x] 1.5 改写 `_announce_resident_service_deployment_hint`（L1181-1200）：正文回显命中明细；按 D3 对 `register-*.ps1` 与 `run-*.vbs` 给不同处置措辞；解析失败时加「部署清单未解析出，已保守判定」一句。
- [x] 1.6 调整调用点 L2723 以适配新返回值；确认仍为纯提示——不阻断、不改退出码、推送失败不影响退出码。

## 2. 反例单测（`0-学习与工具/test_工具-落库sweep.py`）

> 每条对应 `specs/sweep-resident-service-alert/spec.md` 的一个 Scenario；**逐类锁死召回率**，防止「为压误报而牺牲真实命中」。

- [x] 2.1 **只改文档不报**：常驻服务目录下只含 `CLAUDE.md` ⇒ 不发告警（即 2026-08-22 `B-0822_17` 误报的复现口径）。
- [x] 2.2 **文档与代码混改照报，且正文只点名代码**：含 `CLAUDE.md` + `aibot_service/*.py` ⇒ 发告警且正文不出现 `CLAUDE.md`。
- [x] 2.3 **底座命中**（⑷ 漏报面）：只含 `5-平台底座/zhuopin_platform/**.py` ⇒ 发告警且正文点名底座。
- [x] 2.4 **底座测试不命中**：只含 `5-平台底座/zhuopin_platform/tests/**` ⇒ 不发告警。
- [x] 2.5 **`tests/` 与 `sync-to-server.ps1` 自身不命中**：两者各一例 ⇒ 不发告警（验证白名单天然排除，无需黑名单）。
- [x] 2.6 **`run-*.vbs` 命中**（若 0.1 定为 (a)）：⇒ 发告警，处置措辞为「下次触发即生效」。
- [x] 2.7 **`register-*.ps1` 命中且处置措辞不同**（若 0.2 保留）：⇒ 正文说明须重跑注册脚本，而非仅同步重启。
- [x] 2.8 **解析失败从低取值**：构造一份取不出 `-AppFiles` 的 sync 脚本 fixture ⇒ 该目录下任意路径均发告警，且正文含保守判定说明。
- [x] 2.9 **与 #229 互不抑制**：同一轮同时满足两条守卫命中条件 ⇒ 两条告警各自独立发出。
- [x] 2.10 **AST/文本反例守卫**：断言 `RESIDENT_SERVICE_PATH_PREFIXES` 已不存在于模块中（防止后续有人把前缀判据加回来作「兜底」，重造两套判据）。
- [x] 2.11 核对既有断言 `test_工具-落库sweep.py:1651`（断言文案含 `ZhuopinAibotDevListener`）在新文案下仍成立或按新文案更新。

## 3. 真实数据验证（档 2 判定，逐条对应 proposal §验收与晋档条件）

- [x] 3.1 对**真实仓库当前 6 份 `sync-to-server.ps1`** 跑一次解析并回显结果（含第 6 份无 `-AppFiles` 的情形按预期不参与），不是只对 fixture 跑通。
- [x] 3.2 以批次 `B-0822_17` 的真实 touched_paths 输入，验证新判据结论为**不报**。
- [x] 3.3 以真实底座路径输入，验证结论为**报**且正文点名底座。
- [x] 3.4 `0-学习与工具` 全量回归绿（基线 178 passed + 9 subtests），零回归。
- [x] 3.5 `--dry-run` 跑一轮真 sweep 后 `git status --porcelain` 无新增未跟踪文件（对应 proposal §伴生文件复核，**实测不采信推断**）。

## 4. 收口

- [x] 4.1 `openspec validate --all --strict` 通过。
- [x] 4.2 `openspec archive sweep-resident-service-judge -y`（tasks 全 [x] 后当场归档，完工即归档纪律）。
- [x] 4.3 ff 入 master 并 push；队列 §四 #87 回填：销 ⑶⑷、明记 ⑴ 已于 2026-08-21 销号不重复实施、**并按 0.3 显式登记「本次未覆盖 `.51` 四目标」**。
- [x] 4.4 §二 登记本次批次行。
- [x] 4.5 更正派单件 `opener集-CLAUDE进度段lint二期与sweep告警修正-2026-08-22.md` §OP-0822-C 的「约束」小节——该节仍是 v1 残留（要求「⑴ 断言告警文案不再出现已销号行号」「⑶ 断言本批仅含 `.md` 时不发」），与 v2 正文的「⑴ 直接销号／判据改读清单」矛盾。
- [x] 4.6 登记两条**只记不动手**的观察：① `wecom-aibot-service/sync-to-server.ps1` 无 UTF-8 BOM（与根 CLAUDE.md 坑 5 惯例不一致，但该脚本不走 `.51` 常规部署）；② ③ 类常量与真实计划任务 Action 的对齐须列入月度环境体检 `#98` 核对项（design §Risks 第 2 条的残余风险）。
