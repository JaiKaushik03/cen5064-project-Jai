# SOLID refactor: Dependency Inversion

## The concern

Lecture 5 asks for one genuine concern, a small refactor, and a PR named for the
principle. This change addresses **D: Dependency Inversion** in
`src/services/authentication_service.py`.

Before the change, the service accepted repository objects, so dependency
injection was partly present. However, concrete `isinstance` checks required
`TenantAccountRepository` and `OwnerAccountRepository`; a correct in-memory
implementation was rejected. The service also imported and constructed the
Argon2 adapter when it was omitted. Importing the policy consequently loaded
SQLite and Argon2 implementation modules.

This is a dependency-direction problem rather than a claim that every large
module violates Single Responsibility. The authentication workflow remains in
one service; it has not been split into unrelated classes for appearance.

## Before and after

| Concern | Before | After |
|---|---|---|
| Store contract | Concrete SQLite classes and database paths | Service-owned tenant/owner protocols, explicit roles and stable identities |
| Password implementation | Service created a default Argon2 adapter | Required codec supplied by startup |
| Production composition | Repositories passed in, hasher implicit | Startup explicitly supplies all three existing adapters |
| Independent service test | Non-SQLite stores rejected | In-memory stores exercise the same policy |

`authentication_ports.py` imports Domain models and standard-library typing only.
The tenant interface includes lookup and save; the owner interface needs lookup
only because public owner registration is not supported. Both expose role and
identity. The password interface provides hash and verify. SQLite repositories
declare their existing roles and satisfy the protocols structurally; there is
no new adapter framework or package dependency.

The composition factory is the one place that selects SQLite and Argon2 for the
running authentication service. New store implementations must honor the protocol
and identity contract. These are trusted internal dependencies supplied at startup,
not user-submitted objects. Static contracts and runtime shape/role checks do not
certify arbitrary plugins as secure.

## Behavior retained

- Required signup fields, terms, optional preference and normalized unique email.
- Salted Argon2id with the existing parameters; no alternate production hasher.
- Separate tenant/owner files, role checks, account/store session rechecks and logout.
- Preserved signup passwords after validation errors and login email prefill after success.
- Maintenance submission reset, saved requests, priority changes and Domain-owned Completed rejection.
- Non-destructive database initialization/migration and local-only repeat demo setup.
- Authentication-file collision guards, including platform-aware path comparison.

No schema or migration changes, tenant ownership, Active/Fixed Issues, completion,
assignment, repair costs or photos are included.

## Verification

The clean main baseline was `f764c93`: **173 passed, 0 failed** in 26.95 seconds.
After the refactor: **184 passed, 0 failed** in 24.28 seconds, using the project's
Python 3.13 virtual environment. `python -m pip check` found no broken requirements;
`git diff --check` passed.

Ten new tests cover non-SQLite signup/login/logout, owner/tenant isolation,
session invalidation when an account/store changes, validation and duplicates,
swapped roles, shared identities, incomplete adapters, and importing policy in a
fresh interpreter while concrete adapter imports are blocked. One additional
existing-screen case checks both tenant and owner authentication-file collisions;
the local Windows run also changes path case.

Chrome smoke verification used port 8506 with only
`.midterm-verification/solid-dip/accounts/` and `requests.db` overrides. Verified:

1. Owner credentials are rejected on tenant login with the generic error.
2. A demo tenant logs in with its registered name and no shared maintenance data.
3. Missing signup unit keeps entered values and both masked passwords. Correcting
   only the unit creates the account and prefills its email on login.
4. Entering only the password then logs the new tenant in.
5. Owner login opens the existing maintenance workspace. A fictional request saves,
   the form clears to Medium, and its priority changes to High in the saved table.
6. Logout returns to blank login fields.

All original local database hashes remain unchanged. No populated databases or
verification screenshots are committed. CI results are recorded in the PR after
GitHub completes its checks. GoldLion72 should verify that the named DIP concern
is what the change actually fixes. The PR stays open and unmerged until review.
