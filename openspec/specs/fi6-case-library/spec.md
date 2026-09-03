# fi6-case-library Specification

## Purpose

把财务主管每次人工确认的结果沉淀为可疑交易判例库，并用累积判例回看检测口径的误报率，为判据升版提供依据。
🔴 判例的价值全在"谁认的"，故每条判例必须记录确认人实名，匿名判例不得进回归基准。

## Requirements

### Requirement: 可疑交易案例库判例须实名

系统 SHALL 把财务主管每次人工确认的结果沉淀为案例库判例，每条判例 MUST 记录确认人实名、确认时刻、结论（确属异常／误报／待定）与所用 `RULE_VERSION`。匿名判例 MUST NOT 进入回归基准。

> 判例的价值全在"谁认的"。

#### Scenario: 判例必填实名
- **WHEN** 构造一条 `CaseRecord`
- **THEN** `confirmed_by` 是必填项（无默认值），缺失即构造失败

#### Scenario: 判例进回归
- **WHEN** 判例被采纳为回归基准
- **THEN** 其所用 `RULE_VERSION` 一并记录，规则升版时可回溯该判例在旧口径下的结论

### Requirement: 案例库驱动的持续学习闭环

系统 SHALL 支持用累积判例回看检测口径的误报率，为判据升版提供依据。

#### Scenario: 误报率回看
- **WHEN** 给定一个版本区间
- **THEN** 输出该区间内判例的误报占比，按模式分类
