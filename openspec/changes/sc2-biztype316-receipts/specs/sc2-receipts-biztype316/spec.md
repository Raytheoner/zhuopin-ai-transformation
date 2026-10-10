# Spec: SC2 收货 BizType316 过滤与明细

> 正式 delta spec 供审稿。#277口径已批准；design与具体实施计划尚待审，不代表已实现。

## Purpose

本规格将已批准的 BizType316 收货业务边界落实为可审计的来源筛选、指标计算与对应明细行为，同时保护共享收货数据和旧冻结结果不受影响。缺失的业务字段只影响依赖该字段的新316数值；来源成员资格或窗口完整性未证时，则明确报告范围缺口，不以猜测补值。

## ADDED Requirements

### Requirement: Explicit BizType316 scope

The SC2 receiving report SHALL calculate the four approved metrics—receipt line count, receipt quantity, receipt amount, and arrived supplier count—and their matching detail from the same verified BizType316 subset.

#### Scenario: Explicit source-side filter is verified

- **WHEN** the source request explicitly specifies `bizType=316` and available response/source evidence verifies the filter was applied to a complete paginated result
- **THEN** the four metrics and matching receipt detail SHALL use only rows in that verified subset
- **AND** each new 316 report window SHALL inherit the current SC2 BusinessDate window behavior without changing historical reports
- **AND** other receipt-derived metrics not named by #277 SHALL continue using their existing shared-receipt behavior

#### Scenario: Source-side filter is not verified but row type is available

- **WHEN** the source-side filter cannot be verified and every candidate row has an explicit BizType field whose meaning is verified
- **THEN** SC2 SHALL form a 316 subset by comparing the explicit type value to `316`
- **AND** the subset and the filtering method SHALL be recorded with the dataset evidence
- **AND** no document-number or order-number prefix SHALL be used to infer type

#### Scenario: Neither a verified server filter nor complete row-type membership is available

- **WHEN** no verified server-side filter establishes a complete paginated 316 result and not every candidate row has an explicit, semantically verified BizType value sufficient to establish complete membership
- **THEN** the four 316 metrics and matching 316 detail SHALL report the BizType scope as unknown/incomplete
- **AND** the system SHALL NOT present unfiltered values as 316 values
- **AND** the system SHALL NOT recompute, rewrite, or repair an older frozen report to make it appear filtered

### Requirement: Metric semantics are inherited without scope expansion

The SC2 316 metrics SHALL reuse the existing four metric keys, labels, and calculation semantics unless a separately reviewed change authorizes a definition change.

#### Scenario: Complete typed subset

- **WHEN** source rows, window dates, and the fields required by a metric are complete for the verified 316 subset
- **THEN** line count SHALL count included receipt rows, quantity SHALL sum receipt quantities, amount SHALL use the current receipt-row quantity-times-unit-price calculation, and arrived supplier count SHALL count distinct non-empty supplier names
- **AND** the same subset SHALL back the corresponding detail output

#### Scenario: Quantity is missing

- **WHEN** quantity is missing on an included 316 row
- **THEN** quantity and amount SHALL be marked incomplete rather than treating the missing value as zero
- **AND** line count or supplier count SHALL remain available only if their membership and required fields are complete

#### Scenario: Unit price is missing

- **WHEN** unit price is missing on an included 316 row
- **THEN** amount SHALL be marked incomplete rather than treating the missing value as zero

#### Scenario: Supplier name is missing

- **WHEN** supplier name is missing on an included 316 row
- **THEN** arrived supplier count SHALL be marked incomplete rather than silently excluding the row from a complete total

### Requirement: BusinessDate window and source completeness

The 316 cohort SHALL use the current SC2 receiving-window basis and SHALL declare incomplete totals when membership in a reporting window or source row completeness cannot be established.

#### Scenario: BusinessDate is absent

- **WHEN** an included candidate row has no usable BusinessDate
- **THEN** SC2 SHALL mark the affected window's cohort completeness unknown and SHALL NOT silently discard the row while reporting a complete 316 total

#### Scenario: Pagination is incomplete or unverifiable

- **WHEN** the source cannot establish that all pages for the requested range were read
- **THEN** all four metrics and the detail completeness SHALL be reported as unknown/incomplete

### Requirement: Organization and status boundaries do not invent business rules

The 316 change SHALL record observed organization scope and preserve the current GR/Query row-inclusion behavior; it SHALL NOT hardcode an unverified organization default or introduce new return, void, reversal, or status exclusions.

#### Scenario: Organization evidence is available

- **WHEN** source metadata establishes the organization actually queried and that organization matches the existing SC2 business context
- **THEN** SC2 SHALL record that organization scope without overriding other completeness requirements

#### Scenario: Organization scope is uncertain

- **WHEN** the source's actual organization is unclear or data are mixed across organizations
- **THEN** SC2 SHALL report the organization scope uncertainty
- **AND** SHALL NOT claim that a value represents a particular organization unless the source establishes that scope
- **AND** this uncertainty alone SHALL NOT alter membership or calculation of the four BizType316 values when organization scope is not part of the approved query boundary
- **AND** SHALL NOT invent or silently apply `Org=Z`

#### Scenario: Status or return fields are unavailable

- **WHEN** the current GR/Query source supplies rows without status/return fields
- **THEN** SC2 SHALL preserve the current returned-row and BusinessDate inclusion behavior
- **AND** this uncertainty alone SHALL NOT add a new BizType316 business rejection or exclusion rule
- **AND** the result SHALL NOT be described as applying a new return/void filter

### Requirement: Legacy frozen data and caches are preserved

The new 316 scope SHALL use explicit schema and cache identity for typed/verified data while preserving older frozen reports and untyped caches unchanged.

#### Scenario: An older frozen report is opened

- **WHEN** a user views an existing report/data snapshot that predates the verified 316 scope
- **THEN** SC2 SHALL render the saved historical values under their original semantics
- **AND** SHALL NOT recalculate, overwrite, backfill BizType, or label those values as 316

#### Scenario: An untyped cache is found

- **WHEN** a legacy connector cache is keyed only by date/lookback and contains no BizType/filter evidence
- **THEN** that cache SHALL NOT satisfy a request for a verified 316 subset
- **AND** SHALL remain unmodified
