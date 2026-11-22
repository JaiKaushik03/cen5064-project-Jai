"""PropertyCare presentation: collect input, call the service, display saved requests."""

import streamlit as st

from src.domain.priority import Priority
from src.domain.maintenance_request import (ConcurrentRequestError, PROPERTY_UNIT_LIMIT,
                                            TITLE_LIMIT, DESCRIPTION_LIMIT)
from src.domain.work_orders import MAX_PHOTO_BYTES
from src.presentation.ui import clear_feedback, history_page, show_photos


DEFAULT_PRIORITY = Priority.MEDIUM


def submit_request(service):
    """Save submitted state; reset widgets only after a successful save."""
    clear_feedback()
    try:
        optional = {}
        photo = st.session_state.get(f"request_photo_{st.session_state.get('photo_version', 0)}")
        if photo is not None:
            if getattr(photo, "size", 0) > MAX_PHOTO_BYTES:
                raise ValueError("Photo must be a PNG or JPEG of at most 2 MiB. Choose a smaller image.")
            optional["photo"] = photo.getvalue()
        if st.session_state.get("request_unit_id") is not None:
            optional["registered_unit_id"] = st.session_state["request_unit_id"]
        with st.spinner("Saving your request…"):
            saved = service.submit(
                st.session_state["property_unit"], st.session_state["title"],
                st.session_state["description"], st.session_state["priority"], **optional,
            )
    except ValueError as error:
        st.session_state["submission_error"] = str(error)
    else:
        # Callbacks run before widgets are rendered on the next rerun.
        st.session_state["property_unit"] = ""
        st.session_state["title"] = ""
        st.session_state["description"] = ""
        st.session_state["priority"] = DEFAULT_PRIORITY.value
        st.session_state["request_unit_id"] = None
        st.session_state["photo_version"] = st.session_state.get("photo_version", 0) + 1
        st.session_state["submission_success"] = f"Request #{saved.id} saved successfully."


def change_request_priority(service):
    """Forward the submitted manager action; Domain decides whether it is allowed."""
    clear_feedback()
    try:
        updated = service.change_priority(
            st.session_state["manager_request_id"],
            st.session_state["manager_priority"],
            expected_revision=st.session_state.get("manager_priority_revision"),
        )
    except ConcurrentRequestError as error:
        st.session_state["priority_conflict"] = True
        st.session_state["priority_update_error"] = str(error)
    except ValueError as error:
        st.session_state["priority_update_error"] = str(error)
    else:
        st.session_state["manager_priority_revision"] = updated.revision
        st.session_state.pop("priority_conflict", None)
        st.session_state["priority_update_success"] = (
            f"Request #{updated.id} priority updated to {updated.priority.value}."
        )


def reload_priority():
    st.session_state.pop("manager_priority_request_id", None)
    st.session_state.pop("priority_conflict", None)
    clear_feedback()


def render_maintenance(service, *, tenant=False):
    """Share form/history rendering; tenant services enforce ownership on every call."""
    st.title("My maintenance requests" if tenant else "PropertyCare")
    st.caption("Report a maintenance issue and view saved requests.")

    # Session state is the single source for initial values and callback resets.
    st.session_state.setdefault("priority", DEFAULT_PRIORITY.value)

    st.subheader("Submit a maintenance request")
    st.caption("Fields marked * are required. Description is optional.")
    st.write("Tell us where the problem is and what needs repair. Your request stays in the history after it is fixed.")
    units = service.list_units()
    units_by_id = {unit["id"]: unit for unit in units}
    with st.form("maintenance_request"):
        if units:
            st.selectbox("Registered unit (optional)", [None, *units_by_id],
                         format_func=lambda value: "Unregistered / legacy location" if value is None else
                         f"{units_by_id[value]['name']} / Unit {units_by_id[value]['number']}", key="request_unit_id")
            st.caption("Choose a catalog unit if it applies. This selection does not verify your tenancy or expose another tenant's requests.")
        st.text_input(
            "Property / Unit *", placeholder="Oak Court / Unit 2B", key="property_unit", max_chars=PROPERTY_UNIT_LIMIT
        )
        st.text_input("Issue title *", placeholder="Leaking kitchen sink", key="title", max_chars=TITLE_LIMIT)
        st.text_area("Description (optional)", key="description", max_chars=DESCRIPTION_LIMIT)
        priority_options = [item.value for item in Priority]
        st.selectbox(
            "Priority *",
            priority_options,
            key="priority",
        )
        st.file_uploader("Issue photo (optional, PNG/JPEG, up to 2 MiB)", type=["png", "jpg", "jpeg"],
                         key=f"request_photo_{st.session_state.get('photo_version', 0)}", max_upload_size=2)
        st.form_submit_button("Submit request", on_click=submit_request, args=(service,))

    if st.session_state.get("submission_error"):
        st.error(st.session_state["submission_error"])
    if st.session_state.get("submission_success"):
        st.success(st.session_state["submission_success"])

    st.subheader("My saved requests" if tenant else "Saved maintenance requests")
    st.button("Refresh saved requests")
    requests = history_page(service, "maintenance")
    if not requests:
        st.info("No requests yet. Submit your first maintenance request above.")
    else:
        st.caption(f"{len(requests)} saved request(s), newest first.")
        st.table(
            [
                {
                    "ID": request.id,
                    "Property / Unit": request.property_unit,
                    "Issue title": request.title,
                    "Description": request.description,
                    "Priority": request.priority.value,
                    "Status": request.status.value,
                    "Submitted (UTC)": request.created_at,
                    "Fixed (UTC)": request.completed_at or "",
                }
                for request in requests
            ]
        )

    show_photos(service, requests)
    if tenant:
        return

    st.subheader("Manager - Change Request Priority")
    st.caption(
        "Owner maintenance workspace. "
        "Completed requests cannot have their priorities changed."
    )
    if st.session_state.get("priority_update_error"):
        st.error(st.session_state["priority_update_error"])
    if st.session_state.get("priority_update_success"):
        st.success(st.session_state["priority_update_success"])
    if requests:
        requests_by_id = {request.id: request for request in requests}

        def request_label(request_id):
            request = requests_by_id[request_id]
            return f"#{request.id}: {request.title} ({request.property_unit})"

        st.caption("Current priorities and statuses are shown in the saved requests table.")
        # Selection reruns immediately so the dependent dropdown starts at the saved priority.
        request_id = st.selectbox(
            "Request *",
            list(requests_by_id),
            format_func=request_label,
            key="manager_request_id",
        )
        if st.session_state.get("manager_priority_request_id") != request_id:
            # Set state before rendering its widget, only when selecting another request.
            st.session_state["manager_priority"] = requests_by_id[request_id].priority.value
            st.session_state["manager_priority_request_id"] = request_id
            st.session_state["manager_priority_revision"] = requests_by_id[request_id].revision
            st.session_state.pop("priority_conflict", None)

        st.selectbox(
            "New priority *",
            priority_options,
            key="manager_priority",
        )
        st.button("Update Priority", on_click=change_request_priority, args=(service,))
        if st.session_state.get("priority_conflict"):
            st.button("Reload selected request", on_click=reload_priority)
        st.caption("Priority controls apply to the requests on this history page. Completed requests remain protected by Domain rules.")
    else:
        st.info("Submit a request before changing its priority.")
