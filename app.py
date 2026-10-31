"""PropertyCare composition and protected-page router."""

import os
from pathlib import Path

import streamlit as st

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.accounts import AccessDeniedError, AccountRole
from src.presentation.auth_views import (
    configured_authentication, logout, navigate, render_login, render_signup,
)
from src.presentation.maintenance_view import render_maintenance
from src.services.maintenance_request_service import MaintenanceRequestService
from src.services.owner_maintenance_service import OwnerMaintenanceService
from src.services.tenant_maintenance_service import TenantMaintenanceService


def request_repository(authentication):
    path = Path(os.environ.get("PROPERTYCARE_DB_PATH", str(Path(__file__).resolve().parent / "data/propertycare.db")))
    if path.resolve() in {Path(authentication.tenants.identity), Path(authentication.owners.identity)}:
        raise ValueError("Authentication and maintenance databases must be separate.")
    return MaintenanceRequestRepository(path)


def main():
    st.set_page_config(page_title="PropertyCare", page_icon="🏠", layout="centered")
    authentication = configured_authentication()
    token = st.session_state.get("auth_token")
    principal = authentication.resolve_session(token)
    page = st.session_state.get("auth_page", "tenant_login")
    protected = {"tenant_dashboard", "tenant_maintenance", "owner_dashboard", "owner_maintenance"}

    # URLs/query parameters never grant a role. Resolve opaque server-issued sessions.
    if principal is None:
        st.session_state.pop("auth_token", None)
        if page in protected:
            logout(authentication)
            st.session_state["auth_error"] = "Please log in to continue."
            page = "tenant_login"
            st.session_state["auth_page"] = page
        if page == "signup":
            render_signup(authentication)
        elif page == "owner_login":
            render_login(authentication, AccountRole.OWNER)
        else:
            render_login(authentication, AccountRole.TENANT)
        return

    if page in {"owner_dashboard", "owner_maintenance"} and principal.role is not AccountRole.OWNER:
        st.session_state["auth_error"] = "Owner access is required."
        page = "tenant_dashboard"
        st.session_state["auth_page"] = page
    if page == "tenant_maintenance" and principal.role is not AccountRole.TENANT:
        st.session_state["auth_error"] = "Tenant access is required."
        page = "owner_dashboard"
        st.session_state["auth_page"] = page

    if principal.role is AccountRole.TENANT:
        authentication.require_session(token, AccountRole.TENANT)
        if page == "tenant_maintenance":
            try:
                service = TenantMaintenanceService(
                    authentication, lambda: st.session_state.get("auth_token"),
                    request_repository(authentication),
                )
                render_maintenance(service, tenant=True)
            except AccessDeniedError:
                logout(authentication)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
            st.button("Back to Tenant Dashboard", on_click=navigate, args=("tenant_dashboard",))
        else:
            st.title("Tenant Dashboard")
            st.text(f"Welcome, {principal.display_name}.")
            if st.session_state.get("auth_error"):
                st.error(st.session_state["auth_error"])
            st.info("Submit maintenance requests and view your own request history.")
            st.button("My maintenance requests", on_click=navigate, args=("tenant_maintenance",))
        st.button("Logout", on_click=logout, args=(authentication,))
        return

    authentication.require_session(token, AccountRole.OWNER)
    if page == "owner_maintenance":
        try:
            repository = request_repository(authentication)
        except ValueError as error:
            st.error(str(error))
            st.button("Logout", on_click=logout, args=(authentication,))
            return
        service = OwnerMaintenanceService(
            authentication, lambda: st.session_state.get("auth_token"),
            MaintenanceRequestService(repository),
        )
        try:
            render_maintenance(service)
        except AccessDeniedError:
            logout(authentication)
            st.rerun()
        st.divider()
        st.button("Back to Owner Dashboard", on_click=navigate, args=("owner_dashboard",))
    else:
        st.title("Owner Dashboard")
        st.text(f"Welcome, {principal.email}.")
        if st.session_state.get("auth_error"):
            st.error(st.session_state["auth_error"])
        st.button("Open maintenance requests", on_click=navigate, args=("owner_maintenance",))
        st.caption("Active Issues and Fixed Issues management will be added separately.")
    st.button("Logout", on_click=logout, args=(authentication,))


if __name__ == "__main__":
    main()
