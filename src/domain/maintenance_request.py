"""Maintenance request data and business rules; no UI or database dependencies."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.priority import Priority


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

    def __post_init__(self):
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
