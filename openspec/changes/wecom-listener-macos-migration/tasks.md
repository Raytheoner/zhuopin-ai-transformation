## 0. 前置拍板（阻塞项，未完成前不进入实施）

- [x] 0.1 Paul 就 design.md「Open Questions」六项逐条拍板（凭据方案/并行测试路径/断电自启/IT备案/告警收件人/冷备触发阈值）——2026-07-24 拍板落字，见 design.md Open Questions 段
- [ ] 0.2 Paul 确认 Mac Studio 到位可用（物理设备、网络、初始系统账号）——待办，随 §1 一并现场确认

## 1. Mac 环境搭建

- [ ] 1.1 FileVault 全盘加密 + 登录口令设置
- [ ] 1.2 独立路径 `git clone`（非 iCloud Drive/任何云同步目录）
- [ ] 1.3 安装 Python + `pip install -e` 平台底座（`[aibot]` extra）+ 本服务，**立即**验证 `wecom-aibot-python-sdk` 在 macOS 上可安装可用（风险项，design.md 未核实清单第一条）
- [ ] 1.4 本地 git 身份配置为 bot 名义（D2，取决于 0.1 的凭据方案拍板结果）
- [ ] 1.5 `.env` 落位（仅凭据类变量，不含路径覆盖，D3）+ `chmod 600`
- [ ] 1.6 SSH（Remote Login）开启，限制仅 LAN 可达（D6）

## 2. 队列 git 同步能力（D1，新增）——**✅ 全部完成（2026-07-24，CC，Windows 侧可完成部分）**

- [x] 2.1 新增 `aibot_service/queue_git_sync.py`：本地追加成功后 commit + push origin/master
- [x] 2.2 推送冲突处理：fetch → `reset --mixed` 对齐分支指针+索引到远端最新 → `checkout -- <file>` 只重置队列文件工作区内容 → 重新调用 `append_pending_task()` 重算编号 → 重新提交推送（非 rebase 重放）
- [x] 2.3 重试上限（3 次，`DEFAULT_MAX_RETRIES`）+ 每次间隔退避（`DEFAULT_BACKOFF_SECONDS`，可注入 `_sleep` 供测试）
- [x] 2.4 降级路径：重试耗尽 → `reset --hard` 仓库回到与远端一致的干净状态（丢弃基于过期基线算出、编号可能已不准确的本地 commit）→ 写本地暂存文件 `reports/pending_queue_appends.jsonl`（记原始参数，非可能过期的行文本）+ `queue_sync_degraded` 审计事件 + 私信告警（`_send_degraded_alert`，形状仿 `gap_alert` 但用独立审计 action 名，同款主通道失败转 webhook 兜底）
- [x] 2.5 单测（`tests/test_queue_git_sync.py`，10 个用例全绿）：推送成功场景 / 冲突后重算场景（真实 bare origin + 两个 clone 模拟并发写手，断言重算出的编号大于对方已推送的编号、非重放撞号）/ 重试耗尽降级场景（断言 `pushed=False` 且仓库回到与远端一致）/ 非冲突类失败保留本地 commit 场景 / 降级不阻塞归档主流程（异步包装 `sync_after_archive` 全程不向上抛异常，含 `repo_root` 非法场景）
- [x] 2.6 `run_aibot_service.py` 接入：`intake.py::IntakeResult` 新增 `queue_append_kwargs` 字段（供 git 层冲突重试原样重算）；`connection.py::on_message` 归档成功后新增第 4 条独立 try/except 路径调用 `sync_after_archive`（与既有群通报/转发 Paul 路径同构，互不影响）；`build_connector` 新增 `repo_root`/`pending_queue_appends_path`/`queue_sync_fallback_send` 等可选参数，未传时（如既有测试）整条同步路径跳过，向后兼容
- 全量回归验证：120 passed 1 skipped（本服务）+ 218 passed 1 skipped（平台），零回归

## 3. launchd 常驻自愈（D4）

- [ ] 3.1 新增 `start-aibot-service-mac.sh`：三级退避（60/300/900 秒）+ 稳定运行 1200 秒退避归零，逻辑照搬 `start-aibot-service-dev.ps1` 状态机
- [ ] 3.2 孤儿进程清理：`pgrep -f run_aibot_service.py` + `pgrep -f start-aibot-service-mac.sh`（排除自身 PID）
- [ ] 3.3 日志：日期戳文件名，写入 `reports/`（gitignore）
- [ ] 3.4 LaunchDaemon plist（`/Library/LaunchDaemons/`）：`RunAtLoad` + `KeepAlive`，显式指定非特权本地账号（不用默认 root）
- [ ] 3.5 系统设置关闭"电源适配器供电时睡眠"
- [ ] 3.6 故意 kill 进程验证自愈：确认退避重启行为与日志记录正确

## 4. 归档单向同步脚本（D3）

- [ ] 4.1 笔记本侧 SSH 拉取脚本（Mac → 笔记本单方向，仅 `rsync`/等价工具的只读拉取，不提供反向 push 代码路径）
- [ ] 4.2 手动触发验证一次（非常驻自动同步）

## 5. 独立测试环境验证（D5 保守路径）

- [ ] 5.1 企微后台新建独立测试 BotID/Secret（不用生产凭据）
- [ ] 5.2 Mac 端用测试凭据跑通 E2E：连接 + 归档 + 队列本地追加 + 队列 git 推送成功 + 转发 Paul + 部门群回执 + 对账哨兵沉默（五项全过，对应 proposal.md 晋档条件第 1 项）
- [ ] 5.3 launchd 崩溃自愈联调验证（对应 3.6，用测试凭据环境跑一次完整链路）

## 6. 生产切换

- [ ] 6.1 白名单/部门映射/群 webhook 等生产配置换回真实值（此时仍不启动，先就位）
- [ ] 6.2 准备"停 Windows 计划任务 + 起 Mac 服务"背靠背执行的操作序列（脚本化或逐条命令预先写好，不临场现想）
- [ ] 6.3 选定切换窗口（低流量时段，取决于 0.1 拍板结果）
- [ ] 6.4 执行切换：`schtasks /End` 停 Windows → 立即启动 Mac LaunchDaemon → 盯审计日志确认 `authenticated` 事件在预期时间内出现且全程仅一条（防双实例，对应 proposal.md 晋档条件第 3 项）

## 7. 观察期与冷备收口

- [ ] 7.1 满 48 小时观察，`gap_alert` 零异常中断记录（对应 proposal.md 晋档条件第 2 项）
- [ ] 7.2 Windows 计划任务 `Disable`（非删除）
- [ ] 7.3 撰写"紧急启用 Windows 冷备"一页 SOP（`Enable` + `Run` 两条命令 + 触发阈值＝**连续 3 次自愈全部失败**，2026-07-24 已拍板），验证 5 分钟内可执行完成（对应 proposal.md 晋档条件第 4 项）

## 8. 文档收口

- [ ] 8.1 `5-平台底座/wecom-aibot-service/CLAUDE.md` 新增部署状态段（含"协议〇.7 编辑锁覆盖不到 Mac，冲突防护改在 git 层"的边界说明）
- [ ] 8.2 根 `CLAUDE.md` §5 企微通道相关表述更新（Mac Studio 取代笔记本作为收件口）
- [ ] 8.3 跨桌任务队列本行回填 + 新产生的下游任务（如有）追加为待领行
- [ ] 8.4 `ops/wecom-service-home` worktree 按机房交接完成后的既定纪律清理（若确认不再需要）

## 9. 真实数据验证（N.1，本变更包收尾验收）

- [ ] 9.1 Paul 用真实企微账号在生产切换后实际发送一条消息，确认归档+队列追加+GitHub 可见+转发私信+群回执全链路在 Mac 上真实生效，非仅测试凭据环境跑通
