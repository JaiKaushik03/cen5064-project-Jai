# PropertyCare final design

## Scope and actors

The final course application supports tenant signup/login and private maintenance submission, owner property/unit registration and contractor provisioning, owner assignment oversight, contractor progress/completion, and retained maintenance history with photos and repair costs. Owners share one local management portfolio. Tenant identities and contractor assignments use stable keys. The application does not claim lease verification, payment processing or public production hosting.

## Context and containers

```mermaid
flowchart TB
    T[Tenant] -->|private requests and history| P[PropertyCare]
    O[Owner or property manager] -->|properties, units, assignments and completion| P
    C[Contractor] -->|assigned work, progress and completion| P
    P -->|local persistence| DB[(SQLite files)]
```

```mermaid
flowchart TB
    subgraph Server[One local Python server process]
        UI[Streamlit presentation and composition]
        AUTH[AuthenticationService and injected account/password ports]
        S[Tenant, owner and contractor services]
        D[Domain models, Builder and business rules]
        R[SQLite repositories]
        UI --> AUTH
        UI --> S
        S --> AUTH
        S --> D
        S --> R
        AUTH --> AP[Account/password adapter implementations]
        AP --> ADB[(Separate tenant, owner and contractor files)]
        R --> MDB[(Maintenance, property and unit file)]
    end
    B[Browser] --> UI
```

Presentation handles widget state, form callbacks and rendering; it contains no SQL. Service obtains the current principal on every operation and coordinates Domain/Data. Domain owns required-field/priority constraints, contact completeness, costs/photos, Critical-first assignment and immutable completion. Data uses bound parameters and manages transactions/connections. The new workflow update transaction takes a service-supplied transformation; the repository itself does not decide whether Critical assignment or completion is permitted.

## Current class relationships

```mermaid
classDiagram
    class MaintenanceRequest {
        +id
        +property_unit
        +title
        +description
        +priority
        +status
        +tenant_key
        +tenant_name
        +tenant_email
        +tenant_phone
        +tenant_address
        +tenant_unit
        +registered_unit_id
        +photo
        +created_at
        +assigned_contractor_key
        +assigned_at
        +scheduled_for
        +work_started_at
        +estimated_cost_cents
        +actual_cost_cents
        +completed_at
        +completion_notes
        +change_priority()
        +assign()
        +start_work()
        +complete()
    }
    class MaintenanceRequestBuilder {
        +reported_by(account)
        +with_photo(data)
        +at_registered_unit(id)
        +build()
    }
    class Property {
        +id
        +name
        +address
    }
    class Unit {
        +id
        +property_id
        +number
    }
    class OwnerWorkflowService {
        +register_property()
        +register_unit()
        +register_contractor()
        +assign()
        +complete()
    }
    class ContractorWorkflowService {
        +list_requests()
        +start_work()
        +complete()
    }
    class TenantMaintenanceService {
        +submit()
        +list_requests()
        +get_request()
    }
    class MaintenanceRequestRepository {
        +save()
        +list_for_tenant()
        +list_for_contractor()
        +transact_update()
    }
    Property "1" --> "many" Unit
    MaintenanceRequest --> Unit : optional registered reference
    MaintenanceRequestBuilder --> MaintenanceRequest : builds frozen product
    TenantMaintenanceService --> MaintenanceRequestBuilder
    TenantMaintenanceService --> MaintenanceRequestRepository
    OwnerWorkflowService --> MaintenanceRequestRepository
    ContractorWorkflowService --> MaintenanceRequestRepository
    OwnerWorkflowService --> MaintenanceRequest : Domain decisions
    ContractorWorkflowService --> MaintenanceRequest : Domain transitions
```

Work-order assignment/progress/cost values live in the MaintenanceRequest aggregate. There is no separate WorkOrder class or table; the original proposal's WorkOrder diagram is historical. Account models and service-owned ports remain as documented in ADRs 003/004 and the SOLID refactor.

## Assignment sequence and rejection

```mermaid
sequenceDiagram
    actor O as Owner
    participant UI as Streamlit
    participant S as OwnerWorkflowService
    participant A as AuthenticationService
    participant R as Repository
    participant D as MaintenanceRequest Domain
    O->>UI: Assign Low request while Critical is unassigned
    UI->>S: assign(request, contractor, estimate, date)
    S->>A: require current owner session
    A-->>S: authorized principal
    S->>R: transact_update with Domain transformation
    R->>R: BEGIN IMMEDIATE and read current queue
    R->>D: service transformation calls assign()
    D-->>R: reject Critical-first violation
    R->>R: rollback
    R-->>S: validation error
    S-->>UI: meaningful error
    UI-->>O: show error and preserve selections
```

Completion follows the same authorization/transaction path and calls Domain complete(confirmed=True). UI requires both the checkbox and Submit. Contractor transformations additionally compare the assigned stable key inside the transaction. A rejected transition writes nothing. Successful completion retains all original fields, changes stored status to Completed and records exact actual cost, completion notes and UTC time. Subsequent priority changes fail in Domain.

## Persistence and migration

Tenant, owner and contractor credentials remain in separate files with Argon2id hashes. The maintenance file has properties, units and extended maintenance_requests. The registered unit reference is optional for legacy/free-form requests; duplicate units are rejected per property and unit registration requires an existing property. Images are bounded PNG/JPEG bytes in SQLite. All SQL inputs are bound; internal schema identifiers come from fixed code.

Additive migration runs within one transaction and preserves existing values, IDs, account keys, hashes and ID sequences. Legacy unknown contacts are never joined to a possibly changed profile as if historical. Old Completed timestamps remain unknown. Backups cover all four files together.

## Final plan and risks

| Risk | Mitigation and evidence |
|---|---|
| Cross-account disclosure | Current-role/account rechecks, stable keys and filtered repository reads; tenant/contractor isolation and replacement-account tests |
| Losing old data during migration | Additive transactions, repeated migration/rollback tests, copied legacy stores and original file checksums |
| Assignment race | Serialized current-queue read and Domain decision in BEGIN IMMEDIATE |
| Completion changes original history | Frozen replacements, updates limited to workflow fields, preservation/reload tests |
| Malformed images or costs | Decode actual PNG/JPEG content with size/pixel limits; exact Decimal-to-cent validation |
| Streamlit widget errors | Callback resets before rendering; dynamic upload key after success; real screen tests and browser checks |
| Unsupported production assumptions | Document local-process sessions, shared owner portfolio, backup scope and no lease/payment claims |

Implementation is handed off in a single open feature PR with logical commits. Partner review and explicit final merge approval remain the stopping point; no review or approval is invented. Weekly reviews/commits are a continuing course process and cannot be reconstructed after the fact. See final-verification.md for actual receipts and the pattern map for the creational assessment.
