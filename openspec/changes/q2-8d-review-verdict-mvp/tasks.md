> ✅ design与转写intent已于09-18确认、09-19追认；§1/§2及5.1已有历史建造记录，3.3/3.4仍属串行闸/人事。**官方#612记载5.2于09-19晚上线并记录三件套（本轮只消费该历史记录），但部署分支尚未并入当前master；本文件的5.2未勾仅保留主仓交付收口，不再表示“从未部署”。**§4语义来源/真实校准/专业签认/真实接线及5.3继续未完成，不代联络或发送。详见末节#612回灌。

## 1. 工程骨架（🟢，commit `0a52378`）
- [x] 1.1 场景目录＋`pyproject.toml`（`q2-8d-verdict`）；`.gitignore`（`reports/`／`results/`／`data/golden/`，`git check-ignore -v` 实测）
- [x] 1.2 `conftest.py`／`run.py` 用 `bootstrap.ensure_paths` 唯一样板
- [x] 1.3 `config.py`：24 条覆盖层 `Signoff(陈忱)`；`PENDING` 两条读即抛；`AUTOMATION_LEVEL="L2"`
- [x] 1.4 `data/rules/` V3.2 搬运件（sha256 用例守）；`data/mock/samples.json` 11 份合成样本

## 2. 档 1 mock 引擎（🟢）
- [x] 2.1 `rules_loader`（D1）｜2.2 `checks` 26 条确定性规则（无检查器即抛）｜2.3 `redlines`（D5）｜2.4 `engine`（D6/D4/D7/D8）｜2.5 `semantic`（D2）｜2.6 `feed_source`
- [x] 2.7 `pytest -q --tb=short --maxfail=5` 12 passed；`openspec validate --strict` 通过
- [x] 2.8 `intent.md`（转写版 `待确认`）＋场景 `CLAUDE.md`

## 3. 🔴 design 审收口
- [x] 3.1 Shao Peishen 审 D1–D8（D3／D4 须明确拍）⇒ ✅ **2026-09-18 答 `1a`：整表通过、无驳回，D3／D4 一并拍过**
- [x] 3.2 `intent.md` 转 `已确认`（Shao Peishen）⇒ ✅ **2026-09-18 答 `2a`：认可转写版、不补跑 grill**，CI intent 闸转绿
- [ ] 3.3 `Q2-G-01` 并进下一封质量部信（串行闸现取，不单起）
- [ ] 3.4 `Q2-G-04` 持有人／backup 登记（人事，不代指派）

## 4. 档 2 语义层与校准（design 审后）
- [ ] 4.1 语义来源实现（V3/V4）｜4.2 验收集 10 份校准（真实件不入库；红线②③排除、样本 3 单列）｜4.3 `SEMANTIC_LAYER_ACCEPTANCE` 签认｜4.4 接 QD-A 真实解析＋PPT D2 页勾选（LAN 留步）

## 5. 档 3 内部服务（design 审后）
- [x] 5.1 门户页 `/quality/q2`（不新起端口；`q2_8d_verdict/webapp.py`＋`dashboard.py`＋`scripts/run_q2_web.py`，19 passed，`OP-0919-C`）
- [ ] 5.2 `.51` 部署＋冒烟＋回滚 SOP的主仓交付收口（官方#612记载09-19历史上线已完成；三份部署脚本仍仅在原部署分支，合入保留逐项闸，见末节；本项不授权重部署）
- [ ] 5.3 第8步跟进信（串行闸及对外发送逐项授权）

## 2026-10-04 #592 · 已签事实消费

质量部#15 a已于09-24明确样本3为制造，※为漏删的待确认记号；Q2-G-03已闭并已消费到验收集/intent/design/场景笔记。**4.2的“样本3单列”继续保留用于追溯，样本场景按已确认制造；本次未勾4.1–4.4或其它产品实施/验收/上线项。**两项PENDING、红线②③排除、真实原文隔离及L2保持。

## 2026-10-04 #612 · 历史部署与主仓交付

官方#612和`1-转型规划/0-全景路线图/看护件-LAN收口批B-0919_Q2上线-2026-09-19.md`证明09-19晚独立端口改判及部署已有历史执行记录；代码载体为`4816afc75c742d74c8ca9308db6867a7887b66ee`（本地/远端同一原分支）。当前master `2fedfbba4cb6d246dae73debc9ed336aa9980ca6`与该分支双向均非祖先，共同基点`1054716fb3fb9ee6a3ea6ca6f136c9c75706d9b1`，无法直接ff；官方白名单干跑不命中（代码/纪律载体）。原分支八件改动中三份部署脚本在当前master不存在。后续需正式整合与逐项合入闸，不复制旧branch覆盖本轮G-03澄清、不重部署原服务。

本轮未执行产品测试、openspec验证或LAN冒烟；历史19 passed和三件套只按当时记录引用。§4、3.3/3.4、5.3均保持未勾，两项PENDING、红线②③不验收、样本3单列与L2均保持。
