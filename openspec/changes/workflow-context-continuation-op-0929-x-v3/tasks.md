# 【Codex】D3 后续任务（未授权执行）

本次交付仅设计文件。以下未勾选项均为未来阶段，不承接旧 tasks，不复用旧 thread 或 v2 失败现场。OpenSpec 任务清单的复选框仅供机器识别，不代表要求用户点击。

## 1. 外层校验与设计批准

- [ ] 1.1 外层运行 `openspec validate "workflow-context-continuation-op-0929-x-v3" --strict`，保存实际命令、回显、退出码与产物哈希；失败即停，模型 sandbox 不运行 CLI。
- [ ] 1.2 完成 D3 设计审，明确 taskkill 成功报告加根进程 wait 的证明边界及复核责任人；不把 strict 成功当设计批准。
- [ ] 1.3 外层重核真实队列/intent、独立工作树与新 HEAD，封存设计 hash，取得绑定该 HEAD/hash 的逐文件 allowed_paths 实施批准；不沿用旧授权。

## 2. 生产证据写入（批准后）

- [ ] 2.1 在获批 provider 测试文件先写失败用例：process 身份、pending、taskkill 原始 bytes/返回码、父进程 wait 观察及异常清理保留；确认 RED 原因符合契约。
- [ ] 2.2 在获批 `model_provider.py` 中实现 D3.2–D3.3，使用现有 process.json/result.json 及原子写入，不改 context 阈值、timeout、resume 或消费者开关。
- [ ] 2.3 验证正常 Windows 路径完整取证；已退出、非零、超时、fallback、写盘失败和清理重入均不能产出可接受报告。保留已有 stop_child 调用行为的回归覆盖，不删除断言掩盖失败。

## 3. Fail-closed 消费（批准后）

- [ ] 3.1 先为 D3.4–D3.5 编写参数化失败用例，包括 bool 冒充整数、旧版缺字段、输出缺失/哈希不符、错 PID/attempt/workspace、路径逃逸、时间倒序和 context_stopped 掩盖 error。
- [ ] 3.2 在获批 Workflow 接缝实现只读 D3 判定，由外层封存生产文件再验证；D3 satisfied 不自行启动承接、不释放不确定锁、不视为交付通过。
- [ ] 3.3 对每个负例断言下一次 provider 启动次数为 0、现场与锁未被删除、旧 attempt 未被覆盖；正例仅通过 D3，不绕过其余承接和授权闸。

## 4. 隔离验证、review 与发布准备（另行批准后）

- [ ] 4.1 跑生产 writer→文件→真实 verifier 的正反例链，区别 mock 注入与原生 Windows 结果；禁止手填 JSON 充当唯一正例。
- [ ] 4.2 在全新隔离 Windows 夹具创建自有父子进程，执行真实 taskkill /T /F 及 wait；测试侧独立观察子句柄退出，保留原始结果。不得触碰 v2 或旧任务进程。
- [ ] 4.3 按现时 CI 矩阵/项目选择器，在各受影响子项目 cwd 执行批准范围内测试 node-id；保留完整命令、退出码、stdout/stderr 与哈希，失败停止，不能声称根目录混跑等同逐项目验证。
- [ ] 4.4 完成绑定 implementation HEAD 的独立 review，逐项审查 D3 谓词、异常覆盖及其他守卫无回归，形成发布准备证据；不自动 ff、部署或外发。

暂不归档：本阶段未实施，strict 及以上任务尚未完成。部署阶段只引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md` 正本。
