"""Audit regressions: real SQLite, Domain, role services and Streamlit state."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from PIL import Image
import pytest
from streamlit.testing.v1 import AppTest

from src.data.account_repositories import TenantAccountRepository, OwnerAccountRepository
from src.data.contractor_repository import ContractorAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import TenantProfile, TenantAccount, OwnerAccount, ContractorAccount, AccessDeniedError
from src.domain.maintenance_request import MaintenanceRequest, ConcurrentRequestError
from src.services.authentication_service import AuthenticationService
from src.services.maintenance_request_service import MaintenanceRequestService
from src.services.passwords import Passwords
from src.services.tenant_maintenance_service import TenantMaintenanceService
from src.services.workflow_service import OwnerWorkflowService, ContractorWorkflowService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def codec():
    return Passwords()


@pytest.fixture(scope="module")
def encoded(codec):
    return codec.hash("AuditPassword2026!")


@pytest.fixture
def flow(tmp_path, codec, encoded):
    auth_dir = tmp_path / "accounts"
    tenants = TenantAccountRepository(auth_dir / "tenant_accounts.db")
    owners = OwnerAccountRepository(auth_dir / "owner_accounts.db")
    contractors = ContractorAccountRepository(auth_dir / "contractor_accounts.db")
    account = tenants.save(TenantAccount(TenantProfile("Demo Tenant", "tenant@example.com", "2025550123", "100 Fictional Road", "1A"), encoded, "2026-11-21", "test"))
    owners.save(OwnerAccount("owner@example.com", encoded))
    contractor = contractors.save(ContractorAccount("Demo Repairer", "repair@example.com", encoded))
    auth = AuthenticationService(tenants, owners, passwords=codec, contractors=contractors)
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    tenant_token = auth.login_tenant("tenant@example.com", "AuditPassword2026!")
    owner_token = auth.login_owner("owner@example.com", "AuditPassword2026!")
    worker_token = auth.login_contractor("repair@example.com", "AuditPassword2026!")
    return SimpleNamespace(auth=auth, repo=repo, tenant=TenantMaintenanceService(auth, lambda: tenant_token, repo),
        owner=OwnerWorkflowService(auth, lambda: owner_token, repo),
        worker=ContractorWorkflowService(auth, lambda: worker_token, repo), contractor=contractor,
        account=account, auth_dir=auth_dir, tenant_token=tenant_token)


def request(**changes):
    return MaintenanceRequest(**(dict(property_unit="Unit 1A", title="Sink leak", description="", priority="Medium") | changes))


def picture():
    output = BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    return output.getvalue()


def test_priority_compare_and_swap_rejects_second_writer_and_aba(tmp_path):
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    saved = repo.save(request())
    stale = saved.change_priority("Critical")
    current = repo.update_priority(saved.change_priority("High"))
    current = repo.update_priority(current.change_priority("Medium"))
    assert current.revision == 2
    with pytest.raises(ConcurrentRequestError):
        repo.update_priority(stale)
    assert repo.get_by_id(saved.id).priority.value == "Medium"
    assert repo.get_by_id(saved.id).revision == 2


def test_two_simultaneous_priority_writers_cannot_both_commit(tmp_path):
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    saved = repo.save(request())
    def write(priority):
        try:
            repo.update_priority(saved.change_priority(priority))
            return "saved"
        except ConcurrentRequestError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["High", "Critical"]))
    assert sorted(results) == ["conflict", "saved"]
    assert repo.get_by_id(saved.id).revision == 1


def test_service_rejects_stale_screen_revision_before_write(tmp_path):
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    saved = repo.save(request())
    service = MaintenanceRequestService(repo)
    service.change_priority(saved.id, "High", expected_revision=0)
    with pytest.raises(ConcurrentRequestError, match="Another person"):
        service.change_priority(saved.id, "Low", expected_revision=0)
    assert repo.get_by_id(saved.id).priority.value == "High"


def test_workflow_transition_invalidates_priority_snapshot(flow):
    saved = flow.tenant.submit("Unit", "Leak", "", "Medium")
    flow.owner.assign(saved.id, flow.contractor.id, "5")
    with pytest.raises(ConcurrentRequestError):
        flow.repo.update_priority(saved.change_priority("Low"))


def test_shared_service_imports_without_concrete_storage():
    program = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'sqlite3' or fullname == 'src.data' or fullname.startswith('src.data.'):
            raise ImportError(fullname)
sys.meta_path.insert(0, Block())
from src.services.maintenance_request_service import MaintenanceRequestService
assert MaintenanceRequestService is not None
"""
    result = subprocess.run([sys.executable, "-B", "-c", program], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("store", [TenantAccountRepository, OwnerAccountRepository, ContractorAccountRepository])
def test_maintenance_constructor_rejects_each_credential_file_without_changes(tmp_path, store):
    path = tmp_path / "credentials.db"
    store(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="separate"):
        MaintenanceRequestRepository(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("store", [TenantAccountRepository, OwnerAccountRepository, ContractorAccountRepository])
def test_credential_constructor_rejects_maintenance_file_without_changes(tmp_path, store):
    path = tmp_path / "requests.db"
    MaintenanceRequestRepository(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="separate"):
        store(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("field,limit", [("property_unit", 400), ("title", 200), ("description", 10000)])
def test_domain_bounds_new_text_but_retains_legacy_text(tmp_path, field, limit):
    with pytest.raises(ValueError, match="at most"):
        request(**{field: "x" * (limit + 1)})
    path = tmp_path / "legacy.db"
    repo = MaintenanceRequestRepository(path)
    saved = repo.save(request())
    # Fixed, internal column identifier; no untrusted SQL interpolation.
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE maintenance_requests SET {field} = ? WHERE id = ?", ("x" * (limit + 1), saved.id))
    reloaded = MaintenanceRequestRepository(path).get_by_id(saved.id)
    assert len(getattr(reloaded, field)) == limit + 1
    MaintenanceRequestService(repo).change_priority(saved.id, "High")
    assert getattr(repo.get_by_id(saved.id), field) == getattr(reloaded, field)


def test_oversized_upload_is_rejected_before_getvalue_and_preserves_form(monkeypatch):
    from src.presentation import maintenance_view
    upload = SimpleNamespace(size=2 * 1024 * 1024 + 1, getvalue=Mock(side_effect=AssertionError("Must not copy oversized data")))
    state = dict(property_unit="Unit", title="Leak", description="Keep this", priority="High", request_photo_0=upload)
    monkeypatch.setattr(maintenance_view, "st", SimpleNamespace(session_state=state, spinner=lambda _: nullcontext()))
    service = Mock()
    maintenance_view.submit_request(service)
    upload.getvalue.assert_not_called()
    service.submit.assert_not_called()
    assert "2 MiB" in state["submission_error"] and state["description"] == "Keep this"


def test_history_pages_do_not_copy_or_decode_photos(flow, monkeypatch):
    saved = flow.tenant.submit("Unit", "Photo leak", "", "Medium", photo=picture())
    from src.domain import maintenance_request
    monkeypatch.setattr(maintenance_request, "validate_photo", Mock(side_effect=AssertionError("No page decode")))
    page = flow.tenant.list_requests_page()
    assert page.total == 1 and page.items[0].photo is None and page.items[0].has_photo
    assert flow.tenant.get_request(saved.id).photo == picture()


def test_paged_history_counts_and_photo_access_remain_role_scoped(flow):
    own = flow.tenant.submit("Unit", "Private leak", "", "Low", photo=picture())
    foreign = flow.repo.save(request(title="Foreign issue", tenant_key=str(uuid4()), photo=picture()))
    page = flow.tenant.list_requests_page(limit=1)
    assert page.total == 1 and page.items[0].id == own.id
    with pytest.raises(ValueError, match="not found"):
        flow.tenant.get_request(foreign.id)
    flow.owner.assign(own.id, flow.contractor.id, "10")
    assert flow.worker.list_requests_page().total == 1
    with pytest.raises(AccessDeniedError):
        flow.worker.get_request(foreign.id)
    assert flow.worker.totals()["estimated"] == 1000


def test_sql_paging_and_totals_cover_all_rows_without_truncation(tmp_path):
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    for n in range(60):
        repo.save(request(title=f"Request {n}", estimated_cost_cents=100))
    pages = [repo.list_page(limit=25, offset=offset) for offset in (0, 25, 50)]
    assert [len(page.items) for page in pages] == [25, 25, 10]
    assert all(page.total == 60 for page in pages)
    assert [r.id for page in pages for r in page.items] == list(range(60, 0, -1))
    assert repo.totals()["estimated"] == 6000


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (True, 0), (25, -1)])
def test_invalid_history_page_is_rejected(tmp_path, limit, offset):
    repo = MaintenanceRequestRepository(tmp_path / "requests.db")
    with pytest.raises(ValueError, match="history page"):
        repo.list_page(limit=limit, offset=offset)


def test_owner_can_complete_unassigned_work_and_contractor_cannot(flow):
    saved = flow.tenant.submit("Unit", "Owner-fixed leak", "Original", "High", photo=picture())
    with pytest.raises(AccessDeniedError):
        flow.worker.complete(saved.id, True)
    with pytest.raises(ValueError, match="Confirm"):
        flow.owner.complete(saved.id, False)
    fixed = flow.owner.complete(saved.id, True, "7.50", "Owner repaired it")
    assert fixed.assigned_contractor_key is None and fixed.work_started_at is None
    assert fixed.actual_cost_cents == 750 and fixed.photo == saved.photo
    assert fixed.title == saved.title and fixed.tenant_key == saved.tenant_key
    with pytest.raises(ValueError, match="Completed"):
        MaintenanceRequestService(flow.repo).change_priority(saved.id, "Low")


def test_assignment_can_be_unscheduled_or_explicitly_scheduled(flow):
    first = flow.tenant.submit("Unit", "Unscheduled", "", "Medium")
    second = flow.tenant.submit("Unit", "Scheduled", "", "Medium")
    assert flow.owner.assign(first.id, flow.contractor.id, "1").scheduled_for is None
    assert flow.owner.assign(second.id, flow.contractor.id, "1", "2026-12-01").scheduled_for == "2026-12-01"


def test_sessions_expire_without_extending_on_rerun_and_cleanup_other_roles(flow, codec):
    now = [100.0]
    auth = AuthenticationService(flow.auth.tenants, flow.auth.owners, passwords=codec,
        contractors=flow.auth.contractors, session_ttl_seconds=5, clock=lambda: now[0])
    tokens = [auth.login_tenant("tenant@example.com", "AuditPassword2026!"),
              auth.login_owner("owner@example.com", "AuditPassword2026!"),
              auth.login_contractor("repair@example.com", "AuditPassword2026!")]
    now[0] = 104.99
    for token in tokens:
        assert auth.resolve_session(token) is not None
    now[0] = 105.0
    assert auth.cleanup_expired_sessions() == 3
    assert not auth._sessions and not auth._session_expirations
    assert all(auth.resolve_session(token) is None for token in tokens)


@pytest.mark.parametrize("lifetime", [0, -1, True, float("nan"), float("inf"), "5"])
def test_invalid_session_lifetime_fails_clearly(flow, codec, lifetime):
    with pytest.raises(ValueError, match="Session lifetime"):
        AuthenticationService(flow.auth.tenants, flow.auth.owners, passwords=codec, session_ttl_seconds=lifetime)


def click(screen, label):
    return next(button for button in screen.button if button.label == label).click().run()


def owner_screen(flow, monkeypatch):
    monkeypatch.setenv("PROPERTYCARE_AUTH_DATA_DIR", str(flow.auth_dir))
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(flow.repo.database_path))
    screen = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
    click(screen, "Login as Owner")
    screen.text_input(key="owner_email").set_value("owner@example.com")
    screen.text_input(key="owner_password").set_value("AuditPassword2026!")
    click(screen, "Login as Owner")
    assert not screen.exception
    return screen


def test_screen_stale_priority_preserves_proposal_and_requires_reload(flow, monkeypatch):
    saved = flow.repo.save(request())
    screen = owner_screen(flow, monkeypatch)
    click(screen, "Open maintenance requests")
    assert screen.session_state["manager_priority_revision"] == 0
    MaintenanceRequestService(flow.repo).change_priority(saved.id, "Critical")
    screen.selectbox(key="manager_priority").select("High")
    click(screen, "Update Priority")
    assert not screen.exception
    assert any("Another person" in error.value for error in screen.error)
    assert screen.selectbox(key="manager_priority").value == "High"
    assert flow.repo.get_by_id(saved.id).priority.value == "Critical"
    click(screen, "Reload selected request")
    assert screen.selectbox(key="manager_priority").value == "Critical"
    screen.selectbox(key="manager_priority").select("Low")
    click(screen, "Update Priority")
    assert flow.repo.get_by_id(saved.id).priority.value == "Low"


def test_screen_assignment_date_is_initially_optional(flow, monkeypatch):
    flow.repo.save(request())
    screen = owner_screen(flow, monkeypatch)
    assert screen.date_input(key="scheduled_date").value is None
    click(screen, "Assign work")
    assert not screen.exception and flow.repo.get_by_id(1).scheduled_for is None


def test_failed_start_clears_old_success(monkeypatch):
    from src.presentation import owner_views
    state = {"workflow_success": "Previous success", "submission_success": "Old submit"}
    monkeypatch.setattr(owner_views, "st", SimpleNamespace(session_state=state))
    # ui.clear_feedback uses the same Streamlit session normally; patch for this isolated callback.
    from src.presentation import ui
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state=state))
    service = SimpleNamespace(start_work=Mock(side_effect=ValueError("Work has already started.")))
    owner_views.start_action(service, 1)
    assert "workflow_success" not in state and "submission_success" not in state
    assert state["workflow_error"] == "Work has already started."


def test_invalid_session_configuration_shows_setup_error(flow, monkeypatch):
    monkeypatch.setenv("PROPERTYCARE_AUTH_DATA_DIR", str(flow.auth_dir))
    monkeypatch.setenv("PROPERTYCARE_SESSION_TTL_SECONDS", "not-a-number")
    screen = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not screen.exception
    assert any("positive whole number" in error.value for error in screen.error)


@pytest.mark.parametrize("table", ["TENANT_ACCOUNTS", "OWNER_ACCOUNTS", "CONTRACTOR_ACCOUNTS"])
def test_database_separation_handles_case_insensitive_sqlite_names(tmp_path, table):
    path = tmp_path / "credentials.db"
    with sqlite3.connect(path) as db:
        db.execute(f"CREATE TABLE {table} (id INTEGER)")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="separate"):
        MaintenanceRequestRepository(path)
    assert path.read_bytes() == before


def test_service_can_use_memory_storage_instead_of_sqlite():
    saved = request(id=1)
    values = {1: saved}
    def persist(updated):
        values[updated.id] = replace(updated, revision=updated.revision + 1)
        return values[updated.id]
    memory = SimpleNamespace(get_by_id=values.get, update_priority=persist, list_all=lambda: list(values.values()))
    service = MaintenanceRequestService(memory)
    assert service.change_priority(1, "High", expected_revision=0).priority.value == "High"
    assert service.list_requests()[0].revision == 1


def test_expired_session_cannot_submit_and_clears_private_screen_state(flow, monkeypatch):
    from src.presentation.auth_views import authentication_service
    screen = owner_screen(flow, monkeypatch)
    click(screen, "Open maintenance requests")
    screen.text_input(key="property_unit").set_value("Private draft location")
    screen.text_input(key="title").set_value("Expired request")
    service = authentication_service(str(flow.auth_dir.resolve()), 3600)
    token = screen.session_state["auth_token"]
    service._session_expirations[token] = 0
    click(screen, "Submit request")
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare" and not screen.table
    assert "auth_token" not in screen.session_state
    assert "property_unit" not in screen.session_state
    assert flow.repo.list_all() == []


def test_policy_reload_rebuilds_cached_authentication_and_requires_new_login(flow, monkeypatch):
    from src.presentation import auth_views
    first = auth_views.authentication_service(str(flow.auth_dir), 3600)
    token = first.login_owner("owner@example.com", "AuditPassword2026!")
    reloaded_class = type("ReloadedAuthenticationService", (AuthenticationService,), {})
    monkeypatch.setattr(auth_views, "AuthenticationService", reloaded_class)
    second = auth_views.authentication_service(str(flow.auth_dir), 3600)
    assert second is not first
    assert second.resolve_session(token) is None
    assert second.login_owner("owner@example.com", "AuditPassword2026!")


def test_expiry_between_route_resolution_and_authorization_returns_to_login(flow, monkeypatch):
    from src.presentation.auth_views import authentication_service
    screen = owner_screen(flow, monkeypatch)
    service = authentication_service(str(flow.auth_dir.resolve()), 3600)
    original = service.require_session
    def expire_then_require(token, role):
        service.logout(token)
        return original(token, role)
    monkeypatch.setattr(service, "require_session", expire_then_require)
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert any("session ended" in error.value for error in screen.error)
