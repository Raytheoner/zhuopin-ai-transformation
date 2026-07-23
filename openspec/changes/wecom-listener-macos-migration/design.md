# 企微智能机器人双向通道服务 · 常驻监听迁移 Mac mini · Design

## Context

- 现状：常驻监听服务实际运行在长驻 worktree `.claude\worktrees\wecom-service-home`（checkout `ops/wecom-service-home` 分支），由 Windows 计划任务 `ZhuopinAibotDevListener`（`AtLogOn`、`-MultipleInstances IgnoreNew`）拉起 `start-aibot-service-dev.ps1`（gitignore，本机文件，不入库）。该脚本自己拥有一个 while 循环，实现三级重启退避（60/300/900 秒，稳定运行满 1200 秒后档位归零）+ 双重孤儿进程清理（`python.exe` 子进程 + 脚本自身的残留副本）+ `Start-Transcript` 日志。
- 核心业务代码 `aibot_service/`（`connection.py`/`intake.py`/`delivery.py`/`gates.py`/`group_notify.py`/`whitelist.py`/`gap_alert.py`/`queue_appender.py`/`queue_reconcile_sentinel.py` 等）与 `scripts/run_aibot_service.py` 经代码核实（grep 全目录）**不含任何 Windows 专属依赖**——路径经 `pathlib.Path`/环境变量注入，无 `subprocess`/`ctypes`/`win32*` 调用；唯一与 Windows 相关的是**注释文字**里提到部署层 `.ps1` 脚本名，非实际代码耦合。`pyproject.toml` 依赖仅 `zhuopin_platform[aibot]`（引入 `wecom-aibot-python-sdk`）+ `pyyaml`，均为 PyPI 通用包，未见平台限定 marker。
- **队列追加的真实现状（与总线草案的假设有出入，需先澄清）**：`queue_appender.append_pending_task()` 目前**只做本地文件的读-改-写**（乐观并发重试：写入前重读校验磁盘未变，变了则重新计算插入点/编号再试），**从不执行任何 git 操作**。追加后的队列文件要进入 GitHub master，现状**全靠人工/CC 事后手动 `git add/commit/push`**（真实事故：队列 #69/#70，07-21 一条 `queue_appended` 审计事件成功但对应行从未出现在任何 git 提交里，根因是人工/CC 会话的整段改写在追加之后、提交之前的窗口期静默覆盖了它）。总线草案 D1 里"bot 直接 commit+push"是一个**尚不存在、需要新建**的能力，不是"迁移一下就能用"的既有功能。
- **协议〇.7 编辑锁的真实作用范围**：`0-学习与工具/工具-共享文档编辑锁.py` 在队列 #89 修复后，`REPO_ROOT` 改用 `git rev-parse --git-common-dir` 解析——这能覆盖"同一个 `.git` 对象库下的多个 worktree"（本仓库当前 6 个物理 checkout 共享同一个 `.git`），但 **Mac mini 上按本方案 §三 D3 是一个独立的 `git clone`（有自己独立的 `.git`），物理上没有任何文件系统路径能与 Windows 侧共享**——协议〇.7 的本地锁文件**结构性地看不见、也管不到 Mac 侧的写入**，反之亦然。这是 D1 必须正视的事实，而不是"设计一下兼容性"就能绕过的细节：跨机器的冲突防护**只能**发生在 git 层（fetch/push 语义），不能指望复用这把本地文件锁。

## Goals / Non-Goals

**Goals**：
- 把常驻监听进程迁到 Mac mini，核心业务代码零改动。
- 新增"队列本地追加 → 自动同步到 GitHub master"的能力，替代现状的人工事后提交，且经得起"Mac 与 Windows 侧几乎同时都在改队列文件"的真实并发场景（历史上已发生过 3 次同类事故：#69/#70 队列静默丢行、07-23 两次编号撞号）。
- launchd 常驻自愈达到与现状 Windows 三级退避同等（或更好）的可靠性，且不引入 Windows 侧已踩过的两个部署层坑（计划任务窗口隐藏不可靠、孤儿进程未级联清理）。
- 切换过程任何时刻只有一个实例连接企微（07-19 双实例重复通报教训不可重演）。

**Non-Goals**（本变更明确不做）：
- 不改 `aibot_service/` 任何业务逻辑（归档规则/两道门禁/白名单/群通报口径）。
- 不碰 `.51`（IT 边界，`.51` 是否接入本服务功能是另一件未定事项，不在本次范围）。
- 不重新设计协议〇.7 编辑锁本身使其支持跨机器（评估后判断收益/复杂度不成正比，见 D1 决策与否决方案）。
- 不做"队列追加模板嵌入 opener"（二期，见跨桌任务队列 #88 注记原文）。
- 不用 macOS 钥匙串管理凭据（见 D2/D6，权衡后选择与现状一致的 `.env` 文件方案）。

## Decisions

### D1. 队列回写机制：本地追加不变 + 新增 git 层"拉取重算再推"重试，而非重放旧 diff

**决策**：`queue_appender.append_pending_task()` 本身不改（继续只做本地文件读-改-写）。新增一个独立步骤/模块（如 `aibot_service/queue_git_sync.py`），在本地追加成功后调用，逻辑：

1. `git add <队列文件相对路径>` + `git commit -m "bot(队列): 自动追行 #<task_id>"`。
2. `git push origin master`。
3. 若推送被拒绝（非 fast-forward，说明 origin/master 在此期间被别人推进了）：
   - `git fetch origin` + 把本地队列文件内容**对齐到 origin/master 的最新版本**（`git checkout origin/master -- <队列文件>`，只重置这一个文件，不动其他内容/不影响 Mac 本地 `7-外部文档` 等 gitignore 内容）；
   - **重新调用 `append_pending_task()` 对最新内容重新计算插入点与编号**（而不是把第 1 步生成的旧 commit `git rebase`/`cherry-pick` 到新基线上）；
   - 重新 commit + push。
   - 重试上限 3 次，每次间隔数秒退避。
4. 3 次仍失败：不阻塞归档主流程（归档、门禁、通报等既有动作照常完成）——把这条待追加信息写入本地暂存文件（如 `reports/pending_queue_appends.jsonl`，与既有 `reports/wecom_aibot_audit.jsonl` 同目录同治理方式），记一条 `queue_sync_degraded` 审计事件，并通过 `gap_alert` 同款兜底通道私信 Paul"队列同步失败 N 次，一行待人工核对合并"。人工/CC 后续在正常编辑窗口（走协议〇.7 锁）把暂存内容补录。

**为什么"重算"而不是"重放"（对比 git 原生 `pull --rebase`）**：历史事故的真实模式**不是文本行冲突**（单行插入在 diff 层面几乎不会产生 git 冲突标记），**而是语义编号撞号**——两个写手各自基于自己那份"稍旧"的队列内容算出"下一个编号是 79"，各自都成功写入、各自都能通过 git 的文本合并（因为插入点不同、没有 conflict marker），结果队列里出现两行编号相同、内容不同的 `#79`。单纯 `git pull --rebase` 只会重放"在原编号基础上插入这一行"这个动作，**不会重新计算编号该是多少**——推送成功后编号依然可能撞车。必须在检测到"origin 已前进"后，先对齐到最新内容，再**重新跑一遍 `_next_task_id`**，才能保证最终编号是"当时真实最大号之后续排"（协议〇.6 既定原则），而不是"我记忆中的下一个号"。

**为什么不接入协议〇.7 编辑锁**（对比方案：让 bot 也 acquire/release 这把锁）：
- 结构性不可行——见 Context 分析，Mac 独立 clone 与 Windows 侧checkout 没有共享文件系统，锁文件互相看不见。
- 即便强行打通（例如把锁状态存进一个 git 追踪的小文件、双方都读远端锁），协议〇.7 本身是为"人类一次编辑会话持续几分钟到几十分钟"设计的粗粒度互斥（30 分钟陈旧过期），用来保护 bot 这种"单行追加、几百毫秒内完成"的高频自动化写入，代价（额外的跨机器锁同步机制、网络延迟下的锁竞争/超时处理）远大于收益。
- 上述 fetch-重算-重推 循环本质上就是"用 git 自身的乐观并发控制做冲突检测"，对这个具体写入模式（单表格、仅追加、编号确定性可重算）已经是恰好匹配复杂度的方案。

**为什么不干脆不让 bot 碰 git、只做本地追加，靠人工定期同步**（否决方案）：与本次迁移的核心目的矛盾——Paul 最需要看到队列更新的时刻，恰恰是他不在 Mac 旁边、只能靠企微私信+GitHub 远程了解现状的时刯；如果队列追加只落在 Mac 本地、要等人工登录同步，等于把"合盖丢件"换成了"合盖丢队列可见性"，问题性质没变。

**实现细节（供 tasks.md/实施阶段参考，非本次决策核心）**：git 操作走 `subprocess.run(["git", ...], cwd=REPO_ROOT)`（本仓库目前没有引入 GitPython 等封装库的先例，不新增依赖）；因涉及子进程调用，参照 `group_notify.py` 现有模式用 `asyncio.to_thread` 包裹，避免阻塞连接器的事件循环。

### D2. 仓库凭据：Paul 名下仓库范围细粒度 PAT + 本地 commit 身份改为 bot 名义（不新建 GitHub 账号）

**决策**：不新建独立 GitHub 账号，改用 **GitHub fine-grained PAT**——在 Paul 自己账号下创建一个只授权本仓库（`Raytheoner/zhuopin-ai-transformation`）、仅 `Contents: Read and write` 权限的令牌，存入 Mac 侧 `5-平台底座/.env`（复用现有分层惯例）。**PAT 的账号归属与 commit 的作者身份是两回事**：GitHub 只要求"推送时使用的令牌对该仓库有写权限"，commit 里的 `author`/`committer` 字段由本地 `git config user.name/user.email` 决定、与令牌无关——因此在 Mac 侧把本地 git 身份设为独立的 `Zhuopin AI Bot <aibot@noreply.local>`，git log/blame 上就能清楚区分"人工提交"与"机器人自动提交"，不会和 Paul 本人的提交混淆。

**否决方案对比**：
- 方案 A（总线草案默认）：新建独立 bot GitHub 账号。审计清晰度与本方案相同（commit 作者身份本就独立于账号本身），但多一层账号生命周期管理成本（单独的邮箱/2FA/离职交接），对于"只需 push 到一个仓库"这个单一用途是不成比例的开销，否决。
- 方案 B：直接用 Paul 现有登录凭据（如个人 classic token 或缓存的浏览器登录态）。范围过宽（classic token 通常是账号级全仓库权限），一旦 Mac 端 `.env` 泄露，暴露面远大于"只授权这一个仓库的读写"，否决。
- 采纳：细粒度 PAT（仓库+权限双重最小化）+ 本地身份区分（审计清晰度不打折扣）——两个诉求分别用最小代价的机制满足，不需要为了"身份区分"这一个诉求去背"新建账号"这一整套管理成本。

### D3. 归档同步：`7-外部文档` 边界不变，Mac 为收件真身；**路径处理比总线草案设想的更简单**

**决策**：
- `7-外部文档` 继续 gitignore（敏感层边界不变），Mac 本地磁盘是归档原件的权威副本。
- 笔记本回 LAN 时，通过 SSH（Remote Login，仅 LAN 可达，见 D6）单向 `rsync`/等价工具把 Mac 的 `7-外部文档` **拉**到笔记本本地（**只读拉取，不做反向 push**，避免笔记本任何本地误操作反向污染 Mac 权威副本）——**手动触发**（一条命令/脚本，非自动后台常驻同步），因为已有企微私信转发（`forwarding.py`，全量进件转发 Paul）作为实时可见性兜底，这份 rsync 只是"事后本地留一份备份"的低频动作，不需要额外常�instance开一条 SSH 隧道保持连接（降低攻击面，呼应 D6）。
- **与总线草案不同的发现**：草案 §三预设 Windows 的路径覆盖机制（`WECOM_AIBOT_EXTERNAL_DOCS_ROOT`/`WECOM_AIBOT_QUEUE_PATH` 环境变量）在 Mac 上也要照搬。经读 `run_aibot_service.py` 源码：这两个环境变量之所以在 Windows 上**必须**显式设置，是因为服务实际跑在 `.claude\worktrees\wecom-service-home` 这个**链接 worktree**里，若不覆盖，默认值会解析到该 worktree 自己的 `7-外部文档`/队列文件副本（不是 Paul 日常看的那份主仓库）。**Mac 侧按 D3 是一次性、单一用途的独立 clone**（不是多 worktree 场景），默认值（`Path(__file__).resolve()` 反推的 `REPO_ROOT`）天然就是这个 clone 自己的根目录——**不需要任何环境变量覆盖**，`.env` 只需放 `WECOM_AIBOT_BOTID`/`WECOM_AIBOT_SECRET`/`WECOM_WEBHOOK_URL`/部门群 webhook 几项凭据，比 Windows 版本的 `.env`/启动脚本更简单、硬编码路径更少（消解了一整类"路径写死在 gitignore 脚本里、迁移/交接时容易漏改"的风险）。
- 沿用 Paul 既有红线：Mac 仓库副本**不放 iCloud Drive/任何云同步目录**（与"不放 OneDrive"同一条红线的镜像要求）。

### D4. 常驻与自愈：launchd LaunchDaemon（非 LaunchAgent）+ 退避逻辑保留在 shell 脚本内，不下放给 launchd

**决策**：
- **LaunchDaemon（`/Library/LaunchDaemons/`，系统级）而非 LaunchAgent（`~/Library/LaunchAgents/`，用户级）**。理由：LaunchAgent 只在对应用户**登录 GUI 会话后**才启动，Mac mini 意外重启（断电恢复/系统更新）后若无人到场手动登录，服务就不会自动起来——这与本仓库自己踩过的真实事故（`CommandCenterWeb` 用 `AtLogOn`+交互式登录注册，会话"已断开"状态下无法拉起新进程，2026-07-23 已修复改为 `SYSTEM+AtStartup`，详见根 CLAUDE.md 当前进度段）是**同一类"绑定登录会话"的坑**，Mac 版应直接吸取教训选 LaunchDaemon，不必重踩一次。
- **三级退避（60/300/900 秒）+ 稳定运行 1200 秒归零 + 双重孤儿进程清理，逻辑完整搬进一个新的 bash 包装脚本**（如 `start-aibot-service-mac.sh`），launchd 本身只负责"开机/崩溃后拉起这个包装脚本"（`RunAtLoad=true` + `KeepAlive`），**不**依赖 launchd 自带的 `ThrottleInterval`/崩溃节流去实现分级退避——launchd 原生节流是固定极短间隔（约 10 秒量级），无法表达"1 分钟→5 分钟→15 分钟"的分级语义，必须把这段状态机逻辑留在脚本自己的 while 循环里（与 Windows 版本架构一致：Windows 计划任务本身也不管退避，退避全在 `.ps1` 内部）。
- 孤儿进程清理的 macOS 等价：`pgrep -f run_aibot_service.py`（子进程）+ `pgrep -f start-aibot-service-mac.sh`（排除 `$$` 自身，即外层脚本残留副本），`kill`/必要时 `kill -9`——与 Windows 版 `Get-CimInstance Win32_Process` 按命令行匹配的逻辑一一对应。
- **`run-hidden.vbs` 不需要移植**：该文件是为解决"Windows 计划任务以交互式登录方式运行 PowerShell 时会弹出可见窗口、误关窗口即杀掉整个进程树"这个 Windows 特有问题而生的（`WScript.Shell.Run(...,0,...)` 强制隐藏）。launchd daemon/agent 本身不创建任何终端窗口，这整类 bug 在 macOS 上不存在，少一个组件、少一个潜在故障点。
- 日志：沿用 Windows 版的"包装脚本自己写日期戳文件名日志"惯例（如 `reports/service-dev-YYYYMMDD.log`），而不是改用 launchd plist 的 `StandardOutPath`/`StandardErrorPath` 静态单文件——保持与现有排障习惯/工具一致，日志目录仍是 gitignore 覆盖的 `reports/`。
- 防休眠：Mac mini 是常插电桌面设备（不像笔记本要顾虑电池），直接在系统设置里关闭"电源适配器供电时进入睡眠"，不额外跑 `caffeinate` 包装进程（少一个可能被遗忘/崩溃的活动部件）。

### D5. 切换与防双实例：并行测试阶段先验证"同 BotID 双连接"的真实行为，不预设"能安全并行"

**决策与需要先验证的风险**：现有 `wecom-aibot-connector` 的 design.md（D2）已记录一个关键限制——SDK 的断线事件"无法精确识别是否是被踢"，即**从代码层面无法确认"两个进程用同一个 BotID 同时连接"时，企微服务端到底是拒绝第二个连接、还是踢掉第一个、还是两个都保留**（此前的"单连接看门狗"设计只处理过"同一台机器上意外起了两个进程"的场景，从未验证过"两台不同机器分别各起一个进程"的行为，两者对企微服务端来说是否等价未知）。总线草案"先真实并测(Mac 起服务但白名单临时只含 Paul 自测)"隐含假设"两边同时接同一个真实 BotID 是安全的"——**这一假设未经验证，不应直接采纳**。

- **推荐方案**：并行测试阶段**不用生产 BotID/Secret**做双活验证，改为两种更保守的路径之一（留给 Paul 在 Open Questions 里选）：
  a) 用一个独立的测试企微机器人（另开一个 BotID，成本低、企微后台几分钟可建）在 Mac 上跑通全链路（连接/归档/推送/门禁/哨兵），验证 Mac 侧代码本身正确，**不触碰生产 BotID 的双连接风险**；
  b) 或者接受"先短暂停 Windows、再起 Mac"的**顺序**验证（而非真正并行），用一个提前规划好的短窗口（如晚间），中断时长可控且是计划内的，不同于"合盖"那种失控中断。
- 无论哪种，**原子切换**本身：`schtasks /End` 停 Windows 任务 → 立即执行 Mac 端启动 → 盯审计日志确认 `authenticated` 在预期时间内出现且全程只有一条——两个动作应作为同一操作序列背靠背执行（不是"先停、过一会再想起来启动 Mac"），把切换空窗压到最短。
- **冷备**：Windows 计划任务改 `Disable`（非删除）保留定义，文档化一页"紧急启用 SOP"（`Enable` + `Run` 两条命令 + 何种故障严重度触发，具体阈值留 Open Questions 由 Paul 定）。

### D6. 安全：`.env` 文件权限方案（不用 macOS 钥匙串），FileVault + SSH 仅限 LAN

**决策**：
- FileVault 全盘加密 + 登录口令（Paul 已定，本设计确认兼容——LaunchDaemon 不依赖 GUI 登录解锁钥匙串，见下）。
- 凭据统一走 `5-平台底座/.env`（`WECOM_AIBOT_BOTID`/`WECOM_AIBOT_SECRET`/GitHub PAT/`WECOM_WEBHOOK_URL`/各部门群 webhook），`chmod 600`，不用 macOS 登录钥匙串（`security` CLI/Keychain Access）存放。**理由**：D4 选择了 LaunchDaemon（系统级、可在无人登录时于开机后就启动），而 macOS 登录钥匙串默认在用户登录时才解锁——若把凭据放钥匙串、又想让服务在无人登录的情况下开机自启并读到凭据，需要额外配置（如钥匙串密码与登录密码同步、或系统钥匙串而非登录钥匙串），复杂度增加且与 Windows 侧现状（同样是明文 `.env` 文件 + 文件权限+磁盘加密两层防护，未用 Windows Credential Manager）不一致。保持两端方案一致，降低认知负担与实现成本，代价（`.env` 文件本身是明文，安全性依赖 FileVault 静态加密+文件权限）与现状持平，不倒退。
- SSH（Remote Login）仅限 LAN 访问（macOS 防火墙/路由器层限制，不对公网暴露），用于 D3 的单向归档同步与日常运维登录。
- IT 备案：本设计不替 Paul 做这个决定，见 Open Questions。

## 跨平台改造点核实结果（对应总线草案 §三，逐项核实而非照抄预判）

| 组件 | 总线草案预判 | 核实结果 |
|---|---|---|
| `aibot_service/` 核心业务代码 | "预期跨平台零改" | ✅ **核实为真**：grep 全目录未发现任何 Windows 专属 API/路径耦合，仅注释提及部署脚本文件名。零改动。 |
| `wecom-aibot-python-sdk`（PyPI 依赖） | 未提及 | ⚠️ **未核实**——`pyproject.toml` 声明的可选依赖，本次未在 Mac 上实际 `pip install` 验证。**列入 tasks.md 第一步**：迁移一开始就在 Mac 上装这个包 + 跑 `scripts/check_connection.py`/`echo_test.py`，早发现早处理，不留到后期才踩坑。 |
| `start-aibot-service-dev.ps1` → macOS 外壳 | "→ macOS shell 脚本" | ✅ 方向对，但**内容不是逐行翻译**：D3 发现路径覆盖逻辑在 Mac 上大部分可以省略（单一 clone、默认路径即正确），脚本只需保留退避状态机+孤儿清理两块核心逻辑。 |
| `run-hidden.vbs` → ? | "计划任务→launchd天然后台(不需要)" | ✅ 核实为真，且原因比"天然后台"更具体：launchd 不创建可见窗口，该文件要解决的问题在 macOS 上根本不存在，无需任何替代物。 |
| 计划任务 → plist | "→ plist" | ✅ 方向对，补充决策：LaunchDaemon 而非 LaunchAgent（D4），退避逻辑留在 shell 脚本、不下放给 launchd 原生节流。 |
| 路径硬编码 → `.env` 化 | "`WECOM_AIBOT_QUEUE_PATH` 等指向 Mac 仓库副本" | ⚠️ **部分修正**：这些环境变量在 Mac 单一 clone 场景下大概率不需要设置（默认值已正确），`.env` 只需放凭据类变量，不需要放路径覆盖（D3）。 |

## Risks / Trade-offs

- **[Mac 侧 git 推送与 Windows 侧人工/CC 编辑几乎同时发生]** → D1 的 fetch-重算-重推循环 + 推送后立即完成（不批量攒行），把窗口压到最窄；3 次重试耗尽后降级本地暂存+告警，不静默丢数据（对比现状"完全没有兜底、只能靠事后人工比对 git 历史"，本身已是改进）。
- **`wecom-aibot-python-sdk` 在 macOS 上是否有未声明的平台限制** → 未核实，列为 tasks.md 首项验证动作，失败则需评估是否有替代 WS 客户端库（现有 design.md 记录过退化到裸 `websockets` 库的备选路径，若 SDK 真的不支持 macOS 可复用该评估）。
- **企微 aibot 协议对"同 BotID 双连接"真实行为未知** → D5 改为用独立测试 BotID 验证 Mac 侧代码，不用生产凭据做未经验证的双活测试；若 Paul 坚持要用生产凭据并行测试，需先做一次极短窗口（几分钟级）的双连接探测并观察审计日志，确认行为后再决定是否敢真正并行。
- **LaunchDaemon 以系统身份启动，早于任何用户登录** → 已通过 D6"不用钥匙串、纯文件权限"规避钥匙串解锁时序问题；剩余风险是 LaunchDaemon 默认以 `root` 跑（除非指定 `UserName`），需在实施时显式设置为一个非特权本地账号，避免不必要的权限放大（tasks.md 事项，非本次设计决策的阻塞点）。
- **SSH 单向同步脚本若方向写反，可能用笔记本旧数据覆盖 Mac 权威副本** → 脚本只实现"拉取"（Mac→笔记本单方向），不提供反向 push 的代码路径（结构性避免，而非靠人工记住方向）。
- **协议〇.7 编辑锁覆盖不到 Mac，容易被未来的 session 误以为"锁已经保护了所有写入方"** → 本设计文档 + 后续 `wecom-aibot-service/CLAUDE.md` 需显式写明这一边界，避免未来排查故障时误判。

## Migration Plan

1. Mac 环境就位：FileVault+登录口令 → 独立路径 `git clone`（非 iCloud/云同步目录）→ 装 Python + `pip install -e` 平台底座（`[aibot]` extra）+ 本服务 → **立即**验证 `wecom-aibot-python-sdk` 可安装可用（跑 `check_connection.py`/`echo_test.py`，用独立测试 BotID，见 D5）→ `.env` 就位（凭据类变量，不含路径覆盖，见 D3）→ 配置本地 git 身份为 bot 名义（D2）。
2. 新建 `queue_git_sync.py`（D1）+ 单测（含"模拟 fetch 时 origin 已前进，验证重算而非重放"的用例，仿照编辑锁 07-23 那次跨 worktree 回归测试的验证方法）。
3. launchd LaunchDaemon + `start-aibot-service-mac.sh`（D4）落位，白名单临时收窄到 Paul 自测（D5 独立测试 BotID 路径）。
4. E2E 真实验收（用独立测试 BotID）：归档 + 队列本地追加 + git 推送到 master 成功 + 转发 Paul + 群回执 + 哨兵沉默，五项全过；同时验证 launchd 崩溃自愈（故意 kill 进程观察退避重启）。
5. 换回生产 BotID/Secret（此时 Windows 侧仍是唯一生产连接，Mac 已切回配置但未启动）→ 原子切换（D5：背靠背执行"停 Windows + 起 Mac"）→ 盯审计日志确认单实例。
6. 满 48 小时观察期，`gap_alert` 零异常。
7. Windows 计划任务 `Disable`（非删除，冷备，D5）+ 一页紧急启用 SOP 落档。
8. 文档收口：`wecom-aibot-service/CLAUDE.md` 新增部署状态段（含"协议〇.7 覆盖不到 Mac"的边界说明）、根 `CLAUDE.md` §5 企微通道表述更新、跨桌任务队列本行回填。

**回滚**：任意阶段异常，`schtasks /Enable` + `/Run` 重新拉起 Windows 冷备（预期 5 分钟内完成，与 proposal.md 晋档条件一致）；Mac 侧 `launchctl unload` 停止 LaunchDaemon。回滚不涉及数据丢失风险——`7-外部文档`/队列文件的权威副本切换前后始终是同一个 GitHub 仓库 + Mac 本地磁盘，不存在"数据只存在于某一侧"的单点。

## Open Questions（需 Paul 拍板，非本设计可自行决定）

1. **D2 凭据方案确认**：接受"Paul 名下细粒度 PAT + 本地 commit 身份改 bot 名义"，还是坚持要新建独立 GitHub 账号？
2. **D5 并行测试路径**：接受"先用独立测试 BotID 验证 Mac 侧代码、不用生产凭据做未经验证的双活测试"，还是要求先做一次真实的短窗口生产凭据双连接探测？
3. **Mac mini 断电恢复自启**：是否已在 BIOS/固件层设置"来电自动开机"？launchd 只能保证"系统启动后服务自启"，管不到"断电后系统本身要不要自己开机"这一层，需 Paul/IT 现场确认。
4. **IT 备案**：此设备（办公室 Mac mini，7×24 跑企业内部服务）是否需要走 IT 资产登记流程？
5. **队列同步失败告警收件人**：沿用私信 Paul 本人，还是同时抄送孙涛（决策代理）？
6. **冷备触发阈值**：Mac 侧出现何种故障（如中断多久 / 连续几次自愈失败）时，Paul 认为应该临时重新启用 Windows 冷备，而不是等 Mac 自己恢复？
