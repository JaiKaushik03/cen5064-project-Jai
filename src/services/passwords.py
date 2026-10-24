"""Argon2id adapter using the maintained argon2-cffi library."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


class Passwords:
    def __init__(self):
        self._hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash, password) -> bool:
        if not isinstance(password, str) or not 1 <= len(password) <= 128:
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError, TypeError):
            return False
