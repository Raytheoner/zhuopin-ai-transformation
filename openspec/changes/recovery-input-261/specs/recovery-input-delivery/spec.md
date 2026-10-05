## ADDED Requirements

### Requirement: Approved bounded recovery input
The system SHALL accept a recovery input only for the latest terminal empty_changes implement attempt, a clean bound workspace and an unchanged original implementation approval, using a separate explicit recovery approval.

#### Scenario: Missing approval or binding drift
- **WHEN** approval is missing or task, attempt, design, workspace or original approval digest differs
- **THEN** the system SHALL reject before any provider launch and SHALL preserve existing seals and claims.

### Requirement: Formal delivery and public evidence
The system SHALL deliver the same validated immutable recovery snapshot through Workflow advance or Guardian into the effective prompt and SHALL seal its context and base/effective digests in public request evidence.

#### Scenario: Valid delivery
- **WHEN** a paired input and approval pass all bindings
- **THEN** the system SHALL append the bounded data context and SHALL verify request prompt digest matches the exact provider input.

#### Scenario: Evidence mismatch
- **WHEN** recovery context is absent from the public request or effective digests disagree
- **THEN** the stage SHALL not be accepted as recovery delivery.

### Requirement: Preserve historical behavior and authorization
The system MUST preserve historical fingerprints and prompts when recovery input is absent and MUST NOT mutate old intents, approvals, plans, attempts or allowlists to inject recovery instructions.

#### Scenario: Old sealed batch
- **WHEN** a recovery input is supplied to an existing v1 or v2 sealed plan
- **THEN** the system SHALL reject injection and require a separately approved new recovery plan without upgrading the old plan.

### Requirement: Single launch and fail closed concurrency
The system SHALL bind and consume each recovery permission under the existing task lock for at most one model launch; uncertain crash state SHALL require explicit reconciliation.

#### Scenario: Concurrent or repeated request
- **WHEN** two callers attempt the same recovery permission or a consumed permission is replayed
- **THEN** at most one provider launch SHALL occur and the other call SHALL be blocked.

### Requirement: Separate delivery from execution success
The system MUST distinguish input delivery, observed model compliance and implementation acceptance, retaining all existing artifact, CI, independent review and release gates.

#### Scenario: Prompt delivered but model fails
- **WHEN** public request proves delivery but model again uses an invalid path or produces no changes
- **THEN** implementation SHALL remain blocked without automatic retry, retirement or any claim of completed delivery acceptance.
