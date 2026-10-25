# ADR 003: Separate authentication stores and protected legacy workspace

**Date:** 2026-10-24
**Status:** accepted by Jai; October 25 partner-feedback follow-up

## Context

Jai requires separate tenant/owner login, tenant signup, persistent profiles, and
secure passwords with explicit local demo setup. Existing maintenance requests
have no tenant identity. Showing that shared table to tenant accounts would reveal
unrelated request data; the ownership migration and full owner portal are deferred.

## Decision

Extend the four layers from ADR 001 and retain the maintenance database from ADR 002.
Use `data/tenant_accounts.db` and `data/owner_accounts.db` with separate repositories,
automatic repeatable initialization, case-insensitive email uniqueness, and checks
against mixing account/maintenance stores. Domain owns profile/password/consent
validation. Service coordinates signup, login, session checks, and storage.

Use [argon2-cffi](https://pypi.org/project/argon2-cffi/) 25.1.0 for salted Argon2id
hashing (64 MiB, three iterations, parallelism four). The cached local service issues
opaque random tokens backed by server-owned role/account/database identities.
Protected reads/writes recheck the account; logout revokes the token and clears
state. Password widgets are transient and cleared after login attempts, successful
signup, navigation, and logout. Failed signup retains the masked form inputs for
correction; successful signup prefills only the saved email on tenant login. No
plaintext password is placed in authenticated session records or account storage.

Extract the existing maintenance presentation and gate its shared workspace to
owners, including a Service adapter checking callbacks before writes. Tenant
landing pages expose no requests until a separate ownership migration. Preserve
the existing maintenance Domain, Service, Data, and original test assertions.

The CLI seeder requires `--local-demo` and rejects non-local environments. It never
runs automatically or replaces existing accounts. Weak public demo credentials
are exceptions only in that explicit seeder; fictional consent has a demo-seed version.

## Consequences

The project gains repeatable local authentication without a database server, and
role/store separation can be tested without relying on hidden buttons. Three
SQLite files and an in-memory token registry fit the course demonstration; app
restart requires login again. Public deployment and multi-process identity/session
management need later design.

Tenant access to the old shared workspace is deliberately suspended, preserving
data without falsely claiming tenant-specific visibility. Ownership, Active/Fixed
Issues, completion confirmation, assignment, costs, and images remain future work.
Earlier ADRs remain historical records.
