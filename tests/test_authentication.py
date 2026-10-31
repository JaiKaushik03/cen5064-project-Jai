"""Account rules, real Argon2id/SQLite, session guards, and opt-in demo setup."""

from contextlib import closing
from dataclasses import replace
import os
import sqlite3
import subprocess
import sys
from unittest.mock import Mock

from argon2 import extract_parameters, Type
import pytest

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.domain.accounts import (
    AccessDeniedError, AccountRole, DEMO_TERMS_VERSION, OwnerAccount, TenantAccount,
    TenantProfile, TERMS_VERSION, normalize_email, normalize_phone, utc_now,
    validate_signup_password, validate_terms,
)
from src.services.authentication_service import AuthenticationService, INVALID_CREDENTIALS
from src.services.demo_accounts import seed_demo_accounts
from src.services.owner_maintenance_service import OwnerMaintenanceService
from src.services.passwords import Passwords


@pytest.fixture(scope="session")
def passwords():
    return Passwords()


@pytest.fixture(scope="session")
def account_hash(passwords):
    return passwords.hash("StrongTenant2026!")


@pytest.fixture
def stores(tmp_path):
    return (TenantAccountRepository(tmp_path / "tenant_accounts.db"),
            OwnerAccountRepository(tmp_path / "owner_accounts.db"))


@pytest.fixture
def authentication(stores, passwords):
    return AuthenticationService(*stores, passwords=passwords)


def valid_signup(**changes):
    values = dict(full_name=" Demo Tenant ", email="New@Example.com", phone_number="202-555-0110",
                  address="101 Example Lane", unit_number="Demo 1A", password="StrongTenant2026!",
                  confirmation="StrongTenant2026!", updates_opt_in=False, terms_accepted=True)
    values.update(changes)
    return values


def sql_rows(repository):
    with closing(sqlite3.connect(repository.database_path)) as connection:
        return connection.execute(f"SELECT * FROM {repository.table_name} ORDER BY id").fetchall()


@pytest.mark.parametrize("email", ["name", "x@", "@example.com", "a@example", "a..b@example.com",
                                   "a.@example.com", "x@-example.com", "x@example-.com", "a b@example.com"])
def test_malformed_email_is_rejected(email):
    with pytest.raises(ValueError):
        normalize_email(email)


def test_profile_normalization_and_optional_preference():
    profile = TenantProfile(" Demo Name ", " Tenant@Example.COM ", "+1 (202) 555-0110", " Demo Street ", " 1A ")
    assert (profile.full_name, profile.email, profile.phone_number, profile.address, profile.unit_number) == (
        "Demo Name", "tenant@example.com", "+12025550110", "Demo Street", "1A")
    assert profile.updates_opt_in is False


@pytest.mark.parametrize("phone", ["", "   ", "abc", "12345", "1" * 16, "+1+2025550110", None])
def test_invalid_phone_is_rejected(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone)


@pytest.mark.parametrize("field", ["full_name", "email", "phone_number", "address", "unit_number"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_signup_missing_fields_never_save(authentication, stores, field, value):
    with pytest.raises(ValueError):
        authentication.signup(**valid_signup(**{field: value}))
    assert sql_rows(stores[0]) == []


@pytest.mark.parametrize("field", ["password", "confirmation"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_missing_passwords_are_rejected_without_storage(authentication, stores, field, value):
    with pytest.raises(ValueError):
        authentication.signup(**valid_signup(**{field: value}))
    assert sql_rows(stores[0]) == []


@pytest.mark.parametrize("password", ["admin", "user1", "user2", "user3", "abcdefghijklm", "1234567890123", "a1" * 65])
def test_weak_demo_passwords_cannot_be_used_for_signup(authentication, stores, password):
    with pytest.raises(ValueError):
        authentication.signup(**valid_signup(password=password, confirmation=password))
    assert sql_rows(stores[0]) == []


def test_password_mismatch_does_not_echo_secrets(authentication):
    with pytest.raises(ValueError, match="Passwords do not match") as caught:
        authentication.signup(**valid_signup(confirmation="OtherSecret2026!"))
    assert "StrongTenant2026!" not in str(caught.value)
    assert "OtherSecret2026!" not in str(caught.value)


@pytest.mark.parametrize("accepted", [False, None, 1, "true"])
def test_signup_requires_explicit_terms_acceptance(authentication, stores, accepted):
    with pytest.raises(ValueError, match="Terms and Conditions"):
        authentication.signup(**valid_signup(terms_accepted=accepted))
    assert sql_rows(stores[0]) == []


@pytest.mark.parametrize("preference", [False, True])
def test_signup_persists_profile_hash_consent_and_optional_preference(authentication, stores, preference):
    saved = authentication.signup(**valid_signup(updates_opt_in=preference))
    loaded = TenantAccountRepository(stores[0].database_path).get_by_email("NEW@EXAMPLE.COM")
    assert loaded == saved
    assert loaded.profile.full_name == "Demo Tenant"
    assert loaded.profile.email == "new@example.com"
    assert loaded.profile.updates_opt_in is preference
    assert loaded.terms_version == TERMS_VERSION
    assert loaded.terms_accepted_at.endswith("+00:00")
    assert loaded.created_at.endswith("+00:00")
    assert authentication.passwords.verify(loaded.password_hash, "StrongTenant2026!")
    assert extract_parameters(loaded.password_hash).type is Type.ID
    assert not any(value == "StrongTenant2026!" for value in sql_rows(stores[0])[0])
    assert sql_rows(stores[1]) == []


def test_duplicate_email_rejected_ignoring_case(authentication, stores):
    saved = authentication.signup(**valid_signup())
    with pytest.raises(ValueError, match="already exists"):
        authentication.signup(**valid_signup(email=" NEW@example.COM "))
    assert len(sql_rows(stores[0])) == 1
    assert stores[0].get_by_id(saved.id) == saved


def test_password_hashes_are_salted_argon2id_and_do_not_log_passwords(passwords, caplog):
    first = passwords.hash("StrongTenant2026!")
    second = passwords.hash("StrongTenant2026!")
    assert first != second
    parameters = extract_parameters(first)
    assert parameters.type is Type.ID
    assert parameters.memory_cost == 65536 and parameters.time_cost == 3
    assert passwords.verify(first, "StrongTenant2026!")
    assert not passwords.verify(first, "WrongPassword2026!")
    assert not passwords.verify("corrupt hash", "StrongTenant2026!")
    assert "StrongTenant2026!" not in caplog.text


def test_account_models_refuse_plaintext_password_storage():
    with pytest.raises(ValueError, match="Argon2id"):
        OwnerAccount("owner@example.com", "admin")


def test_separate_stores_initialize_twice_and_refuse_mixed_databases(stores, account_hash, passwords):
    tenants, owners = stores
    owner = owners.save(OwnerAccount("owner@example.com", account_hash))
    assert OwnerAccountRepository(owners.database_path).get_by_id(owner.id) == owner
    TenantAccountRepository(tenants.database_path)
    with pytest.raises(ValueError, match="separate"):
        OwnerAccountRepository(tenants.database_path)
    with pytest.raises(ValueError, match="separate"):
        TenantAccountRepository(owners.database_path)
    with closing(sqlite3.connect(tenants.database_path)) as connection:
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name = 'owner_accounts'").fetchall()
    with pytest.raises(ValueError, match="correct identity"):
        AuthenticationService(owners, tenants, passwords=passwords)


def test_auth_store_cannot_be_initialized_over_maintenance_database(tmp_path):
    path = tmp_path / "maintenance.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE maintenance_requests (id INTEGER)")
        connection.execute("INSERT INTO maintenance_requests VALUES (99)")
    with pytest.raises(ValueError, match="separate"):
        TenantAccountRepository(path)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT * FROM maintenance_requests").fetchall() == [(99,)]


def test_seeding_requires_opt_in_and_never_overwrites_or_duplicates(stores, passwords):
    with pytest.raises(ValueError, match="opt-in"):
        seed_demo_accounts(*stores)
    assert not sql_rows(stores[0]) and not sql_rows(stores[1])
    assert seed_demo_accounts(*stores, allow_local_demo=True, passwords=passwords) == {"tenants": 3, "owners": 1}
    before = (sql_rows(stores[0]), sql_rows(stores[1]))
    assert seed_demo_accounts(*stores, allow_local_demo=True, passwords=passwords) == {"tenants": 0, "owners": 0}
    assert (sql_rows(stores[0]), sql_rows(stores[1])) == before
    for number in (1, 2, 3):
        account = stores[0].get_by_email(f"user{number}@login.com")
        assert passwords.verify(account.password_hash, f"user{number}")
        assert account.profile.full_name and account.profile.address and account.profile.unit_number
        assert account.terms_version == DEMO_TERMS_VERSION
        assert not account.profile.updates_opt_in
    owner = stores[1].get_by_email("admin@admin.com")
    assert passwords.verify(owner.password_hash, "admin")
    assert len(before[0]) == 3 and len(before[1]) == 1


def test_seed_preserves_an_existing_account_with_different_credentials(stores, account_hash):
    existing = stores[1].save(OwnerAccount("admin@admin.com", account_hash))
    seed_demo_accounts(*stores, allow_local_demo=True)
    assert stores[1].get_by_email("admin@admin.com") == existing


def test_demo_cli_rejects_missing_flag_and_nonlocal_environment(tmp_path):
    environment = dict(os.environ, PROPERTYCARE_AUTH_DATA_DIR=str(tmp_path / "accounts"))
    result = subprocess.run([sys.executable, "-m", "scripts.seed_demo_accounts"], env=environment,
                            capture_output=True, text=True)
    assert result.returncode != 0 and "--local-demo" in result.stderr
    assert not (tmp_path / "accounts").exists()
    environment["PROPERTYCARE_ENV"] = "production"
    result = subprocess.run([sys.executable, "-m", "scripts.seed_demo_accounts", "--local-demo"],
                            env=environment, capture_output=True, text=True)
    assert result.returncode != 0 and "only" in result.stderr
    assert not (tmp_path / "accounts").exists()


def test_tenant_owner_login_cross_rejection_persistence_and_logout(authentication, stores, account_hash):
    tenant = authentication.signup(**valid_signup())
    owner = stores[1].save(OwnerAccount("owner@example.com", account_hash))
    tenant_token = authentication.login_tenant("NEW@EXAMPLE.COM", "StrongTenant2026!")
    owner_token = authentication.login_owner("owner@example.com", "StrongTenant2026!")
    assert tenant_token != owner_token
    assert authentication.require_session(tenant_token, AccountRole.TENANT).account_id == tenant.id
    assert authentication.require_session(owner_token, AccountRole.OWNER).account_id == owner.id
    with pytest.raises(AccessDeniedError):
        authentication.require_session(tenant_token, AccountRole.OWNER)
    for method, email, password in [
        (authentication.login_owner, "new@example.com", "StrongTenant2026!"),
        (authentication.login_tenant, "owner@example.com", "StrongTenant2026!"),
        (authentication.login_tenant, "new@example.com", "wrong"),
        (authentication.login_tenant, "absent@example.com", "wrong"),
        (authentication.login_tenant, "bad input", "wrong"),
    ]:
        with pytest.raises(ValueError) as caught:
            method(email, password)
        assert str(caught.value) == INVALID_CREDENTIALS
    restarted = AuthenticationService(TenantAccountRepository(stores[0].database_path),
                                      OwnerAccountRepository(stores[1].database_path), passwords=authentication.passwords)
    assert restarted.resolve_session(tenant_token) is None
    assert restarted.resolve_session(restarted.login_tenant("new@example.com", "StrongTenant2026!")).display_name == "Demo Tenant"
    authentication.logout(tenant_token)
    assert authentication.resolve_session(tenant_token) is None
    assert authentication.resolve_session(owner_token) is not None
    assert authentication.resolve_session("forged-owner-token") is None
    assert authentication.resolve_session({"role": "owner", "id": owner.id}) is None


def test_session_rechecks_account_existence_and_database_identity(authentication, stores, account_hash):
    owner = stores[1].save(OwnerAccount("owner@example.com", account_hash))
    token = authentication.login_owner(owner.email, "StrongTenant2026!")
    principal = authentication.resolve_session(token)
    authentication._sessions[token] = replace(principal, database_identity=stores[0].identity)
    assert authentication.resolve_session(token) is None
    token = authentication.login_owner(owner.email, "StrongTenant2026!")
    with closing(sqlite3.connect(stores[1].database_path)) as connection, connection:
        connection.execute("DELETE FROM owner_accounts WHERE id = ?", (owner.id,))
    assert authentication.resolve_session(token) is None


def test_legacy_service_checks_owner_on_every_operation(authentication, stores, account_hash):
    authentication.signup(**valid_signup())
    stores[1].save(OwnerAccount("owner@example.com", account_hash))
    state = {"token": authentication.login_owner("owner@example.com", "StrongTenant2026!")}
    maintenance = Mock()
    guarded = OwnerMaintenanceService(authentication, lambda: state["token"], maintenance)
    guarded.list_requests()
    maintenance.list_requests.assert_called_once()
    state["token"] = authentication.login_tenant("new@example.com", "StrongTenant2026!")
    for operation, args in [(guarded.list_requests, ()), (guarded.submit, ("Unit", "Leak", "", "Medium")),
                             (guarded.change_priority, (1, "High"))]:
        with pytest.raises(AccessDeniedError):
            operation(*args)
    maintenance.submit.assert_not_called()
    maintenance.change_priority.assert_not_called()


def test_repositories_bind_sql_and_close_connections(stores, account_hash, tmp_path):
    owners = stores[1]
    saved = owners.save(OwnerAccount("owner@example.com", account_hash))
    assert owners.get_by_email("' OR 1=1 --") is None
    assert owners.get_by_id(saved.id) == saved
    moved = tmp_path / "moved.db"
    owners.database_path.rename(moved)
    assert OwnerAccountRepository(moved).get_by_id(saved.id) == saved



@pytest.mark.parametrize("email", ["a@b.c", "a@example.123", "a@" + "b" * 64 + ".com"])
def test_email_suffix_and_dns_label_validation(email):
    with pytest.raises(ValueError, match="valid email"):
        normalize_email(email)


def test_parenthesized_phone_format_is_accepted():
    assert normalize_phone("(202) 555-0119") == "2025550119"


def test_corrupt_stored_credentials_revoke_sessions_and_use_generic_login_error(authentication, stores, account_hash):
    owner = stores[1].save(OwnerAccount("owner@example.com", account_hash))
    token = authentication.login_owner(owner.email, "StrongTenant2026!")
    with closing(sqlite3.connect(stores[1].database_path)) as connection, connection:
        connection.execute("UPDATE owner_accounts SET password_hash = ? WHERE id = ?", ("invalid", owner.id))
    assert authentication.resolve_session(token) is None
    with pytest.raises(ValueError) as caught:
        authentication.login_owner(owner.email, "StrongTenant2026!")
    assert str(caught.value) == INVALID_CREDENTIALS


def test_repeat_seed_does_not_consume_ids_or_change_existing_values(stores):
    seed_demo_accounts(*stores, allow_local_demo=True)
    def snapshot():
        result = []
        for repository in stores:
            with closing(sqlite3.connect(repository.database_path)) as connection:
                result.append((sql_rows(repository), connection.execute("SELECT * FROM sqlite_sequence").fetchall()))
        return result
    before = snapshot()
    assert seed_demo_accounts(*stores, allow_local_demo=True) == {"tenants": 0, "owners": 0}
    assert snapshot() == before
