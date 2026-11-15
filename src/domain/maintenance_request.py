"""Maintenance request data and business rules; no UI or database dependencies."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from src.domain.accounts import normalize_account_key, utc_now
from src.domain.work_orders import require_assignment_order, validate_photo
from src.domain.priority import Priority
from src.domain.request_status import RequestStatus


@dataclass(frozen=True)
class MaintenanceRequest:
    property_unit: str
    title: str
    description: str
    priority: Priority
    id: int | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    status: RequestStatus = RequestStatus.OPEN
    tenant_key: str | None = None
    tenant_name: str | None = None
    tenant_email: str | None = None
    tenant_phone: str | None = None
    tenant_address: str | None = None
    tenant_unit: str | None = None
    completed_at: str | None = None
    assigned_contractor_key: str | None = None
    assigned_contractor_name: str | None = None
    assigned_at: str | None = None
    work_started_at: str | None = None
    scheduled_for: str | None = None
    estimated_cost_cents: int | None = None
    actual_cost_cents: int | None = None
    completion_notes: str = ""
    registered_unit_id: int | None = None
    photo: bytes | None = field(default=None, repr=False)

    def __post_init__(self):
        contact = (self.tenant_name, self.tenant_email, self.tenant_phone, self.tenant_address, self.tenant_unit)
        if any(value is not None for value in contact) and not all(isinstance(value, str) and value.strip() for value in contact):
            raise ValueError("Tenant contact snapshot must contain all five fields.")
        for value in (self.estimated_cost_cents, self.actual_cost_cents):
            if value is not None and (type(value) is not int or not 0 <= value <= 1000000000):
                raise ValueError("Repair costs must be nonnegative integer cents within the supported limit.")
        if not isinstance(self.completion_notes, str) or len(self.completion_notes) > 4000:
            raise ValueError("Completion notes must be text of at most 4000 characters.")
        if self.registered_unit_id is not None and (type(self.registered_unit_id) is not int or self.registered_unit_id <= 0):
            raise ValueError("Registered unit ID must be a positive integer.")
        if self.assigned_contractor_key is not None:
            object.__setattr__(self, "assigned_contractor_key", normalize_account_key(self.assigned_contractor_key))
        if self.scheduled_for is not None:
            from datetime import date
            try:
                date.fromisoformat(self.scheduled_for)
            except (ValueError, TypeError):
                raise ValueError("Scheduled date must be an ISO calendar date.") from None
        if self.completed_at is not None and self.status not in (RequestStatus.COMPLETED, "Completed"):
            raise ValueError("Only Completed requests can have a completion timestamp.")
        if self.photo is not None:
            validate_photo(self.photo)
        if self.tenant_key is not None:
            object.__setattr__(self, "tenant_key", normalize_account_key(self.tenant_key))
        for name, label in (("property_unit", "Property / Unit"), ("title", "Issue title")):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} is required.")
            object.__setattr__(self, name, value.strip())
        if not isinstance(self.description, str):
            raise ValueError("Description must be text.")
        object.__setattr__(self, "description", self.description.strip())
        try:
            object.__setattr__(self, "priority", Priority(self.priority))
        except (ValueError, TypeError) as error:
            choices = ", ".join(priority.value for priority in Priority)
            raise ValueError(f"Priority must be one of: {choices}.") from error

        try:
            object.__setattr__(self, "status", RequestStatus(self.status))
        except (ValueError, TypeError) as error:
            raise ValueError("Status must be Open or Completed.") from error

    def assign(self, contractor_key, contractor_name, estimate, requests, scheduled_for=None):
        require_assignment_order(self, requests)
        key = normalize_account_key(contractor_key)
        if not isinstance(contractor_name, str) or not contractor_name.strip():
            raise ValueError("Contractor name is required.")
        return replace(self, assigned_contractor_key=key, assigned_contractor_name=contractor_name.strip(),
                       assigned_at=utc_now(), estimated_cost_cents=estimate, scheduled_for=scheduled_for)

    def start_work(self):
        if self.status is RequestStatus.COMPLETED or self.assigned_contractor_key is None:
            raise ValueError("Only an assigned Open request can be started.")
        if self.work_started_at is not None:
            raise ValueError("Work has already started.")
        return replace(self, work_started_at=utc_now())

    def complete(self, *, confirmed, actual_cost=None, notes=""):
        if confirmed is not True:
            raise ValueError("Confirm that this request has been fixed before submitting.")
        if self.status is RequestStatus.COMPLETED:
            raise ValueError("This request is already Completed.")
        return replace(self, status=RequestStatus.COMPLETED, completed_at=utc_now(),
                       actual_cost_cents=actual_cost, completion_notes=notes)

    def change_priority(self, priority: str | Priority) -> "MaintenanceRequest":
        """Return a validated replacement; completed requests cannot change priority."""
        if self.status is RequestStatus.COMPLETED:
            raise ValueError(
                "Completed maintenance requests cannot have their priority changed."
            )
        return replace(self, priority=priority)
