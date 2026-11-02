"""Interfaces needed by authentication policy, independent of storage and hashing tools."""

from typing import Protocol, runtime_checkable

from src.domain.accounts import AccountRole, OwnerAccount, TenantAccount


@runtime_checkable
class AccountStoreIdentity(Protocol):
    @property
    def role(self) -> AccountRole: ...

    @property
    def identity(self) -> str: ...


@runtime_checkable
class TenantAccountStore(AccountStoreIdentity, Protocol):
    def get_by_email(self, email: str) -> TenantAccount | None: ...

    def get_by_id(self, account_id: int) -> TenantAccount | None: ...

    def save(self, account: TenantAccount) -> TenantAccount: ...


@runtime_checkable
class OwnerAccountStore(AccountStoreIdentity, Protocol):
    def get_by_email(self, email: str) -> OwnerAccount | None: ...

    def get_by_id(self, account_id: int) -> OwnerAccount | None: ...


@runtime_checkable
class PasswordCodec(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...
