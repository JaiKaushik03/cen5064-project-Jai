"""Final slice: real Domain decisions, SQLite transactions and role boundaries."""
from contextlib import closing
from dataclasses import replace, FrozenInstanceError
from io import BytesIO
import sqlite3
from uuid import uuid4
import pytest
from PIL import Image
from src.data.account_repositories import TenantAccountRepository, OwnerAccountRepository
from src.data.contractor_repository import ContractorAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import TenantProfile, TenantAccount, OwnerAccount, AccountRole, AccessDeniedError
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.request_builder import MaintenanceRequestBuilder
from src.domain.request_status import RequestStatus
from src.domain.work_orders import cost_in_cents
from src.services.authentication_service import AuthenticationService
from src.services.passwords import Passwords
from src.services.tenant_maintenance_service import TenantMaintenanceService
from src.services.maintenance_request_service import MaintenanceRequestService
from src.services.workflow_service import OwnerWorkflowService, ContractorWorkflowService

@pytest.fixture(scope='module')
def credentials():
    codec = Passwords()
    return codec, codec.hash('TestPassword2026!')

@pytest.fixture
def flow(tmp_path, credentials):
    codec, encoded = credentials
    tenants = TenantAccountRepository(tmp_path / 'tenants.db')
    owners = OwnerAccountRepository(tmp_path / 'owners.db')
    contractors = ContractorAccountRepository(tmp_path / 'contractors.db')
    profile = TenantProfile('Fictional Tenant', 'tenant@example.com', '2025550123', '100 Fictional Road', '1A')
    account = tenants.save(TenantAccount(profile, encoded, '2026-11-08T00:00:00+00:00', 'test'))
    owners.save(OwnerAccount('owner@example.com', encoded))
    auth = AuthenticationService(tenants, owners, passwords=codec, contractors=contractors)
    repo = MaintenanceRequestRepository(tmp_path / 'requests.db')
    owner_token = auth.login_owner('owner@example.com', 'TestPassword2026!')
    tenant_token = auth.login_tenant(profile.email, 'TestPassword2026!')
    owner = OwnerWorkflowService(auth, lambda: owner_token, repo)
    tenant = TenantMaintenanceService(auth, lambda: tenant_token, repo)
    contractor = owner.register_contractor('Fictional Repairer', 'repair@example.com', 'RepairSecret2026!')
    worker_token = auth.login_contractor('repair@example.com', 'RepairSecret2026!')
    worker = ContractorWorkflowService(auth, lambda: worker_token, repo)
    return owner, tenant, worker, repo, auth, account, contractor, owner_token, tenant_token, worker_token

def png():
    target = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(target, format='PNG')
    return target.getvalue()

def test_builder_builds_independent_immutable_products_and_validates(flow):
    _, _, _, _, _, account, *_ = flow
    builder = MaintenanceRequestBuilder(' Unit 1A ', ' Leak ', '', 'High').reported_by(account).with_photo(png())
    first = builder.build()
    second = builder.at_registered_unit(3).build()
    assert first.property_unit == 'Unit 1A' and first.title == 'Leak'
    assert first.tenant_name == account.profile.full_name
    assert first.tenant_email == account.profile.email and first.photo == png()
    assert first.registered_unit_id is None and second.registered_unit_id == 3
    with pytest.raises(FrozenInstanceError):
        first.title = 'Changed'
    with pytest.raises(ValueError, match='Issue title'):
        MaintenanceRequestBuilder('Unit', '', '', 'High').build()

@pytest.mark.parametrize('value', ['-1', 'NaN', 'Infinity', '1.001', '10000000.01', '', None, True])
def test_invalid_money_is_rejected(value):
    with pytest.raises(ValueError, match='Cost'):
        cost_in_cents(value)

@pytest.mark.parametrize('value,cents', [('0', 0), ('12.30', 1230), ('10000000', 1000000000)])
def test_costs_use_exact_integer_cents(value, cents):
    assert cost_in_cents(value) == cents

@pytest.mark.parametrize('changes', [dict(tenant_name='Only name'), dict(actual_cost_cents=-1),
    dict(estimated_cost_cents=True), dict(registered_unit_id=-1), dict(scheduled_for='tomorrow'),
    dict(completed_at='2026-11-08T00:00:00+00:00'), dict(completion_notes=1)])
def test_domain_rejects_inconsistent_request_parts(changes):
    with pytest.raises(ValueError):
        MaintenanceRequest('Unit', 'Leak', '', 'Medium', **changes)

@pytest.mark.parametrize('data', [b'<script>bad</script>', b'GIF89a', b'x' * (2 * 1024 * 1024 + 1)], ids=['html', 'truncated-gif', 'oversized'])
def test_invalid_or_oversized_photos_cannot_be_built(data):
    with pytest.raises(ValueError, match='Photo'):
        MaintenanceRequestBuilder('Unit', 'Leak', '', 'Medium').with_photo(data).build()

def test_contact_snapshot_photo_unit_and_history_survive_profile_changes_and_restart(flow):
    owner, tenant, _, repo, auth, account, *_ = flow
    prop = owner.register_property('Demo Court', '100 Fictional Road')
    unit = owner.register_unit(prop.id, '1A')
    saved = tenant.submit('Demo Court / 1A', 'Leak', '', 'High', photo=png(), registered_unit_id=unit.id)
    with closing(sqlite3.connect(auth.tenants.database_path)) as connection, connection:
        connection.execute('UPDATE tenant_accounts SET full_name = ? WHERE id = ?', ('Changed profile', account.id))
    reloaded = MaintenanceRequestRepository(repo.database_path).get_by_id(saved.id)
    assert reloaded == saved
    assert reloaded.tenant_name == 'Fictional Tenant' and reloaded.photo == png()
    assert owner.list_units()[0]['id'] == unit.id
    with pytest.raises(ValueError, match='already registered'):
        owner.register_property('Demo Court', '100 Fictional Road')
    with pytest.raises(ValueError):
        owner.register_unit(prop.id, '1A')
    with pytest.raises(ValueError, match='not found'):
        tenant.submit('Unit', 'Leak', '', 'Low', registered_unit_id=999)
    assert len(repo.list_all()) == 1

def test_critical_assignment_rule_rejects_lower_priority_without_changing_storage(flow):
    owner, tenant, worker, repo, _, _, contractor, *_ = flow
    low = tenant.submit('Unit', 'Minor', '', 'Low')
    critical = tenant.submit('Unit', 'Emergency', '', 'Critical')
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError, match='Critical'):
        owner.assign(low.id, contractor.id, '10.00')
    assert repo.database_path.read_bytes() == before
    assert repo.get_by_id(low.id) == low
    assigned = owner.assign(critical.id, contractor.id, '125.50', '2026-11-09')
    assert assigned.estimated_cost_cents == 12550 and assigned.scheduled_for == '2026-11-09'
    owner.assign(low.id, contractor.id, '10.00')
    assert {r.id for r in worker.list_requests()} == {low.id, critical.id}
    with pytest.raises(ValueError, match='already assigned'):
        owner.assign(low.id, contractor.id, '20.00')

def test_completion_requires_confirmation_preserves_all_fields_and_rejects_later_priority(flow):
    owner, tenant, _, repo, *_ = flow
    saved = tenant.submit('Unit', 'Leak', 'Kitchen', 'High', photo=png())
    before = repo.database_path.read_bytes()
    with pytest.raises(ValueError, match='Confirm'):
        owner.complete(saved.id, False, '20.50', 'Repair done')
    assert repo.database_path.read_bytes() == before
    fixed = owner.complete(saved.id, True, '20.50', 'Repair done')
    assert fixed.status is RequestStatus.COMPLETED and fixed.completed_at
    assert fixed.actual_cost_cents == 2050
    assert replace(fixed, status=saved.status, completed_at=None, actual_cost_cents=None, completion_notes='') == saved
    assert MaintenanceRequestRepository(repo.database_path).get_by_id(saved.id) == fixed
    with pytest.raises(ValueError, match='Completed'):
        MaintenanceRequestService(repo).change_priority(saved.id, 'Low')
    with pytest.raises(ValueError, match='already Completed'):
        owner.complete(saved.id, True)
    assert repo.get_by_id(saved.id) == fixed

def test_only_assigned_contractor_can_start_and_complete_work(flow):
    owner, tenant, worker, repo, auth, _, contractor, *_ = flow
    saved = tenant.submit('Unit', 'Assigned repair', '', 'Medium')
    other = tenant.submit('Unit', 'Private unassigned', '', 'Low')
    owner.assign(saved.id, contractor.id, '50')
    started = worker.start_work(saved.id)
    assert started.work_started_at
    with pytest.raises(ValueError, match='already started'):
        worker.start_work(saved.id)
    for operation in (worker.start_work, lambda key: worker.complete(key, True)):
        with pytest.raises(AccessDeniedError):
            operation(other.id)
    assert repo.get_by_id(other.id) == other
    fixed = worker.complete(saved.id, True, '45.25', 'Fictional repair complete')
    assert fixed.actual_cost_cents == 4525 and fixed.work_started_at
    assert [r.id for r in worker.list_requests()] == [saved.id]
    owner.register_contractor('Other Repairer', 'other@example.com', 'OtherSecret2026!')
    token = auth.login_contractor('other@example.com', 'OtherSecret2026!')
    other_worker = ContractorWorkflowService(auth, lambda: token, repo)
    assert other_worker.list_requests() == []
    with pytest.raises(AccessDeniedError):
        other_worker.complete(saved.id, True)

@pytest.mark.parametrize('role', ['tenant', 'contractor', 'forged', 'logged-out'])
def test_owner_operations_are_authorized_before_any_database_change(flow, role):
    _, _, _, repo, auth, _, _, owner_token, tenant_token, worker_token = flow
    tokens = dict(tenant=tenant_token, contractor=worker_token, forged={'role': 'owner'}, **{'logged-out': owner_token})
    if role == 'logged-out':
        auth.logout(owner_token)
    forbidden = OwnerWorkflowService(auth, lambda: tokens[role], repo)
    for call in (forbidden.list_requests, forbidden.list_contractors, forbidden.list_units,
                 lambda: forbidden.register_property('Forbidden', 'Address'),
                 lambda: forbidden.register_unit(1, 'X'),
                 lambda: forbidden.register_contractor('Bad', 'bad@example.com', 'BadSecret2026!'),
                 lambda: forbidden.assign(1, 1, '0'), lambda: forbidden.complete(1, True)):
        with pytest.raises(AccessDeniedError):
            call()
    assert repo.list_all() == [] and repo.list_properties() == []

def test_contractor_store_is_separate_and_cross_role_credentials_are_rejected(flow):
    _, _, _, _, auth, _, _, _, _, token = flow
    assert auth.require_session(token, AccountRole.CONTRACTOR).email == 'repair@example.com'
    for login, email, password in ((auth.login_owner, 'repair@example.com', 'RepairSecret2026!'),
                                  (auth.login_contractor, 'owner@example.com', 'TestPassword2026!'),
                                  (auth.login_tenant, 'repair@example.com', 'RepairSecret2026!')):
        with pytest.raises(ValueError, match='Invalid'):
            login(email, password)
    with pytest.raises(ValueError, match='separate'):
        ContractorAccountRepository(auth.tenants.database_path)
    with pytest.raises(ValueError, match='separate'):
        TenantAccountRepository(auth.contractors.database_path)
    auth.logout(token)
    assert auth.resolve_session(token) is None

def test_recreated_contractor_cannot_inherit_old_assignments_or_session(flow):
    owner, tenant, worker, repo, auth, _, contractor, _, _, token = flow
    saved = tenant.submit('Unit', 'Leak', '', 'Low')
    owner.assign(saved.id, contractor.id, '0')
    with closing(sqlite3.connect(auth.contractors.database_path)) as connection, connection:
        connection.execute('UPDATE contractor_accounts SET account_key = ? WHERE id = ?', (str(uuid4()), contractor.id))
    assert auth.resolve_session(token) is None
    replacement_token = auth.login_contractor('repair@example.com', 'RepairSecret2026!')
    assert ContractorWorkflowService(auth, lambda: replacement_token, repo).list_requests() == []

def test_repeatable_legacy_migration_preserves_rows_ids_sequence_and_unknown_contacts(tmp_path):
    path = tmp_path / 'old.db'
    row = (12, 'Legacy Unit', 'Old repair', 'Original notes', 'Critical', '2026-10-01T12:00:00+00:00')
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('CREATE TABLE maintenance_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, property_unit TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, created_at TEXT NOT NULL)')
        connection.execute('INSERT INTO maintenance_requests VALUES (?, ?, ?, ?, ?, ?)', row)
    repo = MaintenanceRequestRepository(path)
    MaintenanceRequestRepository(path)
    reloaded = repo.get_by_id(12)
    assert reloaded.tenant_name is None and reloaded.completed_at is None and reloaded.photo is None
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute('SELECT id, property_unit, title, description, priority, created_at FROM maintenance_requests').fetchone() == row
        columns = [r[1] for r in connection.execute('PRAGMA table_info(maintenance_requests)')]
        assert len(columns) == len(set(columns))
    assert repo.save(MaintenanceRequest('Unit', 'Next', '', 'Low')).id == 13

def test_failed_domain_decision_rolls_back_transaction(flow):
    _, tenant, _, repo, *_ = flow
    saved = tenant.submit('Unit', 'Leak', '', 'Medium')
    def reject(request, requests):
        raise ValueError('Rejected decision')
    with pytest.raises(ValueError, match='Rejected decision'):
        repo.transact_update(saved.id, reject)
    assert repo.get_by_id(saved.id) == saved


def test_truncated_jpeg_body_is_rejected_before_storage():
    target = BytesIO()
    Image.new('RGB', (100, 100), 'white').save(target, format='JPEG')
    data = target.getvalue()
    assert MaintenanceRequestBuilder('Unit', 'Leak', '', 'Low').with_photo(data).build().photo == data
    with pytest.raises(ValueError, match='Photo'):
        MaintenanceRequestBuilder('Unit', 'Leak', '', 'Low').with_photo(data[:-20]).build()
