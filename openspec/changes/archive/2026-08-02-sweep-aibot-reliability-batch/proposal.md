# sweep-aibot-reliability-batch Proposal

## Why

`工具-落库sweep.py`（每小时定时任务）与企微机器人服务 `wecom-aibot-service`（常驻）近期各自暴露出**同一族病理**：失败/推迟/异常已经在代码路径里发生，但审计留了痕、机制却没有把它"收敛给人看"——sweep 起跑段静默空转（分叉之外的场景）、机器人写队列被锁忙推迟后靠不住的补录、哨兵配对判据与实际写入事件不一致、计划任务间歇性失败无人知晓、断连期间零信号。队列 #192／#193／#194／#198／#199 五行是这一族病理在两个物理落点（`工具-落库sweep.py`、`wecom-aibot-service/`）的五个具体实例，且各自内部改动同一份代码、跨落点共用同一次部署验证，必须同批交付（详见 `1-转型规划/0-全景路线图/开场prompt-【CC】192-199-sweep与机器人机制五行同批-交接.md`）。

## What Changes

- `工具-落库sweep.py`：起跑段新增顺序写死的四步（编辑锁前置探测 #198b → 无条件补推未推送提交 #194 → flush `pending_queue_lock_appends.jsonl` #192-A → 原有前置检查与批次处理），`main()` 加通用异常兜底（独立退出码 + webhook 告警 + UTC 日志 #198a），本批改动命中常驻服务路径时附部署提示（#198c）。
- `run_aibot_service.py`：两个 pending 暂存文件路径从硬编码 `SERVICE_DIR / "reports"` 改走 `resolve_repo_root()`，与 #126 对齐（#192-C 硬前置，否则 #192-A 的 flush 会静默空转）；给此前只写不读的 `pending_queue_appends.jsonl` 补消费方或至少哨兵告警。
- `queue_lock_pending.py` / `queue_reconcile_sentinel.py`：恢复配对不变式——补录成功事件 `queue_append_pending_flushed` 需被哨兵 `find_unreconciled_archives` 识别为与 `archived` 配对的事件之一（#192-B），否则被锁忙推迟过的批次会被哨兵误判为"未配对"。
- 企微机器人 `connection.py` / 新增复用 `liveness.py`：断连持续超阈值（60~90 秒）即私信一条"进行中"提示（含重试次数+下次退避秒数），恢复后仍发既有 `gap_alert`；去重按 #172 口径（#193）。
- `register-decision-reminder-task.ps1` + 在跑计划任务 `ZhuopinDecisionReminderDaily`：查明 `LastTaskResult=0x800710E0` 间歇性失败触发条件，补 `-StartWhenAvailable` 等设置并同步注册脚本源码，源码与在跑设置分叉的口子堵上（#199）。
- **BREAKING**：无。均为在既有函数/文件内新增前置检查与告警路径，不改变已有正常路径的输出结构。

## Capabilities

### New Capabilities

- `sweep-startup-resilience`：`工具-落库sweep.py` 起跑段的锁前置探测、补推、pending flush、异常兜底、部署提示五个新增前置动作的行为契约。
- `aibot-queue-pairing-invariant`：企微机器人锁忙推迟补录事件与 #107 哨兵配对判据必须保持一致的不变式。
- `aibot-liveness-inprogress-alert`：企微机器人断连期间"进行中"提示的触发阈值、去重、内容契约。

### Modified Capabilities

（无——现存 specs 目录下未见 sweep / wecom-aibot-service 相关 capability，本批新增的均为全新 capability，非对既有 spec 的 delta。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 三处：① "断连多久算需要报警"的阈值（60~90 秒）——目前是 Shao Peishen 与环境保障线讨论后的经验拍板，非算法推导；② "计划任务错误码 `0x800710E0` 是否值得继续追查根因、还是已知的间歇性可接受窗口"——需要交叉核对审计真身路径+`Get-ScheduledTaskInfo` 历史才能判断，无固定规则；③ "sweep 起跑段哪些异常属于健康跳过（退出码0）、哪些属于需要人工介入（非0）"——由 `SweepAbort.exit_code`/`is_fork` 编码，但新增场景（编辑锁占用、pending flush 异常）该归哪一类需要人判断而非照抄既有分类。
2. **由谁显性化？** 本变更为平台机制/工具类模块（非对客业务场景），无部门专员对口；持有人＝环境保障线（Cowork，负责取证与判据设计）+ CC 建造车间（负责实现与部署验证），backup／仲裁＝Shao Peishen 本人（唯一拍板方，见开场 prompt §五问题2 已拍板记录）。
3. **用什么方法提取？** 历史案例反推——#171（分叉告警）／#172（决策提醒去重）／#180（未同步标记自愈）同族修复的判据与去重逻辑直接复用，不重新发明；`0x800710E0` 触发条件走"历史案例反推"（`Get-ScheduledTaskInfo` 历史 + audit 真身路径交叉核对），查不出如实标注"未查清"，不编造解释。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：本变更为**平台底座可靠性机制加固**，非独立业务场景，不适用四档"对客交付"口径；套用最接近的档位描述＝**档3 内部服务**（`工具-落库sweep.py` 与 `wecom-aibot-service` 均已在生产常驻运行，本次是加固而非首次上线）。
- **晋下一档的条件**：不适用"晋档"概念（机制类模块无对客/内部界限跃迁）；改用**验收标准**——① 全量回归零漂移；② 真实部署 `ops/wecom-service-home` + 重启 `ZhuopinAibotDevListener`，文件哈希/进程启动时间交叉确认新代码已加载；③ 合入 master 后手动触发 `ZhuopinCommitSweep` 一轮，核 `reports/sweep-commit.log` 新增行；④ `#192-A` 真实构造一次"锁忙推迟 → 下一轮 sweep 自动补录"场景验证；⑤ `#199` 三任务设置（`Get-ScheduledTask` + `Get-ScheduledTaskInfo`）并列输出作证据。
- **价值指标**（风险型）：消除"失败/推迟已发生但机制未收敛给人看"的静默失效窗口数——基线＝五行问题各自的真实复现记录（队列 #192/#193/#194/#198/#199 行内既有实证），目标＝五处窗口均补上告警/补偿/配对路径，且新增单测覆盖回归。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断）。

## Impact

- 受影响代码：`0-学习与工具/工具-落库sweep.py`（+对应测试 `test_工具-落库sweep.py`）；`5-平台底座/wecom-aibot-service/scripts/run_aibot_service.py`；`5-平台底座/wecom-aibot-service/aibot_service/{queue_lock_pending.py, queue_reconcile_sentinel.py, connection.py, liveness.py}`；`0-学习与工具/register-decision-reminder-task.ps1`（若不在仓库内则为 `5-平台底座/wecom-aibot-service/scripts/register-decision-reminder-task.ps1`，以实读路径为准）。
- 受影响计划任务：`ZhuopinCommitSweep`（每小时）、`ZhuopinAibotDevListener`（常驻）、`ZhuopinDecisionReminderDaily`（每日 08:30）——三者的**实际设置**均不在仓库版本控制范围内，需真实登录/提权操作 `.51` 或本机对应任务后核验（#199 (2) 需 Shao Peishen 本人提权执行）。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——沿用既有 `wecom_aibot_audit.jsonl` 与 `sweep-commit.log`，新增事件类型均写入同一审计流；OEM 隔离——不适用（机制类模块不涉 OEM 技术数据）；L2 人工确认门禁——不适用（无自动执行业务决策的新增路径）；ISO 26262——不适用（非车规安全相关代码）。
