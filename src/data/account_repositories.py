"""Separate SQLite credential stores; no shared tenant/owner credential table."""

from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
from uuid import uuid4

from src.domain.accounts import AccountRole, DuplicateEmailError, OwnerAccount, TenantAccount, TenantProfile


class _AccountRepository:
    table_name = ""
    forbidden_table = ""
    schema = ""

    def __init__(self, database_path):
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )}
            if self.forbidden_table in tables or "maintenance_requests" in tables:
                raise ValueError("Tenant, owner, and maintenance databases must be separate.")
            connection.execute(self.schema)
            self._migrate(connection)

    def _migrate(self, connection):
        """Repository-specific migrations run inside the initialization transaction."""

    @property
    def identity(self):
        return str(self.database_path)

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _find(self, column, value):
        # Table/column identifiers are internal constants; account data is always bound.
        with closing(self._connect()) as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE {column} = ?", (value,)
            ).fetchone()
        return self._from_row(row) if row else None

    def get_by_email(self, email):
        return self._find("email", email)

    def get_by_id(self, account_id):
        return self._find("id", account_id)


class TenantAccountRepository(_AccountRepository):
    role = AccountRole.TENANT
    table_name = "tenant_accounts"
    forbidden_table = "owner_accounts"
    schema = """CREATE TABLE IF NOT EXISTS tenant_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_key TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        phone_number TEXT NOT NULL,
        address TEXT NOT NULL,
        unit_number TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        updates_opt_in INTEGER NOT NULL CHECK (updates_opt_in IN (0, 1)),
        terms_accepted_at TEXT NOT NULL,
        terms_version TEXT NOT NULL,
        created_at TEXT NOT NULL
    )"""

    def _migrate(self, connection):
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tenant_accounts)")}
        if "account_key" not in columns:
            connection.execute("ALTER TABLE tenant_accounts ADD COLUMN account_key TEXT")
        for row in connection.execute("SELECT id FROM tenant_accounts WHERE account_key IS NULL").fetchall():
            connection.execute("UPDATE tenant_accounts SET account_key = ? WHERE id = ?",
                               (str(uuid4()), row["id"]))
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS tenant_account_key_unique "
                           "ON tenant_accounts(account_key)")

    @staticmethod
    def _from_row(row):
        profile = TenantProfile(row["full_name"], row["email"], row["phone_number"],
                                row["address"], row["unit_number"], bool(row["updates_opt_in"]))
        return TenantAccount(profile, row["password_hash"], row["terms_accepted_at"],
                             row["terms_version"], row["created_at"], row["id"], row["account_key"])

    def save(self, account: TenantAccount, *, if_missing=False):
        profile = account.profile
        sql = """INSERT INTO tenant_accounts
            (full_name, email, phone_number, address, unit_number, password_hash,
             updates_opt_in, terms_accepted_at, terms_version, created_at, account_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        if if_missing:
            sql += " ON CONFLICT(email) DO NOTHING"
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(sql, (
                    profile.full_name, profile.email, profile.phone_number, profile.address,
                    profile.unit_number, account.password_hash, int(profile.updates_opt_in),
                    account.terms_accepted_at, account.terms_version, account.created_at, account.account_key,
                ))
                return replace(account, id=cursor.lastrowid) if cursor.rowcount else None
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed: tenant_accounts.email" in str(error):
                raise DuplicateEmailError("An account with that email already exists.") from error
            raise


class OwnerAccountRepository(_AccountRepository):
    role = AccountRole.OWNER
    table_name = "owner_accounts"
    forbidden_table = "tenant_accounts"
    schema = """CREATE TABLE IF NOT EXISTS owner_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )"""

    @staticmethod
    def _from_row(row):
        return OwnerAccount(row["email"], row["password_hash"], row["created_at"], row["id"])

    def save(self, account: OwnerAccount, *, if_missing=False):
        sql = "INSERT INTO owner_accounts (email, password_hash, created_at) VALUES (?, ?, ?)"
        if if_missing:
            sql += " ON CONFLICT(email) DO NOTHING"
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(sql, (account.email, account.password_hash, account.created_at))
                return replace(account, id=cursor.lastrowid) if cursor.rowcount else None
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed: owner_accounts.email" in str(error):
                raise DuplicateEmailError("An account with that email already exists.") from error
            raise
