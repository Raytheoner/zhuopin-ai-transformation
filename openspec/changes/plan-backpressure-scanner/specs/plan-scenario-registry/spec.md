## Purpose

为「规划倒逼开工」扫描器提供 35 个场景的**机读正本**（场景码／域／权威排期月／别名／同名排除项／暂缓标记），并以一条 CI 一致性校验保证它不会在全景规划权威排期表变更后静默过期——消灭"把一份会过期的场景清单硬编码进代码"这一取证件遗留问题。

## ADDED Requirements

### Requirement: registry 载体、格式与落点
场景 registry SHALL 以 JSONL 格式（每行一个场景对象）落在 `1-转型规划/0-全景路线图/` 目录下并纳入版本控制；MUST NOT 落在 `reports/` 或任何被 `.gitignore` 覆盖的路径下。

#### Scenario: registry 入库可见
- **WHEN** 对 registry 文件路径执行 `git check-ignore`
- **THEN** 退出码为 1（未被忽略），且 `git status -uall` 中该文件可见

#### Scenario: 每行独立可解析
- **WHEN** 逐行解析 registry
- **THEN** 每一行 SHALL 为一个独立的合法 JSON 对象，任一行解析失败 SHALL 使整个扫描以非零退出码失败并指明行号，MUST NOT 跳过该行继续

### Requirement: registry 字段集合
每个场景对象 SHALL 含以下字段：`code`（场景码）、`domain`（六域之一）、`title`（中文场景名）、`planned_month`（权威排期月）、`aliases`（别名列表）、`excludes`（同名冲突排除词列表，可为空）、`suspended`（域级暂缓标记，含来源与日期，可为空）。

#### Scenario: 排期月仅供展示
- **WHEN** 扫描器执行任一「是否未承接」「是否可开」的判定
- **THEN** `planned_month` MUST NOT 参与该判定；它 SHALL 仅出现在输出清单的展示字段中

#### Scenario: 暂缓标记必须带来源与日期
- **WHEN** 某场景的 `suspended` 非空
- **THEN** 其内容 SHALL 同时含来源（如队列行号）与生效日期；缺任一项 SHALL 被 lint 判为违规

### Requirement: 空置编号显式留行
已下架且不得重新分配的编号（`Q1`／`Q3`／`Q5`／`Q7`／`Q8`）SHALL 在 registry 中以 `retired` 标记留行；该类行 MUST NOT 参与任何承接判定，且 SHALL 被一致性校验视为"已知不在排期表内"，不计入差集。

#### Scenario: 退休编号不进扫描
- **WHEN** 扫描器遍历 registry
- **THEN** 带 `retired` 标记的行 SHALL 被跳过，不出现在未承接清单的任何一档中

#### Scenario: 退休编号不制造永久差集
- **WHEN** 一致性校验比对 registry 与权威排期表
- **THEN** 带 `retired` 标记的编号 MUST NOT 因"排期表中不存在"而被报为差集

### Requirement: 与权威排期表的一致性校验
SHALL 存在一条可在 CI 中执行的校验：从全景规划 §加速启动总览权威排期表逐格提取场景码，与 registry 中非 `retired` 的 `code` 集合做双向差集；任一方向非空 SHALL 使校验以非零退出码失败，并分别列出"排期表有而 registry 无"与"registry 有而排期表无"两组。

#### Scenario: 排期表新增场景未同步
- **WHEN** 权威排期表新增一个场景码而 registry 未同步
- **THEN** 校验 SHALL 失败并在输出中点名该场景码，归入"排期表有而 registry 无"

#### Scenario: 校验只比场景码
- **WHEN** 权威排期表的某个单元格内的中文标题、脚注、删除线或沿革注被改写，而场景码集合未变
- **THEN** 校验 SHALL 通过；一致性校验 MUST NOT 解析或比对中文标题、排期月或单元格内的自然语言内容

### Requirement: registry 不作为排期正本
registry MUST NOT 被任何流程当作排期的权威来源；全景规划 §加速启动总览权威排期表 SHALL 保持唯一权威地位，registry 与它的同步方向单一（排期表 → registry）。

#### Scenario: 反向同步被禁止
- **WHEN** registry 与权威排期表不一致
- **THEN** 处置 SHALL 为修改 registry 使其跟随排期表；MUST NOT 以 registry 为准修改排期表，也 MUST NOT 提供任何自动回写排期表的能力
