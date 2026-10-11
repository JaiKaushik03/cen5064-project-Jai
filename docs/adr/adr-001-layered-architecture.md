# ADR 001: Layered Architecture

**Date:** 2026-10-10
**Status:** accepted

## Context

PropertyCare's midterm needs a real tenant workflow that can be demonstrated in two minutes. The project already has a priority rule in the Domain layer, and the README proposes four layers. Putting validation and SQL directly into Streamlit would make those boundaries difficult to explain and test.

## Decision

Use four layers for the working flow: Presentation -> Service -> Domain -> Data.
`app.py` collects input and displays results. `MaintenanceRequestService` creates a validated `MaintenanceRequest` using the existing `Priority` enum before passing that object to `MaintenanceRequestRepository` for SQLite storage. The service also loads saved requests for the screen.

The arrows describe the submission flow, not a dependency from Domain to Data: the domain has no Streamlit or SQLite imports. The service coordinates validation and persistence. Repository construction in `app.py` wires the application together; SQL stays in the Data layer.

## Consequences

Business rules can be tested without a browser or a database. Service and repository tests verify that rejected inputs never reach storage, while Streamlit tests exercise the complete screen flow. Four small modules are enough for this use case; a dependency-injection framework or abstract repository hierarchy would add little value now. A future interface or database change can keep the same domain rules.
