"""Signup, separate-store login, and server-owned opaque local sessions."""

import secrets
from threading import Lock

from src.domain.accounts import (
    AccessDeniedError, AccountRole, Principal, TenantAccount, TenantProfile,
    TERMS_VERSION, normalize_email, utc_now, validate_signup_password, validate_terms,
)
from src.services.authentication_ports import OwnerAccountStore, PasswordCodec, TenantAccountStore

INVALID_CREDENTIALS = "Invalid email address or password."


class AuthenticationService:
    def __init__(self, tenants: TenantAccountStore, owners: OwnerAccountStore, *, passwords: PasswordCodec):
        if (not isinstance(tenants, TenantAccountStore) or tenants.role is not AccountRole.TENANT
                or not isinstance(owners, OwnerAccountStore) or owners.role is not AccountRole.OWNER):
            raise ValueError("Tenant and owner repositories must have the correct identity.")
        if tenants.identity == owners.identity:
            raise ValueError("Tenant and owner databases must be separate.")
        if not isinstance(passwords, PasswordCodec):
            raise ValueError("A password codec with hash and verify operations is required.")
        self.tenants = tenants
        self.owners = owners
        self.passwords = passwords
        self._dummy_hash = self.passwords.hash(secrets.token_urlsafe(32))
        self._sessions = {}
        self._lock = Lock()

    def signup(self, full_name, email, phone_number, address, unit_number,
               password, confirmation, updates_opt_in=False, terms_accepted=False):
        profile = TenantProfile(full_name, email, phone_number, address, unit_number, updates_opt_in)
        validate_signup_password(password, confirmation)
        validate_terms(terms_accepted)
        account = TenantAccount(profile, self.passwords.hash(password), utc_now(), TERMS_VERSION)
        return self.tenants.save(account)

    def login_tenant(self, email, password):
        return self._login(self.tenants, AccountRole.TENANT, email, password)

    def login_owner(self, email, password):
        return self._login(self.owners, AccountRole.OWNER, email, password)

    def _login(self, repository, role, email, password):
        try:
            email = normalize_email(email)
        except ValueError:
            email = ""
        try:
            account = repository.get_by_email(email)
        except ValueError:
            # A malformed stored credential/profile must not authenticate or expose details.
            account = None
        encoded = account.password_hash if account else self._dummy_hash
        if not self.passwords.verify(encoded, password) or account is None:
            raise ValueError(INVALID_CREDENTIALS)
        name = account.profile.full_name if role is AccountRole.TENANT else "Owner"
        principal = Principal(account.id, role, email, name, repository.identity)
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = principal
        return token

    def resolve_session(self, token):
        if not isinstance(token, str):
            return None
        with self._lock:
            principal = self._sessions.get(token)
        if principal is None:
            return None
        repository = self.tenants if principal.role is AccountRole.TENANT else self.owners
        try:
            account = repository.get_by_id(principal.account_id)
        except ValueError:
            account = None
        email = (account.profile.email if principal.role is AccountRole.TENANT else account.email) if account else None
        if repository.identity != principal.database_identity or email != principal.email:
            self.logout(token)
            return None
        return principal

    def require_session(self, token, role):
        principal = self.resolve_session(token)
        if principal is None or principal.role is not role:
            raise AccessDeniedError(f"{role.value.title()} login is required to access this page.")
        return principal

    def logout(self, token):
        if isinstance(token, str):
            with self._lock:
                self._sessions.pop(token, None)
