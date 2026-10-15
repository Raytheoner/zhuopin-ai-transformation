## ADDED Requirements

### Requirement: Authorized real document input
The system SHALL accept the bound OEM-A-01 A0 ASIL B PPTX through the PC form, preserve source bytes and enforce trusted actor, source SHA and OEM scope before scoring.

#### Scenario: Different document or ASIL C/D
- **WHEN** metadata, source SHA or access is outside the authorized pilot
- **THEN** the system rejects it without scoring or a successful-report badge.

### Requirement: Complete located evidence
The system SHALL preserve all source paragraphs across repeated sections, tables, images and embedded cached cells, and distinguish missing evidence from reading failures.

#### Scenario: A continued chapter appears on another slide
- **WHEN** a D3/D4/D5 heading repeats on a later slide
- **THEN** both chapter bodies and their page and cell references remain available.

#### Scenario: An asset cannot be read
- **WHEN** image or embedded evidence extraction fails
- **THEN** the report identifies the affected asset and does not interpret the failure as absence or zero points.

### Requirement: Unconfirmed AI advice
The system SHALL request gpt-6-luna/high through the approved restricted business adapter, validate applicable-rule coverage, scores, quotations and provenance, and retain professional signoff as pending.

#### Scenario: Valid complete model advice
- **WHEN** all applicable items have validated evidence, scores and remediation
- **THEN** a complete AI advisory score and numeric grade may be shown separately from the unchanged formal verdict and professional acceptance.

#### Scenario: Invalid response, unavailable model or tool access
- **WHEN** a response is incomplete, model unavailable or required tool restrictions cannot be verified
- **THEN** the system records a specific failure, does not change model and does not fabricate a complete score.

### Requirement: Portable Excel result
The system SHALL export five linked sheets containing every applicable finding, source text, image preview and embedded cached data, with correct numeric formula caches and safe text handling.

#### Scenario: Browser export
- **WHEN** the authorized actor downloads the completed operation
- **THEN** the actual saved Excel agrees with the immutable report and audit, and optional original assets can be downloaded in a matching ZIP.

### Requirement: Audited recoverable single operation
The system SHALL preserve immutable input, evidence, model response and output hashes, verify successful audit persistence, avoid duplicate successful operations, and report process interruptions accurately.

#### Scenario: Repeat download or submit after success
- **WHEN** an identical authorized operation is retried
- **THEN** the saved result is reused without another model charge or duplicate assessment event.

#### Scenario: Process interruption
- **WHEN** a job is interrupted by service exit
- **THEN** it remains recoverable evidence and is not reported as running or business accepted.
