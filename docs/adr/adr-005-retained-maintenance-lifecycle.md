# ADR 005 Retained maintenance lifecycle

Status: accepted for the final implementation; feature PR pending partner review.

## Context

The owner needs tenant contact details, assignments, costs and Active/Fixed history. Existing saved requests and the Completed priority restriction must survive. Old rows cannot supply verified contact snapshots or missing completion times. Concurrent assignment decisions must observe the same current queue.

## Decision

Keep Open/Completed in storage and display Completed as Fixed in the new dashboard. Capture immutable tenant contact values when a tenant submits. Persist assignment, scheduled/start/completion times, exact cent costs and optional validated image bytes with the same request. Use stable contractor keys and a separate contractor credential file. Service checks current roles and assignment ownership; Domain owns Critical-first assignment and completion validation. Serialize workflow read/decision/write with BEGIN IMMEDIATE and rollback on rejection. Add columns/tables transactionally without guessing legacy identity/history.

## Consequences

Requests retain their original ID, information and submission time. Fixed rows remain visible and cannot change priority. Owner confirmation is a service/Domain requirement backed by a dialog and checkbox. Contractors can act only on their assigned work. Existing historical contacts/times remain unknown when absent. SQLite stores bounded images, so backups grow; all account/request files must be backed up together. The local server shares one management portfolio across owner accounts; leases and multi-company tenancy are not modeled.
