# CLAUDE.md — FI3 付款申请自动校验（场景级进度笔记）

> 本文件是 FI3 的本地记忆/进度笔记。项目级上下文见仓库根 `CLAUDE.md`；FI3 规划权威见全景规划 §2.1.4 FI3 块（v10 2026-09-17 前拉至 2026-09）、`1-转型规划/FI3-付款校验-就绪清单与MVP细化.md`（R1–R8 定稿）、`1-转型规划/0-全景路线图/FI3前置就绪包-节假日日历落档与design落字指令-2026-09-02.md`。本场景 ＝ CC 建造车间产物；**不改规划文档**。

## 1. 定位
- 财务域资金安全场景，**2026-09 启动**（v10 前拉）。七子场景 FI3-1～FI3-7 同批开工（两段制已取消：FI2 已上线 `.51:8094`）。
- 自动化等级 **L3**（旁路校验清单，乙方案；唐燕萍 2026-07-10 圈定）。**L4 自动拦截须 Shao Peishen ＋ CFO 会签**（R8／D2）。
- 🔴 **AI 不碰钱**：只出校验结果与拦截建议，付款执行永远人工。
- 当前档位：**档 1（mock 验证）**，`python -m pytest tests -q` 32 passed（2026-09-18，`OP-0918-A`）；**已上线 `.51:8097`**（过渡期独立端口，见 §5b）。

## 2. 决策
- 业务判据 R1–R8 ＝ 唐燕萍 2026-07-10 圈改定稿（R1 暂估价 07-14 回件确认），逐条 `Signoff` 登记 `config.CRITERIA`，`RULE_VERSION=fi3-v1-tangyanping-2026-07-10`。
- 审批层级口径已完整确认（§四 #93），不再对接 CFO 办公室；**不放松 R8**。
- 节假日日历：唯一权威源 745 行表（2026-01-01～2028-01-15），直查 `是否工作日`，越界 fail-loud；旧 33 天表作废。
- 工程决策 D1–D8 见 `openspec/changes/fi3-payment-validation-mvp/design.md`，**🟡 待 Shao Peishen 审**。
- 两项未签认在 `config.PENDING`（账龄预警天数／L4 会签），读即抛，本包不代填。

## 3. 底座
- `zhuopin_platform.criteria_signoff`（判据签认）、`audit`（每张申请一条 `AuditEvent`）、`bootstrap.ensure_paths`（唯一样板）、`shared_tools.connector_errors.RealEndpointNotReadyError`（u9c fail-loud）。
- 上游：FI2 三单匹配结果（按发票号消费，D1 口径 `FI2_MATCHED_CLASSES={完全匹配}`）。
- 不接 `data_isolation_layer`（公司自有财务数据）。

## 4. 红线
- mock 先行；`u9c` 不回退 mock。收款账号任何呈现只留尾 4 位。主数据缺失＝拦截，不＝通过。
- 引擎不得写死任何数字；新口径先立 `Criterion`。`AUTOMATION_LEVEL` 改 L4 唯一前提＝会签签认落档。
- 不发信、不代指派持有人、不代联络 CFO 办公室。`.51` 只动 `C:i3\`／`Fi3WebServer`／`Fi3-WebServer-8097` 三处（`#615` 授权范围），不碰网关 8090、不动其余服务；口令值不入库、不打印、不进日志。

## 5. 时间线
- 2026-07-07 就绪清单立；07-10 唐燕萍 R1–R8 圈改；07-14 暂估价统一确认；07-19 核实零开放项。
- 2026-08-22 节假日日历 745 行交付；09-02 就绪包落字指令成文；§四 #93 CFO 审批流免除。
- 2026-09-17 v10 前拉至 2026-09；`OP-0917-J` 无头泳道从零建到档 1（分支 `claude/op0917j-fi3-new`，commit `6df5926` 起）；同日 design 审 D1–D8 通过（Shao Peishen 答 `1a`）。
- 2026-09-17 `OP-0917-R`（队列 §一 `#613`）：tasks 5.1 门户页 `/finance/fi3` 落地——`fi3_payment_validation/webapp.py`（Flask 蓝图，路由前缀 `/finance/fi3`，首屏显著标注「mock 数据」，网关 `X-Zp-Identity` 接入点已挂但只预留不实现，`install_flask_gate` 用 `FI3_GATE_PASSWORD` 环境变量未配置即不生效）＋ `scripts/run_fi3_web.py`（默认只绑 `127.0.0.1:8097`、不建防火墙规则——**不比照 SC2 8096 的过渡期新端口豁免**，对外访问设计上唯一走 `.51:8090` 统一门户网关反代，收编条件见 `5-平台底座/unified-portal-gateway/CLAUDE.md` §6）。回归 32 passed（原 25＋新增 7）。**5.2 `.51` 部署未做**（off-LAN 留步，本轮不碰 `.51`、不开防火墙、不申请端口）。
- 2026-09-18 `OP-0918-A`（队列 §一 `#615`，批 `B-0918_FI3上线`）：tasks 5.2 **`.51:8097` 上线**——Shao Peishen 当日答 `a`「现在都是内网，先上功能，认证完善以后慢慢上」⇒ 走现有服务老形态（独立端口＋防火墙＋共享口令门禁 `#160`），与 D7 相反、属过渡形态，先例 SC2 8096；网关收编时端口一并回收。改动：门禁 env 由 `FI3_GATE_PASSWORD` 改共享 `ZP_GATE_PASSWORD`；`run_fi3_web.py` 经 `env_anchor.load_env` 读 `.env`（默认仍只绑 127.0.0.1，`.51` 由 `start-fi3.ps1` 置 `0.0.0.0`）；`pyproject` 补 flask/waitress；新建 `deploy-server.ps1`／`sync-to-server.ps1`／`smoke-server.ps1`（三件均带 BOM）。回归 32 passed；部署证据见下「部署状态」段。
- 下一步：5.3 第 8 步跟进信（🔴 **写死「看形态、不看数字」**——本版是 mock，真实数据等唐燕萍回 `财务部#19`；发送三条硬前置＝串行闸／ff 已合入／`.51` 冒烟通过）→ 档 2 接 U9C 五端点＋FI2 真实结果 → `#339` 浮出后补 P2P 对照与会签底稿模板。

## 5b. 部署状态（tasks 5.2；判据正本＝`3-治理与合规/.51部署标准清单-服务侧与笔记本侧-2026-08-01.md`，自证型逐条打勾）

| 项 | 值 |
|---|---|
| 地址 | `http://192.168.100.51:8097/finance/fi3/`（档 1 mock，首屏黄条标注；**看形态、不看数字**） |
| 健康检查 | `http://192.168.100.51:8097/finance/fi3/api/ping`（门禁豁免；无裸 `/api/ping`） |
| 布局 | `C:i3\{zhuopin_platform, app, .venv, .env, deploy-tools}`，同 FI2 扁平布局 |
| 计划任务 | `Fi3WebServer`：`MSFT_TaskBootTrigger`（AtStartup）＋ `SYSTEM`＋ Restart `3x/PT1M`（smoke §0 回显） |
| 防火墙 | 入站规则 `Fi3-WebServer-8097`，`RemoteAddress=Any`（smoke §0 回显 `remote=Any`） |
| 门禁 | 共享口令 `ZP_GATE_PASSWORD`（`#160`），`C:i3\.env` 由 `deploy-server.ps1` 从同机 `C:i2\.env` 服务器本地借行、值不出机不回显；程序化读取走 `X-Auth-Token` |
| 脚本 | `sync-to-server.ps1`（笔记本跑）／`deploy-server.ps1`（`.51` 跑）／`smoke-server.ps1`（`.51` 跑，`exit`＝失败数） |
| 部署 commit | `ae6a2d8`（webapp.py sha256 `CAE140BF…41F95` 两侧一致：本机 `sha256sum` ＝ `.51` `Get-FileHash`） |

- **§二 前置**：全量 32 passed（`python -m pytest tests -q`）；design D1–D8 09-17 审过（答 `1a`）；变更包 `fi3-payment-validation-mvp` 仍开（5.3／§3 档 2 未做，不归档）；场景 CLAUDE.md 本段即更新；§三 无冻结标。
- **§三 七类坑**：① 三脚本文件头 `EF BB BF`（`xxd` 取证）✅ ② 防火墙 `Any` ✅ ③ AtStartup＋SYSTEM ✅ ④ `start-fi3.ps1` 烘焙 `C:i3\.venv\Scripts\python.exe` 绝对路径（smoke §0 `CmdLine` 回显）✅ ⑤ `3x/PT1M` ✅ ⑥ `.env` 键非空、门禁生效（未登录 302 实测）✅ ⑦ 口令值未进任何库内文件／日志 ✅。
- **§五 冒烟三件套（2026-09-18 08:26–08:40 本地）**：⑴ `/api/ping` 200——`.51` 本机（smoke §1）＋ 笔记本外部 `curl` 各一次 ✅；⑵ 未登录 `GET /finance/fi3/` → 302 `/_gate/login`（本机＋外部各一次），登录后 200 ✅；⑶ 主流程＝登录后首页渲染 mock 判定表，`bytes=3565`，关键字 `<b>mock</b>`／`并非真实付款申请`／`fi3-v1-tangyanping-2026-07-10`／`<th>结果态</th>` 四项全 True，前后 PID 9920 同一（未崩） ✅。`smoke-server.ps1` 回显 `SMOKE DONE failures=0`，exit 0。
- **§六 回滚 SOP（已写死 TaskName）**：`schtasks /End /TN Fi3WebServer ; schtasks /Delete /TN Fi3WebServer /F ; Remove-NetFirewallRule -DisplayName Fi3-WebServer-8097`；门禁回滚＝清空 `C:i3\.env` 的 `ZP_GATE_PASSWORD=` 值后 `/End`＋`/Run`；代码回滚＝`sync-to-server.ps1` 重推上一 commit＋重启。
- **§七 可常驻**：服务由计划任务拉起（非手工前台）、AtStartup、带失败重启；重部署前 `Start-ZhuopinWebServiceAndCheckHealth` 先杀端口占用旧实例（防双实例）。
- ⚠️ 未做／留步：`.51:8090` 网关未接管 `/finance/fi3`（`#615` 明令本批不碰网关）；5.3 跟进信未起草（对外发送永不代办）。

## 6. 依赖
- 输入：U9C 供应商收款账户／采购合同（框架/暂估/账期）／已付款凭证 12 个月／预付款台账／应付配票状态（IT 2026-07 给齐）；FI2 结果；节假日日历（年度更新由李姣龙执行）。
- 下游：FI6 `#607` §2.4 接口形状（本包落地即消掉「FI3 无工程实体」前提；FI6 需要的是 `ValidationVerdict`/`CheckFinding` 形状）；FI4／FI7 消费 `#339` 产出。
- 开放点：`FI3-G-01` 账龄天数（唐燕萍）／`FI3-G-02` L4 会签流程（Shao Peishen＋CFO）／`FI3-G-03` 持有人 backup（人事）。

**Last Updated**: 2026-09-18
