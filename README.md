# PropertyCare

[![CI](https://github.com/JaiKaushik03/cen5064-project-Jai/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JaiKaushik03/cen5064-project-Jai/actions/workflows/ci.yml)

**Student:** Jai LNU · **Course:** CEN 5064 Software Design, Fall 2026 · **Partner:** GoldLion72

PropertyCare is a rental maintenance and work-order project for tenants, property managers, and maintenance contractors. The implemented midterm slice lets a tenant **submit and view a maintenance request**. Requests are validated, stored in SQLite, and displayed again after restarting the application.

## How to run from a clean clone

Requirements: Git, Python **3.13**, and internet access to install dependencies.
No database server, credentials, environment file, or manual schema setup is needed.

### Windows (Command Prompt)

Use Command Prompt for the following commands. Python's Windows launcher avoids a Microsoft Store `python` alias.

```bat
git clone https://github.com/JaiKaushik03/cen5064-project-Jai.git
cd cen5064-project-Jai
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If using PowerShell instead, activate with `.\.venv\Scripts\Activate.ps1`.
If that is blocked by your execution policy, use Command Prompt as above; no policy change is required.

### macOS / Linux

```bash
git clone https://github.com/JaiKaushik03/cen5064-project-Jai.git
cd cen5064-project-Jai
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open **http://localhost:8501**. Streamlit prints the address in the terminal.
If Streamlit asks for an onboarding email, press Enter to skip it.

Stop the server with **Ctrl+C**. Restart with `python -m streamlit run app.py`.
Saved requests remain in the table.

### Database setup

The first application run automatically creates `data/propertycare.db` and the
`maintenance_requests` table. Every save commits to disk. The path is relative to
`app.py`, so restarting from another working directory does not create a second default database.

Database files are ignored by Git. An optional `PROPERTYCARE_DB_PATH` environment
variable overrides the file location; normal startup needs no environment variables.
Tests select isolated database files and never use the application's default database.

## Tests

From the repository root, with the virtual environment activated:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

This runs the original priority tests plus domain, service, real SQLite, and
Streamlit screen tests. It checks all four valid priorities, invalid priority,
blank required fields, saving and reloading records, preservation of existing
records after rejected submissions, new connections/sessions, and parameterized SQL.
Test temporary files live in the ignored `.pytest-tmp/` directory.

GitHub Actions uses Python 3.13, installs the same dependencies, and runs the same
test command for pushes to `main` and pull requests targeting `main`.

## Actual architecture

| Layer | Implementing files | Responsibility |
|---|---|---|
| Presentation | `app.py` | Streamlit form, validation messages, and saved-request table; wires the repository and service together. |
| Service | `src/services/maintenance_request_service.py` | Coordinates submission: constructs the domain object before saving, and loads requests for display. |
| Domain | `src/domain/maintenance_request.py`, `src/domain/priority.py` | Maintenance request data and validation; no UI or database dependency. |
| Data | `src/data/maintenance_request_repository.py` | Automatic SQLite setup, parameterized inserts, committed storage, and loading domain objects. |

```mermaid
flowchart LR
    UI[Streamlit screen] -->|submit| S[MaintenanceRequestService]
    S -->|construct and validate| D[MaintenanceRequest + Priority]
    S -->|save validated request / load requests| R[SQLite repository]
    R --> DB[(SQLite)]
    DB --> R
    R --> S
    S -->|confirmation and saved requests| UI
```

**Working slice:** Tenant submits request -> service validates by creating the
domain model -> SQLite repository saves -> service loads saved requests ->
Streamlit displays confirmation and the stored record.

The main rule is that priority must be exactly **Low, Medium, High, or Critical**,
using the existing `Priority` enum. Property / Unit and Issue title must contain
non-whitespace text. Description is optional. Invalid data raises a domain
validation error before the service calls storage; the UI displays that error.

## Architecture Decision Records

| Decision | Status |
|---|---|
| [ADR 001: Layered Architecture](docs/adr/adr-001-layered-architecture.md) | accepted |
| [ADR 002: SQLite Persistence](docs/adr/adr-002-sqlite-persistence.md) | accepted |

The original ADR template and worked example remain as course references.
They are not counted as PropertyCare decisions.

## Professor demo (60-90 seconds)

1. Open http://localhost:8501.
2. Enter **Oak Court / Unit 2B**, **Leaking kitchen sink**, and **Water pools below the cabinet.** Select **Critical**.
3. Click **Submit request**. Show the success message and matching row in **Saved maintenance requests**.
4. Stop the server with Ctrl+C, restart with `python -m streamlit run app.py`, and refresh the browser. Show that the row remains.
5. Leave Issue title blank and click **Submit request**. Show the validation message and that the saved-request count does not increase.
6. Show the README layer table and green CI badge; briefly show the passing test result.

## Semester scope and future work

The broader design includes registered properties and units, login and role-based
owner access, optional request images, work orders, assignment, status updates,
maintenance history, and repair costs. These features are planned and are **not**
implemented in this midterm slice. The original C4/UML diagrams and priority/image
design are preserved in [the planned full-semester design](docs/planned-design.md).

[Issue #5](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/5) tracks the working slice.
[PR #4](https://github.com/JaiKaushik03/cen5064-project-Jai/pull/4) documents the original priority rule and AI critique.

## Weekly log

- Week 1 (Aug 24): Repository created, three project ideas drafted, PropertyCare selected, and the approval paragraph added.
- Week 2 (Aug 31): Defined the four-tier architecture and its responsibilities.
- Week 3 (Sep 7): Created C4 diagrams, the initial UML class diagram, and the maintenance-request sequence.
- Week 4 (Sep 14): Expanded the planned design with optional images and four priority levels.
- Week 5 (Sep 21): Started Issue #1's planned login and owner portal workflow documentation.
- Week 6 (Sep 28): Implemented Domain priority validation, unit tests, AI critique, and peer-review README feedback.
- Week of Oct 5 (Oct 10): Implemented the midterm submit-and-view slice, SQLite persistence, interface/integration tests, two real ADRs, CI, and reproducible run instructions.
