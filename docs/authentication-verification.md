# October 24 authentication/signup verification

These are Codex-executed technical checks for Jai's requirements, not a claim
that Jai personally wrote or tested this code or that GoldLion72 approved it.
UI work used the hidden in-app browser with DOM interactions only. No native
desktop application, global mouse/keyboard input, or desktop takeover was used.

## Baseline and scope

- Local main was clean and matched live GitHub main at `1a6223c6c2667142098a7450a6cab6caad6dbb8d`.
- The existing project environment ran **75 passed, 0 failed** before changes.
- Issue [#12](https://github.com/JaiKaushik03/cen5064-project-Jai/issues/12) tracks the focused authentication scope. Broader Issue #1 stays open.
- Work is on `feature/tenant-owner-authentication`, created from that main revision.
- All existing maintenance Domain, Service, and repository modules are unchanged. Its UI moved into a presentation view and is called through an owner authorization adapter.
- The old maintenance tests retain their assertions; their fixture and restarted screen now log in through the real owner UI before opening the workspace.

## Automated verification

Executed in the project's Python 3.13.7 virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Final complete suite: **169 passed, 0 failed**. All 75 original cases are retained,
with 94 new account/security/UI cases. Dependency checks found no broken requirements.
Whitespace checks passed.

Coverage includes tenant and owner authentication, invalid and cross-store
credentials, generic failures, all required signup fields, malformed email and
phone input, case-insensitive duplicates, password policy/confirmation, required
terms, both updates preferences, salted Argon2id hashing/verification, no plaintext
account fields, separate store initialization/identity, bound queries, connection
cleanup, opt-in/non-local seed rejection, repeat seeding without changing account
values or ID sequences, account reconnection/restart, role and URL guards,
server-issued session tokens, logout/replay rejection, malformed stored credentials,
and recovery from expired protected routes. Startup without opt-in creates empty
account stores and does not open the maintenance database.

An explicit configuration test points the maintenance path at an authentication
file and verifies rejection before a maintenance table can be written there.
The original required fields, successful reset, failed-input retention, supported
priorities, priority changes, Completed rejection, migration, and persistence
regressions still pass through authenticated owner access.

## Default local demonstration setup

Executed the documented command against the actual default local account stores:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo_accounts --local-demo
```

The first run created **three tenant accounts and one owner account** in
`data/tenant_accounts.db` and `data/owner_accounts.db`. A second run created zero
new records; direct snapshots confirmed all existing fields, hashes, IDs, and
SQLite ID sequences were unchanged. No populated database is tracked by Git.

Verified all three exact `user1@login.com` through `user3@login.com` credentials
and `admin@admin.com` against a fresh authentication service. Tenant and owner
credentials were rejected by the other login method. Stored hashes parsed as
Argon2id with the documented cost; mandatory fictional tenant profiles and their
demo-seed terms versions were present. Hashes, not plaintext passwords, are stored.

## Real browser and server restart

Started Streamlit on loopback port 8504 using only ignored isolated data:

```powershell
$env:PROPERTYCARE_AUTH_DATA_DIR = "$PWD\.midterm-verification\auth-20261024\accounts"
$env:PROPERTYCARE_DB_PATH = "$PWD\.midterm-verification\auth-20261024\requests.db"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8504 --server.headless true --browser.gatherUsageStats false --server.fileWatcherType none
```

Observed in the in-app browser:

1. Tenant login was the first screen, with empty credentials and both navigation actions.
2. Owner credentials on tenant login produced the generic error and cleared the password field.
3. Each of the three demo tenants logged in and saw their own registered name, Logout, and no shared request table.
4. Signup displayed seven required fields, optional updates unchecked, and terms unchecked.
5. A complete fictional signup without terms was rejected; profile inputs stayed entered and password fields cleared.
6. Read the explicitly nonbinding academic terms, accepted that test acknowledgement, and created a fictional tenant with updates left unchecked.
7. Account creation confirmed and returned to login; the new credentials opened the Tenant Dashboard with the registered name.
8. Navigating to an owner-role URL did not grant protected access. The logged-in tenant also remained a tenant when using that URL after restart.
9. Owner login was separate, had no signup option or prefilled password, rejected tenant credentials, and accepted the exact owner credentials.
10. Only after owner login, the preserved maintenance workspace displayed isolated legacy rows. Open Medium changed to High; Completed Low rejected High and retained Low in storage.
11. A valid legacy submission showed success, cleared text fields, restored Medium, and kept the saved row. A blank-title submission preserved other entered text and added no row.
12. Logout returned to empty tenant login fields with no protected table. Stopped and restarted the actual server against the same files; the new signup account still logged in successfully.

Direct SQL checks confirmed the new fictional profile, normalized phone, unchecked
updates preference, UTC terms timestamp/version, and password hash after restart.
The isolated owner store still had one account; the isolated tenant store had the
three seed accounts plus the one UI signup. Exact maintenance queries showed only
the intended priority change and valid submission; the Completed fixture was intact.

The normal `data/propertycare.db` was not opened or migrated for these checks.
Its SHA-256 remained
`7CEF1520419228386A493BA6F460C57C556C4CE0D6CC44A03E974B3FC771DB7F`.
The test servers were stopped after checks without widget-state errors or warnings.

## Boundaries and handoff

Authentication session state stores opaque tokens. Typed password-widget values
exist transiently in Streamlit memory and are cleared after submissions/navigation;
they are not retained in authenticated session records or written/logged as plaintext.
Tenant/request ownership is not implemented, so tenant dashboards deliberately
cannot use or read the shared legacy workspace. The exact future owner Active/Fixed
Issues requirements are documented separately; no status, ownership, or assignment
tables/columns are added by this PR.

The feature PR must be open and ready for GoldLion72, without a review submitted,
approval invented, merge, or branch deletion. The previous October 18 merge
authorization applied to PR #9 only. Today's explicit instruction is to stop before
peer review and merge. Latest-head GitHub CI and the real PR URL are recorded in
the PR description and final handoff after GitHub confirms them.
