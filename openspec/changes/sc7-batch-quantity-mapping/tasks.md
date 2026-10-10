# Tasks: SC7 标准化批量数量合成证据

## 文档准备

- [x] 整理 #125/#403 已答业务口径、当前代码边界和 Stage 0 架构候选；根修正操作者/摘要/落盘验收合同，并经独立 Luna 复审，形成供审四件。

## 设计与实施闸

- [x] 审阅并书面批准正式 design（本人 call_ddN5hY9Ddcj2KikNHxd1F2uV/0 A，2026-10-10；已答勿重做）：SC7 私有模块边界、标准化映射合同、hash/snapshot 内容、JSONL 成功条件与失败语义。
- [x] 独立批准具体实施计划和逐文件白名单；未批准前不得开始代码实现。

## Stage 0 合成实现（仅在前两项获批后）

- [x] 新增纯映射函数：严格校验 Supplier material ID 集与 mapping key 集相等；拒绝非严格正整数；以新 Supplier 对象设置相同 MOQ/MPQ；保留输入顺序与其他字段。
- [x] 新增 Stage 0 evidence entry：要求 synthetic fixture ID/revision/source/evaluator；完整七字段严格类型快照及三层非自引用 SHA-256；独立空 JsonlSink 写后严格回读本次唯一事件全字段，再核链 ok/total=1 后才返回成功。
- [x] 对完整/缺 key/额外 key/非法 value/纯空白与带首尾空格 ID/相同物料多供应商/顺序与对象不可变/逐字段类型/hash 稳定与来源变化/非有限数和不可序列化对象/audit 类型错误、写失败、空文件、错误或重复事件建立批准范围内的测试。
- [x] 逐项目运行批准的定向测试、检查差异及独立 review；不得修改共享 connector、模型、算法、`run_sc7()` 或 K2 默认交期。

## 后续真实数据阶段（不属于本 change 自动执行）

- [ ] IT 提供并核验 ItemMaster raw 请求/响应、物料自证、权限/组织、类型/单位、缺值和重复行语义；另行设计 raw adapter 与 query 白名单。
- [ ] 为 raw adapter 单独取得设计/计划/实现批准；先检查 raw duplicate/conflict，再规范化为 mapping；独立验证真实来源与审计。
- [ ] K2 仅在真实读取单独授权后核验既有统计器的数据卫生和样本分布，交采购专业人员签认；参数采用另行批准，未批准前 `lead_time_days=30` 保持不变。

具体计划已登记 `docs/superpowers/plans/2026-10-10-sc7-batch-quantity-mapping.md`；具体计划本人 call_kDMLTzO69DQEhhJ7zYFE2HHQ/1 已批；两文件合成实现及唯一测试57项通过、独立复审完成，结果见《SC7标准批量合成首项实现结果-2026-10-10》。原冻结输入tasks SHA B260…F129留于Native design-input不追改，后续真实阶段仍未完成。
