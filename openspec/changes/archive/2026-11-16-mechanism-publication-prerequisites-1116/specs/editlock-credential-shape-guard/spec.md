## ADDED Requirements

### Requirement: Repository scanning distinguishes verified public protocol labels
The repository credential scanner SHALL classify only exact verified file/name/public-literal tuples as non-credential protocol labels. It MUST retain structured secret detection and the existing write-side shape API. Unknown values or locations MUST remain subject to the original checks.

#### Scenario: A verified protocol label is scanned
- **WHEN** a file contains an exact verified public protocol label assignment
- **THEN** the generic assignment heuristic does not report it as a credential

#### Scenario: The value or location changes
- **WHEN** a known variable has another value or occurs in another file
- **THEN** original generic credential checks still apply

#### Scenario: A structured credential is present
- **WHEN** the same file also contains a matching structured credential pattern
- **THEN** it remains blocked regardless of the protocol label classification

#### Scenario: A write-side caller checks a shape
- **WHEN** an existing caller uses the original shared shape API without a verified repository location
- **THEN** its strict decision is unchanged
