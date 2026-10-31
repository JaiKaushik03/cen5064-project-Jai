# Part 1: tenant requests and private history verification

## Review scope

Branch: `codex/tenant-owned-requests`, based on SOLID commit `5cd18b0` from PR #15.
Issue #16 covers only tenant submission/history and the ownership migration.
The feature PR targets `codex/solid-authentication-dip` so its diff excludes that
refactor. Review and merge #15 first, then retarget this PR to main and rerun CI.
Neither PR is approved or merged by this handoff.

## Actual automated results

The base has 184 passing tests. After Part 1, the project virtual environment ran
`python -m pytest -q`: **225 passed, 0 failed**, in 34.82 seconds. The 41 added
cases cover valid/private submission, invalid input, scoped lists/IDs, foreign and
missing ID indistinguishability, forged input, logged-out/owner/forged sessions,
recreated account/session isolation, relocation, both legacy schemas, repeat and
rollback migrations, private UI history/reset, role routes, expired-session drafts,
authentication-file collision checks and restart/reconnection.

Existing SOLID, authentication, signup password preservation/email prefill,
maintenance form reset, SQLite persistence, priority and Completed restrictions
continue passing. `python -m pip check` reports no broken requirements;
`git diff --check` passes. No new package dependency is required.

CI also accepts PR targets matching `codex/**`, in addition to main, so the
stacked review receives its own full-suite run. Push CI remains main-only.
The exact PR run and commit are recorded in the PR after GitHub completes them.

## Ownership and migration checks

Tenant account UUIDs persist and are unique. New requests get their key from
the current authenticated account. Legacy requests remain NULL/unassigned.
SQL list and ID queries include the key; there is no public tenant-key parameter.
Services recheck authentication before each operation and reject owners on the
tenant workflow. Domain still validates required text, priority, status and key.

Repeated migrations on fresh ignored copies of all three actual local databases
preserved every preexisting column value, credential hash, row ID and sequence.
New account keys were populated once; old requests stayed unassigned. Injected
index-creation failures in unit tests roll back prior ALTER/backfill changes.

All three original files under `data/` remain byte-for-byte unchanged during
verification. The migrations will run on first use of this branch's application;
they were exercised against copies and isolated fixtures here. No populated
database, verification copy or screenshot is committed.

## Real Chrome checks

Used port 8507 and only `.midterm-verification/part1/accounts/` plus `requests.db`.
Seeded three fictional demo tenants and one owner. The request fixture had two
unassigned rows, including one Completed record.

1. Tenant 1 opened My maintenance requests and saw no legacy records.
2. A missing title produced validation feedback and retained the entered unit and
   description. Correcting only the title saved request #3, reset fields/Medium,
   and displayed only that tenant's saved row.
3. Tenant 2 logged in with forged tenant/request/owner URL parameters present.
   They still saw empty personal history. Their own submission became #4, and
   their screen showed only #4, without #3 or legacy rows.
4. Owner login displayed all four records. Updating #3 to High succeeded.
   Updating the Completed #2 failed with the Domain error; its stored Medium stayed.
5. The actual server was stopped and restarted against the same files. Tenant 1
   still saw only #3 with High; tenant 2 still saw only #4 with Medium. Logout
   returned to blank login fields. Final session-cleanup code was smoke checked
   after a further restart.

Direct SQLite/service receipts confirmed each ownership key, filtered row IDs,
the owner update, unchanged Completed row, generic rejection of the other tenant's
ID, and repeated demo seeding without changing existing account keys/records.

## Limits

The property/unit label remains required free-form text; registered property/unit
authorization is later work. Owner contact-rich Active Issues is Part 2; contact
snapshots must be defined before profile editing. Mark Fixed, the confirmation
dialog and Fixed Issues history are Part 3. Existing owner-created requests remain
unassigned. Tenant priority editing, completion, deletion, assignment, costs and
photos are not implemented by this PR. Keep account and request backups together.
