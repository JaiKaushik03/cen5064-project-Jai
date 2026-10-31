"""Private tenant request screens through real login and isolated SQLite stores."""

from pathlib import Path
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import OwnerAccount, TenantAccount, TenantProfile
from src.domain.maintenance_request import MaintenanceRequest
from src.services.passwords import Passwords

APP = Path(__file__).resolve().parents[1] / "app.py"


def button(screen, label):
    return next(item for item in screen.button if item.label == label)


@pytest.fixture(scope="module")
def encoded():
    return Passwords().hash("TenantSecret2026!")


@pytest.fixture
def tenant_app(tmp_path, monkeypatch, encoded):
    directory = tmp_path / "accounts"
    path = tmp_path / "requests.db"
    monkeypatch.setenv("PROPERTYCARE_AUTH_DATA_DIR", str(directory))
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(path))
    tenants = TenantAccountRepository(directory / "tenant_accounts.db")
    accounts = []
    for number in (1, 2):
        profile = TenantProfile(f"Demo Tenant {number}", f"tenant{number}@example.com", "2025550123",
                                "123 Fictional Lane", f"Demo {number}A")
        accounts.append(tenants.save(TenantAccount(profile, encoded, "2026-10-31T00:00:00+00:00", "test")))
    OwnerAccountRepository(directory / "owner_accounts.db").save(OwnerAccount("owner@example.com", encoded))
    repository = MaintenanceRequestRepository(path)
    repository.save(MaintenanceRequest("Legacy 9A", "Legacy owner-only request", "", "Low"))
    for number, account in enumerate(accounts, 1):
        repository.save(MaintenanceRequest(f"Demo {number}A", f"Tenant {number} private request", "", "Medium",
                                           tenant_key=account.account_key))
    screen = AppTest.from_file(str(APP), default_timeout=20).run()
    return screen, repository, accounts, directory


def open_tenant(screen, number=1):
    screen.text_input(key="tenant_email").set_value(f"tenant{number}@example.com")
    screen.text_input(key="tenant_password").set_value("TenantSecret2026!")
    button(screen, "Log In").click().run()
    assert not screen.exception
    button(screen, "My maintenance requests").click().run()
    assert not screen.exception
    return screen


def titles(screen):
    return list(screen.table[0].value["Issue title"])


def test_tenant_screen_only_lists_own_rows_and_has_no_manager_actions(tenant_app):
    screen, _, accounts, _ = tenant_app
    open_tenant(screen)
    assert screen.title[0].value == "My maintenance requests"
    assert titles(screen) == ["Tenant 1 private request"]
    assert all(item.label != "Update Priority" for item in screen.button)
    assert all(item.label != "New priority *" for item in screen.selectbox)
    screen.query_params["tenant_key"] = accounts[1].account_key
    screen.query_params["request_id"] = "3"
    screen.session_state["tenant_id"] = accounts[1].id
    screen.session_state["tenant_key"] = accounts[1].account_key
    screen.run()
    assert titles(screen) == ["Tenant 1 private request"]


def test_tenant_submission_failure_preserves_inputs_and_success_resets_with_saved_row(tenant_app):
    screen, repository, accounts, _ = tenant_app
    open_tenant(screen)
    screen.text_input(key="property_unit").set_value("Demo 1A")
    screen.text_input(key="title").set_value(" ")
    screen.text_area(key="description").set_value("Keep these details")
    screen.selectbox(key="priority").set_value("Critical")
    button(screen, "Submit request").click().run()
    assert not screen.exception
    assert "Issue title" in screen.error[0].value
    assert screen.text_area(key="description").value == "Keep these details"
    assert screen.selectbox(key="priority").value == "Critical"
    assert len(repository.list_all()) == 3
    screen.text_input(key="title").set_value("New private request")
    button(screen, "Submit request").click().run()
    assert not screen.exception
    assert "saved successfully" in screen.success[0].value
    assert screen.text_input(key="property_unit").value == ""
    assert screen.text_input(key="title").value == ""
    assert screen.text_area(key="description").value == ""
    assert screen.selectbox(key="priority").value == "Medium"
    assert titles(screen) == ["New private request", "Tenant 1 private request"]
    assert repository.get_by_id(4).tenant_key == accounts[0].account_key


def test_switching_tenants_after_logout_does_not_reuse_previous_history_or_feedback(tenant_app):
    screen, _, _, _ = tenant_app
    open_tenant(screen)
    button(screen, "Logout").click().run()
    assert not screen.table
    open_tenant(screen, 2)
    assert titles(screen) == ["Tenant 2 private request"]
    assert not screen.success
    assert screen.text_area(key="description").value == ""


def test_new_session_keeps_owned_history_after_reconnection(tenant_app):
    screen, _, _, _ = tenant_app
    open_tenant(screen)
    restarted = AppTest.from_file(str(APP), default_timeout=20).run()
    assert restarted.title[0].value == "PropertyCare"
    assert not restarted.table
    open_tenant(restarted)
    assert titles(restarted) == ["Tenant 1 private request"]


def test_unauthenticated_tenant_route_cannot_read_history(tenant_app):
    screen, _, _, _ = tenant_app
    screen.session_state["auth_page"] = "tenant_maintenance"
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert not screen.table
    assert "Please log in" in screen.error[0].value


def test_owner_cannot_use_tenant_route_but_still_sees_all_requests_in_owner_workspace(tenant_app):
    screen, _, _, _ = tenant_app
    button(screen, "Login as Owner").click().run()
    screen.text_input(key="owner_email").set_value("owner@example.com")
    screen.text_input(key="owner_password").set_value("TenantSecret2026!")
    button(screen, "Login as Owner").click().run()
    screen.session_state["auth_page"] = "tenant_maintenance"
    screen.run()
    assert not screen.exception
    assert screen.title[0].value == "Owner Dashboard"
    assert "Tenant access" in screen.error[0].value
    assert not screen.table
    button(screen, "Open maintenance requests").click().run()
    assert set(titles(screen)) == {"Legacy owner-only request", "Tenant 1 private request", "Tenant 2 private request"}


@pytest.mark.parametrize("store_name", ["tenant_accounts.db", "owner_accounts.db"])
def test_tenant_workspace_also_refuses_authentication_file_collision(tenant_app, monkeypatch, store_name):
    screen, _, _, directory = tenant_app
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(directory / store_name))
    open_tenant(screen)
    assert "databases must be separate" in screen.error[0].value
    assert not screen.table
    with sqlite3.connect(directory / store_name) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'maintenance_requests'").fetchone() is None


def test_expired_session_cannot_submit_a_request_from_a_stale_form(tenant_app):
    screen, repository, _, _ = tenant_app
    open_tenant(screen)
    screen.text_input(key="property_unit").set_value("Demo 1A")
    screen.text_input(key="title").set_value("Must not save")
    screen.session_state["auth_token"] = "expired-or-forged"
    button(screen, "Submit request").click().run()
    assert not screen.exception
    assert screen.title[0].value == "PropertyCare"
    assert not screen.table
    assert len(repository.list_all()) == 3


def test_expired_session_then_another_login_cannot_reuse_private_drafts_or_feedback(tenant_app):
    screen, _, _, _ = tenant_app
    open_tenant(screen)
    screen.text_input(key="property_unit").set_value("Private tenant 1 unit")
    screen.text_input(key="title").set_value("Private tenant 1 draft")
    screen.text_area(key="description").set_value("Private tenant 1 details")
    # Submit widgets to state without saving, then expire the server session.
    button(screen, "Refresh saved requests").click().run()
    screen.session_state["submission_success"] = "Private tenant 1 feedback"
    screen.session_state["auth_token"] = "expired"
    screen.run()
    assert screen.title[0].value == "PropertyCare"
    open_tenant(screen, 2)
    assert titles(screen) == ["Tenant 2 private request"]
    assert screen.text_input(key="property_unit").value == ""
    assert screen.text_input(key="title").value == ""
    assert screen.text_area(key="description").value == ""
    assert not screen.success
