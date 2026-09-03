# SC4 合同条款自动提取与审核（骨架期）

> 🔴 **本场景已被 Shao Peishen 2026-09-03 正式顺延**（原权威排期 2026-10 不可行）。
> 移交单：`1-转型规划/0-全景路线图/移交单-SC4顺延与前置总表补5行-全景路线图线执行重组循环-2026-09-03.md`。
> 顺延到哪个月尚未定，算术下界＝ 2026-10-29（两项知识型前置即便今日开工，按「启动前 8 周」纪律倒推）。

## 现在能跑什么

```bash
cd "4-数字员工/采购部/SC4-合同条款自动提取与审核"
python -m pytest -q                 # 19 passed
python -m sc4_contract.agent        # 对脱敏样例合同跑一次抽取，打印概览
```

- ✅ **取文层**（`text_source.py`）：纯文本 mock 实现；PDF/Word 后缀当场拒绝。
- ✅ **切分与定类**（`clause_extract.py`）：按条款标题切段，按 mock 词表定四类，保留原文偏移量。
- ✅ **审计留痕**（`agent.py`）：写平台 `audit`，`review_status="待前置到位"`。

## 现在**不能**跑什么，以及为什么

`review.py` 三个函数（标准条款库比对 / 风险分级 / 缺失条款识别）**全部 fail-loud**，
调用即抛 `PendingPrerequisiteError` 并点名卡在哪一项前置。

| 卡住的能力 | 前置 | Owner | 实读状态（2026-09-03） |
|---|---|---|---|
| 与标准条款库比对、缺失条款识别 | 公司标准合同条款库 | 法务 + 采购 | 🟡 状态格零回填（原定 8月初启动／9月底截止） |
| 风险等级判定 | 合同风险条款判据 | 法务（backup 待点名） | 首轮工作坊无记录、backup 未点名 |

**不给默认值**是刻意的：给了默认值，下游测试就会围着一个法务从未认可的口径长出黄金基准。
理由全文见 `sc4_contract/pending.py` 模块 docstring。

## 目录

```
sc4_contract/
  pending.py          前置闸（判据缺席即抛，不给默认值）
  models.py           ClauseType/ClauseSpan/ContractDocument/ExtractionResult
  text_source.py      取文接口 + 纯文本 mock 实现
  clause_lexicon.py   定位词表（mock-v0，非法务判据）
  clause_extract.py   切分、定类、覆盖概览
  review.py           审核层（整层在前置闸后）
  agent.py            入口 run_extraction / main
tests/                19 tests，含"判据必须抛"的一组
```
