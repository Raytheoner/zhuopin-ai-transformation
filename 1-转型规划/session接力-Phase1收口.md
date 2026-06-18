# Session 接力 —— Phase 1 收口 + 下一程（质量域）

> 用途：跨会话接力点。新 Cowork / Claude Code 会话读这份 + CLAUDE.md 当前进度即可恢复。
> 更新：**2026-06-13（刷新，覆盖 6-11 旧版）**。CC 已交付 A/B/C 三个 stacked PR（未合，停在 Paul 审阅）；质量域规划 + 四项决策（D1–D4 全选 A）已落地。Paul 下周回公司，本周 off-LAN 重心 = **清掉挡在上线前的审批与协调动作**。

## 工作分工

Cowork = 规划治理桌（改 .md / 出文档 / 审 design / 守门禁，不碰真实库、不写生产码）；Claude Code Desktop = 建造车间（写码 / 连真实库 / git）。master 线性历史。凭据（U9C/SRM/FO/DB）只进 `.env`，从不入库 / 记忆。

## 本周 off-LAN 任务清单（按杠杆排序）

### 一、关键路径 —— 先做，纯 GitHub 不需 LAN

合并顺序是硬约束：**A(#10) → B(#11) → C(#12)**，不可乱序（B3 依赖 A2 的外发总开关，stacked base 链；A 合入后 #11/#12 base 自动改指上游）。

1. 审合 **PR #10（A 安全 P0）**。重点三处：erp_connector TLS 默认校验 + `real` 硬禁逃生开关、`submit_commitment` 首道一律入队 + Notifier 第二道总开关、verify_chain genesis 豁免只限第 1 行。**这一包是后面一切的地基。**
2. 依次审合 **#11（B 数据正确性/审计强制化）**、**#12（C 偏差监控）**。
3. 守边界：**`CUSTOMER_OUTBOUND_ENABLED` 仍不得开**——待 A+C1 合入、C2 跑 LAN、SRM 接通、L2 签字四者齐备（SOP 第 3 节）。本周只合代码，不碰对客开关。

### 二、抢 6/20 红线 —— off-LAN 起草，A 合入即发

先修信道再换钥匙：**A1（#10）合入后**立即发 IT 轮换 U9C client_secret（明文在归档仓 history、是能读真实 ERP 的活凭据）。邮件草稿已备：`1-转型规划/IT-U9C轮换与FO监控-邮件草稿.md`，A 一合即发。

### 三、治理签发 —— Cowork 桌，改 .md 即可

4. 签发 `3-治理与合规/OEM数据隔离规范.md`（现"待签发"）。
5. 确认 D1–D4 四项决策已回填对应文档（全景规划 / 两 PRD / 实施计划），收口 `待决策清单-2026-06.md`。

### 四、前置数据预热 —— off-LAN 协调（发指令，不依赖系统）

8 月才正式启动，但现在**预先知会 owner**可避免 6 周提前量被压缩（详见 `跨场景前置数据与知识库任务总表.md`）：

6. 知会质量部：8 月初启动**历史 8D 归集脱敏**（Q2 10 月上线硬前提，6–8 周）；同时指定 Q2 过渡期**客诉人工录入接口人**（D-2 已决）。
7. 知会 PMO + 财务：定**立项标准机器可核清单 + 财务规则边界**（Q6 11 月上线硬前提）。
8. 继续盯 **U9C MCP 接口**（7/1 申请）；FO 健康监控请求已并入第二节邮件草稿。

### 五、有余量再做

9. AIOps 第 2 人 JD / 打分卡 / onboarding 收尾 → 启动招聘（全景 #1 风险，现仅 1 人；`6-人才与组织/` 已有基线可扩）。

## 明确不在 off-LAN（回 LAN 再做，CC prompt 见附录 A）

- **C2 真实黄金回归**：`build_golden_real.py` 取数依赖 FO（`192.168.100.51:8800`，LAN-only）→ 必须回 LAN/VPN。跑通后 `data/golden/real_frozen/` 生成，`test_golden_real` 自动脱 skip。
- **SC1 任务 9.1 真实验证**：先确认数据源——仅 SRM（外网已通）则 off-LAN 可跑；涉内网则等 LAN。

## Phase 1 真实上线收口 —— 现状

| # | 步骤 | 责任 | 状态 |
|---|------|------|------|
| 1 | SRM 凭据迁入 `.env` + 只读冒烟（解 900401） | CC | ✅ 完成（看板 345 条、真实承诺交期；凭据进本仓库 `.env`） |
| 2 | SC8 内部真实验证 + 黄金基准（C2） | CC | 🟡 机理就绪，**卡 FO LAN-only，等回 LAN/VPN** |
| 3 | L2 门禁 + 回滚 SOP 签字 | Cowork/Paul | ✅ Paul 已签 2026-06-11 |
| 4 | A/B/C 代码修复（安全 P0 / 数据正确性 / 偏差监控） | CC | 🟡 **已修完，三 PR 停在 Paul 审合（#10→#11→#12）** |
| 5 | client_secret 轮换 | Paul→IT | 🔴 最急、A1 合入即发请求，盯 6/20 红线 |
| 6 | 小范围对客 | CC+VP | ⬜ 前置（A+C1 合入 + C2 LAN + SRM + L2 签字）全绿才开外发开关 |

## 关键事实 / 决策（延续有效）

- SRM 900401 = 本仓库缺凭据（非未开通）；凭据已迁入本仓库 `.env`。
- U9C 外网鉴权 = OAuth2（无需 admin 密码）；外网仅 OAuth + BOM/Query，`CommonEntity/Query` 外网 404；`U9C_API_BASE` host-only。
- **FO（客户订单）= LAN-only 内网服务 `192.168.100.51:8800`**，独立于 U9C/SRM 外网，仅 LAN/VPN 可达 → SC8 黄金基准取数需回 LAN。
- 置信度 = 引擎 2 级（高=全真实承诺交期可外发候选 / 低=任何启发式介入不外发）；"晚于客户目标日"是与置信度正交的独立外发拦截。
- 引擎默认场景本地，第 2 真实消费方才提升底座（rule of three），提升前查实际代码确认复用。
- D1–D4（2026-06-13 全拍板，均选 A）：SC8 深化不消费 SC6/SC7（移 S3）/ Q2 过渡客诉人工录入 SOP / SC9 降 MVP / 全场景两级验收。

## 待提交文档（纯文档无密钥，回 LAN 随 CC 一起 commit）

`3-治理与合规/SC8上线前置门禁-错误回滚SOP与黄金基准校验.md`（已签版）、本文件、`1-转型规划/U9C接入与连接器收敛-待办追踪.md`、`1-转型规划/IT-U9C轮换与FO监控-邮件草稿.md`、CLAUDE.md 当前进度行（与 Cowork 规划批次一并提交）。

---

## 附录 A：回 LAN 后 SC8 收口 CC prompt

```
回 LAN/VPN 后 SC8 收口一次性跑(都依赖内网 FO,外网做不了)。开工先 git pull master。

前置:已在公司 LAN 或 VPN。先 curl/ping 确认 FO(192.168.100.51:8800)通,再往下;不通停下报我。

1. SC8 黄金基准真实跑:
   python scripts/build_golden_real.py --limit 8
   - 拉真实 FO→三类取样(有反馈/无反馈/含委外)→冻结 FO/BOM/SRM 快照→预测+全链审计→dispatch 只入队不外发→出人工交叉核对表 + expected.json,落 data/golden/real_frozen/。
   - ⚠️ real_frozen/ 含真实客户数据 → 确认 gitignore,绝不 commit。
   - CUSTOMER_OUTBOUND_ENABLED=False 全程关;启发式 v0 不改,先看真实偏差。
   - 核对表报我(每张单:预测交付日/置信度2级/齐套日/瓶颈物料/承诺交期/委外+10/无反馈+30/延期/风险 + 留空"手工核算""偏差"两列),我和 PMC 逐张对。

2. SC1 真实数据验证(任务 9.1):
   - 先确认 SC1 数据源:若仅 SRM(外网已通)其实不依赖 LAN,能跑就跑;涉内网才需 LAN。
   - mock→真实,结果报我,先别合。

3. (可选)FO 健康告警应用层安全网:SC8/FO 连接器在 FO 不可达(502/超时)时,除 fail-loud 外写 audit(source=FO 不可达)+ 经 notifiers/wecom 推企微告警。小改动,可单独提交。

4. 回归 + 提交:
   - tests/test_golden_real.py(冻结夹具零漂移回归)+ mock 全套跑绿。
   - git add 本轮代码/测试/脚本 + 纯文档(SOP 已签版/本接力文档/U9C待办追踪/IT邮件草稿)。
   - 排除:.env、data/golden/real_frozen/(真实客户数据)、历史无关改动。
   - commit + push,开 PR 或留分支等我审。先别合 master、先别开对客。

红线:对客外发开关全程关;真实客户数据(real_frozen)不入库;凭据不入库;real 缺真实端点 fail-loud。
跑完把黄金基准核对表 + SC1 结果 + git 状态报我。
```

---
*关联：CLAUDE.md 当前进度、`3-治理与合规/SC8上线前置门禁-错误回滚SOP与黄金基准校验.md`、`1-转型规划/U9C接入与连接器收敛-待办追踪.md`、`1-转型规划/IT-U9C轮换与FO监控-邮件草稿.md`、`1-转型规划/supplychain收割与全景推进策略.md`。*
