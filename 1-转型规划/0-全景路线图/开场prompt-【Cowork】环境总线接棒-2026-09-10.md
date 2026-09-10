---
title: "开场prompt-【Cowork】环境总线接棒-2026-09-10"
created: 2026-09-10
执行方: Cowork 环境总线（新开会话，OP-0910-H）
来源: OP-0907-AL 转场（转场判据①⑤阳性：压缩后事实漂移一处＋token 压力真实）
status: 待执行
---

# [OP-0910-H]【Cowork】环境总线接棒

▶ 首次派出：[OP-0910-H]
```
[OP-0910-H]【Cowork】环境总线接棒
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产改 `.md`） ｜ 工作区：无（纯库内，不触碰 `.51`／企微机器人／定时任务） ｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0907-AL
读 ① `1-转型规划/0-全景路线图/session接力-Phase1收口.md` → ② `CLAUDE.md` §3／§5 恢复上下文，按下述执行。本件为 A 类。

做什么：
1. 开工自检三查（不问）：读 `1-转型规划/0-全景路线图/session接力-Phase1收口.md` 全文；`python 0-学习与工具/工具-队列查询.py --digest`（机制）＋ `--digest --file 1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md`（业务）扫在办行与触碰区，命中再 `--row N --field all`；`python 0-学习与工具/工具-共享文档编辑锁.py status`；本机 `Get-Date` 取时。
2. 陈忱三个 8D 样本 zip 重发后核入档：查 `5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl` 中 `sender=ChenChen, msgtype=file` 是否走到归档（时间戳为 UTC，标基准）；成功 ⇒ 拆件班自动接 §一 `#540`（业），本线不代销；81.7 MB 那包若仍超时 ⇒ 只登 §四 兜底「共享盘给路径」，不改码。
3. 机制类可动 WIP 现 26/22（`#532` 补域后上涨，`_count_mechanism_wip` 实测）：按 `#454` 批量分诊出候选（done 未销／可并入／可 hold）报他定，不裸改任何行状态。
4. K2 行长 2026-09-11 起阻断：`#439` 状态列 >4096 B，走 `edit-row --changes-json` 整格重写并外置到 `1-转型规划/0-全景路线图/队列行日志/#439.md`；同法扫其余超长行。
5. 接力卡 §三 其余续项：`#439` 2.2／2.3（Cowork）；状态机记账滞后两泳道关闭；`队列回写待补/B-0908_AL4-*.json` 残留核后删。
6. 口令承接：他说「开启Opener OP-MMDD-X」⇒ 按 `.claude/rules/两桌同步与取证.md` §一 执行（【CC】⇒ 经 `0-学习与工具/工具-opener批处理执行v2.ps1` 先 `-DryRun -Yes` 再 `-FullAuto`；【Cowork】⇒ 就地）；他说「我已回Lan」⇒ skill `zhuopin-lan-closeout`；「开启泳道看护」⇒ skill `zhuopin-lane-watch`。

不做什么：
- 不 commit／不 push／不碰 `.51`／不发企微；对外发送／L2 门禁／合规红线／ASIL C-D 永不代办；🟡 档（ff 入 master／改判据阈值／design 审／关他人在办行）停等他一字母。
- 不新立机制行（26/22 已超限；出血除外，行内写 `WIP豁免：<理由>` 并 `--force-mechanism-wip`）；业务行不受 WIP 约束但归业务总线立。
- 不 Read／grep 队列真身；读队列只用 `工具-队列查询.py --digest／--row`。
- 产出任何 opener 一律先 Read `1-转型规划/0-全景路线图/opener骨架.md`，成品经 `工具-opener生成.py`（>500 字有文件 ⇒ `--variant reference`）＋ `工具-opener块lint.py --enforce --file`，禁手抄。
- 不改企微机器人代码；配置类改动（环境变量／重启监听）只在他明示授权后做、做完 `psutil` 回读实证并登 §二。

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit），由落库 sweep 取活。
```
