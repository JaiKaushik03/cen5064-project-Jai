"""Contractor credentials have their own SQLite file and persistent account key."""
from contextlib import closing
from dataclasses import replace
import sqlite3
from src.data.account_repositories import _AccountRepository
from src.domain.accounts import AccountRole, ContractorAccount, DuplicateEmailError

class ContractorAccountRepository(_AccountRepository):
    role = AccountRole.CONTRACTOR
    table_name = 'contractor_accounts'
    schema = """CREATE TABLE IF NOT EXISTS contractor_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE, password_hash TEXT NOT NULL,
        account_key TEXT NOT NULL UNIQUE)"""

    @staticmethod
    def _from_row(row):
        return ContractorAccount(row['full_name'], row['email'], row['password_hash'], row['id'], row['account_key'])

    def save(self, account):
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute('INSERT INTO contractor_accounts (full_name, email, password_hash, account_key) VALUES (?, ?, ?, ?)',
                                            (account.full_name, account.email, account.password_hash, account.account_key))
            return replace(account, id=cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError('A contractor with that email already exists.') from error

    def list_all(self):
        with closing(self._connect()) as connection:
            rows = connection.execute('SELECT * FROM contractor_accounts ORDER BY full_name, id').fetchall()
        return [self._from_row(row) for row in rows]
