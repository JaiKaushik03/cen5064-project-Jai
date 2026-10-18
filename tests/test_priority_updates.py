"""Domain-owned priority changes, service coordination, and safe SQLite migration."""

from contextlib import closing
from dataclasses import FrozenInstanceError, replace
import sqlite3
from unittest.mock import Mock, patch

import pytest

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.priority import Priority
from src.domain.request_status import RequestStatus
from src.services.maintenance_request_service import MaintenanceRequestService


def request(**changes):
    values = dict(
        property_unit="Oak Court / Unit 2B",
        title="Sink leak",
        description="Water below cabinet.",
        priority=Priority.MEDIUM,
        created_at="2026-10-18T14:00:00+00:00",
    )
    values.update(changes)
    return MaintenanceRequest(**values)


def stored_rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(
            "SELECT id, property_unit, title, description, priority, created_at, status "
            "FROM maintenance_requests ORDER BY id"
        ).fetchall()


@pytest.mark.parametrize(
    "status", [RequestStatus.OPEN, "Open", RequestStatus.COMPLETED, "Completed"]
)
def test_status_converts_to_enum(status):
    assert request(status=status).status is RequestStatus(status)


@pytest.mark.parametrize("status", [None, "In Progress", "", 0])
def test_invalid_status_is_rejected(status):
    with pytest.raises(ValueError, match="Status must be Open or Completed"):
        request(status=status)


@pytest.mark.parametrize("priority", list(Priority) + [item.value for item in Priority])
def test_domain_open_request_returns_validated_immutable_replacement(priority):
    original = request(id=7)
    assert original.status is RequestStatus.OPEN
    updated = original.change_priority(priority)
    assert updated == replace(original, priority=Priority(priority))
    assert updated is not original
    assert original.priority is Priority.MEDIUM
    with pytest.raises(FrozenInstanceError):
        original.priority = Priority.HIGH


@pytest.mark.parametrize("priority", list(Priority))
def test_domain_completed_request_rejects_priority_change(priority):
    original = request(status=RequestStatus.COMPLETED)
    with pytest.raises(ValueError, match="Completed maintenance requests cannot"):
        original.change_priority(priority)
    assert original.priority is Priority.MEDIUM


@pytest.mark.parametrize("priority", ["Urgent", None, "", 42])
def test_domain_rejects_invalid_new_priority(priority):
    with pytest.raises(ValueError, match="Priority must be one of"):
        request().change_priority(priority)


def test_allowed_change_persists_after_reload_and_preserves_unrelated_fields(tmp_path):
    path = tmp_path / "allowed.db"
    repository = MaintenanceRequestRepository(path)
    saved = repository.save(request())
    before = stored_rows(path)[0]

    updated = MaintenanceRequestService(repository).change_priority(saved.id, "High")

    assert updated == replace(saved, priority=Priority.HIGH)
    expected = list(before)
    expected[4] = "High"
    assert stored_rows(path) == [tuple(expected)]
    restarted = MaintenanceRequestService(MaintenanceRequestRepository(path))
    assert restarted.list_requests() == [updated]
    assert saved.priority is Priority.MEDIUM


def test_completed_change_never_calls_update_and_preserves_database_after_reload(tmp_path):
    path = tmp_path / "completed.db"
    repository = MaintenanceRequestRepository(path)
    saved = repository.save(request(status=RequestStatus.COMPLETED))
    before = stored_rows(path)
    observed_repository = Mock(spec=MaintenanceRequestRepository, wraps=repository)

    with pytest.raises(ValueError, match="Completed maintenance requests cannot"):
        MaintenanceRequestService(observed_repository).change_priority(saved.id, "High")

    observed_repository.get_by_id.assert_called_once_with(saved.id)
    observed_repository.update_priority.assert_not_called()
    assert stored_rows(path) == before
    assert MaintenanceRequestRepository(path).get_by_id(saved.id) == saved


@pytest.mark.parametrize("priority", ["Extreme", None, "", 42])
def test_service_does_not_persist_invalid_priority(tmp_path, priority):
    repository = MaintenanceRequestRepository(tmp_path / "invalid.db")
    saved = repository.save(request())
    observed_repository = Mock(spec=MaintenanceRequestRepository, wraps=repository)
    with pytest.raises(ValueError, match="Priority must be one of"):
        MaintenanceRequestService(observed_repository).change_priority(saved.id, priority)
    observed_repository.update_priority.assert_not_called()
    assert repository.get_by_id(saved.id) == saved


def test_service_handles_missing_id_without_update(tmp_path):
    repository = MaintenanceRequestRepository(tmp_path / "missing.db")
    observed_repository = Mock(spec=MaintenanceRequestRepository, wraps=repository)
    with pytest.raises(ValueError, match="Maintenance request #999 was not found"):
        MaintenanceRequestService(observed_repository).change_priority(999, "High")
    observed_repository.update_priority.assert_not_called()
    assert repository.list_all() == []


def test_service_delegates_validation_to_domain_before_persistence():
    original = request(id=4)
    updated = replace(original, priority=Priority.HIGH)
    repository = Mock(spec=MaintenanceRequestRepository)
    repository.get_by_id.return_value = original
    repository.update_priority.return_value = updated
    with patch.object(
        MaintenanceRequest, "change_priority", autospec=True, return_value=updated
    ) as change:
        assert MaintenanceRequestService(repository).change_priority(4, "High") is updated
    repository.get_by_id.assert_called_once_with(4)
    change.assert_called_once_with(original, "High")
    repository.update_priority.assert_called_once_with(updated)


def test_old_schema_migrates_twice_preserving_every_field_and_id_sequence(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_rows = [
        (7, "Unit 7", "Tenant's leak", "Original details", "Medium", "2026-09-01T10:00:00+00:00"),
        (12, "Unit 12", "A/C repair", "Keep café text", "Critical", "2026-10-01T11:00:00+00:00"),
    ]
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("""CREATE TABLE maintenance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, property_unit TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        connection.executemany(
            "INSERT INTO maintenance_requests VALUES (?, ?, ?, ?, ?, ?)", legacy_rows
        )

    MaintenanceRequestRepository(path)
    repository = MaintenanceRequestRepository(path)

    assert stored_rows(path) == [row + ("Open",) for row in legacy_rows]
    with closing(sqlite3.connect(path)) as connection:
        columns = connection.execute("PRAGMA table_info(maintenance_requests)").fetchall()
    assert [column[1] for column in columns].count("status") == 1
    status_column = next(column for column in columns if column[1] == "status")
    assert status_column[3] == 1  # NOT NULL
    assert status_column[4] == "'Open'"
    updated = MaintenanceRequestService(repository).change_priority(7, "High")
    assert MaintenanceRequestRepository(path).get_by_id(7) == updated
    assert stored_rows(path)[1] == legacy_rows[1] + ("Open",)
    assert repository.save(request(title="New request")).id == 13


def test_stale_status_does_not_overwrite_database(tmp_path):
    path = tmp_path / "stale.db"
    repository = MaintenanceRequestRepository(path)
    saved = repository.save(request())
    proposed = saved.change_priority("High")
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "UPDATE maintenance_requests SET status = ? WHERE id = ?",
            ("Completed", saved.id),
        )
    before = stored_rows(path)
    with pytest.raises(ValueError, match="status changed"):
        repository.update_priority(proposed)
    assert stored_rows(path) == before


def test_update_missing_record_does_not_insert(tmp_path):
    repository = MaintenanceRequestRepository(tmp_path / "deleted.db")
    with pytest.raises(ValueError, match="no longer exists"):
        repository.update_priority(request(id=99).change_priority("High"))
    assert repository.list_all() == []


def test_lookup_and_update_close_connections(tmp_path):
    path = tmp_path / "connections.db"
    repository = MaintenanceRequestRepository(path)
    saved = repository.save(request())
    assert repository.get_by_id(saved.id) == saved
    assert repository.get_by_id(999) is None
    repository.update_priority(saved.change_priority("High"))
    # On Windows, an outstanding SQLite handle prevents this rename.
    moved = path.with_name("closed.db")
    path.rename(moved)
    assert MaintenanceRequestRepository(moved).get_by_id(saved.id).priority is Priority.HIGH
