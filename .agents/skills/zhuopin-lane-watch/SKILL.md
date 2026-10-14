---
name: zhuopin-lane-watch
description: Use when Shao Peishen asks to start lane watch or requests read-only progress. Default is one foreground session, serial slices, test-first acceptance; no automatic implementer or reviewer agents.
---

# Codex 泳道看护入口（§四313，2026-10-14）

先读根AGENTS.md，再定向读正本`0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`。普通默认主会话自行串行实现，当前片测试与检查点完成后立即下一片；不自动派实现/review代理、并发泳道、Guardian --run或无头批处理。已批目标/design/tasks不逐片重审。

每片仅输入目标/版本/必要函数/失败用例/下一步/禁项；不重复全景、全历史或巨大旧计划。用invoke解析的隔离Python，在对应项目根运行定向pytest；最终候选跑对应项目完整回归和功能/audit自动验收。普通代码不增加模型形式review。用户明确要求独审、冻结旧Workflow合同及安全相关人工审查仍按对应范围执行。

具体候选ff仍逐项授权；干净主线、可快进且测试/范围绑定有效才复用原工具ff-only并更新R5。主线当前master，不自动push、生产、外发或修改凭据/权限。旧状态/锁不因新默认而释放或伪造成功。写队列/共享文档仍acquire→写→登记→release，只读队列仅专用查询。

## 看看泳道：只读

使用当前Windows仓库正式入口，结构化截取必要字段，不把整份状态灌入上下文：
1. 从工具-泳道看护状态机.py show --json返回的lane映射中，只取非终态lane/status/batch，去重batch。
2. 对返回的batch调用invoke.ps1 -Mode Guardian observe --batch，再对返回task_id调用Mode Workflow status --id。
3. 报告真实phase/last attempt/busy/thread/证据；缺thread为未知、不估百分比。旧引擎无批次绑定单列，命令失败/权限不足/状态损坏不能混作完成。
只读查看不调用start/advance/resume/recover/retire，不创建模型或修改私有state。Python从主仓或Git common-dir定位.codex/runtime.local.json的python字段；不安装依赖、不用全局editable替换。

## 用户明确选择旧headless时

仅该明确授权允许派生，全部显式gpt-6-luna/high；wrapper不能指定时先核目标版本确实强制Luna，不允许继承。新计划/启动并行度只允许整数1；旧并行计划先拒绝启动、记录原件保留。不把调用参数或技能模板当intent/design/ff/部署授权。
沿README的真实旧stage合同运行，不写假review或成功记录。正常hooks信任及必要前置缺失时保全，只阻断对应依赖。涉及.51只引用zhuopin-lan-closeout正本，不复制程序或执行源端Claude/Cowork专属API。没有真实调度器不得声称会自行继续。
