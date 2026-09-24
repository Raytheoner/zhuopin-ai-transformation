## ADDED Requirements
### Requirement: Bounded native execution
The system SHALL invoke only Codex with explicit bounded sandbox permissions and SHALL remain paused without enablement.
#### Scenario: Consumer paused
- **WHEN** a consumer has no explicit enablement
- **THEN** no model process starts and input signals remain available
#### Scenario: Model failure
- **WHEN** a process, tool, turn, protocol or context guard fails
- **THEN** evidence records failure and the consumer does not claim delivery acceptance

### Requirement: Evidence-based acceptance
The system SHALL distinguish execution completion from delivery acceptance for all three consumers.
#### Scenario: Successful output
- **WHEN** a native turn completes and emits a completion sentinel
- **THEN** the result remains output-needs-review until tools, hooks, tests and artifacts are independently checked

### Requirement: Safe recovery
The system SHALL preserve signals and stop automatic model consumption on unrecoverable faults without any Claude fallback.
#### Scenario: Repeated patrol failure
- **WHEN** the persisted failure threshold is reached
- **THEN** the chain stops and preserves the unconsumed signal
