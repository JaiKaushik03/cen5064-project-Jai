"""Authentication policy also works with non-SQLite adapters supplied at startup."""

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from src.domain.accounts import AccessDeniedError, AccountRole, DuplicateEmailError, OwnerAccount
from src.services.authentication_service import AuthenticationService, INVALID_CREDENTIALS
from src.services.passwords import Passwords


class MemoryAccounts:
    def __init__(self, identity):
        self.identity = identity
        self.accounts = {}

    def get_by_email(self, email):
        return next((account for account in self.accounts.values()
                     if self.email_of(account) == email.casefold()), None)

    def get_by_id(self, account_id):
        return self.accounts.get(account_id)

    def save(self, account):
        if self.get_by_email(self.email_of(account)) is not None:
            raise DuplicateEmailError("An account with that email already exists.")
        saved = replace(account, id=len(self.accounts) + 1)
        self.accounts[saved.id] = saved
        return saved


class MemoryTenants(MemoryAccounts):
    role = AccountRole.TENANT

    @staticmethod
    def email_of(account):
        return account.profile.email


class MemoryOwners(MemoryAccounts):
    role = AccountRole.OWNER

    @staticmethod
    def email_of(account):
        return account.email


@pytest.fixture(scope="module")
def passwords():
    return Passwords()


@pytest.fixture
def memory_authentication(passwords):
    tenants = MemoryTenants("memory:tenants")
    owners = MemoryOwners("memory:owners")
    return AuthenticationService(tenants, owners, passwords=passwords)


def signup(authentication, **changes):
    fields = dict(full_name="Memory Tenant", email="Tenant@Example.com", phone_number="2025550123",
                  address="123 Fictional Lane", unit_number="Demo 1A", password="StrongTenant2026!",
                  confirmation="StrongTenant2026!", terms_accepted=True)
    fields.update(changes)
    return authentication.signup(**fields)


def test_signup_login_and_logout_work_without_sqlite_adapters(memory_authentication):
    authentication = memory_authentication
    assert not hasattr(authentication.tenants, "database_path")
    saved = signup(authentication)
    token = authentication.login_tenant(" TENANT@EXAMPLE.COM ", "StrongTenant2026!")
    principal = authentication.require_session(token, AccountRole.TENANT)
    assert principal.account_id == saved.id
    assert principal.display_name == "Memory Tenant"
    assert principal.database_identity == "memory:tenants"
    assert saved.password_hash != "StrongTenant2026!"
    assert authentication.passwords.verify(saved.password_hash, "StrongTenant2026!")
    authentication.logout(token)
    assert authentication.resolve_session(token) is None


def test_memory_owner_login_keeps_role_and_cross_store_rejections(memory_authentication):
    authentication = memory_authentication
    signup(authentication)
    owner = authentication.owners.save(OwnerAccount("owner@example.com", authentication.passwords.hash("OwnerSecret2026!")))
    token = authentication.login_owner(owner.email, "OwnerSecret2026!")
    assert authentication.require_session(token, AccountRole.OWNER).account_id == owner.id
    for method, email, password in [
        (authentication.login_tenant, owner.email, "OwnerSecret2026!"),
        (authentication.login_owner, "tenant@example.com", "StrongTenant2026!"),
        (authentication.login_tenant, "tenant@example.com", "wrong"),
        (authentication.login_tenant, "missing@example.com", "wrong"),
    ]:
        with pytest.raises(ValueError, match=INVALID_CREDENTIALS):
            method(email, password)
    tenant_token = authentication.login_tenant("tenant@example.com", "StrongTenant2026!")
    with pytest.raises(AccessDeniedError):
        authentication.require_session(tenant_token, AccountRole.OWNER)


@pytest.mark.parametrize("change", ["removed_account", "store_identity"])
def test_memory_session_is_revoked_when_its_account_or_store_changes(memory_authentication, change):
    authentication = memory_authentication
    saved = signup(authentication)
    token = authentication.login_tenant("tenant@example.com", "StrongTenant2026!")
    if change == "removed_account":
        authentication.tenants.accounts.pop(saved.id)
    else:
        authentication.tenants.identity = "memory:replacement"
    assert authentication.resolve_session(token) is None
    assert token not in authentication._sessions


def test_memory_signup_still_validates_before_saving_and_rejects_duplicates(memory_authentication):
    authentication = memory_authentication
    with pytest.raises(ValueError, match="Unit number"):
        signup(authentication, unit_number=" ")
    assert authentication.tenants.accounts == {}
    saved = signup(authentication)
    with pytest.raises(DuplicateEmailError):
        signup(authentication, email=" TENANT@EXAMPLE.COM ")
    assert list(authentication.tenants.accounts.values()) == [saved]
    assert authentication.owners.accounts == {}


def test_store_roles_remain_explicit_without_concrete_repository_checks(passwords):
    with pytest.raises(ValueError, match="correct identity"):
        AuthenticationService(MemoryOwners("memory:owners"), MemoryTenants("memory:tenants"), passwords=passwords)


def test_two_adapters_cannot_share_the_same_store_identity(passwords):
    with pytest.raises(ValueError, match="separate"):
        AuthenticationService(MemoryTenants("memory:shared"), MemoryOwners("memory:shared"), passwords=passwords)


def test_incomplete_store_is_rejected_before_authentication(passwords):
    incomplete = SimpleNamespace(role=AccountRole.TENANT, identity="memory:incomplete")
    with pytest.raises(ValueError, match="correct identity"):
        AuthenticationService(incomplete, MemoryOwners("memory:owners"), passwords=passwords)


def test_password_adapter_requires_both_operations():
    with pytest.raises(ValueError, match="password codec"):
        AuthenticationService(MemoryTenants("memory:tenants"), MemoryOwners("memory:owners"),
                              passwords=SimpleNamespace(hash=lambda value: value))


def test_authentication_policy_imports_without_sqlite_or_argon2_implementations():
    # A clean interpreter prevents an earlier test's imports from hiding a dependency.
    program = """
import importlib.abc
import sys

class BlockAdapters(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname == 'src.data' or fullname.startswith('src.data.')
                or fullname == 'src.services.passwords' or fullname == 'argon2'
                or fullname.startswith('argon2.') or fullname == 'sqlite3'):
            raise ImportError('Authentication policy imported a concrete adapter: ' + fullname)

sys.meta_path.insert(0, BlockAdapters())
from src.services.authentication_service import AuthenticationService
assert AuthenticationService is not None
"""
    result = subprocess.run([sys.executable, "-B", "-c", program],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
