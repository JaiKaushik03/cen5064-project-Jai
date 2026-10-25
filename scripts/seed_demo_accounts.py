"""Run: python -m scripts.seed_demo_accounts --local-demo"""

import argparse
import os
from pathlib import Path

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.services.demo_accounts import seed_demo_accounts


def main():
    parser = argparse.ArgumentParser(description="Seed fictional local demo accounts without overwriting existing accounts.")
    parser.add_argument("--local-demo", action="store_true", help="Explicitly opt in to the public, weak demo credentials on this local development machine.")
    arguments = parser.parse_args()
    if not arguments.local_demo:
        parser.error("Pass --local-demo to explicitly opt in; no accounts were created.")
    if os.environ.get("PROPERTYCARE_ENV", "local").casefold() != "local":
        parser.error("Demo seeding is available only with PROPERTYCARE_ENV=local.")
    directory = Path(os.environ.get("PROPERTYCARE_AUTH_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
    tenants = TenantAccountRepository(directory / "tenant_accounts.db")
    owners = OwnerAccountRepository(directory / "owner_accounts.db")
    result = seed_demo_accounts(tenants, owners, allow_local_demo=True)
    print(f"Created {result['tenants']} tenant(s) and {result['owners']} owner(s). Existing accounts were not changed.")
    print("Local demonstration only. Do not use these public demo accounts in a public deployment.")


if __name__ == "__main__":
    main()
