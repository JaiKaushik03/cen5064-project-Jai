"""Coordinates use cases; Domain owns request validation and priority-change rules."""

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.priority import Priority
from src.domain.request_builder import MaintenanceRequestBuilder


class MaintenanceRequestService:
    def __init__(self, repository: MaintenanceRequestRepository):
        self.repository = repository

    def submit(
        self, property_unit: str, title: str, description: str, priority: str | Priority, *, photo=None, registered_unit_id=None
    ) -> MaintenanceRequest:
        if registered_unit_id is not None and self.repository.get_unit(registered_unit_id) is None:
            raise ValueError("Registered unit was not found.")
        request = (MaintenanceRequestBuilder(property_unit, title, description, priority)
                   .with_photo(photo).at_registered_unit(registered_unit_id).build())
        return self.repository.save(request)

    def list_requests(self) -> list[MaintenanceRequest]:
        return self.repository.list_all()

    def change_priority(self, request_id: int, priority: str | Priority) -> MaintenanceRequest:
        request = self.repository.get_by_id(request_id)
        if request is None:
            raise ValueError(f"Maintenance request #{request_id} was not found.")
        updated = request.change_priority(priority)
        return self.repository.update_priority(updated)

    def list_units(self):
        return self.repository.list_units()
