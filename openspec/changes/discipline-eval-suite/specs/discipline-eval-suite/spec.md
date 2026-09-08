## ADDED Requirements

### Requirement: 纪律 eval 套件 SHALL 只覆盖「今天没有任何机器守」的纪律形态
一期套件 SHALL 只含三条题：`%ERRORLEVEL%` 解析期展开导致假 0（eval-5）／写侧日期未当场重取
（eval-6）／提方案前未先查环境已有能力（eval-7）。

已有 hook、lint 或反例单测覆盖的纪律形态 MUST NOT 进入一期；把它们纳入 MUST 以「回归网二期」
的名义单独立项，MUST NOT 与一期混编。

新增一条题前 MUST 先做一次守卫盘点并把实测结果写进变更包；MUST NOT 以「应该没有守卫」这类推断
作为纳入依据。

#### Scenario: 已有机器守的形态被挡在一期外
- **WHEN** 有人提议把「从名字推断性别」纳入一期
- **THEN** 该提议被拒，理由为 `0-学习与工具/hooks/sentinel-pronoun.ps1` 已覆盖该形态，且该文件的
  存在经实测确认

#### Scenario: 纳入依据必须是实测
- **WHEN** 一条新题的纳入理由写的是「据我所知没有守卫」
- **THEN** 该理由不成立，MUST 补一次 grep／`git ls-files` 级别的实测记录后再判

---

### Requirement: 每道题 SHALL 带诱饵，且断言 SHALL 带反例
每道 eval 的冻结情境 MUST 让错误做法看起来更省事、更自然，且**错误做法执行后不报错**。
不含诱饵的题 MUST NOT 计入套件——照着规则背一遍就能过的题不构成检验。

每条 `expectation` SHALL 附一句「反例」，说明什么样的输出看着像过其实没过。
只写正面断言而不写反例的题 MUST 在 design 审被打回。

#### Scenario: 无诱饵的题被打回
- **WHEN** 一道题的 prompt 直接问「写日期时应该注意什么」
- **THEN** 该题被判为无诱饵（正确答案就是复述规则），不计入套件

#### Scenario: 断言缺反例被打回
- **WHEN** eval-5 的断言只写「使用了 `$LASTEXITCODE`」
- **THEN** 该断言被打回，须补反例「写了 `$LASTEXITCODE` 但整段仍包在 `cmd /c` 里 ⇒ 不算过」

---

### Requirement: 套件 SHALL 维护一份「纪律在库载体坐标表」并在运行前校验
`evals/rules-locus.json` SHALL 为每道题记录该题所守纪律的在库载体：文件路径、锚点字符串、
最后校验日期。

runner 启动时 MUST 先校验每条锚点在其载体文件中仍存在；任一锚点不存在时 MUST **fail-loud**
判红，判词 MUST 写明「该纪律的在库载体已消失，eval 无靶可打」，MUST NOT 跳过该题后照常跑其余题
并报绿。

坐标表 MUST 入库（不得被 `.gitignore` 覆盖）。

#### Scenario: 纪律被瘦身瘦掉时套件变红
- **WHEN** 某条纪律的原文在一次文档瘦身中从 `.claude/rules/` 消失，而无人执行退休判定
- **THEN** 下一次运行时锚点校验失败，套件判红并指名该纪律与其载体路径

#### Scenario: 载体迁址后坐标表须同批更新
- **WHEN** 一条纪律从 `CLAUDE.md` 迁入 `.claude/rules/`，锚点字符串一字未改
- **THEN** 锚点校验失败，且修复方式 MUST 是更新坐标表的路径，MUST NOT 是删掉该题

---

### Requirement: 套件 SHALL 以「注入回归」而非「跑绿」作为可信性依据
每道题 MUST 至少捕获一次**人为注入的回归**——把对应纪律从其在库载体摘掉后，该题 MUST 变红。

「每天在跑、全绿」MUST NOT 被接受为通过依据。未完成注入回归的题 MUST 标注为「未验证」，
且该题 MUST NOT 被用作任何人守规则退休判定的依据。

注入回归 MUST 逐题记录：摘掉的是哪个载体的哪一句、变红的是哪几条断言。

#### Scenario: 未做注入回归的题不得用于退休判定
- **WHEN** eval-6 连续两周全绿，但从未做过注入回归
- **THEN** 它 MUST NOT 被用来论证「写侧日期那条人守规则可以降为指针」

#### Scenario: 注入后仍绿即判题目失效
- **WHEN** 摘掉 eval-7 的靶点句后该题仍然全绿
- **THEN** 该题被判为无效题（断言与纪律无因果关系），MUST 重写而非保留

---

### Requirement: 冻结情境 SHALL 脱敏，且 MUST NOT 含 OEM 技术数据
入库的冻结情境与夹具 MUST 先脱敏并逐条过目。任何 OEM（比亚迪／上汽／理想等）技术数据
MUST NOT 出现在 `evals/` 下的任何文件中。

带时间语义的夹具 MUST 动态生成，MUST NOT 写死一个日期常量——写死会在某个运行日与真实当日
重合，使断言假通过。

#### Scenario: 回件语料入库前须脱敏
- **WHEN** 二期拟取某封专员回件片段作冻结情境
- **THEN** 入库前 MUST 脱敏并逐条过目；含 OEM 技术数据的片段 MUST 换用其它语料

#### Scenario: eval-6 夹具的日期不得写死
- **WHEN** eval-6 的夹具把「上文已记录的时间」写死为某个常量日期
- **THEN** 该夹具被打回，MUST 改为按运行日回推生成

---

### Requirement: eval 报告 SHALL NOT 默认对外发布
运行 eval 时 MUST 显式关闭报告的对外发布（如 `claude plugin eval` 的 `--no-publish`），
MUST NOT 依赖该工具当前的默认值不变。

CI 中该开关 MUST 写死在 workflow 文件里，MUST NOT 由运行时环境或个人配置决定。

#### Scenario: CI 不得把含内部纪律原文的报告发到外部
- **WHEN** CI job 调用 eval 而未带关闭发布的开关
- **THEN** 该 workflow MUST 被判不合格，理由为报告含队列行片段与内部纪律原文

---

### Requirement: eval 的 CI 作业 SHALL 独立成 workflow 并自带编码与成本约束
本套件的 CI 作业 MUST 落在独立的 workflow 文件中，MUST NOT 并入 `.github/workflows/ci.yml`
——并入会改变既有全部作业的触发面，并让每次 push 都可能计费。

该 workflow MUST 自带 `env: PYTHONUTF8: "1"`——workflow 级环境变量不跨文件继承，而本套件的
情境含大量中文，`windows-latest` runner 的默认编码为 cp1252。

该作业 MUST 设置成本上限；预算触顶与断言失败 MUST 以不同的退出码区分，MUST NOT 合并成一种红。

`.github/workflows/ci.yml` 中 `secrets.` 的命中数 MUST 保持为 0。

#### Scenario: 新 workflow 缺 PYTHONUTF8
- **WHEN** 新 workflow 未设 `PYTHONUTF8` 而作业输出含中文
- **THEN** 该作业以 `UnicodeEncodeError: 'charmap' codec` 失败，与本仓库首次真实 CI 运行同因

#### Scenario: 预算红与断言红不得混为一谈
- **WHEN** 一次运行因触及成本上限而中止
- **THEN** 报告 MUST 标明这是预算中止而非纪律回归，退出码与断言失败不同

---

### Requirement: 阈值 SHALL 由实测方差得出，且一期 MUST NOT 从满分起步
通过阈值 MUST 由「连跑 5 轮记录 pass_rate 均值与 stddev」得出，MUST NOT 直接拍定。

一期阈值 MUST NOT 设为 1.0。一期作业 MUST NOT 阻断合并；切换为阻断式门禁的前提 MUST 是三道题
各自完成过一次注入回归。

#### Scenario: 上线首日即红的门禁会被习惯性忽略
- **WHEN** 一期把阈值设为 1.0 并阻断合并
- **THEN** 该配置被打回，先例为 `opener-block-lint` 与 `claude-progress-lint` 两个作业刻意
  不加 `--enforce` 的既有判断

---

### Requirement: 运行产物 SHALL 不入库，题目与坐标表 SHALL 入库
`evals/` 下的题目文件、夹具与 `rules-locus.json` MUST 入库——它们是黄金集。

运行产物（含模型输出全文的运行树、聚合结果、HTML 报告）MUST 落在已被 `.gitignore` 覆盖的路径下，
且该覆盖 MUST 以 `git check-ignore -v` 的实际输出确认，MUST NOT 以推断代替。

若选用的跑法会自动生成一种此前不存在的文件名形态（例如往 `.claude/commands/` 写临时命令文件），
则 `.gitignore` MUST 在同一批次内补上对应规则并以 `git check-ignore -v` 实测坐实；
「我们不会跑它」MUST NOT 作为不补规则的理由。

#### Scenario: 运行产物落在未被忽略的路径
- **WHEN** 运行产物被写到仓库根下一个未被 `.gitignore` 覆盖的新目录
- **THEN** 该路径被判不合格，须改落到已覆盖路径或同批补规则并实测

#### Scenario: 临时命令文件形态须同批补忽略规则
- **WHEN** 选用的跑法会往 `.claude/commands/` 写形如 `<name>-skill-<hex>.md` 的临时文件
- **THEN** `.gitignore` MUST 同批补上该形态，并以 `git check-ignore -v` 实测确认命中
