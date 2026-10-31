"""Tenant ownership, scoped storage, account identity and safe legacy migrations."""

from contextlib import closing
from dataclasses import replace
import sqlite3
from uuid import uuid4

import pytest

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import AccessDeniedError, OwnerAccount, TenantAccount, TenantProfile
from src.domain.maintenance_request import MaintenanceRequest
from src.services.authentication_service import AuthenticationService
from src.services.maintenance_request_service import MaintenanceRequestService
from src.services.passwords import Passwords
from src.services.tenant_maintenance_service import TenantMaintenanceService


@pytest.fixture(scope="module")
def credentials():
    codec = Passwords()
    return codec, codec.hash("TenantSecret2026!")


def profile(number=1):
    return TenantProfile(f"Demo Tenant {number}", f"tenant{number}@example.com", "2025550123",
                         "123 Fictional Lane", f"Demo {number}A")


@pytest.fixture
def setup(tmp_path, credentials):
    codec, encoded = credentials
    tenants = TenantAccountRepository(tmp_path / "tenants.db")
    owners = OwnerAccountRepository(tmp_path / "owners.db")
    first = tenants.save(TenantAccount(profile(1), encoded, "2026-10-31T00:00:00+00:00", "test"))
    second = tenants.save(TenantAccount(profile(2), encoded, "2026-10-31T00:00:00+00:00", "test"))
    owners.save(OwnerAccount("owner@example.com", encoded))
    auth = AuthenticationService(tenants, owners, passwords=codec)
    repository = MaintenanceRequestRepository(tmp_path / "requests.db")
    state = {"token": auth.login_tenant(first.profile.email, "TenantSecret2026!")}
    service = TenantMaintenanceService(auth, lambda: state["token"], repository)
    return service, auth, repository, tenants, first, second, state


def request(**changes):
    values = dict(property_unit="Demo 1A", title="Fictional leak", description="", priority="Medium")
    values.update(changes)
    return MaintenanceRequest(**values)


@pytest.mark.parametrize("value", ["", "not-a-key", 7, True])
def test_domain_rejects_invalid_owned_request_keys(value):
    with pytest.raises(ValueError, match="account key"):
        request(tenant_key=value)


def test_submission_identity_is_server_owned_and_history_is_private(setup):
    service, auth, repository, _, first, second, state = setup
    legacy = repository.save(request(title="Unassigned legacy"))
    other = repository.save(request(title="Other tenant", tenant_key=second.account_key))
    saved = service.submit(" Demo 1A ", " My leak ", " Details ", "High")
    newer = service.submit("Demo 1A", "Newer request", "", "Low")
    assert saved.tenant_key == first.account_key
    assert saved.property_unit == "Demo 1A" and saved.title == "My leak"
    assert service.list_requests() == [newer, saved]
    assert service.get_request(saved.id) == saved
    assert repository.get_for_tenant(other.id, first.account_key) is None
    assert repository.get_for_tenant(legacy.id, first.account_key) is None
    state["token"] = auth.login_tenant(second.profile.email, "TenantSecret2026!")
    assert service.list_requests() == [other]
    assert len(repository.list_all()) == 4


@pytest.mark.parametrize("target", ["other", "legacy", "missing", "sql"])
def test_request_id_lookup_does_not_reveal_other_tenants_or_unassigned_rows(setup, target):
    service, _, repository, _, _, second, _ = setup
    ids = {"other": repository.save(request(tenant_key=second.account_key)).id,
           "legacy": repository.save(request()).id, "missing": 999, "sql": "1 OR 1=1"}
    with pytest.raises(ValueError) as caught:
        service.get_request(ids[target])
    assert str(caught.value) == "Maintenance request was not found."
    assert service.list_requests() == []


@pytest.mark.parametrize("field,value", [("property_unit", " "), ("title", ""),
                                         ("description", None), ("priority", "Urgent")])
def test_invalid_tenant_submission_never_saves(setup, field, value):
    service, _, repository, _, _, _, _ = setup
    values = dict(property_unit="Demo 1A", title="Leak", description="", priority="Medium")
    values[field] = value
    with pytest.raises(ValueError):
        service.submit(**values)
    assert repository.list_all() == []


def test_form_cannot_supply_ownership_or_status(setup):
    service, _, repository, _, _, second, _ = setup
    for injected in [{"tenant_key": second.account_key}, {"status": "Completed"}]:
        with pytest.raises(TypeError):
            service.submit("Demo 1A", "Leak", "", "Medium", **injected)
    assert repository.list_all() == []


@pytest.mark.parametrize("identity", ["logged_out", "owner", "forged"])
@pytest.mark.parametrize("operation", ["submit", "list_requests", "get_request"])
def test_every_tenant_operation_rechecks_current_authorization(setup, identity, operation):
    service, auth, repository, _, _, _, state = setup
    if identity == "logged_out":
        auth.logout(state["token"])
    elif identity == "owner":
        state["token"] = auth.login_owner("owner@example.com", "TenantSecret2026!")
    else:
        state["token"] = {"role": "tenant", "id": 1}
    arguments = {"submit": ("Demo 1A", "Leak", "", "High"), "list_requests": (), "get_request": (1,)}
    with pytest.raises(AccessDeniedError):
        getattr(service, operation)(*arguments[operation])
    assert repository.list_all() == []


def test_owner_priority_updates_preserve_tenant_key_and_completed_rule(setup):
    service, _, repository, _, first, _, _ = setup
    saved = service.submit("Demo 1A", "Leak", "", "Medium")
    manager = MaintenanceRequestService(repository)
    updated = manager.change_priority(saved.id, "High")
    assert updated.tenant_key == first.account_key
    assert service.list_requests() == [updated]
    with closing(sqlite3.connect(repository.database_path)) as connection, connection:
        connection.execute("UPDATE maintenance_requests SET status = 'Completed' WHERE id = ?", (saved.id,))
    with pytest.raises(ValueError, match="Completed"):
        manager.change_priority(saved.id, "Low")
    assert service.get_request(saved.id).priority.value == "High"


def test_stable_account_key_survives_reconnect_and_store_relocation(setup, tmp_path, credentials):
    service, _, repository, tenants, first, _, _ = setup
    saved = service.submit("Demo 1A", "Leak", "", "Medium")
    moved = tmp_path / "moved-tenants.db"
    tenants.database_path.rename(moved)
    moved_tenants = TenantAccountRepository(moved)
    assert moved_tenants.get_by_id(first.id).account_key == first.account_key
    auth = AuthenticationService(moved_tenants, OwnerAccountRepository(tmp_path / "owners.db"), passwords=credentials[0])
    token = auth.login_tenant(first.profile.email, "TenantSecret2026!")
    restarted = TenantMaintenanceService(auth, lambda: token, MaintenanceRequestRepository(repository.database_path))
    assert restarted.list_requests() == [saved]


def test_recreated_account_does_not_inherit_requests_or_previous_session(setup):
    service, auth, repository, tenants, first, _, state = setup
    saved = service.submit("Demo 1A", "Original account's request", "", "Medium")
    old_token = state["token"]
    # Represents a replacement account with even the same numeric ID and email.
    replacement_key = str(uuid4())
    with closing(sqlite3.connect(tenants.database_path)) as connection, connection:
        connection.execute("UPDATE tenant_accounts SET account_key = ? WHERE id = ?", (replacement_key, first.id))
    assert auth.resolve_session(old_token) is None
    state["token"] = auth.login_tenant(first.profile.email, "TenantSecret2026!")
    assert service.list_requests() == []
    with pytest.raises(ValueError, match="not found"):
        service.get_request(saved.id)
    assert repository.get_by_id(saved.id).tenant_key == first.account_key


LEGACY_TENANT_SCHEMA = """CREATE TABLE tenant_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE, phone_number TEXT NOT NULL,
    address TEXT NOT NULL, unit_number TEXT NOT NULL, password_hash TEXT NOT NULL,
    updates_opt_in INTEGER NOT NULL, terms_accepted_at TEXT NOT NULL,
    terms_version TEXT NOT NULL, created_at TEXT NOT NULL)"""


def legacy_tenants(path, encoded):
    row = (17, "Legacy Demo", "legacy@example.com", "2025550199", "Fictional Road", "Demo 17",
           encoded, 0, "2026-10-24T00:00:00+00:00", "legacy-test", "2026-10-24T00:00:00+00:00")
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(LEGACY_TENANT_SCHEMA)
        connection.execute("INSERT INTO tenant_accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
    return row


def test_existing_tenant_migration_preserves_fields_hash_ids_sequence_and_stable_keys(tmp_path, credentials):
    path = tmp_path / "legacy-tenants.db"
    before = legacy_tenants(path, credentials[1])
    tenants = TenantAccountRepository(path)
    saved = tenants.get_by_id(17)
    assert saved.account_key
    assert TenantAccountRepository(path).get_by_id(17).account_key == saved.account_key
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT id, full_name, email, phone_number, address, unit_number, "
                                  "password_hash, updates_opt_in, terms_accepted_at, terms_version, created_at "
                                  "FROM tenant_accounts").fetchone() == before
        assert connection.execute("SELECT seq FROM sqlite_sequence WHERE name = 'tenant_accounts'").fetchone() == (17,)
    new = tenants.save(TenantAccount(profile(3), credentials[1], "2026-10-31T00:00:00+00:00", "test"))
    assert new.id == 18 and new.account_key != saved.account_key


def legacy_requests(path, with_status=False):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE maintenance_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "property_unit TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, "
                           "priority TEXT NOT NULL, created_at TEXT NOT NULL" +
                           (", status TEXT NOT NULL DEFAULT 'Open'" if with_status else "") + ")")
        values = (9, "Legacy 9A", "Original request", "Keep this", "Low", "2026-10-01T00:00:00+00:00")
        if with_status:
            values += ("Completed",)
        connection.execute("INSERT INTO maintenance_requests VALUES (" + ",".join("?" for _ in values) + ")", values)
    return values


@pytest.mark.parametrize("with_status", [False, True])
def test_old_request_migrations_never_assign_legacy_rows_to_tenants(tmp_path, with_status):
    path = tmp_path / "legacy-requests.db"
    before = legacy_requests(path, with_status)
    MaintenanceRequestRepository(path)
    repository = MaintenanceRequestRepository(path)
    key = str(uuid4())
    assert repository.list_for_tenant(key) == []
    assert repository.get_by_id(9).tenant_key is None
    assert repository.get_by_id(9).status.value == ("Completed" if with_status else "Open")
    with closing(sqlite3.connect(path)) as connection:
        columns = "id, property_unit, title, description, priority, created_at" + (", status" if with_status else "")
        assert connection.execute("SELECT " + columns + " FROM maintenance_requests").fetchone() == before
        assert connection.execute("SELECT seq FROM sqlite_sequence WHERE name = 'maintenance_requests'").fetchone() == (9,)
    saved = repository.save(request(tenant_key=key))
    assert saved.id == 10
    assert repository.list_for_tenant(key) == [saved]


@pytest.mark.parametrize("kind", ["accounts", "requests"])
def test_migration_failure_rolls_back_all_schema_and_data_changes(tmp_path, credentials, monkeypatch, kind):
    path = tmp_path / "rollback.db"
    if kind == "accounts":
        before = legacy_tenants(path, credentials[1])
        repository_type = TenantAccountRepository
        table, new_column = "tenant_accounts", "account_key"
    else:
        before = legacy_requests(path)
        repository_type = MaintenanceRequestRepository
        table, new_column = "maintenance_requests", "tenant_key"

    def denied_connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY
                                  if action == sqlite3.SQLITE_CREATE_INDEX else sqlite3.SQLITE_OK)
        return connection

    with monkeypatch.context() as context:
        context.setattr(repository_type, "_connect", denied_connection)
        with pytest.raises(sqlite3.DatabaseError):
            repository_type(path)
    with closing(sqlite3.connect(path)) as connection:
        assert new_column not in {row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")}
        assert connection.execute("SELECT * FROM " + table).fetchone() == before
    assert repository_type(path) is not None
