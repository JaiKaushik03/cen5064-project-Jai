"""Explicit local-only fictional fixture seeding; never called at app startup."""

from src.domain.accounts import DEMO_TERMS_VERSION, OwnerAccount, TenantAccount, TenantProfile, utc_now
from src.services.passwords import Passwords


def seed_demo_accounts(tenants, owners, *, allow_local_demo=False, passwords=None):
    if allow_local_demo is not True:
        raise ValueError("Demo seeding requires an explicit local development opt-in.")
    passwords = passwords or Passwords()
    created = {"tenants": 0, "owners": 0}
    for number in (1, 2, 3):
        profile = TenantProfile(
            f"Demo Tenant {number}", f"user{number}@login.com", f"202555010{number}",
            "101 Example Lane, Demo City (fictional)", f"Demo {number}A", False,
        )
        if tenants.get_by_email(profile.email) is not None:
            continue
        account = TenantAccount(profile, passwords.hash(f"user{number}"), utc_now(), DEMO_TERMS_VERSION)
        if tenants.save(account, if_missing=True) is not None:
            created["tenants"] += 1
    if owners.get_by_email("admin@admin.com") is None:
        owner = OwnerAccount("admin@admin.com", passwords.hash("admin"))
        if owners.save(owner, if_missing=True) is not None:
            created["owners"] += 1
    return created
