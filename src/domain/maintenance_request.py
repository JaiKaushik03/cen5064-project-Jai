"""Maintenance request data and business rules; no UI or database dependencies."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from src.domain.accounts import normalize_account_key
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

    def __post_init__(self):
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

    def change_priority(self, priority: str | Priority) -> "MaintenanceRequest":
        """Return a validated replacement; completed requests cannot change priority."""
        if self.status is RequestStatus.COMPLETED:
            raise ValueError(
                "Completed maintenance requests cannot have their priority changed."
            )
        return replace(self, priority=priority)
