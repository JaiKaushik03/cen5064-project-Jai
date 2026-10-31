# Future owner issue-management workflow

**Status:** Part 1 ownership is implemented on its review branch; the owner
Active/Fixed workflow remains planned. This records Jai's October 24 requirements. Related: broader Issue #1
and completion Issue #10.

## Tenant/request ownership first

Part 1 associates new requests with the authenticated account's stable UUID key.
Service validates the current session on every operation; request forms and URLs
cannot supply an owner. Tenant history and ID lookup filter by that key. The
repeatable account/request migrations preserve existing fields and sequences.

Legacy requests have no verified tenant association and remain unassigned,
visible only in the existing owner workspace. No automatic matching uses unit
labels or email. New account creation cannot reuse a previous account's history
through the same numeric ID. Parts 2 and 3 build on this association.

Tenant contact details are still stored in the account database, not snapshotted
onto requests. Part 2 must define/capture the requested historical contact snapshot
before profile editing is introduced. No profile editing exists in Part 1.

## Active Issues table

The authenticated Owner Dashboard will display Active Issues. Each row must show:

- Issue ID, title, and description.
- Priority and current status.
- Original submission timestamp.
- Tenant full name, email, phone number, address, and unit number.

Every active issue will offer **Mark Fixed**. Tenant accounts and unauthenticated
users must be denied by application/service authorization, not only by hidden UI.

## Mark Fixed confirmation

1. The owner selects Mark Fixed for an active issue.
2. A confirmation popup/dialog explains that the issue will be marked Fixed.
3. The owner must check an explicit confirmation checkbox.
4. The owner must click Submit.
5. Submission without the checkbox is rejected without changing storage.
6. Service loads the authorized issue and asks Domain to validate the transition.
7. Data commits the changed state and fixed/completion timestamp in SQLite.
8. The issue leaves Active Issues and appears in Fixed Issues.

No permanent deletion is allowed for this transition. Preserve the same issue ID,
all original issue information, associated tenant details, and original submission
timestamp. Fixed Issues also displays the fixed/completion timestamp. The future
design must retain historical tenant information even if profiles later change.

## State and layer responsibilities

The current Domain has Open and Completed states. Fixed is the requested future
UI term. A later design must define its mapping/transition without silently
renaming current stored states or weakening the Completed priority restriction.

Presentation supplies the table and confirmation controls; authentication/service
checks owner identity; Domain enforces allowed status transitions; Service
coordinates the workflow; Data performs parameterized transactional updates.

Future tests must cover ownership isolation, unauthenticated/tenant rejection,
missing confirmation, allowed/rejected transitions, unchanged data after rejection,
retained profile/issue details, both timestamps, table movement, and persistence
after restart. Contractor assignment, repair costs, and optional photos remain
separate future work.
