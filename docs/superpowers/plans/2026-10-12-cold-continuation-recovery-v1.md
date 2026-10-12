# 三项停点的有界冷接续计划 v1

## 1 真实终态与目标

本计划只消费现有成果与已有业务设计，不修改Guardian/Workflow/hook，不删除旧树/失败资产，不整批重做成功设计。原6A-v2已执行完指定两v2退役与四设计保全；7A实际启动SC2/FI14实现。本次两**v3**批的退役与两个新增外部树不在原限定范围，需本项明确批准。

- SC2：20:39–21:09（Asia/Shanghai）implement超时；实际Luna、原生context 171658，进程树终止证据保留，普通thread续跑只读资格检查false。原树10个白名单路径dirty，另有不可读`.pytest-tmp`警告；不是可验收实现。12个精确现有文件（包括未变report/webapp）已逐件复制并SHA到`reports/pc-mvp-1012/v3/sc2-partial-assets/`及manifest；临时目录不读不搬不删不改ACL。
- FI14：20:40–20:44规则核验后停下，零代码/测试；outer给`empty_changes`。父Test-Path确认财务目录和FI14本级CLAUDE均不存在，读取缺路径触发hook拒绝；不是缺财务业务资料。已存在的根/数字员工/场景合规规则仍完整执行，不补造缺文件或改守卫。
- FI5：20:48–21:08四件已写且父strict=0，但创建前`Get-ChildItem <本task目录>`退出1，使formal admission blocked。当前仅一项native tool failure，实际Luna；四件字节与父strict原文保留，不能当已正式design。
- QD-A：20:49–21:09四件outer strict通过，design正式封存HEAD`8b129752770c3cc73c4848b8a2937fcccb96d18a`、SHA`e08bb4863ddf21cb994186b7a1a662c3f190d2e7b5276552ef04c551ac7516a6`；独立审查及技术附录另供实际design审，不在本计划实现。

正式接口只读诊断`reports/pc-mvp-1012/v3/pc-continuation-contract.md`：普通implementation-blocked批没有原批resume通路；现时driver超时续跑只返回原thread，不支持改成新上下文。不能裸advance、替换sealed authorization、伪造accepted或靠清理绕过。因此SC2用新树/新task/新上下文；FI14原task原clean树在新单项批中继续。无工具改造。

## 2 唯一退役对象

只正式退役`B-1012_v3PC双设计保全`与`B-1012_v3两项接纳恢复`的未完成claims，保留所有历史。绑定当前官方公开计划身份在`reports/pc-mvp-1012/v3/cold-review-fingerprints.json`及两个public-plan-cold-review.json；执行前再次核observe、每task phase_status/busy/锁、live row、watch/manifest/plan SHA。具体指纹表由同一供审集合绑定；任一身份变化、running或completed row保留冲突即停对应依赖。

所有五份已成功设计（SC2/FI14/Q2/Q9/QD-A）原HEAD/SHA/原四件继续保全。Q2/Q9质量双设计批不退役、不改；已批准的质量计划准备独立推进。

## 3 两个精确新树、已有内容接纳及原任务复用

| 场景 | task / tree | 唯一工作 |
|---|---|---|
| SC2 | 新`sc2-three-metric-cold-1012v4`；`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai`，固定source`b2933132b733756b30b94e309e2066bbd50d6e43` | 先仅把原已封存四件**同字节搬到新namespace**，actual strict/outer commit；设计字节严格等于原已批SHA`9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e`时，允许父级将原设计批准机械绑定新task/新design HEAD。不能重新设计；不相等停止另审。 |
| FI5 | 新`fi5-wecom-pc-review-alignment-1012v4`；`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-fi5-admission/zhuopin-ai`，固定source`d6851ac082adfa1c0a7e74085bb0f4f7bd1ca206` | 仅把已成四件同字节搬到新namespace，先保全、actual strict/outer commit；design SHA必须等于`d74b3870da9298058d0c8e1abc5641fb543016fc6a1f2e857fcb7a1591b76e2f`。正式接纳后仍停实际design审，不能实现或继承旧批准。 |
| FI14 | 原`fi14-payment-plan-pc-mvp-1012v2`及原v2-fi14树 | clean/原design与原7A封存approval匹配后，在新单项批以新模型上下文继续原17文件计划；不是再prepare或proposal。 |
| QD-A | 原`qda-seven-step-extraction-1012v3`及原v3-qda树 | 在新单项批只claim保全已成功四件，authorizations为空，停design闸；零新proposal模型。 |

唯一新批次：`B-1012_v4SC2冷接续`、`B-1012_v4FI14实施接续`、`B-1012_v4FI5四件接纳`、`B-1012_v4QD设计保全`，各单项。新OP编号在生成器查重后分配，lane/row/task/actual tree绑定后冻结；旧OP保全只有生成器不支持的原号重用时沿骨架原成品搬运并lint。全球并行≤4、错峰≥90秒、所有派生显式gpt-6-luna。

新两树创建/attach后验证top/common-dir/sourceHEAD/clean。prepare可从相同固定source的既有linked checkout使用未修改官方入口；它按common-dir读取主仓live队列，source checkout与模型写树不同。所有原代码/原树保持，不把部分SC2源码预写到新产品目录造成dirty；只先复制到ignored reports输入。

为两机械四件搬运预创建**空**`openspec/changes/<新task>/specs/<原capability>/`目录，git仍clean，再prepare/派发；不提前写proposal/design/spec/tasks。不存在目录只用Test-Path bool。模型只复制已核四件和检查目标字节，不复写专业需求、不全仓探针、不运行OpenSpec（outer运行）。各单项提案4件唯一写区，两个新task四件身份JSON在`reports/pc-mvp-1012/v3/*-cold-four-piece-identity.json`。

## 4 产品实现范围

SC2冷接续计划v2：`docs/superpowers/plans/2026-10-12-sc2-three-metric-cold-implementation-v2.md`，SHA`32e7ef06172407f7b3745b65da10d5eb2d029426450b594087ac838810adf99d`。原7A冻结计划不改；本v2只换精确执行树/任务身份，增加部分资产只读复用和新上下文说明。**12产品/测试路径原样不扩**，列表为原实施集合v1第2节。先与新树基线对照，部分输入不等于accepted implementation；补齐report/webapp及兼容缺口，原TDD记录只作历史，新缺口做行为RED→GREEN，最后实际项目CI/独立Luna审查。

FI14继续原计划SHA`7cb1fe70ac82ecb7dd247410a6447e78b9762b13c8eb0becc808ef19eb00a383`、原17文件/附录与现已封存`fi14-7a.json`，不得改其字节或假造缺CLAUDE。新同字节输入索引列出真实存在的根/数字员工/合规规则、明确两缺路径的bool事实；旧INPUTS原副本保留为proposal-v2索引，新索引仅指路，不授予额外权力。

两项产品实现仍只合成/mock，不读取真实源/付款，不填G专业PENDING。CI固定隔离Python，分别场景根`-m pytest -q --tb=short --junit-xml=pytest-result.xml`，保留原退出/JUnit/hash/范围证据。SC2的不可读临时目录仅在旧树原位留存；新验证TEMP/TMP/basetemp只在新树ignored reports及主仓指定UUID验证目录。原thread不继续；父按原生context元数据与逐task状态看护，不把批级running当每task仍在运行，不声称未测通过。

## 5 新增仓库外及主仓范围（本项待批）

1. `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1012-v4-cold-continuation/`：两个具体retire证据、新task intent/LAN身份/本地stage证据、SC2新task标准implementation JSON；只在SC2新正式design字节等于上述已批SHA后机械填写actual新HEAD，text绑定本计划及SC2 v2全正文/12文件。FI14旧authorization只引用，不替换。
2. 既有runtime state/logs：上述两个old/四个new batch、SC2/FI5两个new task、原FI14/QD-A接续的claim/prepare/dispatch/stop/CI/review/封存；旧SC2/FI5 task、attempt/失败证据保全。原v3两批retire不会改其它任务或当作成功。
3. 第3节两精确新native trees：Git元数据/创建附着、ignored reports同字节只读输入、各自唯一新OpenSpec四件；SC2在actual同字节设计接纳后仅原12产品/测试文件及Git outer commit/验证副作用。FI5无产品实现/测试。
4. 原FI14树仅原7A17路径/证据/验证/outer Git；原QD-A树设计只读/正式driver保全。原SC2 dirty树只读精确12资产，不搬/删临时目录、不改ACL、不强制清理。主仓新UUID验证目录`reports/pc-mvp-1012/cold-implementation-verification/`，进程级环境，不改系统设置。
5. 主仓只准备两源行654/470在正式retire成功后的新task/lane锚、看护件、供审/执行留痕、R5/进展视图及锁登记。FI14/QD-A/Q2/Q9原源行full SHA不改。机械同字节SC2 design绑定不是新的业务design选择；内容/白名单改变即另审。

## 6 顺序、验收与答复

顺序：明确本计划与供审指纹→现场前检→两个v3整体retire→原FI14/QD-A单项保全→两个指定新树/空namespace/同字节输入→两机械四件接纳→SC2同字节设计身份机械绑定→SC2 v2/FI14原计划实现/CI/独审。独立步骤按资源并行，失败只停对应依赖。没有safe API就留具体停点，不能改工具或state让它绿。

验收：原五成功设计/全部旧资产保全；SC2新上下文确实消费部分资产且通过实际29文件内的各自CI/review，或明确真实停点；FI5获正式strict/HEAD/SHA且仍停design闸；QD-A不重做。无ff、生产、真实取数、付款、外发或专业签认授权。

9A（推荐）：批准本v1第2–6节限定两个v3退役、四小批、两个新树、SC2同字节设计机械绑定及冷接续v2/原FI1429文件、标准证据和验证范围。9B仅保全当前资产，暂不新增接续。本项无默认，未答不执行新外部范围或退役。
