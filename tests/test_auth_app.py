"""Exercise the real login/signup/router UI with isolated stores and demo fixtures."""

from pathlib import Path
import os

import pytest
from streamlit.testing.v1 import AppTest

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.maintenance_request import MaintenanceRequest
from src.services.demo_accounts import seed_demo_accounts

APP = Path(__file__).resolve().parents[1] / "app.py"


def button(screen, label):
    return next(item for item in screen.button if item.label == label)


def assert_passwords_cleared(screen):
    for key in ("tenant_password", "owner_password", "signup_password", "signup_confirmation"):
        assert key not in screen.session_state or screen.session_state[key] == ""


@pytest.fixture
def auth_app(tmp_path, monkeypatch):
    directory = tmp_path / "auth"
    maintenance_path = tmp_path / "requests.db"
    monkeypatch.setenv("PROPERTYCARE_AUTH_DATA_DIR", str(directory))
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(maintenance_path))
    tenants = TenantAccountRepository(directory / "tenant_accounts.db")
    owners = OwnerAccountRepository(directory / "owner_accounts.db")
    seed_demo_accounts(tenants, owners, allow_local_demo=True)
    MaintenanceRequestRepository(maintenance_path).save(
        MaintenanceRequest("Legacy Unit", "Legacy request hidden from tenants", "Private fixture", "Medium")
    )
    screen = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not screen.exception
    return screen, tenants, owners, maintenance_path


def login_tenant(screen, email="user1@login.com", password="user1"):
    screen.text_input(key="tenant_email").set_value(email)
    screen.text_input(key="tenant_password").set_value(password)
    return button(screen, "Log In").click().run()


def login_owner(screen, email="admin@admin.com", password="admin"):
    button(screen, "Login as Owner").click().run()
    screen.text_input(key="owner_email").set_value(email)
    screen.text_input(key="owner_password").set_value(password)
    return button(screen, "Login as Owner").click().run()


def fill_signup(screen, **changes):
    values = dict(full_name="Demo New Signup", email="new-signup@example.com", phone="202-555-0119",
                  address="200 Fictional Avenue", unit="Demo 4B", password="NewSignup2026!",
                  confirmation="NewSignup2026!")
    values.update(changes)
    for name, value in values.items():
        screen.text_input(key=f"signup_{name}").set_value(value)


def test_initial_login_is_empty_and_does_not_expose_maintenance(auth_app):
    screen, _, _, _ = auth_app
    assert screen.title[0].value == "PropertyCare"
    assert screen.caption[0].value == "Rental Maintenance Management System"
    assert screen.text_input(key="tenant_email").value == ""
    assert screen.text_input(key="tenant_password").value == ""
    assert {item.label for item in screen.button} == {"Log In", "Sign Up", "Login as Owner"}
    assert not screen.table


@pytest.mark.parametrize("number", [1, 2, 3])
def test_all_demo_tenants_log_in_with_name_and_without_shared_data(auth_app, number):
    screen, _, _, path = auth_app
    before = path.read_bytes()
    login_tenant(screen, f"user{number}@login.com", f"user{number}")
    assert not screen.exception
    assert screen.title[0].value == "Tenant Dashboard"
    assert screen.text[0].value == f"Welcome, Demo Tenant {number}."
    assert not screen.table
    assert all(item.label != "Open maintenance requests" for item in screen.button)
    assert path.read_bytes() == before
    assert_passwords_cleared(screen)


def test_owner_login_and_existing_workspace_are_protected(auth_app):
    screen, _, _, _ = auth_app
    login_owner(screen)
    assert not screen.exception
    assert screen.title[0].value == "Owner Dashboard"
    assert "admin@admin.com" in screen.text[0].value
    assert_passwords_cleared(screen)
    button(screen, "Open maintenance requests").click().run()
    assert not screen.exception
    assert screen.table[0].value.iloc[0]["Issue title"] == "Legacy request hidden from tenants"
    button(screen, "Logout").click().run()
    assert not screen.table
    assert screen.title[0].value == "PropertyCare"


def test_invalid_and_cross_role_credentials_have_generic_errors(auth_app):
    screen, _, _, _ = auth_app
    login_tenant(screen, "admin@admin.com", "admin")
    assert not screen.exception
    assert screen.error[0].value == "Invalid email address or password."
    assert_passwords_cleared(screen)
    login_tenant(screen, "user1@login.com", "wrong")
    assert screen.error[0].value == "Invalid email address or password."
    login_owner(screen, "user1@login.com", "user1")
    assert screen.error[0].value == "Invalid email address or password."
    assert not screen.table
    assert_passwords_cleared(screen)


def test_owner_login_has_no_public_signup_and_no_prefilled_password(auth_app):
    screen, _, _, _ = auth_app
    button(screen, "Login as Owner").click().run()
    assert screen.title[0].value == "PropertyCare — Owner Login"
    assert screen.text_input(key="owner_password").value == ""
    assert {item.label for item in screen.button} == {"Login as Owner", "Back to User Login"}
    assert not screen.checkbox
    button(screen, "Back to User Login").click().run()
    assert screen.title[0].value == "PropertyCare"


def test_signup_required_indicators_terms_and_default_preferences(auth_app):
    screen, _, _, _ = auth_app
    button(screen, "Sign Up").click().run()
    assert screen.title[0].value == "Create Your PropertyCare Account"
    assert len(screen.text_input) == 7
    assert all(item.label.endswith("*") for item in screen.text_input)
    assert screen.checkbox(key="signup_updates").value is False
    assert screen.checkbox(key="signup_terms").value is False
    assert "nonbinding academic demonstration" in screen.markdown[0].value
    assert "2026-10-24" in screen.markdown[0].value


@pytest.mark.parametrize("opt_in", [False, True])
def test_signup_confirmation_persistence_tenant_login_and_no_owner_access(auth_app, opt_in):
    screen, tenants, _, _ = auth_app
    button(screen, "Sign Up").click().run()
    screen.session_state["tenant_email"] = "previous@example.com"
    fill_signup(screen, email="  NEW-SIGNUP@example.com  ")
    screen.checkbox(key="signup_terms").set_value(True)
    screen.checkbox(key="signup_updates").set_value(opt_in)
    button(screen, "Create Account").click().run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert "Account created successfully" in screen.success[0].value
    assert screen.text_input(key="tenant_email").value == "new-signup@example.com"
    assert screen.text_input(key="tenant_password").value == ""
    assert_passwords_cleared(screen)
    saved = TenantAccountRepository(tenants.database_path).get_by_email("NEW-SIGNUP@example.com")
    assert saved.profile.updates_opt_in is opt_in
    assert saved.profile.unit_number == "Demo 4B"
    assert "auth_token" not in screen.session_state
    # Use the prefilled email without entering it again.
    screen.text_input(key="tenant_password").set_value("NewSignup2026!")
    button(screen, "Log In").click().run()
    assert screen.title[0].value == "Tenant Dashboard"
    assert screen.text[0].value == "Welcome, Demo New Signup."
    screen.session_state["auth_page"] = "owner_dashboard"
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "Tenant Dashboard"
    assert "Owner access is required" in screen.error[0].value
    assert not screen.table
    button(screen, "Logout").click().run()
    login_owner(screen, "new-signup@example.com", "NewSignup2026!")
    assert screen.error[0].value == "Invalid email address or password."


@pytest.mark.parametrize(("changes", "terms", "message"), [
    ({}, False, "Terms and Conditions"),
    ({"full_name": "   "}, True, "Full name"),
    ({"unit": "   "}, True, "Unit number"),
    ({"address": ""}, True, "Address"),
    ({"email": "not-an-email"}, True, "valid email"),
    ({"phone": "abc"}, True, "phone number"),
    ({"confirmation": "OtherPassword2026!"}, True, "do not match"),
    ({"email": "USER1@LOGIN.COM"}, True, "already exists"),
])
def test_signup_errors_preserve_inputs_and_do_not_create_accounts(auth_app, changes, terms, message):
    screen, tenants, _, _ = auth_app
    button(screen, "Sign Up").click().run()
    fill_signup(screen, **changes)
    screen.checkbox(key="signup_terms").set_value(terms)
    button(screen, "Create Account").click().run()
    assert not screen.exception
    assert message in screen.error[0].value
    assert screen.title[0].value == "Create Your PropertyCare Account"
    assert screen.text_input(key="signup_password").value == changes.get("password", "NewSignup2026!")
    assert screen.text_input(key="signup_confirmation").value == changes.get("confirmation", "NewSignup2026!")
    assert tenants.get_by_email("new-signup@example.com") is None
    assert screen.text_input(key="signup_address").value == changes.get("address", "200 Fictional Avenue")
    assert screen.checkbox(key="signup_terms").value is terms


@pytest.mark.parametrize("page", ["owner_dashboard", "owner_maintenance", "tenant_dashboard"])
def test_unauthenticated_route_changes_do_not_open_protected_pages(auth_app, page):
    screen, _, _, _ = auth_app
    screen.session_state["auth_page"] = page
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert "Please log in" in screen.error[0].value
    assert not screen.table
    login_tenant(screen, "user1@login.com", "wrong")
    assert screen.error[0].value == "Invalid email address or password."


def test_urls_and_forged_role_fields_cannot_grant_owner_access(auth_app):
    screen, _, _, _ = auth_app
    screen.query_params["page"] = "owner_maintenance"
    screen.query_params["role"] = "owner"
    screen.session_state["auth_token"] = {"role": "owner", "id": 1}
    screen.session_state["auth_role"] = "owner"
    screen.session_state["auth_page"] = "owner_maintenance"
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert not screen.table
    login_tenant(screen)
    screen.session_state["auth_page"] = "owner_maintenance"
    screen.run()
    assert screen.title[0].value == "Tenant Dashboard"
    assert "Owner access is required" in screen.error[0].value
    assert not screen.table


def test_logout_revokes_token_and_clears_private_state(auth_app):
    screen, _, _, _ = auth_app
    login_owner(screen)
    token = screen.session_state["auth_token"]
    button(screen, "Logout").click().run()
    assert "auth_token" not in screen.session_state
    assert screen.text_input(key="tenant_email").value == ""
    assert_passwords_cleared(screen)
    screen.session_state["auth_token"] = token
    screen.session_state["auth_page"] = "owner_dashboard"
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert "auth_token" not in screen.session_state


def test_accounts_persist_and_a_fresh_browser_session_requires_login(auth_app):
    screen, _, _, _ = auth_app
    login_tenant(screen)
    restarted = AppTest.from_file(str(APP), default_timeout=20).run()
    assert restarted.title[0].value == "PropertyCare"
    assert "auth_token" not in restarted.session_state
    login_tenant(restarted, "user2@login.com", "user2")
    assert not restarted.exception
    assert restarted.title[0].value == "Tenant Dashboard"
    assert "Demo Tenant 2" in restarted.text[0].value



@pytest.mark.parametrize("store_name", ["tenant_accounts.db", "owner_accounts.db"])
def test_misconfigured_maintenance_path_cannot_write_into_an_auth_store(auth_app, monkeypatch, store_name):
    from contextlib import closing
    import sqlite3

    screen, tenants, _, _ = auth_app
    account_path = tenants.database_path.with_name(store_name)
    # Windows paths remain the same file even when the configuration changes case.
    configured_path = str(account_path).swapcase() if os.name == "nt" else str(account_path)
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", configured_path)
    login_owner(screen)
    button(screen, "Open maintenance requests").click().run()
    assert not screen.exception
    assert "databases must be separate" in screen.error[0].value
    assert not screen.table
    with closing(sqlite3.connect(account_path)) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'maintenance_requests'"
        ).fetchall() == []



def test_startup_creates_empty_auth_stores_without_automatic_demo_seeding(tmp_path, monkeypatch):
    from contextlib import closing
    import sqlite3

    directory = tmp_path / "empty-auth"
    maintenance = tmp_path / "untouched-requests.db"
    monkeypatch.setenv("PROPERTYCARE_AUTH_DATA_DIR", str(directory))
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(maintenance))
    screen = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not screen.exception
    for filename, table in [("tenant_accounts.db", "tenant_accounts"),
                             ("owner_accounts.db", "owner_accounts")]:
        with closing(sqlite3.connect(directory / filename)) as connection:
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert not maintenance.exists()
    login_tenant(screen)
    assert screen.error[0].value == "Invalid email address or password."


def test_signup_missing_unit_can_be_corrected_without_retyping_passwords(auth_app):
    screen, tenants, _, _ = auth_app
    button(screen, "Sign Up").click().run()
    fill_signup(screen, unit="")
    screen.checkbox(key="signup_terms").set_value(True)
    screen.checkbox(key="signup_updates").set_value(True)
    button(screen, "Create Account").click().run()
    assert not screen.exception
    assert "Unit number" in screen.error[0].value
    assert screen.text_input(key="signup_password").value == "NewSignup2026!"
    assert screen.text_input(key="signup_confirmation").value == "NewSignup2026!"
    assert screen.checkbox(key="signup_updates").value is True
    assert tenants.get_by_email("new-signup@example.com") is None

    screen.text_input(key="signup_unit").set_value("Demo 4B")
    button(screen, "Create Account").click().run()
    assert not screen.exception
    assert not screen.error
    assert "Account created successfully" in screen.success[0].value
    assert screen.text_input(key="tenant_email").value == "new-signup@example.com"
    assert_passwords_cleared(screen)
    assert tenants.get_by_email("new-signup@example.com").profile.updates_opt_in is True


def test_leaving_failed_signup_clears_passwords_and_does_not_prefill_login(auth_app):
    screen, _, _, _ = auth_app
    button(screen, "Sign Up").click().run()
    fill_signup(screen, unit="")
    screen.checkbox(key="signup_terms").set_value(True)
    button(screen, "Create Account").click().run()
    assert screen.text_input(key="signup_password").value == "NewSignup2026!"
    button(screen, "Back to User Login").click().run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert screen.text_input(key="tenant_email").value == ""
    assert not screen.error
    assert_passwords_cleared(screen)
    button(screen, "Sign Up").click().run()
    assert not screen.exception
    assert screen.text_input(key="signup_password").value == ""
    assert screen.text_input(key="signup_confirmation").value == ""
