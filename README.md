```markdown
# PropertyCare

<!-- CI badge will be added after Session 4 when the GitHub Actions workflow is configured.
-->

**Student:** Jai LNU · **Course:** CEN 5064 Software Design, Fall 2026 · **Partner:** GoldLion72

## Project (approval paragraph — write this by Sun Aug 30)

PropertyCare is a rental maintenance and work-order management system designed for small landlords, property managers, tenants, and maintenance contractors. The system will allow property managers to register properties and rental units, tenants to submit maintenance requests, managers to prioritize requests and assign repair work, and contractors to update the progress and completion details of assigned work orders. It will also maintain repair histories and cost summaries for each property and unit. The application will use a layered architecture, a single relational database, and a simple web-based interface so that it remains achievable within one semester.

## How to run


```

PropertyCare is currently in the design and initial development stage.
Exact installation and execution commands will be added when the first
working version of the application is committed.

```

## Architecture

### Tier breakdown (Session 2 studio)

| Tier | Responsibilities in THIS system |
|------|--------------------------------|
| Presentation | Displays role-based views (Tenant Portal, Property Manager Dashboard, Contractor Hub) and handles UI form validation without executing business logic. |
| Service | Coordinates core use cases and role authorization, managing atomic multi-step operations (such as linking maintenance request updates to work order creation). |
| Domain | Houses entities (`User`, `Tenant`, `PropertyManager`, `Contractor`, `Property`, `Unit`, `MaintenanceRequest`, `WorkOrder`) and enforces business rules for priorities, cost tracking, and state-machine status lifecycle transitions. |
| Data | Manages database persistence using abstract repository interfaces to decouple logic, executing queries and aggregate cost summaries against a SQLite database with migration support. |

### C4 — Context & Container (Session 3 studio)

```mermaid
flowchart TB
    tenant([Tenant])
    manager([Property Manager])
    contractor([Maintenance Contractor])
    system[PropertyCare]
    database[(SQLite Database)]

    tenant -->|submits and tracks maintenance requests| system
    manager -->|manages properties, requests, and work orders| system
    contractor -->|views assigned work and records repair updates| system
    system -->|stores and retrieves property maintenance data| database

```

```mermaid
flowchart TB
    subgraph PropertyCareSystem [PropertyCare]
        ui[Streamlit Web Interface<br/>Presentation Tier]
        service[Application Services<br/>Service Tier]
        domain[Domain Model<br/>Domain Tier]
        data[Repository Layer<br/>Data Tier]
        database[(SQLite Database)]

        ui -->|sends user requests| service
        service -->|applies use cases| domain
        service -->|requests data operations| data
        data -->|reads and writes records| database
    end

```

### UML — Class & Sequence (Session 3 studio)

```mermaid
classDiagram
    class Property {
        -int id
        -String name
        -String address
        +addUnit()
        +getMaintenanceHistory()
    }

    class Unit {
        -int id
        -int propertyId
        -String unitNumber
        +getOpenRequests()
        +getMaintenanceHistory()
    }

    class MaintenanceRequest {
        -int id
        -int unitId
        -String tenantName
        -String title
        -String description
        -String category
        -String priority
        -String status
        -Date createdAt
        +changePriority()
        +changeStatus()
        +createWorkOrder()
    }

    class WorkOrder {
        -int id
        -int requestId
        -String assignedContractor
        -Date scheduledDate
        -double estimatedCost
        -double actualCost
        -String status
        -String completionNotes
        +assignContractor()
        +startWork()
        +completeWork()
    }

    Property "1" --> "*" Unit : contains
    Unit "1" --> "*" MaintenanceRequest : receives
    MaintenanceRequest "1" --> "0..1" WorkOrder : produces

```

```mermaid
sequenceDiagram
    actor T as Tenant
    participant UI as PropertyCare UI
    participant S as Maintenance Request Service
    participant DM as Domain Model
    participant D as Data Repository

    T->>UI: Enter unit and maintenance details
    UI->>S: Submit maintenance request
    S->>DM: Validate and create request
    DM-->>S: Return validated request
    S->>D: Save maintenance request
    D-->>S: Return request ID
    S-->>UI: Return submission confirmation
    UI-->>T: Display request number and status

```

## Architecture Decision Records

Decisions live in [`docs/adr/`](https://www.google.com/search?q=docs/adr/). Start with ADR-001 in Session 4.

| # | Decision | Status |
| --- | --- | --- |
| [001](https://www.google.com/search?q=docs/adr/adr-001.md) | Build PropertyCare as a rental maintenance and work-order management system | proposed |

## Weekly log (optional but recommended)

A one-line note per week keeps your commit story readable:

* Week 1 (Aug 24): Repository created, three project ideas drafted, PropertyCare selected, and the approval paragraph added.
* Week 2 (Aug 31): Defined the four-tier architectural breakdown, layer responsibilities, and system boundary definitions during the Session 2 studio.

```

```
