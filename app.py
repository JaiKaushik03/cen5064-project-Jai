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
from src.services.workflow_service import OwnerWorkflowService, ContractorWorkflowService
from src.presentation.owner_views import render_issues, render_catalog, render_assignments
from src.presentation.ui import apply_style, sidebar


@st.cache_resource(show_spinner=False)
def cached_request_repository(path, repository_token):
    return MaintenanceRequestRepository(path)


def request_repository(authentication):
    path = Path(os.environ.get("PROPERTYCARE_DB_PATH", str(Path(__file__).resolve().parent / "data/propertycare.db")))
    if path.resolve() in {Path(authentication.tenants.identity), Path(authentication.owners.identity), Path(authentication.contractors.identity)}:
        raise ValueError("Authentication and maintenance databases must be separate.")
    return cached_request_repository(str(path.resolve()), id(MaintenanceRequestRepository))


def main():
    st.set_page_config(page_title="PropertyCare", page_icon="🏠", layout="wide")
    apply_style()
    try:
        authentication = configured_authentication()
    except ValueError as error:
        st.title("PropertyCare")
        st.error(f"Application setup needs attention: {error}")
        return
    token = st.session_state.get("auth_token")
    principal = authentication.resolve_session(token)
    sidebar(principal, dashboard_action=lambda: navigate(f"{principal.role.value}_dashboard") if principal else None,
            logout_action=lambda: logout(authentication))
    page = st.session_state.get("auth_page", "tenant_login")
    protected = {"tenant_dashboard", "tenant_maintenance", "owner_dashboard", "owner_maintenance", "contractor_dashboard"}

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
        elif page == "contractor_login":
            render_login(authentication, AccountRole.CONTRACTOR)
        elif page == "owner_login":
            render_login(authentication, AccountRole.OWNER)
        else:
            render_login(authentication, AccountRole.TENANT)
        return

    try:
        authentication.require_session(token, principal.role)
    except AccessDeniedError:
        logout(authentication)
        st.session_state["auth_error"] = "Your session ended. Please log in again."
        st.rerun()
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
        if page == "tenant_maintenance":
            try:
                account = authentication.get_tenant_account(token)
                st.session_state.setdefault(
                    "property_unit", f"{account.profile.address} / Unit {account.profile.unit_number}"
                )
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
            st.write("Start a new request, add an optional photo, or check the status of a previous repair.")
            st.button("My maintenance requests", on_click=navigate, args=("tenant_maintenance",))
        st.button("Logout", on_click=logout, args=(authentication,))
        return

    if principal.role is AccountRole.CONTRACTOR:
        st.title("Contractor Dashboard")
        st.text(f"Welcome, {principal.display_name}.")
        st.caption("Your assigned repairs only. Start work when ready, then confirm Mark Fixed after the repair is complete.")
        try:
            render_issues(ContractorWorkflowService(authentication, lambda: st.session_state.get("auth_token"), request_repository(authentication)), contractor=True)
        except AccessDeniedError:
            logout(authentication)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        st.button("Logout", on_click=logout, args=(authentication,))
        return

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
        st.caption("Review active repairs, coordinate contractors and keep a clear record of completed work.")
        if st.session_state.get("auth_error"):
            st.error(st.session_state["auth_error"])
        st.button("Open maintenance requests", on_click=navigate, args=("owner_maintenance",))
        try:
            workflow = OwnerWorkflowService(authentication, lambda: st.session_state.get("auth_token"), request_repository(authentication))
            render_issues(workflow)
            with st.expander("Manage properties and units", key="catalog_panel"):
                render_catalog(workflow)
            with st.expander("Manage contractors and assignments", key="assignments_panel"):
                render_assignments(workflow)
        except AccessDeniedError:
            logout(authentication)
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.button("Logout", on_click=logout, args=(authentication,))


if __name__ == "__main__":
    main()
