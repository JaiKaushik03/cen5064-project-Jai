# ADR 004: Stable tenant/request ownership

**Date:** 2026-10-31
**Status:** proposed for Part 1 partner review

## Context

Authenticated tenants need private request submission and history. Existing
maintenance rows contain only a free-form property/unit label and cannot safely
be attributed to a tenant. Numeric account IDs can be reused after a restore or
recreation; storing an absolute database path would break links after relocation.
Tenant and maintenance databases must remain separate.

## Decision

Give every tenant account a persisted UUID `account_key`. New tenant requests
store it as `tenant_key`; the Service derives it from the current server-validated
account on each operation. SQL list and ID lookup bind this key. A missing or
foreign request returns the same not-found result. Browser forms/URLs cannot
choose ownership. Session principals bind the key as well as ID/email/store identity.

Account initialization backfills missing keys and creates a unique index inside
its existing transaction. Request initialization adds a nullable key and index,
retaining the prior status migration in the same transaction. Old request keys
remain NULL. Neither migration rebuilds tables, renumbers rows or resets sequences.
No unit/email heuristic claims ownership of legacy requests.

The existing owner workspace remains authorized to see all rows. Tenants receive
a scoped service for form/history rendering with no priority-update interface.
Expired protected sessions and successful new logins clear private UI state.

## Consequences

Ownership survives restarts and relocation, and an unrelated recreated account
does not inherit old history. SQLite cannot provide a normal foreign key across
these separate files, so the service validates account access. Migrations are
atomic per file, not a distributed transaction; either file can be initialized
again safely. Back up the account/request files together to retain their links.

Legacy rows stay owner-only until a separately designed, verified assignment
workflow exists. No completion, assignment, contact snapshot or profile-editing UI
is added. Parts 2/3 must retain original issue details and define the requested
historical contact information before allowing profile changes.
