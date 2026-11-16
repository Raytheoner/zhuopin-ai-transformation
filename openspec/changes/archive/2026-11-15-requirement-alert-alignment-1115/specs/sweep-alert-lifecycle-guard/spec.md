## ADDED Requirements
### Requirement: Reviewed requirement triage governs stale alerts without hiding change
The existing sweep SHALL consume the requirements INDEX and reviewed triage evidence. Frozen or externally blocked incomplete packages SHALL be logged as managed only when state, progress, owner pointers and the complete package fingerprint match the review. Completed, changed, invalid or unreviewed packages MUST retain anomaly detection. This MUST NOT grant construction or publication authority.
#### Scenario: Reviewed frozen package unchanged
- **WHEN** an incomplete frozen package matches the reviewed INDEX state, progress and full content fingerprint
- **THEN** sweep records its state and original queue pointers without calling it forgotten archiving
#### Scenario: Reviewed content changes
- **WHEN** any package content or INDEX state differs from the review or review data is unreadable
- **THEN** sweep retains the stale anomaly candidate rather than assuming it is controlled
#### Scenario: Complete package cannot hide behind freezing
- **WHEN** all tasks are checked despite a reviewed frozen state
- **THEN** the existing completion/archive gate remains effective
### Requirement: Planning coverage preserves queue and acceptance boundaries
The requirements gate SHALL cover every non-retired planning-registry scenario with its exact domain and schedule, original queue or explicit existing-delivery route, and suspension and acceptance boundary. Mere file or alias existence MUST NOT prove business acceptance.
#### Scenario: Missing or conflicting planning route
- **WHEN** a non-retired scenario lacks a route, has duplicate routes, or disagrees with the registry domain, schedule or suspension
- **THEN** the requirements lint rejects it
#### Scenario: Controlled output remains unfinished
- **WHEN** unclosed output is reported after ownership review
- **THEN** the message retains all unresolved and unavailable records and identifies the original custody lookup without claiming that every item is unowned
