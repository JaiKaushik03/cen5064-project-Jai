"""Authentication presentation and local service composition; no SQL in the UI."""

import os
from pathlib import Path

import streamlit as st

from src.data.account_repositories import OwnerAccountRepository, TenantAccountRepository
from src.domain.accounts import AccountRole, PASSWORD_POLICY, TERMS_VERSION
from src.services.authentication_service import AuthenticationService

PASSWORD_KEYS = ("tenant_password", "owner_password", "signup_password", "signup_confirmation")
TERMS_TEXT = f"""### Terms and Conditions — academic demonstration
Version: **{TERMS_VERSION}**

This is a nonbinding academic demonstration for CEN 5064, not a legally reviewed
commercial agreement or a production service. Use fictional demonstration details;
do not enter real personal information or passwords reused elsewhere.

Account profile details and the time/version of this acknowledgement are stored
locally in SQLite. Passwords are stored as salted hashes. The optional updates
checkbox only records a preference; this demonstration sends no notifications.
Owner access is created through local setup, not public registration.

The required checkbox records acknowledgement of these demonstration terms.
"""


@st.cache_resource(show_spinner=False)
def authentication_service(directory):
    path = Path(directory)
    return AuthenticationService(
        TenantAccountRepository(path / "tenant_accounts.db"),
        OwnerAccountRepository(path / "owner_accounts.db"),
    )


def configured_authentication():
    default = Path(__file__).resolve().parents[2] / "data"
    directory = Path(os.environ.get("PROPERTYCARE_AUTH_DATA_DIR", str(default))).resolve()
    return authentication_service(str(directory))


def clear_password_fields():
    # This runs in callbacks, before the next widget render.
    for key in PASSWORD_KEYS:
        if key in st.session_state:
            st.session_state[key] = ""


def navigate(page):
    clear_password_fields()
    st.session_state["auth_page"] = page
    st.session_state.pop("auth_error", None)
    st.session_state.pop("auth_success", None)


def logout(authentication):
    authentication.logout(st.session_state.get("auth_token"))
    st.session_state.clear()
    st.session_state["auth_page"] = "tenant_login"


def login(authentication, role):
    st.session_state.pop("auth_error", None)
    st.session_state.pop("auth_success", None)
    prefix = role.value
    try:
        method = authentication.login_tenant if role is AccountRole.TENANT else authentication.login_owner
        token = method(st.session_state.get(f"{prefix}_email", ""),
                       st.session_state.get(f"{prefix}_password", ""))
    except ValueError as error:
        st.session_state["auth_error"] = str(error)
    else:
        authentication.logout(st.session_state.get("auth_token"))
        st.session_state["auth_token"] = token
        st.session_state["auth_page"] = f"{prefix}_dashboard"
    finally:
        clear_password_fields()


def signup(authentication):
    st.session_state.pop("auth_error", None)
    try:
        account = authentication.signup(
            st.session_state.get("signup_full_name", ""),
            st.session_state.get("signup_email", ""),
            st.session_state.get("signup_phone", ""),
            st.session_state.get("signup_address", ""),
            st.session_state.get("signup_unit", ""),
            st.session_state.get("signup_password", ""),
            st.session_state.get("signup_confirmation", ""),
            updates_opt_in=st.session_state.get("signup_updates", False),
            terms_accepted=st.session_state.get("signup_terms", False),
        )
    except ValueError as error:
        st.session_state["auth_error"] = str(error)
    else:
        # Form callbacks run before widgets render, so these assignments are safe.
        st.session_state["tenant_email"] = account.profile.email
        clear_password_fields()
        for key in ("signup_full_name", "signup_email", "signup_phone", "signup_address", "signup_unit"):
            st.session_state[key] = ""
        st.session_state["signup_updates"] = False
        st.session_state["signup_terms"] = False
        st.session_state["auth_page"] = "tenant_login"
        st.session_state["auth_success"] = "Account created successfully. You can now log in."


def feedback():
    if st.session_state.get("auth_error"):
        st.error(st.session_state["auth_error"])
    if st.session_state.get("auth_success"):
        st.success(st.session_state["auth_success"])


def render_login(authentication, role):
    owner = role is AccountRole.OWNER
    st.title("PropertyCare — Owner Login" if owner else "PropertyCare")
    st.caption("Owner access" if owner else "Rental Maintenance Management System")
    feedback()
    with st.form(f"{role.value}_login"):
        st.text_input("Email address", key=f"{role.value}_email", max_chars=254)
        st.text_input("Password", type="password", key=f"{role.value}_password", max_chars=128)
        st.form_submit_button("Login as Owner" if owner else "Log In",
                              on_click=login, args=(authentication, role))
    if owner:
        st.button("Back to User Login", on_click=navigate, args=("tenant_login",))
    else:
        st.button("Sign Up", on_click=navigate, args=("signup",))
        st.button("Login as Owner", on_click=navigate, args=("owner_login",))


def render_signup(authentication):
    st.title("Create Your PropertyCare Account")
    st.caption("Fields marked * and terms acceptance are required. Updates and notifications are optional.")
    feedback()
    with st.expander("Read Terms and Conditions"):
        st.markdown(TERMS_TEXT)
    with st.form("tenant_signup"):
        st.text_input("Full Name *", key="signup_full_name", max_chars=100)
        st.text_input("Email Address *", key="signup_email", max_chars=254)
        st.text_input("Phone Number *", key="signup_phone", max_chars=40)
        st.text_input("Address *", key="signup_address", max_chars=300)
        st.text_input("Unit Number *", key="signup_unit", max_chars=50)
        st.text_input("Password *", type="password", key="signup_password", max_chars=128)
        st.text_input("Confirm Password *", type="password", key="signup_confirmation", max_chars=128)
        st.caption(PASSWORD_POLICY)
        st.checkbox("I would like to receive updates and notifications from PropertyCare.", key="signup_updates")
        st.checkbox("I have read and agree to the Terms and Conditions.", key="signup_terms")
        st.form_submit_button("Create Account", on_click=signup, args=(authentication,))
    st.button("Back to User Login", on_click=navigate, args=("tenant_login",))
