> 🔴 design 审 🟡 待 Shao Peishen。§1／§2 为档 1 范围（`#612`），本泳道已完成；§3 起 design 审通过前不得动手。停在档 1：语义层上线须 `PENDING.SEMANTIC_LAYER_ACCEPTANCE` 签认；不代联络陈忱。

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
- [ ] 3.1 Shao Peishen 审 D1–D8（D3／D4 须明确拍）
- [ ] 3.2 `intent.md` 转 `已确认`（Shao Peishen）
- [ ] 3.3 `Q2-G-01` 并进下一封质量部信（串行闸现取，不单起）
- [ ] 3.4 `Q2-G-04` 持有人／backup 登记（人事，不代指派）

## 4. 档 2 语义层与校准（design 审后）
- [ ] 4.1 语义来源实现（V3/V4）｜4.2 验收集 10 份校准（真实件不入库；红线②③排除、样本 3 单列）｜4.3 `SEMANTIC_LAYER_ACCEPTANCE` 签认｜4.4 接 QD-A 真实解析＋PPT D2 页勾选（LAN 留步）

## 5. 档 3 内部服务（design 审后）
- [ ] 5.1 门户页 `/quality/q2`（不新起端口）｜5.2 `.51` 部署＋冒烟＋回滚 SOP｜5.3 第 8 步跟进信
