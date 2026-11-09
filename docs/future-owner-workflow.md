# Owner maintenance workflow

Status: implemented on codex/final-maintenance-workflow, awaiting partner review and merge. The filename is retained for existing links.

Active Issues includes issue ID/title/description, property/unit, priority, submission date, tenant name/email/phone/address/unit snapshot, assignment/progress and costs. Fixed Issues preserves those fields and adds completion time/notes. Legacy missing contacts/times remain explicitly unknown.

Mark Fixed opens a dialog requiring a confirmation checkbox and Submit. Cancel and unchecked submissions preserve storage. Service authorizes the current owner or assigned contractor; Domain validates completion; Data commits a serialized update. Completed remains the stored status and still rejects priority changes.

Owners register properties/units and contractor accounts, then assign Open work. Unassigned Critical requests must be assigned first. Contractors see only their own stable-key assignments, can record work started and complete repairs. Estimates and actual costs are recorded in cents. Optional photos are validated before persistence. No transition deletes the request.

See [final design](final-design.md), [ADR 005](adr/adr-005-retained-maintenance-lifecycle.md), [patterns](pattern-map.md) and [verification](final-verification.md). There is no deferred owner/contractor feature in this agreed final scope. Partner review, final merge approval and ongoing course review activity remain separate process steps.
