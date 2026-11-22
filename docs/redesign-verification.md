# Accessible UI and audit follow-up

Branch: `design/fiu-inspired-accessible-ui`. Target: main. PR #22 contains the implementation and verification history; merge requires project-owner authorization.

## Audit changes

| Finding | Implementation / regression coverage |
|---|---|
| Stale/concurrent priority changes | Additive revision column; screen snapshot, service precondition and atomic SQL compare-and-swap; interleaved/ABA and simultaneous-writer regressions. |
| Concrete repository dependency | Service-owned MaintenanceRequestStore Protocol; clean-interpreter test blocks Data/SQLite imports. |
| Unbounded history and repeated image work | SQL pagination and aggregates; photo-free summaries; explicit scoped photo access; selected request + relevant Critical queue per transaction; indexed ownership/status/unit lookups. |
| Database mixing | Constructor-level rejection in both directions, including case-insensitive table names; rejected initialization leaves existing bytes unchanged. |
| Contradictory feedback | Shared feedback cleanup before new actions and navigation; failed Start work clears older success. |
| Completion rules | Owner may confirm their own repair of unassigned Open work; contractor may start/complete only their own assigned work; confirmation, retained history and Completed priority restriction remain. |
| Input limits and historical data | Domain bounds new text; UI mirrors limits; existing longer values survive read/reload/priority updates without truncation. |
| Oversized images | Browser upload limit plus upload-size check before getvalue; full byte-format/decode/pixel validation remains. |
| Forced scheduling | Date starts empty; both unscheduled and explicitly scheduled assignments covered. |
| Session lifetime | Configurable positive lifetime; fake-clock tests for exact expiration, all roles, cleanup and rerun behavior. |
| Unit-selection privacy | Existing catalog selection retained; tenant/contractor paged counts and photo access remain scoped by stable account keys; no lease-verification claim. |
| Beginner/accessibility feedback | Native labeled widgets, larger type, navy/white contrast, gold focus/accents, responsive spacing, guidance, empty states and loading feedback. |
| Static/security checks | Ruff E4/E9/F, pip check and strict pip-audit in CI; no ignored advisory IDs. |
| Actions maintenance | Checkout 7.0.1 and setup-python 7.1.0; Python 3.13; full tests + lint + consistency + security audit on PRs and branch pushes. |
| Dependency advisories | Initial audit reported 42 Pillow 12.3.0 advisories; Pillow 13.0.0 requires the compatible Streamlit 1.67.0 update. |

## Preservation and scope

All original tests are retained. The existing scheduled-assignment screen test now chooses an explicit date, so it continues checking scheduled persistence while a new regression checks the newly optional blank date. Lint removes unused imports only. Historical verification documents and all existing README diagrams/screenshots remain.

New test data and the live review server use an isolated directory outside saved application data. No populated database, credentials, virtual environment or temporary test data belongs in the PR. SQL migrations add fields/indexes; they do not rebuild or delete rows. Completion/assignment retain original photos, contact snapshots and issue fields.

Jai supplied project direction and acceptance criteria. Codex performed the redesign, audit implementation and verification assistance. GoldLion72's November 16 issue identified the maintenance-service dependency-inversion concern addressed here. No new peer approval or grade is claimed.

## Verification — November 21, 2026

- Clean branch virtual environment: Python 3.13.7; installed `requirements-dev.txt`, including Streamlit 1.67.0 and Pillow 13.0.0.
- Full suite: **319 passed, 0 failed in 41.15 seconds**. All 277 existing cases remain; 42 added cases cover the audit changes.
- `python -m ruff check .`: all checks passed. `python -m pip check`: no broken requirements. `git diff --check`: clean.
- `python -m pip_audit -r requirements-dev.txt --strict --progress-spinner off`: no known vulnerabilities in the updated project dependencies. No advisory exclusions.
- SQLite backup copies of all four saved databases were migrated twice. All original columns, rows, photo bytes, IDs and sequences were preserved. SHA-256 hashes of the saved source files remained unchanged. The live review server used separate fictional data.
- Live browser: tenant signup/login; invalid submission retained input; successful submission cleared fields and reset priority; registered-unit request; owner property/unit/contractor creation; Critical-first rejection; assignment with blank scheduling; contractor-only assigned list; Start work; completion cancellation/unchecked rejection/confirmed completion; retained Fixed Issues and costs; owner completion of unassigned work; Completed-priority rejection; keyboard owner login; navigation and logout.
- Desktop and mobile views checked at 1280×800 and 390×844. The mobile document width was 390 pixels with no horizontal document overflow. Keyboard focus used a visible 3-pixel gold outline. Caption opacity was verified as 1 with text color `#42556C`.
- Restarting the isolated server preserved fictional requests and totals. A development-time partial module reload produced an authorization mismatch while source files were being edited; a clean process with the finished code passed the affected routes. Restart after authentication-code or dependency changes; normal reruns retain sessions until expiration.
- Automated coverage, rather than a manual upload claim, verifies valid/corrupt/oversized images, lazy scoped photo retrieval, concurrent writers, larger histories, both scheduling cases and exact session-expiry boundaries.

Screenshots: [owner dashboard](screenshots/redesign-owner.jpg), [mobile login](screenshots/redesign-login-mobile.jpg). GitHub Actions results for the pushed commit are recorded in the review PR; main remains unchanged until separately approved.

## Remaining limits

This remains a local academic application: SQLite files are not encrypted at rest; sessions are held in one process; registered units do not verify a lease; no email or payment integration is implied. Keyboard/layout/contrast checks are not a complete screen-reader or WCAG certification. These limits do not remove an existing feature or bypass an audit correction.

## Partner photo feedback — November 22, 2026

GoldLion72's COMMENTED review of `8a814a4` identified that viewing a request photo and completing a different repair closed the preview. This was a usability correction, not a formal approval.

The shared photo helper now retains one validated photo in session state and gives each expander a stable key. It only renders the cached image when the current authorized history includes that request; request revisions trigger a fresh authorized fetch, selecting another photo replaces the cache, and logout clears it. Existing View photo controls and lazy loading remain.

Two additional real-screen regressions check completion without losing the preview, logout cleanup, a single bounded selection, and revision refresh. Full suite: **321 passed, 0 failed in 40.16 seconds**; Ruff and pip check passed. A live isolated owner session opened photo #3, confirmed completion of unrelated request #4, and retained the expanded image afterward. No saved application database was used.
