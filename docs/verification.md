# PropertyCare technical verification

These checks were executed by Codex as AI-assisted technical verification.
They provide evidence for the student and partner to review; they do not claim
student execution, partner approval, or final acceptance.

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

## Review boundary

Main does not yet contain the application or CI workflow. README therefore clones
the working feature branch, and its badge selects feature-branch PR checks.
No green main run is claimed. Issue #1 remains future login/owner-portal work.
Issue #5 remains open while the implementation awaits real partner review and merge.
