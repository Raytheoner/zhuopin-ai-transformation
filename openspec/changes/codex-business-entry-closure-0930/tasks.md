# 六入口收口实施计划

Goal: 按design.md完成六业务入口Codex适配及可追溯验收。Architecture: 复用现有Guardian/Workflow/队列/Aibot/provider接口，只补精确入口文档及隔离验收。Tech Stack: Python、PowerShell、Codex skills/native provider、OpenSpec。执行采用executing-plans与writing-skills；独立review保留。

## 1. 自举前置
- [x] 1.1 完成已批准四文件P1终止确认修复、定点回归、完整codex-handoff pytest与独立review；记录实际源码哈希。
  Evidence: workflow_state.py 的伪造恢复观察与直接 finish_attempt 均有 RED/GREEN 回归；目标回归 275 passed, 4 skipped；完整 codex-handoff 为 486 passed, 4 skipped（420.33s）；3 个此前环境权限失败项在 WhatIf/临时子进程条件下单独复验 3 passed；Luna 独立复核确认无残留问题。源码哈希与复核意见见 acceptance.md。
- [x] 1.2 新旧任务/批准/工作树证据分开，核#648现时开放且旧v5不在运行。
  Evidence: 官方 Workflow status 分别核对旧 v5 attempts=[]/busy=false 与 R3 三次终态 attempts/busy=false；官方队列 #648 为 open；详见 acceptance.md。

## 2. 入口文档与场景验证
- [x] 2.1 记录当前看看泳道/值周计划skill基线缺口；按design D1只改5个入口/说明文件。
  Evidence: 基线无效管道参数/缺少具体锁与Sweep流程、Guardian尚未迁移等差距已记录；D1入口变更限于允许的三个差异文件，另外两个既有规则按独立review确认保留。见 acceptance.md。
- [x] 2.2 验证查看口令：无batch、多batch、busy、暂停、损坏状态、缺线程证据；必须只读调用show/observe/status，不能启动或直接扫state。
  Evidence: 候选只读路径实测；status/observe相关定点回归37 passed、450 deselected；最新官方 show/observe/status 结果见 acceptance.md。
- [x] 2.3 新weekly skill引用原章程并映射Codex；根据现时队列产出当前计划，检查四节、≤10000B、日期/负责人/截止/承接、锁登记及写后反查。
  Evidence: 2026-09-30 计划 7,654 B/A–D 四节；官方行 B-0930_周计划入档回读为已完成；CommitSweep 自动落库提交 cd7fcb62 已同步 origin/master，当前编辑锁无锁。见 acceptance.md。
- [x] 2.4 核回LAN与跟进信Codex映射；off/unknown与未授权真实发送拒绝，源串行部署规程不复制不放宽。
  Evidence: 独立 Luna 复核确认入口拒绝条件及源规程边界；未执行真实部署或发送，见 acceptance.md 红/绿表。
- [x] 2.5 独立Luna技能情景复核，记录红/绿行为与最终文档hash.
  Evidence: 独立review六入口红/绿情景完成，五份文档SHA逐项核对；验收记录见 acceptance.md。

## 3. 原生回灌联验
- [ ] 3.1 建独立可信linked fixture，配置四个隔离env、Luna测试consumer、脱敏docx/README和两份合法队列；保存主仓/fixture边界证据。
- [ ] 3.2 从真实bridge与dispatcher启动native provider/watcher，验归档拆件/真实新队列行/信号处理/幂等/失败保留；不使用假Process代写。
- [ ] 3.3 用正式队列工具读取新行，生成fixture manifest并由Guardian选入；记录原生thread/hooks及delivery_accepted=false，不启动未经批准的业务任务。

## 4. 最终候选建造链
- [ ] 4.1 形成已review的bootstrap+入口提交，以该HEAD建立承接target与workflow-path-guard-v5-mvp-0930 task；新intent审批证据引用本包实际批准。
- [ ] 4.2 Guardian proposal阶段原字节复制原v5包并strict；核全部设计产物hash相同后按D3建立新实际task/HEAD批准绑定，保留旧v5。
- [ ] 4.3 同manifest恢复，运行实施→逐项目CI→不同原生thread只读review→release-prep；用看看泳道取得运行中及停点真实信息。
- [ ] 4.4 复核每项证据绑定最终HEAD；测试失败或未知终止时禁止下阶段，最多两次有界重试。

## 5. 集中放行与验收
- [x] 5.1 提供六入口验收矩阵：源码/隔离native/现场启用/实际业务结果分别标明，禁止用单任务绿冒称全量绿。
  Evidence: acceptance.md 矩阵明确记录 MVP 未通过、未闭合项和分层实测。
- [ ] 5.2 准备具体ff、patrol开关/模型/待消费范围、既有周报自动化完整更新，集中请求最后放行；此前不更改生产开关。
- [ ] 5.3 获准后按每项具体授权交付并复查；On LAN实际部署与外发按对象另行留证。队列/接力按锁工具登记，不提前关闭#648。
