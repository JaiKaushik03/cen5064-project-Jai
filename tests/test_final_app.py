"""Real Streamlit screen flows on isolated account and request databases."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from src.data.account_repositories import TenantAccountRepository, OwnerAccountRepository
from src.data.contractor_repository import ContractorAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import TenantAccount, TenantProfile, OwnerAccount, ContractorAccount
from src.domain.maintenance_request import MaintenanceRequest
from src.domain.request_status import RequestStatus
from src.services.passwords import Passwords

APP = Path(__file__).resolve().parents[1] / 'app.py'
def button(screen, label):
    return next(item for item in screen.button if item.label == label)

@pytest.fixture(scope='module')
def encoded():
    return Passwords().hash('ScreenSecret2026!')

@pytest.fixture
def screen_flow(tmp_path, monkeypatch, encoded):
    directory = tmp_path / 'auth'
    path = tmp_path / 'requests.db'
    monkeypatch.setenv('PROPERTYCARE_AUTH_DATA_DIR', str(directory))
    monkeypatch.setenv('PROPERTYCARE_DB_PATH', str(path))
    tenants = TenantAccountRepository(directory / 'tenant_accounts.db')
    profile = TenantProfile('Fictional Tenant', 'tenant@example.com', '2025550123', '100 Fictional Road', '1A')
    tenant = tenants.save(TenantAccount(profile, encoded, '2026-11-08T00:00:00+00:00', 'test'))
    OwnerAccountRepository(directory / 'owner_accounts.db').save(OwnerAccount('owner@example.com', encoded))
    contractor = ContractorAccountRepository(directory / 'contractor_accounts.db').save(ContractorAccount('Fictional Repairer', 'repair@example.com', encoded))
    repo = MaintenanceRequestRepository(path)
    request = repo.save(MaintenanceRequest('Unit 1A', 'Fictional leak', 'Kitchen', 'Medium', tenant_key=tenant.account_key,
                tenant_name=profile.full_name, tenant_email=profile.email, tenant_phone=profile.phone_number,
                tenant_address=profile.address, tenant_unit=profile.unit_number))
    screen = AppTest.from_file(str(APP), default_timeout=20).run()
    return screen, repo, request, contractor

def owner_login(screen):
    button(screen, 'Login as Owner').click().run()
    screen.text_input(key='owner_email').set_value('owner@example.com')
    screen.text_input(key='owner_password').set_value('ScreenSecret2026!')
    button(screen, 'Login as Owner').click().run()
    assert not screen.exception

def contractor_login(screen):
    button(screen, 'Login as Contractor').click().run()
    screen.text_input(key='contractor_email').set_value('repair@example.com')
    screen.text_input(key='contractor_password').set_value('ScreenSecret2026!')
    button(screen, 'Login as Contractor').click().run()
    assert not screen.exception

def test_owner_tables_show_snapshot_and_completion_requires_checkbox(screen_flow):
    screen, repo, request, _ = screen_flow
    owner_login(screen)
    assert 'Active Issues' in [item.value for item in screen.subheader]
    assert screen.dataframe[0].value.iloc[0]['Tenant'] == 'Fictional Tenant'
    button(screen, f'Mark Fixed #{request.id}').click().run()
    assert not screen.exception
    button(screen, 'Submit').click().run()
    assert not screen.exception
    assert any('Confirm' in item.value for item in screen.error)
    assert repo.get_by_id(request.id).status is RequestStatus.OPEN
    screen.checkbox(key=f'confirm_fix_{request.id}').check()
    screen.text_input(key=f'actual_cost_{request.id}').set_value('25.50')
    screen.text_area(key=f'completion_notes_{request.id}').set_value('Fictional repair completed')
    button(screen, 'Submit').click().run()
    assert not screen.exception
    fixed = repo.get_by_id(request.id)
    assert fixed.status is RequestStatus.COMPLETED and fixed.actual_cost_cents == 2550
    assert any('marked Fixed' in item.value for item in screen.success)
    assert screen.dataframe[0].value.iloc[0]['Status'] == 'Fixed'
    assert screen.dataframe[0].value.iloc[0]['Fixed (UTC)'] == fixed.completed_at
    button(screen, 'Open maintenance requests').click().run()
    assert not screen.exception
    screen.selectbox(key='manager_priority').select('Low')
    button(screen, 'Update Priority').click().run()
    assert any('Completed' in item.value for item in screen.error)
    assert repo.get_by_id(request.id).priority == request.priority

def test_cancel_confirmation_preserves_open_request(screen_flow):
    screen, repo, request, _ = screen_flow
    owner_login(screen)
    button(screen, f'Mark Fixed #{request.id}').click().run()
    button(screen, 'Cancel').click().run()
    assert not screen.exception
    assert repo.get_by_id(request.id) == request
    assert 'pending_completion' not in screen.session_state

def test_owner_registers_catalog_and_contractor_and_assigns_work(screen_flow):
    screen, repo, request, contractor = screen_flow
    owner_login(screen)
    screen.text_input(key='property_name').set_value('Fictional Court')
    screen.text_input(key='property_address').set_value('100 Fictional Road')
    button(screen, 'Register property').click().run()
    assert not screen.exception
    screen.text_input(key='new_unit_number').set_value('1A')
    button(screen, 'Register unit').click().run()
    assert repo.list_units()[0]['number'] == '1A'
    screen.text_input(key='new_contractor_name').set_value('Second Fictional Repairer')
    screen.text_input(key='new_contractor_email').set_value('second@example.com')
    screen.text_input(key='new_contractor_password').set_value('SecondSecret2026!')
    button(screen, 'Create contractor account').click().run()
    assert not screen.exception
    assert screen.text_input(key='new_contractor_password').value == ''
    screen.selectbox(key='assign_request_id').select(request.id)
    screen.selectbox(key='assign_contractor_id').select(contractor.id)
    screen.text_input(key='estimated_cost').set_value('100.25')
    button(screen, 'Assign work').click().run()
    assert not screen.exception
    assigned = repo.get_by_id(request.id)
    assert assigned.assigned_contractor_key == contractor.account_key
    assert assigned.estimated_cost_cents == 10025 and assigned.scheduled_for

def test_contractor_only_sees_assigned_work_and_can_start_and_complete(screen_flow):
    screen, repo, request, contractor = screen_flow
    repo.transact_update(request.id, lambda item, items: item.assign(contractor.account_key, contractor.full_name, 5000, items))
    repo.save(MaintenanceRequest('Other Unit', 'Hidden from contractor', '', 'Low'))
    contractor_login(screen)
    assert screen.title[0].value == 'Contractor Dashboard'
    assert screen.dataframe[0].value['Issue title'].tolist() == ['Fictional leak']
    assert not any(item.label == 'Register property' for item in screen.button)
    button(screen, f'Start work #{request.id}').click().run()
    assert not screen.exception
    assert repo.get_by_id(request.id).work_started_at
    button(screen, f'Mark Fixed #{request.id}').click().run()
    screen.checkbox(key=f'confirm_fix_{request.id}').check()
    button(screen, 'Submit').click().run()
    assert not screen.exception
    assert repo.get_by_id(request.id).status is RequestStatus.COMPLETED
    button(screen, 'Logout').click().run()
    assert not screen.dataframe
    assert screen.text_input(key='tenant_email').value == ''

def test_tenant_cannot_open_owner_or_contractor_controls(screen_flow):
    screen, repo, request, _ = screen_flow
    screen.text_input(key='tenant_email').set_value('tenant@example.com')
    screen.text_input(key='tenant_password').set_value('ScreenSecret2026!')
    button(screen, 'Log In').click().run()
    for target in ('owner_dashboard', 'contractor_dashboard'):
        screen.session_state['auth_page'] = target
        screen.run()
        assert not screen.exception
        assert screen.title[0].value == 'Tenant Dashboard'
        assert not screen.dataframe
    assert repo.get_by_id(request.id) == request
