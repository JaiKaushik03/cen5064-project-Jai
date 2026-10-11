"""Check service behavior at the storage boundary, independently of SQLite."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.priority import Priority
from src.services.maintenance_request_service import MaintenanceRequestService


@pytest.mark.parametrize(
    ("property_unit", "title", "priority"),
    [("   ", "Leak", "High"), ("Unit 2B", "", "High"), ("Unit 2B", "Leak", "Urgent")],
)
def test_invalid_input_never_calls_storage(property_unit, title, priority):
    repository = Mock(spec=MaintenanceRequestRepository)
    service = MaintenanceRequestService(repository)
    with pytest.raises(ValueError):
        service.submit(property_unit, title, "", priority)
    repository.save.assert_not_called()


def test_service_passes_validated_domain_object_and_returns_storage_result():
    repository = Mock(spec=MaintenanceRequestRepository)
    repository.save.side_effect = lambda request: replace(request, id=42)
    service = MaintenanceRequestService(repository)
    result = service.submit(" Unit 2B ", " Leak ", " Under sink ", "Critical")
    repository.save.assert_called_once()
    submitted = repository.save.call_args.args[0]
    assert isinstance(submitted, MaintenanceRequest)
    assert submitted.property_unit == "Unit 2B"
    assert submitted.title == "Leak"
    assert submitted.description == "Under sink"
    assert submitted.priority is Priority.CRITICAL
    assert submitted.id is None
    assert result == replace(submitted, id=42)
