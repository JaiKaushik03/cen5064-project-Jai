# PropertyCare

[![CI](https://github.com/JaiKaushik03/cen5064-project-Jai/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/JaiKaushik03/cen5064-project-Jai/actions/workflows/ci.yml)

CEN 5064 Software Design · Jai LNU · Partner: GoldLion72

PropertyCare is a local rental-maintenance application built with Streamlit and SQLite. Tenants submit private requests; owners register properties and units, review tenant contact details, prioritize repairs and assign contractors; contractors see their own assignments and record progress and completion. Requests retain photos, cost records and history after completion.

This README describes the final implementation. For the pending review, clone the feature branch:

```bash
git clone --branch codex/final-maintenance-workflow https://github.com/JaiKaushik03/cen5064-project-Jai.git
cd cen5064-project-Jai
```

After merge, a normal clone of the repository gets the same implementation from main. Review and merge status are recorded on the PR, not inferred from this badge.

## Run on Windows

Install Git and Python 3.13. From the cloned repository, use Command Prompt or PowerShell:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.seed_demo_accounts --local-demo
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. If Streamlit asks for an onboarding email, press Enter. Stop with Ctrl+C; restart with the same Streamlit command. No activation command, database server, manual SQL or secret file is required.

## Run on Linux or macOS

With Python 3.13 installed, run these commands from the cloned repository:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.seed_demo_accounts --local-demo
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

## Local demonstration accounts

| Login | Email | Password |
|---|---|---|
| Tenant | user1@login.com | user1 |
| Tenant | user2@login.com | user2 |
| Tenant | user3@login.com | user3 |
| Owner | admin@admin.com | admin |

Demo profiles are fictional. The explicit `--local-demo` setup is repeatable: it does not overwrite existing accounts or reset passwords. It refuses a non-local `PROPERTYCARE_ENV`; startup never silently creates demo users. These weak published credentials are for the local course demonstration. Use fictional details and passwords that are not used elsewhere.

Owners create contractor accounts under **Manage contractors and assignments**, using a name, email and initial password. New passwords, including contractor passwords, require 12–128 characters with a letter and a number. Contractor signup is not public. Use **Login as Contractor** with the account the owner created. Contractor creation clears the masked password field after each attempt.

## Tenant workflow

1. Log in or choose Sign Up. Signup requires name, email, phone, address/unit, matching passwords and the academic terms acknowledgement. The optional updates preference sends no notifications.
2. Open **My maintenance requests**. Property / Unit initially uses the saved address/unit and stays editable. Property / Unit, Issue title and Priority are required; Description is optional.
3. Optionally link a registered unit and attach a PNG/JPEG of at most 2 MiB and 20 million pixels. Actual image content is decoded and validated before storage; renaming a file does not make it an image.
4. Submit. Success clears the text, optional unit selection and upload, resets Priority to Medium, preserves the confirmation and displays the saved request. Validation failure retains the entered form values.
5. View only your own persisted history and photos. Another tenant's request ID does not grant access. Logout and a new login clear private drafts, uploads and feedback.

Each new tenant request records a snapshot of their name, email, phone, address and unit. A later account/profile change cannot rewrite that snapshot. Registered-unit linking is a maintenance catalog reference, not a lease-verification system; tenants can still report an unregistered location. Request ownership always comes from the current authenticated account, never the selected unit or browser-supplied identity.

## Owner and contractor workflow

The **Owner Dashboard** contains Active Issues and Fixed Issues with request details, tenant contact snapshots, priorities, original submission times, assignment/progress, estimated/actual costs and completion times. Older rows with no verified contact information display **Unavailable (legacy/unassigned)**. Older Completed fixtures may have no known completion time; no timestamp or contact history is invented.

- **Manage properties and units:** register a property and its units. Duplicate registrations are rejected. Select a registered unit to see its maintenance history and repair costs.
- **Manage contractors and assignments:** create contractor credentials, select an unassigned request and contractor, enter an estimate and scheduled date, then Assign work.
- **Critical-first rule:** an unassigned, Open Critical request must be assigned before any lower-priority request. The Domain decides this rule inside a serialized SQLite read/decision/write transaction. Assigning Completed or already assigned work is rejected without changing storage.
- **Contractor Dashboard:** displays only the signed-in contractor's assigned requests. Start work records progress; Mark Fixed records completion. Another contractor's account or ID cannot access or complete that work. Owners retain oversight of the shared maintenance portfolio.
- **Mark Fixed:** opens a dialog with a required confirmation checkbox, actual repair cost and optional completion notes. Submit without confirmation is rejected. Cancel leaves the stored request unchanged. Success moves the row to Fixed Issues while preserving its ID, original details, contact snapshot, photo and submission time, and adds a completion time. No deletion occurs.
- **Open maintenance requests:** preserves the earlier owner submission/table/priority workspace. New priority loads the selected request's saved priority. Domain rejects all priority changes once the request is Completed.

**Fixed** is the display term for stored `Completed`; the original `Open`/`Completed` states are preserved. Assignment and In Progress are recorded separately. Costs are exact integer cents; negative, non-finite and more-than-two-decimal amounts are rejected. Zero is allowed. The course application records costs; it does not make payments.

## Storage and migration

| SQLite file | Contents |
|---|---|
| data/tenant_accounts.db | Tenant profiles, Argon2id hashes, stable account keys and signup acknowledgements |
| data/owner_accounts.db | Owner credentials |
| data/contractor_accounts.db | Owner-created contractor credentials and stable contractor keys |
| data/propertycare.db | Properties, units, requests, contact snapshots, photos, assignments, costs and retained history |

Files are created automatically and ignored by Git. Credential files reject the opposite account tables and maintenance tables; maintenance startup also rejects credential paths. `PROPERTYCARE_AUTH_DATA_DIR` selects the directory for all three account filenames; `PROPERTYCARE_DB_PATH` selects the maintenance file. Tests/browser checks use isolated stores. Back up all files together.

Migrations use transactions and add missing columns/tables without rebuilding existing rows or resetting IDs/sequences. Legacy requests remain owner-only when their tenant key is unknown. Missing historical snapshots stay unknown. Existing accounts are not reseeded or overwritten. Request and contractor ownership uses UUID keys so a replacement account with a reused numeric ID cannot inherit old history.

Passwords use salted Argon2id. Server-side opaque sessions resolve current roles and account/store identities on each operation. Presentation guards are backed by service authorization; hiding a button is not the access check. Sessions live in one server process and expire on server restart. This is a local academic application, not a production identity or multi-server platform.

## Tests

Windows:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
```

On Linux/macOS substitute `.venv/bin/python`. The full suite contains **267 cases**, including the 227-case baseline and 40 final workflow checks. It covers Domain decisions, Builder products, exact costs, actual image validation, safe legacy migrations, rollback, privacy, role boundaries, account replacement, confirmation/cancellation, Streamlit form behavior and persistence. Verification results are in [final verification](docs/final-verification.md).

## Architecture and design

| Layer | Files | Responsibility |
|---|---|---|
| Presentation | app.py; src/presentation/auth_views.py, maintenance_view.py, owner_views.py | Composition, guarded screens, forms, tables, session/widget state; no SQL |
| Service | AuthenticationService, TenantMaintenanceService, OwnerMaintenanceService, OwnerWorkflowService, ContractorWorkflowService, MaintenanceRequestService | Current-account authorization and use-case coordination through injected dependencies |
| Domain | accounts.py, maintenance_request.py, priority.py, request_status.py, properties.py, work_orders.py, request_builder.py | Account/request validation, immutable products, assignment order, completion, cost/image constraints |
| Data | account_repositories.py, contractor_repository.py, maintenance_request_repository.py | Separate account stores, bound SQL, transactional migrations and request persistence |

[Current C4, UML and sequence diagrams](docs/final-design.md) describe the actual code. [The five-pattern assessment](docs/pattern-map.md) explains the implemented **Builder** and the four alternatives. The [SOLID refactor](docs/solid-refactor.md) keeps authentication dependent on service-owned account/password interfaces. [Original design](docs/planned-design.md) and dated verification files remain historical references.

ADRs: [001 Layering](docs/adr/adr-001-layered-architecture.md), [002 SQLite](docs/adr/adr-002-sqlite-persistence.md), [003 Authentication](docs/adr/adr-003-separate-authentication.md), [004 Ownership](docs/adr/adr-004-tenant-request-ownership.md), [005 Lifecycle](docs/adr/adr-005-retained-maintenance-lifecycle.md), [006 Builder](docs/adr/adr-006-request-builder.md).

## Professor check-in demonstration

Prepare two tenant requests: one Critical and one Low. In two minutes: show tenant-private submission/history; log in as owner and show the contact snapshot; attempt to assign Low and show the Domain's Critical-first rejection; assign Critical; complete it with explicit confirmation; show the same row and timestamps in Fixed Issues; attempt a priority change and show the Completed restriction. Contractor progress, photos and unit cost history are supporting demonstrations.

## Tracking and review

[Project board](https://github.com/users/JaiKaushik03/projects/1), [owner portal #1](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/1), [completion #10](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/10), [final workflow/patterns #18](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/18). Implementation and verified corrections are committed in logical steps. Peer review and green CI precede merging; the final review PR is left open.

Jai supplied the project direction, requirements, professor feedback and acceptance criteria, and selected the full final scope. Codex provided substantial implementation and verification assistance. Recorded partner feedback is credited in the relevant PRs. The final PR includes the required AI critique with actual findings and corrections.
