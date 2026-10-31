"""Account data and signup rules, independent of Streamlit, hashing, and SQLite."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from uuid import UUID, uuid4

TERMS_VERSION = "2026-10-24"
DEMO_TERMS_VERSION = "2026-10-24-demo-seed"
PASSWORD_POLICY = "Use 12 to 128 characters, including a letter and a number."


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AccountRole(Enum):
    TENANT = "tenant"
    OWNER = "owner"


class DuplicateEmailError(ValueError):
    pass


class AccessDeniedError(ValueError):
    pass


def required_text(value, label, limit):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required.")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{label} must be at most {limit} characters.")
    return value


def normalize_email(value) -> str:
    value = required_text(value, "Email address", 254).casefold()
    pattern = r"[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+"
    local = value.split("@", 1)[0]
    labels = value.rsplit("@", 1)[-1].split(".")
    if (not re.fullmatch(pattern, value) or len(local) > 64
            or local.endswith(".") or ".." in local
            or any(len(label) > 63 for label in labels)
            or not re.fullmatch(r"[a-z]{2,63}", labels[-1])):
        raise ValueError("Enter a valid email address.")
    return value


def normalize_phone(value) -> str:
    value = required_text(value, "Phone number", 40)
    digits = re.sub(r"[^0-9]", "", value)
    if not re.fullmatch(r"\+?[0-9(][0-9 ()\.\-]*", value) or not 10 <= len(digits) <= 15:
        raise ValueError("Enter a phone number with 10 to 15 digits.")
    return ("+" if value.startswith("+") else "") + digits


def validate_signup_password(password, confirmation):
    if not isinstance(password, str) or not password or password.isspace():
        raise ValueError("Password is required.")
    if not isinstance(confirmation, str) or not confirmation or confirmation.isspace():
        raise ValueError("Confirm password is required.")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    if (not 12 <= len(password) <= 128 or not any(c.isalpha() for c in password)
            or not any(c.isdigit() for c in password)):
        raise ValueError(PASSWORD_POLICY)


@dataclass(frozen=True)
class TenantProfile:
    full_name: str
    email: str
    phone_number: str
    address: str
    unit_number: str
    updates_opt_in: bool = False

    def __post_init__(self):
        for name, label, limit in (("full_name", "Full name", 100),
                                   ("address", "Address", 300),
                                   ("unit_number", "Unit number", 50)):
            object.__setattr__(self, name, required_text(getattr(self, name), label, limit))
        object.__setattr__(self, "email", normalize_email(self.email))
        object.__setattr__(self, "phone_number", normalize_phone(self.phone_number))
        if type(self.updates_opt_in) is not bool:
            raise ValueError("Updates preference must be checked or unchecked.")


def validate_terms(accepted):
    if accepted is not True:
        raise ValueError("You must accept the Terms and Conditions to register.")


def validate_hash(value):
    if not isinstance(value, str) or not value.startswith("$argon2id$"):
        raise ValueError("An Argon2id password hash is required.")


def normalize_account_key(value) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        return str(UUID(value))
    except ValueError as error:
        raise ValueError("A valid tenant account key is required.") from error


@dataclass(frozen=True)
class TenantAccount:
    profile: TenantProfile
    password_hash: str = field(repr=False)
    terms_accepted_at: str
    terms_version: str
    created_at: str = field(default_factory=utc_now)
    id: int | None = None
    account_key: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "account_key", normalize_account_key(self.account_key))
        validate_hash(self.password_hash)
        required_text(self.terms_accepted_at, "Terms acceptance timestamp", 60)
        required_text(self.terms_version, "Terms version", 60)


@dataclass(frozen=True)
class OwnerAccount:
    email: str
    password_hash: str = field(repr=False)
    created_at: str = field(default_factory=utc_now)
    id: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "email", normalize_email(self.email))
        validate_hash(self.password_hash)


@dataclass(frozen=True)
class Principal:
    account_id: int
    role: AccountRole
    email: str
    display_name: str
    database_identity: str
    account_key: str | None = None
