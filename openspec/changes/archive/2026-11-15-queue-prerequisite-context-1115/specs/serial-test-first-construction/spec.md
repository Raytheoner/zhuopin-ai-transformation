## ADDED Requirements

### Requirement: Short entry distinguishes queue candidates from execution authority
The existing short-entry reader SHALL use the official queue query, exclude queued stop markers in either task or status from its default candidate list, and surface elapsed timed rows for review only. It MUST preserve all nonclosed rows in all-open mode, never change permissions or queue state, and fail closed on unavailable or unrecognized queue output.

#### Scenario: A task title still queues the row
- **WHEN** an open row has a leading stop marker in its task title
- **THEN** the default candidate list excludes it and all-open retains it

#### Scenario: A scheduled review is due
- **WHEN** a non-stopped timed row has reached its date
- **THEN** the short entry includes it as a review candidate with no execution authority

#### Scenario: Frozen or future work remains
- **WHEN** a row is blocked, on hold, or scheduled for a future date
- **THEN** it stays outside the default candidate list without disappearing from the full audit

### Requirement: Existing queue consumption resolves prerequisites by stage
The lane watch SHALL recover prerequisites and next actions from original queue evidence, review or complete permitted predecessors before dependent work, and preserve explicit single-writer and approval boundaries. Final real-data, professional or publication gates MUST NOT block an independent already-approved offline preparation stage. Audit reports are evidence, never a replacement queue or new executor.

#### Scenario: An independent offline proposal is authorized
- **WHEN** its original scope permits offline preparation while final deployment requires more evidence
- **THEN** preparation proceeds in the existing serial workflow and deployment retains its gate

#### Scenario: A predecessor or owner is still active
- **WHEN** the dependency or unique writer remains unresolved
- **THEN** the dependent slice retains that boundary and the watch selects another independent permitted item
