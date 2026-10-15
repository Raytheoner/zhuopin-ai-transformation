## 1. 冻结设计和范围

- [x] 1.1 消费§四313对design v1及7路径的明确批准；只核本任务HEAD/已有diff，不重新扫描业务全景。当前主线既有脏文件保留，不新增恢复任务或后台消费者。
- [x] 1.2 主会话自行串行实施；预先记录首段测试节点和检查点，禁止派实现/审查代理。

## 2. 串行机器约束

- [x] 2.1 在test_guardian_adapter.py建立RED：省略并行参数仍只有1、大于1计划拒绝、并行旧计划启动前拒绝且executor/model调用为0/原记录不变。
- [x] 2.2 只改guardian_adapter.py最小计划/执行入口，GREEN后记录第一个检查点；保持正常串行阶段推进和历史只读兼容。

## 3. 默认流程与规则同步

- [x] 3.1 同步AGENTS.md、场景建造规则、Codex lane-watch适配、源lane-watch、handoff README为单主会话标准模式，取消普通新任务默认headless和模型互审；冻结旧合同/安全人工审查/具体ff权限仍明确。
- [x] 3.2 将切片输入、定向测试、检查点、最终完整回归写为唯一默认运行步骤。旧技能全文只保留发生过的历史说明，不让当前并行/子分支push要求与新入口冲突。

## 4. 验证与交付

- [x] 4.1 单主会话按受影响节点定向验证；全部代码收敛后从handoff子项目根实跑全部12个现存测试模块并保留原文/JUnit/命令与HEAD绑定；569 collected: 565 passed，4 skipped。4个skip均由JUnit逐例证明当前Windows symlink缺少WinError 1314特权，作为环境限制披露，不称分支已覆盖。（写前实测当前基线为12模块；原13数来自未ff的旧kernel，不增空模块或借用未授权源码。）
- [x] 4.2 自查最终白名单diff、入口一致性、拒绝零副作用和无模型review默认；不再派形式审查代理或改既有断言掩盖缺陷。
- [x] 4.3 候选、R5与正常队列登记已收口。原候选 `6ceb68403023826ad37de88a0398e3e7e741a728` 在用户明确1A授权下重基到 `master` `55ac0a9b6877c172b35af452b27806a1938f5851`，保留主线原7个提交；重基后、快进前 `master...candidate=0/3`，候选tip为 `a975787cee581b66edf382f0b1340b08c853fc1f`。回归回执见 `reports/lane-watch-serial-1014/full-004caa44/receipt.json`；其13个Python源码SHA256与重基后候选逐一匹配。严格OpenSpec校验通过。只将本次两个重叠目标文件存入路径限定可恢复stash，未清理其它主仓改动。
- [x] 4.4 本地 `git merge --ff-only codex/lane-watch-serial-1014` 已完成；机制实际进入 `master`（快进目标 `a975787cee581b66edf382f0b1340b08c853fc1f`）。主线规则保留PC-MVP优先段，以批准的单主会话串行条款取代旧并行条款。无push、无生产部署；具体业务ff、安全审核、业务审批及旧冻结合同仍按原规则执行。

## 实施检查点

§四313已按批准SHA消费，主会话串行实现，未派实现或review代理。新增21例先RED（21 failed）；直接模块首轮58 passed/1 failed，旧双opener用例与串行新合同不符，改为验证第二片缺失opener时不启动。随后完整直接模块59 passed，回执155567d20351a20482c2d5b9229c7f995bc91413d0e52f8bafa6f04fb4816437。完整回归已于HEAD 1c5605a4249e3a4fdd80cabda1fa1164d7979125完成：565 passed、4个Windows WinError1314 symlink skip，exit 0；receipt SHA256 b45a84fbd4d10bdc7db5fcf0df32256df706cdddf54cb253fb33edae2fdae311。详细原因与停点见下。

## 最终收口（2026-10-15）

机制候选已重基并本地快进合入 `master`，快进目标为 `a975787cee581b66edf382f0b1340b08c853fc1f`。完整回归仍绑定代码HEAD `1c5605a4249e3a4fdd80cabda1fa1164d7979125` 的13个Python源码哈希（重基后13/13一致）：12个模块共569项，565 passed、4 skipped，exit 0；4项均因Windows `WinError 1314` 无法创建符号链接权限而跳过，仍不计为通过。重基后严格OpenSpec校验通过。

主仓其它既存未提交、未跟踪和删除项均保留。合入前两份重叠目标文件以路径限定stash保全，回退refs为 `codex/lane-watch-serial-1014-pre-rebase-20261015` 和 `codex/lane-watch-serial-1014-main-preff-20261015`。本轮机制改造到此收口，不新增机制课题。
