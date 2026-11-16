## ADDED Requirements

### Requirement: Foreground watch continues after context lookup
The foreground consumer SHALL treat the short watch request as permission to continue existing authorized independent work in the same session. Read-only context metadata MUST NOT create a new approval barrier. The current pool MUST be queried again before any hold or closeout.

#### Scenario: One wake creates the first authorized candidate
- **WHEN** one watch request finds an authorized task with no writer or scope conflict
- **THEN** the same foreground session records the original claim and preregistration, produces a real isolated candidate and writes its checkpoint without another user request

#### Scenario: One blocked item does not stall independent work
- **WHEN** the first item fails a prerequisite or preregistration
- **THEN** its failure is preserved without target implementation writes and the consumer obtains the next independent eligible item before stopping

#### Scenario: The pool changes before a hold
- **WHEN** a pass is about to stop after an earlier candidate snapshot
- **THEN** it re-queries the original pool and does not use the old snapshot as proof that no work remains

### Requirement: Native writes follow original claim and preregistration
Before the first substantive target write the consumer MUST verify the original row, existing approved scope, unique writer, exact physical target paths and successful section two preregistration under the original shared lock. Preregistration MUST accept safe planned file paths that do not yet exist, using the original preregistration state. Ordinary registration validation MUST remain unchanged.

#### Scenario: A new target is registered before creation
- **WHEN** a verified approved slice includes a safe absent target file
- **THEN** the original preregistration succeeds before creation and the row records the approved scope and unique writer before implementation

#### Scenario: Registration is rejected
- **WHEN** the original preregistration or readback fails
- **THEN** the implementation callback is not invoked and no target file is created

#### Scenario: Existing writer or frozen work is present
- **WHEN** an item is already owned by another writer, frozen, only for review or in touch conflict
- **THEN** it is not claimed or implemented and another eligible independent item remains consumable

#### Scenario: Scope or evidence is unsafe
- **WHEN** approval evidence drifts or a planned path escapes the approved root or denotes an ambiguous target
- **THEN** the claim fails before implementation and the original safety checks are not bypassed
