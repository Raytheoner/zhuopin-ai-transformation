# 采购门户 UI 离网定向集成执行计划

> For agentic workers: REQUIRED SUB-SKILL: Use executing-plans。Native 执行，不派实现代理；完成后仅一次 Luna 集成 review。用户2026-10-09本会话“我已offlan，如果还有任务可以推进，请继续”为仓内续作授权；沿已批准两包设计，不扩为ff/部署/外发授权。

**Goal:** 将已审核 SC8/SC2 UI 定向移植到当前主仓基线，形成可独立审核的仓内候选。

**Architecture:** 两场景分步提交；SC2 两件与源候选 Git blob 完全相等。SC8 仅消费UI四十余行与新mock测试，保留主仓旧引擎及 `render_legend(params)` 接口；图例配置与快照版本分别标识。原R2树、分支和commit不动。

**Tech Stack:** 现有 Flask/Python/HTML/CSS/Node；项目隔离Python；不装依赖。

**Spec:** `openspec/changes/portal-sc8-ui/design.md`、`specs/sc8-portal-display/spec.md`；`openspec/changes/portal-sc2-ui/design.md`、`specs/sc2-portal-display/spec.md`。原计划与批准及候选见两包实施证据。

## Global Constraints

1. 代码仅限两场景各自 `webapp.py` 与 `tests/test_webapp_ui_contract.py` 四件。
2. 原SC8R2尚未发布：不复制任何 `baoguan.py/config.py`、引擎、比较器或fixture，原规则/阈值/开关留在主仓原版。
3. 不改来源、计算、刷新/重算、案例、身份与审计语义；mock与既有展示/交付回归，不访问真实源、LAN或写真实审计。
4. 唯一执行会话 `01a11df8-f725-7f61-b1de-bd912fa2a0ce`，#538不改；既有dirty、旧分支与树保留。
5. 分支 `codex/portal-procurement-integrate-1009`，本地 ignored树 `C:/Dev/zhuopin-ai/.claude/worktrees/portal-procurement-integrate-1009`；native工具仅提供仓外目录，本轮依用户仓外修改先确认的更高约束采用仓内git linked worktree，不产生仓外修改。
6. ff、push、.51部署、原服务重启/启用、真实验收与外发逐项另审。本次停在候选与发布准备，暂不归档。

## Review Focus

1. SC2两件内容与已审核源候选字节相同，主仓依赖能加载。
2. SC8没有`include_version`旧主仓不支持参数；图例按主仓当前配置且不能冒充快照规则版本。
3. 未带入R2功能，四件以外diff为空。
4. UI mock检查不会调用POST/真实数据或审计；已有写入口与身份校验未变。
5. 当前source time缺口、时效未分类与专业待签认状态保留；离网结果不宣称服务在线。

### Task 1: SC2机械集成

**Files:** `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`、`4-数字员工/采购部/SC2-采购周报自动生成/tests/test_webapp_ui_contract.py`。
**Interfaces:** Consumes源候选`b9798d50`；Produces相同Git blob，现时主仓parent的新SC2候选。

1. 重取主仓HEAD为集成基线；核 clean、本地tree未占用/ignored。创建独立tree，不切原两树。先跑主仓SC2`tests/test_delivery.py`，Expected:37 passed。
2. 从源候选读取上述两件Git blob，写进新树；不重造已有测试/功能。已批准feature的RED→GREEN见源证据，本机械移植不伪造新feature RED。
3. 用隔离Python运行 `pytest -q --tb=short --basetemp "reports/ui-sc2-integration-1009" "4-数字员工/采购部/SC2-采购周报自动生成/tests/test_webapp_ui_contract.py" "4-数字员工/采购部/SC2-采购周报自动生成/tests/test_delivery.py"`；Expected:44 passed、exit0。逐件`git hash-object`＝源候选blob。
4. 仅git add这两件，commit `feat(sc2): integrate reviewed portal UI on current master`；记录新SHA。

### Task 2: SC8展示接口适配

**Files:** `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/webapp.py`、`4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_webapp_ui_contract.py`。
**Interfaces:** Consumes`4401eb4f` UI及主仓`render_legend(params)`；Produces仅四件diff的完整候选。

1. 主仓SC8回归范围：`test_baoguan_webapp.py`、`test_baoguan_webapp_materials.py`、`test_baoguan_webapp_feedback.py`；Expected:全部通过，实际数记录，不跑引擎矩阵。
2. 读取源UI两blob；webapp仅将`render_legend(config.default_params(), include_version=False)`恢复为主仓支持的`render_legend(config.default_params())`，不改baoguan。新增测试：

```python
def test_legend_uses_master_interface_and_labels_its_separate_provenance():
    page = webapp._shell_page()
    assert '图例来源：当前服务配置' in page
    assert '结果规则版本以快照来源栏为准' in page
```

3. 先运行该新增测试，Expected:只因缺图例来源文案FAIL；若TypeError或其它失败，先处理移植兼容而不宣称feature RED。
4. 在legendPanel现有图例前加`<p>图例来源：当前服务配置；结果规则版本以快照来源栏为准。专业签认仍待确认。</p>`；不改图例判据/内容/原默认版本生成。
5. `pytest -q --tb=short`运行SC8新UI测试及上述三个既有文件；Expected:全通过，记录实际数/exit0，`git diff --check`exit0。
6. 仅提交SC8两件`feat(sc8): integrate portal display against existing master rules`。

### Task 3: 集成复核与发布准备

**Files:** 两包`主仓集成证据.md/.json`、`发布准备.md`；R5/opener、661/660及对应§二。
**Interfaces:** ConsumesTask1/2提交与sourceblob；Produces有精确parent、SHA、允许diff与测试收据的发布候选。

1. 断言基线..候选恰为四件、clean，源/集成SC2两blob一致、SC8diff仅UI接口与文字；主仓引擎文件blob＝集成基线blob。
2. 用独立fresh Luna进行一次只读集成review，范围仅移植、依赖兼容与四件隔离；不是重复原UI语义设计review。Important/Critical一个修复pass RED→GREEN；无发现不重跑旧review。
3. OpenSpec strict验证两个既有change；整理命令/原始stdout/stderr/hash、review与Rulings，锁协议登记与回读，#538不变。
4. 主仓若有Sweep新文档提交，记录漂移与前置条件，不把当时ancestor关系承诺为未来ff许可；最终合入前重新对齐并验证，无ff/push/部署。

## Self-review

设计覆盖两包完整展示契约；保持业务/授权边界。SC8已查明父分支仅两处webapp差异，接口在baoguan而不在UI包，不扩大文件范围；SC2代码除历史CLAUDE注记与主仓完全相同。无新场景、无新设计选择；本计划为既有批准UI的机械集成续作。执行方法沿用Native，用户已明确继续，不重复询问同一实施许可。
