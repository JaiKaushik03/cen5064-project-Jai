"""Coordinates use cases; Domain owns request validation and priority-change rules."""

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.priority import Priority


class MaintenanceRequestService:
    def __init__(self, repository: MaintenanceRequestRepository):
        self.repository = repository

    def submit(
        self, property_unit: str, title: str, description: str, priority: str | Priority
    ) -> MaintenanceRequest:
        request = MaintenanceRequest(property_unit, title, description, priority)
        return self.repository.save(request)

    def list_requests(self) -> list[MaintenanceRequest]:
        return self.repository.list_all()

    def change_priority(self, request_id: int, priority: str | Priority) -> MaintenanceRequest:
        request = self.repository.get_by_id(request_id)
        if request is None:
            raise ValueError(f"Maintenance request #{request_id} was not found.")
        updated = request.change_priority(priority)
        return self.repository.update_priority(updated)
