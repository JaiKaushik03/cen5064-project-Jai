"""Coordinates use cases; Domain owns request validation and priority-change rules."""

from src.domain.maintenance_request import MaintenanceRequest, ConcurrentRequestError
from src.domain.priority import Priority
from src.domain.request_builder import MaintenanceRequestBuilder
from src.services.maintenance_ports import MaintenanceRequestStore


class MaintenanceRequestService:
    def __init__(self, repository: MaintenanceRequestStore):
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

    def change_priority(self, request_id: int, priority: str | Priority, *, expected_revision=None) -> MaintenanceRequest:
        request = self.repository.get_by_id(request_id)
        if request is None:
            raise ValueError(f"Maintenance request #{request_id} was not found.")
        updated = request.change_priority(priority)
        if expected_revision is not None and request.revision != expected_revision:
            raise ConcurrentRequestError("Another person changed this request. Reload the selected request and review it before saving.")
        return self.repository.update_priority(updated)

    def list_units(self):
        return self.repository.list_units()

    def list_requests_page(self, **filters):
        return self.repository.list_page(**filters)

    def get_request(self, request_id):
        request = self.repository.get_by_id(request_id)
        if request is None:
            raise ValueError("Maintenance request was not found.")
        return request
