"""Shared accessible presentation: palette, feedback, paged history and photos."""

import streamlit as st

from src.domain.work_orders import validate_photo

CSS = """
<style>
:root { --pc-navy:#081E3F; --pc-gold:#B6862C; }
html { font-size:18px; }
[data-testid="stAppViewContainer"] { background:#F7FAFD; color:#081E3F; }
[data-testid="stMainBlockContainer"] { max-width:1240px; padding-top:2rem; padding-bottom:3rem; }
h1 { letter-spacing:-.035em; line-height:1.15; margin-bottom:.5rem; }
h2,h3 { color:#081E3F; letter-spacing:-.015em; }
[data-testid="stCaptionContainer"] { opacity:1 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:#42556C !important; }
[data-testid="stForm"], [data-testid="stExpander"] {
  background:#FFF; border:1px solid #D4DFEC; border-radius:14px;
  box-shadow:0 3px 14px rgba(8,30,63,.04);
}
[data-testid="stForm"] { border-top:3px solid #B6862C; padding:1.3rem; }
button { min-height:44px; font-weight:600 !important; border-radius:9px !important; }
button[kind="primary"], [data-testid="stFormSubmitButton"] button {
  background:#081E3F; color:#FFF; border-color:#081E3F;
}
button:focus-visible, input:focus-visible, textarea:focus-visible,
[role="combobox"]:focus-visible, a:focus-visible {
  outline:3px solid #B6862C !important; outline-offset:3px;
}
input,textarea,[role="combobox"] { font-size:1rem !important; }
[data-testid="stSidebar"] { background:#F1F6FB; border-right:1px solid #D4DFEC; }
[data-testid="stMetric"] { background:#FFF; padding:1rem; border-radius:12px; border:1px solid #D4DFEC; }
@media(max-width:640px) {
  [data-testid="stMainBlockContainer"] { padding:1rem .8rem 2rem; }
  [data-testid="stForm"] { padding:.8rem; }
  h1 { font-size:1.9rem !important; }
}
</style>
"""

FEEDBACK_KEYS = ("submission_success", "submission_error", "priority_update_success", "priority_update_error",
                 "workflow_success", "workflow_error")


def apply_style():
    st.html(CSS)


def sidebar(principal=None, *, dashboard_action=None, logout_action=None):
    with st.sidebar:
        st.markdown("## PropertyCare")
        st.caption("Rental maintenance, clearly organized")
        if principal:
            st.markdown(f"**{principal.role.value.title()} workspace**")
            st.text(principal.display_name)
            st.caption("Your role controls which requests and actions are available.")
            if dashboard_action:
                st.button("My dashboard", key="sidebar_dashboard", on_click=dashboard_action, width="stretch")
            if logout_action:
                st.button("Logout", key="sidebar_logout", on_click=logout_action, width="stretch")
        else:
            st.write("Tenants report. Owners coordinate. Contractors repair.")
        st.divider()
        st.caption("A CEN 5064 academic project. FIU-inspired colors; no university endorsement.")


def clear_feedback():
    for key in FEEDBACK_KEYS:
        st.session_state.pop(key, None)


def history_page(service, key, **filters):
    labels = {"maintenance": "Request history page", "active": "Active issues page", "fixed": "Fixed issues page",
              "unit_history": "Unit history page", "assignments": "Assignment page"}
    page = int(st.number_input(labels[key], min_value=1, value=1, step=1, key=f"{key}_page"))
    result = service.list_requests_page(limit=25, offset=(page - 1) * 25, **filters)
    if page > 1 and not result.items:
        st.info("There are no requests on this page. Choose an earlier history page.")
    if result.total:
        st.caption(f"Showing {min((page - 1) * 25 + 1, result.total)}–{min(page * 25, result.total)} of {result.total} requests. Change the history page to see more.")
    return result.items


def show_photos(service, requests):
    for request in requests:
        if request.has_photo or request.photo:
            with st.expander(f"Photo for request #{request.id}", key=f"photo_panel_{request.id}"):
                selected = st.session_state.get("request_photo_preview")
                opened = st.button("View photo", key=f"view_photo_{request.id}")
                # Keep one validated photo per session, rather than one image per
                # history row. The rows supplied here are authorized on each rerun.
                showing = selected is not None and selected["id"] == request.id
                if opened or (showing and selected["revision"] != request.revision):
                    st.session_state.pop("request_photo_preview", None)
                    try:
                        photo = service.get_request(request.id)
                        if photo.photo:
                            validate_photo(photo.photo)
                            st.session_state["request_photo_preview"] = {
                                "id": photo.id, "revision": photo.revision,
                                "photo": photo.photo,
                            }
                        else:
                            st.info("This request no longer has a photo.")
                    except ValueError as error:
                        st.error(str(error))
                selected = st.session_state.get("request_photo_preview")
                if selected is not None and selected["id"] == request.id:
                    st.image(selected["photo"], caption=request.title)
