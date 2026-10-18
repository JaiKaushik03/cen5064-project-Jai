# PropertyCare technical verification

These checks were executed by Codex as AI-assisted technical verification.
They provide evidence for the student and partner to review; they do not claim
student execution, partner approval, or final acceptance.

These notes are chronological. The October 10 audit and initial October 18 implementation are historical snapshots; later sections record the partner feedback and the owner-authorized merge handoff.

## Existing implementation audit

- All 22 tracked files were read, including source, tests, README, ADRs, workflow,
  dependency files, preserved design, and course templates.
- Git status was clean before edits; local main matched live main at e2fa5a8.
- Issues #1, #3, and #5 and PRs #2, #4, and #6 were read, including PR diffs and recorded reviews.
- PR #2 added only one README log entry. GoldLion72 left a COMMENTED review.
- PR #4 added the priority enum and tests and updated README. GoldLion72's COMMENTED review reports passing tests.
- PR #6 has a successful Actions run at its existing head and no recorded partner review.
- The repository Projects page lists zero linked open or closed projects.

## Local commands and observed results

Run in the repository using its Python 3.13.7 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The initial audit produced **24 passed** and no broken dependencies.
After adding tests at the service/storage boundary, the suite produced **28 passed, 0 failed**.
Git whitespace checks passed after the documentation edits.

The new tests verify that blank property/unit, blank title, and unsupported priority
never call repository.save. A valid submission passes a normalized domain object to
storage and returns the stored result. Existing tests cover real SQLite insertion,
retrieval, new connections, SQL-like text, and the Streamlit form/display/new session.

## Fresh feature-branch verification

A separate clone was created under the original repository's ignored
`.midterm-verification/partner-review-20261010/` directory. It had its own new
virtual environment and an initially empty default database. Revision tested:
`7dfb14554211f35bca8b16e33ee2dcddb1828c36`.

Executed the README Windows Command Prompt setup and test commands:

```bat
git clone --branch maintenance-request-working-slice --single-branch https://github.com/JaiKaushik03/cen5064-project-Jai.git
cd cen5064-project-Jai
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
python -m streamlit run app.py
```

Observed results:
- Runtime and development installations succeeded.
- Python reported 3.13.7; the fresh environment produced **28 passed, 0 failed**.
- Dependency checks reported no broken requirements.
- Streamlit prompted for an onboarding email; pressing Enter skipped it as documented.
- Streamlit started at http://localhost:8501.
- The browser initially displayed no requests.
- Submitting Oak Court / Unit 2B, Fresh clone sink leak, description text, and Critical
  displayed success and a saved row.
- Blank title and blank property/unit were each rejected on the real screen.
- A direct sqlite3 query returned exactly:
  `[(1, 'Oak Court / Unit 2B', 'Fresh clone sink leak', 'Critical')]`.
- Submitting Extreme priority directly through the service raised
  `ValueError: Priority must be one of: Low, Medium, High, Critical.`
  A new repository connection still loaded exactly one request.
- Stopped the actual server using Ctrl+C, started it again with the same README
  command, reloaded the browser, and confirmed the same saved row remained.
- The optional PowerShell activation command was also executed successfully;
  the activated interpreter reported Python 3.13.7.

Additional SQLite/service check executed in the fresh clone using
`.\\.venv\\Scripts\\python.exe -c $verifyScript` with this source:

```python
from contextlib import closing
import sqlite3
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.services.maintenance_request_service import MaintenanceRequestService

with closing(sqlite3.connect("data/propertycare.db")) as connection:
    rows = connection.execute(
        "SELECT id, property_unit, title, priority FROM maintenance_requests"
    ).fetchall()
assert rows == [(1, "Oak Court / Unit 2B", "Fresh clone sink leak", "Critical")]
service = MaintenanceRequestService(MaintenanceRequestRepository("data/propertycare.db"))
try:
    service.submit("Unit 2B", "Invalid priority check", "", "Extreme")
except ValueError:
    pass
else:
    raise AssertionError("Invalid priority accepted")
assert len(service.list_requests()) == 1
```

These are Codex-observed results. They do not claim student execution or partner acceptance.

## Review boundary (historical: October 10)

At that point, main did not contain the application or CI workflow. README cloned
the working feature branch, and its badge selected feature-branch PR checks.
No green main run was claimed. Issue #1 was future login/owner-portal work.
Issue #5 was open while the implementation awaited partner review and merge.
These statements describe that earlier snapshot, not the current main branch.


## October 18: manager priority updates

### Baseline and scope

- Repository: `JaiKaushik03/cen5064-project-Jai`.
- Clean local main matched live main at `1ca46ffa4ef53aa22674c837ed130ae919b24be6`.
- Baseline: **30 passed, 0 failed** using the project's Python 3.13.7 virtual environment; `pip check` found no broken requirements.
- Work is on `feature/manager-priority-update`; main is not edited or merged.
- Existing ADRs, dependencies, CI configuration, and planned full-semester design are preserved.

### Automated verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The updated suite produced **69 passed, 0 failed**, including all 30 existing cases.

- Allowed: real SQLite Open request changes Medium to High, returned replacement is immutable, all unrelated fields match, and a fresh repository/service reloads High.
- Rejected: a Completed fixture raises the Domain's meaningful validation error. A spy wrapping the real repository proves `update_priority()` is not called. SQL and a fresh repository show the original priority unchanged.
- All four priority enum members and strings remain valid for Open requests. Unsupported priorities and statuses are rejected.
- Service delegation is tested explicitly: retrieve, call `MaintenanceRequest.change_priority()`, persist its result. Missing IDs never reach update.
- A populated original six-column schema migrates twice without lost fields or duplicate columns; old rows become Open, an updated row reloads correctly, and the next ID preserves the old sequence.
- Stale-status and missing-row update failures preserve stored data. Lookup/update connection cleanup is checked by renaming the database on Windows.
- AppTest exercises successful manager update/reload, Completed rejection with selection retention, and deletion between render and submit. Existing required labels, successful reset, failed-input retention, repeated submit, and saved-row tests still pass.

### Running application verification

Used `PROPERTYCARE_DB_PATH` to isolate a disposable database under the ignored
`.midterm-verification/oct18-priority-update/` directory. The normal
`data/propertycare.db` was not opened or migrated for these checks.

Started Streamlit on loopback port 8502 with:

```powershell
$env:PROPERTYCARE_DB_PATH = "$PWD\.midterm-verification\oct18-priority-update\manual.db"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

Observed through the actual browser:

1. Startup migrated two existing six-column records to Open. IDs 7/8, property/unit, titles, descriptions, original priority values, and exact UTC timestamps survived.
2. Selected legacy request #7 and changed Medium to High. Success and the saved table showed High; a direct SQLite query confirmed the exact original row except for priority.
3. Submitted a new request through the original form. Success and the new saved row stayed visible; text fields cleared and priority returned to Medium.
4. Marked only disposable fixture #8 Completed using a test setup script (there is no completion UI). The browser rejected its proposed High priority with the Domain error; the table kept Low/Completed.
5. Submitted a blank title with other text entered. The validation message appeared; property/unit and description stayed entered and no new row was added.
6. Stopped the actual server, restarted it against the same file, and reloaded the browser. High for #7, Low/Completed for #8, and submitted rows remained.
7. Live regression checks exposed a pre-existing default/session-state duplication warning after successful submission. Both priority dropdowns now initialize from session state without a competing explicit widget default, and the full suite still passes. Request selection labels are stable; current priority/status are shown in the table. Repeated successful and failed submissions against the final source produced no widget-state warnings in the server output.

### Responsibility and review boundary

Domain owns the Completed restriction and value validation. Service coordinates
lookup, Domain validation, and persistence. Data performs SQLite reads/writes and
the repeatable schema migration. The UI calls Service and displays results.

The manager controls are a demonstration, without authentication or role authorization.
Open/Completed is the minimal state model needed for the rule; a status-change
workflow, assignment, and contractor features are not implemented.

These initial implementation results were AI-assisted technical verification,
not peer review or student execution. At that handoff, the PR was Draft and Codex
stopped before peer review. Codex did not request, submit, or approve a review or
merge the PR. The later partner review is recorded below.
GitHub Actions evidence for each tested commit is recorded in the PR.


## October 18: partner-review follow-up for PR #9

### Review verified on GitHub

GoldLion72 submitted a **COMMENTED** review of commit
`76bca39894ce3bc8ddb2ad2ccb6b6fb9c7807c69` on October 18. It was not an APPROVED
or CHANGES_REQUESTED review. The
[review](https://github.com/JaiKaushik03/cen5064-project-Jai/pull/9#pullrequestreview-5564434492)
supported the Domain placement and passing tests, then recommended two improvements:

- Make New priority match the selected request's saved priority.
- Address a completion UI in future work if it falls outside this assignment.

All PR discussion entries and review threads were read. There were no inline
review threads to resolve. No review was submitted or approved by Codex.

### Corrections and contribution credit

The request selector and manager priority control now use normal Streamlit reruns
outside the submission form. A request-ID marker synchronizes the dependent
priority only when selection changes, before its widget is rendered. Selecting
a request does not write to storage. An unrelated rerun keeps an unsaved proposal
for the same request; a failed update preserves that proposal. Update Priority
still calls Service and the Domain method before persistence.

The original request-submission form and its Medium default/reset remain intact.
Domain, Service, SQLite migration, and repository implementation are unchanged
by this follow-up.

The completion UI is recorded as planned work in
[Issue #10](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/10).
The assignment explicitly allowed Completed fixtures without a completion UI, so
no status-management subsystem was added to this PR.

README credit now states that Jai directed the requirements, professor feedback,
and acceptance criteria; Codex performed most of the coding, automated tests,
implementation documentation, and technical verification; and GoldLion72 provided
the recorded peer feedback. It does not attribute Codex execution to the student
or treat a GitHub commit author as proof of who wrote every line.

### Verification actually performed

- Baseline before this follow-up: **69 passed, 0 failed** in the project's virtual environment.
- Updated complete suite: **75 passed, 0 failed**. All 69 prior cases are retained.
- Six added cases check the four saved priority defaults, request switching without persistence, preservation of an unsaved proposal across refresh, correct selected-record updates, and Completed rejection with the proposed value retained.
- `python -m pip check`: no broken requirements. `git diff --check`: passed.
- Started Streamlit on loopback port 8503 with an isolated database at `.midterm-verification/pr9-review-followup-20261018/manual.db`.
- The real browser initially selected a Completed Low fixture with New priority Low. Switching to the Critical request immediately loaded Critical; switching to the Low request loaded Low without clicking Update.
- Changed the Open Low fixture to High and saw the saved table update. Proposing High for the Completed Low fixture showed the Domain error and retained proposed High; the saved row stayed Low/Completed.
- Submitted a valid new request and observed cleared text fields, Medium submission priority, success, and the saved row. Submitted a blank title with other text entered and observed the normal error, retained inputs, and no extra row.
- Direct SQLite assertions confirmed exact original fixture fields except the intended priority change, and confirmed the Completed and unselected Critical fixtures were unchanged.
- The normal `data/propertycare.db` was not opened or migrated for the checks; its SHA-256 remained unchanged.
- The server was stopped after verification and produced no widget-state error/warning output.

### Previous stopping point (historical)

The correction was committed as `bbf159406c65985b0df96de904cc90c7769fe66f`
and pushed to the same branch. Its CI run
[39170131829](https://github.com/JaiKaushik03/cen5064-project-Jai/actions/runs/39170131829)
passed all 75 tests. At that handoff, Codex recommended re-review and left PR #9
Draft and unmerged. No review was requested, submitted, or approved by Codex.
The owner later gave a different instruction, recorded below.


## October 18: owner-authorized final integration

After the partner's comments were addressed, Jai explicitly instructed Codex to
merge without a second review and update the project, README, and related records.
This supersedes the previous stop-before-merge instruction and re-review
recommendation. It does not turn GoldLion72's COMMENTED review into APPROVED,
and no review or approval is submitted on the partner's behalf.

The final documentation cleanup removes the temporary feature-branch checkout
instructions, clones `main` explicitly, links the public project board, and lists
implemented versus planned scope. It also clarifies the earlier description
question: digit-only strings are text; a non-string value is rejected by Domain.
The Linux/macOS setup alternatives remain documented. No new description
restriction or unrelated subsystem is introduced.

The board keeps completed priority validation and request submission in Done,
tracks PR #9 through its merge, and keeps login/owner access (#1) and completion
UI (#10) as future Todo work. The completed workflow issue's old waiting-for-PR-7
wording is corrected. The partner's original review text is preserved.

The functional implementation is unchanged from `bbf1594`: Domain owns the
Completed restriction, Service coordinates, Data performs safe migration and
parameterized storage, and the manager selector loads the saved priority. Local
verification before this documentation cleanup and the corresponding CI both
passed all 75 tests; real-browser and original-database-preservation evidence is
recorded above.

The final documentation commit is checked in PR CI before a normal GitHub merge
with an expected-head SHA. No force merge, protection override, fabricated review,
or branch deletion is authorized. The resulting merge SHA and main-branch CI
receipt are recorded in PR #9 and the final handoff after GitHub confirms them.
