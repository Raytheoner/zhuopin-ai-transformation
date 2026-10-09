# SC8规则2主仓对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans，沿用当前Native；一次绑定最终候选的独立review显式gpt-6-luna。步骤使用纯编号。

**Goal:** 将#660已获准、已在隔离树实施的P1 R2代码，与已ff的采购UI对齐为可审候选；交付新基线下的mock回归和范围证据。

**Architecture:** 以当时master为新隔离基线，复制13件源候选blob。唯一双边改动文件webapp.py保留当前UI，恢复R2的图例版本契约；不重写算法。新候选单独记录批准链，发布仍由原P1闸控制。

**Tech Stack:** 现有Python/pytest、Git、HTML/JS、平台bootstrap/audit；不加依赖。

**Spec:** `openspec/changes/sc8-atp-batch2-closeout/design.md`、`tasks.md`、`specs/delivery-date-forecast/spec.md`及已批准`docs/superpowers/plans/2026-10-03-sc8-rule2-literal-native.md`；本件是原已审业务设计的主仓对齐步骤，不新增判据。

**状态：2026-10-09T15:50:19.7432205+08:00 Shao Peishen已明确批准本具体计划及mock验证，沿用Native。原审批SHA与原文见`openspec/changes/sc8-atp-batch2-closeout/主仓对齐批准与执行.json`。** 原批准保留，#660写明“四CI/主仓对齐/ff另审”；该独立闸现已明确获批。执行进展据批准与执行记录和当前账本；Native继续，不新选执行方式。

## Global Constraints

- R2默认OFF且与R1独立；未来三自然月含边界沿原实现，不声称D4已专业签认；规则1/3、四色、ForecastParams字段、真实黄金期望不改。
- 已批准源候选`29c1ee92167a4f4bba217078c80cd97928b635a3`；共同基线`637fa6f6140afb43bf73acab5366b7cde8dae0cb`；准备时master`463922cabb4dd2644a5c8095c0074fdf35a7dbdb`。执行时再现取master，只有文档推进且SC8/平台产品树等价才允许同步；产品漂移即停止本依赖。
- 当前master的SC8门户UI与SC2完整子树保留；不把旧树覆盖到主仓，不复制旧源码配置/凭据/报告；本轮产品范围仅表列13件＋webapp.py和原UI测试文件，共15件。
- 所有测试逐子项目cwd，隔离Python `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`；PYTHONPATH为新树SC8根及新树`5-平台底座/zhuopin_platform`。不安装editable，不在根目录混跑。
- 本次计划只请求离网对齐与mock验证；真实黄金缺expected.json继续skip，不重建/重采或运行真实比较器。现有10-07报告只解析与核hash。
- ff、push、生产部署/CreationDate、启用、refresh、专业签认、外发/L2另审；P2不并入。原候选/树/dirty/旧失败保留；不建立后台调度。

## Review Focus

1. 双边webapp改动：保留已ff的读取超时/权限/最近已知快照/样式/notice；新图例调用传include_version=False，结果参数版本仍来自Snapshot。
2. R2 OFF/ON及四开关组合：沿用全部原构造用例，六个已单列批准旧测试只固定各自R2 OFF前提，不给全套强制OFF，不改原断言。
3. 新主仓基线/平台导入：候选SC8+平台树/HEAD与测试receipt绑定；禁止读到旧editable包还声称新代码已测。
4. 比较器安全契约：冻结来源SHA/客户身份/重复行顺序及Python -O不关闭guard，复制13blob逐件等价；mock CLI不许回退读真实文件。
5. 缺真实golden、D4零边界及真实颜色空过分别留步，不用构造性D5或119行报告补齐其签认/生产条件。

## 文件范围及接口

以下路径相对`4-数字员工/采购部/SC8-客户订单交期智能承诺/`。

| 文件 | 动作 |
|---|---|
| `sc8/baoguan.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `sc8/baoguan_service.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `sc8/config.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `sc8/forecast.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `sc8/kit_date_comparison.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `scripts/compare_kit_date_rule2.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `scripts/run_baoguan_dashboard.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_baoguan.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_baoguan_service.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_baoguan_webapp.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_kit_date_rule1_start.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_kit_date_rule2.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `tests/test_kit_date_rule2_comparison.py` | 源候选blob逐件复制；主仓相对共同基线无漂移 |
| `sc8/webapp.py` | 保留现master，只把现图例调用传include_version=False；现UI已含快照版本展示 |
| `tests/test_webapp_ui_contract.py` | 保留原UI全部用例，新增图例不显示现场参数版本的调用契约用例 |

治理只更新本计划、当前change发布准备/tasks/场景CLAUDE事实记录、R5/opener和660/§二；新的代码提交仅发生在获准隔离树。两UI包的已完成ff证据不重写。

### Task 1：冻结基线与构造图例红灯

**Interfaces:** `render_legend(params: ForecastParams|None=None, *, include_version: bool=True)->str`为源候选已实现接口；`_shell_page()->str`为当前UI入口。

1. 批准后查询660及队列锁、read approved scope；沿using-git-worktrees先列本聊天附件，创建或选择适合本对齐的隔离树。保留所有原树，不改源树。使用实际返回路径，不猜路径。将实际新树写入`reports/sc8-r2-alignment-1009/alignment-runtime.json`，键为`tree`、`master_base`、`branch`、`source_candidate`；branch取`codex/sc8-rule2-align-1009`，若已有同名先核归属且不重置。
2. 记录master、源blob、两侧SC8/平台tree、所有未提交文件SHA；查源13件与主仓共同基线无漂移、UI仍等于b146合入blob。任一产品前置改变则停止本候选，保留证据。
3. 在原UI契约测试文件末尾新增以下纯mock用例，先运行单个测试。当前图例未传False，应实际RED为`[True] != [False]`；未运行不记红灯。

```python
def test_rule2_legend_hides_live_parameter_version(monkeypatch):
    calls = []
    def legend(params=None, *, include_version=True):
        calls.append(include_version)
        return '<p>legend sentinel</p>'
    monkeypatch.setattr(webapp, 'render_legend', legend)
    page = webapp._shell_page()
    assert calls == [False]
    assert '图例来源：当前服务配置' in page
    assert '结果规则版本以快照来源栏为准' in page
```

未来命令均以此解析真实树，后续不重新猜路径：

```powershell
$r2Runtime = Get-Content -LiteralPath 'C:/Dev/zhuopin-ai/reports/sc8-r2-alignment-1009/alignment-runtime.json' -Raw | ConvertFrom-Json
$r2Tree = $r2Runtime.tree
$r2Scene = Join-Path "$r2Tree" '4-数字员工/采购部/SC8-客户订单交期智能承诺'
$r2Python = 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe'
$env:PYTHONPATH = "$r2Scene;$(Join-Path "$r2Tree" '5-平台底座/zhuopin_platform')"
Set-Location -LiteralPath "$r2Scene"
& "$r2Python" -m pytest 'tests/test_webapp_ui_contract.py::test_rule2_legend_hides_live_parameter_version' -q -p no:cacheprovider
```

### Task 2：复制源blob并保留已ff UI

1. 仅在新树执行下列命令，复制13件获准源blob；未列产品文件不得变化。源增量patch已准备但未应用，其SHA见`离网发布准备-2026-10-09.json`。

```powershell
$r2Paths = @(
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/baoguan_service.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/config.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/forecast.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/kit_date_comparison.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/scripts/compare_kit_date_rule2.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/scripts/run_baoguan_dashboard.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_service.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_webapp.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_kit_date_rule1_start.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_kit_date_rule2.py',
    '4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_kit_date_rule2_comparison.py'
)
& git -C "$r2Tree" restore --source='29c1ee92167a4f4bba217078c80cd97928b635a3' --worktree -- @r2Paths
if ($LASTEXITCODE -ne 0) { throw '源blob复制失败，停止对齐' }
```

2. 新树`sc8/webapp.py`中现有且唯一`render_legend(config.default_params())`改为`render_legend(config.default_params(), include_version=False)`，保留其前后来源说明及当前UI全部代码。重复计数不是1则停止；不以源webapp整文件覆盖。
3. 同一单测实际GREEN；再跑UI全套及R2定向；逐件git diff核13源blob相等、主仓UI原变更未丢，提交产品15件为`feat(sc8): align approved rule2 with current procurement UI`。保存确切最终HEAD、diff和hash。

### Task 3：新候选mock验证与一次独立review

1. 场景cwd、同版代码，分别执行全量R2 OFF/ON；两套不同时运行以免audit/cache目录互扰，输出写不同receipt且保存exit码/raw SHA。

```powershell
Set-Location -LiteralPath "$r2Scene"
$env:SC8_KIT_DATE_RULE2_LITERAL = 'off'
& "$r2Python" -m pytest -q -p no:cacheprovider
$r2OffExit = $LASTEXITCODE
if ($r2OffExit -ne 0) { throw 'OFF回归失败' }
$env:SC8_KIT_DATE_RULE2_LITERAL = 'on'
& "$r2Python" -m pytest -q -p no:cacheprovider
$r2OnExit = $LASTEXITCODE
if ($r2OnExit -ne 0) { throw 'ON回归失败' }
```

2. 明确审阅并现时记录pass/skip；mock golden应1pass，真实golden缺expected时skip，三项真实集成等跳过逐项列明。对照历史29c候选580/4仅作数量解释，不把原报告冒充新候选结果。新增测试不能减掉原用例。
3. 平台cwd单独执行平台全套；再在新树执行`openspec validate --all --strict`。现时结果写报告，真实skip仍留步；不为绿灯改黄金期望、默认开关或旧断言。
4. requesting-code-review按最终commit/diff实际派出一次无历史上下文review，显式模型gpt-6-luna；重点上述五类。Critical/Important先修、绑定修后HEAD复验受影响范围；不得用旧review代替新UI/引擎组合review。
5. 交付新候选、15件精确diff/批准源blob映射、新验证receipt、review及完整停点；#660继续partial，tasks暂不归档。此时再根据真实黄金/专业等实际前置决定是否提出具体ff申请；计划批准不授权ff。

## 当前发布闸与自审

现有119行冻结报告46行前移、73行不动、颜色均63红/49橙/5黄/2绿；原coverage颜色为untriggered_unverified，D4边界当天/前后计数0。真实黄金仍缺expected.json。此计划不关闭这些留步，不宣称已上线或已开启。

自审：13件源blob＋唯一webapp双边冲突＋原UI测试组成全部15件产品范围；原P1设计接口/测试/独立开关约束逐项覆盖。没有新接口、无占位实现、P2/SC2/平台源码不改。评审仍Native且实际review统一Luna。

**本具体计划及mock验证范围已明确批准；ff/生产等仍另审。** 当前执行证据见`openspec/changes/sc8-atp-batch2-closeout/主仓对齐批准与执行.md/.json`。

## 本次执行完成记录

2026-10-09T16:21:54.1401771+08:00（上海）：Task1实际基线与新调用RED、Task2精确15件对齐/新调用GREEN/定向90/候选commit、Task3现时OFF/ON591/4各一套、mock golden1、平台646/1、strict220/0及一次无上下文Luna全分支review均已完成。候选`2bdd92f6bb0cde62962a85daae618994fe2209a8`及逐项证据见`openspec/changes/sc8-atp-batch2-closeout/主仓对齐批准与执行.md/.json`。所有skip与专业/发布/P2闸留步，未做ff或生产；分支/树/账本保留。
