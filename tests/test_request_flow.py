"""Business rules and real SQLite round trips through the service."""

from pathlib import Path
import sqlite3

import pytest

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.priority import Priority
from src.services.maintenance_request_service import MaintenanceRequestService


@pytest.mark.parametrize("priority", list(Priority))
def test_valid_request_uses_existing_priority_rule(priority):
    request = MaintenanceRequest(" Oak Court / 2B ", " Leak ", " Under sink ", priority.value)
    assert request.property_unit == "Oak Court / 2B"
    assert request.title == "Leak"
    assert request.description == "Under sink"
    assert request.priority is priority
    assert request.id is None
    assert request.created_at.endswith("+00:00")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("property_unit", ""),
        ("property_unit", "   "),
        ("property_unit", None),
        ("title", ""),
        ("title", "\t\n"),
        ("title", None),
        ("priority", "Extreme"),
        ("priority", ""),
        ("priority", None),
        ("description", None),
    ],
)
def test_invalid_request_does_not_save(tmp_path, field, value):
    repository = MaintenanceRequestRepository(tmp_path / "requests.db")
    service = MaintenanceRequestService(repository)
    values = dict(property_unit="Oak Court / 2B", title="Leak", description="", priority="High")
    values[field] = value
    with pytest.raises(ValueError):
        service.submit(**values)
    assert repository.list_all() == []
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM maintenance_requests").fetchone()[0] == 0


def test_valid_request_is_persisted_and_survives_new_repository(tmp_path):
    path = tmp_path / "nested" / "requests.db"
    service = MaintenanceRequestService(MaintenanceRequestRepository(path))
    saved = service.submit("Oak Court / 2B", "Leak", "Under the sink", "Critical")
    assert saved.id == 1
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT property_unit, title, description, priority FROM maintenance_requests"
        ).fetchone()
    assert row == ("Oak Court / 2B", "Leak", "Under the sink", "Critical")
    restarted = MaintenanceRequestService(MaintenanceRequestRepository(path))
    assert restarted.list_requests() == [saved]


def test_rejected_submission_preserves_existing_request(tmp_path):
    service = MaintenanceRequestService(MaintenanceRequestRepository(tmp_path / "requests.db"))
    saved = service.submit("Unit 2B", "Leak", "", "Medium")
    with pytest.raises(ValueError, match="Priority"):
        service.submit("Unit 2B", "Broken door", "", "Urgent")
    assert service.list_requests() == [saved]


def test_sql_like_input_is_saved_as_text_and_requests_are_newest_first(tmp_path):
    service = MaintenanceRequestService(MaintenanceRequestRepository(tmp_path / "requests.db"))
    first = service.submit("Unit 1", "Leak", "", Priority.LOW)
    second = service.submit("Unit 2", "'); DROP TABLE maintenance_requests; --", "", Priority.HIGH)
    assert service.list_requests() == [second, first]


def test_repository_closes_connections(tmp_path):
    path = tmp_path / "requests.db"
    repository = MaintenanceRequestRepository(path)
    saved = repository.save(MaintenanceRequest("Unit 1", "Leak", "", Priority.LOW))
    assert repository.list_all() == [saved]
    # On Windows an open SQLite handle prevents renaming: all operations must close it.
    renamed = Path(tmp_path) / "renamed.db"
    path.rename(renamed)
    assert MaintenanceRequestRepository(renamed).list_all() == [saved]
