"""PropertyCare presentation: collect input, call the service, display saved requests."""

import streamlit as st

from src.domain.priority import Priority


DEFAULT_PRIORITY = Priority.MEDIUM


def submit_request(service):
    """Save submitted state; reset widgets only after a successful save."""
    st.session_state.pop("submission_success", None)
    st.session_state.pop("submission_error", None)
    try:
        saved = service.submit(
            st.session_state["property_unit"],
            st.session_state["title"],
            st.session_state["description"],
            st.session_state["priority"],
        )
    except ValueError as error:
        st.session_state["submission_error"] = str(error)
    else:
        # Callbacks run before widgets are rendered on the next rerun.
        st.session_state["property_unit"] = ""
        st.session_state["title"] = ""
        st.session_state["description"] = ""
        st.session_state["priority"] = DEFAULT_PRIORITY.value
        st.session_state["submission_success"] = f"Request #{saved.id} saved successfully."


def change_request_priority(service):
    """Forward the submitted manager action; Domain decides whether it is allowed."""
    st.session_state.pop("priority_update_success", None)
    st.session_state.pop("priority_update_error", None)
    try:
        updated = service.change_priority(
            st.session_state["manager_request_id"],
            st.session_state["manager_priority"],
        )
    except ValueError as error:
        st.session_state["priority_update_error"] = str(error)
    else:
        st.session_state["priority_update_success"] = (
            f"Request #{updated.id} priority updated to {updated.priority.value}."
        )


def render_maintenance(service):
    """Render the existing workflow through an owner-authorized service adapter."""
    st.title("PropertyCare")
    st.caption("Report a maintenance issue and view saved requests.")

    # Session state is the single source for initial values and callback resets.
    st.session_state.setdefault("priority", DEFAULT_PRIORITY.value)

    st.subheader("Submit a maintenance request")
    st.caption("Fields marked * are required. Description is optional.")
    with st.form("maintenance_request"):
        st.text_input(
            "Property / Unit *", placeholder="Oak Court / Unit 2B", key="property_unit"
        )
        st.text_input("Issue title *", placeholder="Leaking kitchen sink", key="title")
        st.text_area("Description (optional)", key="description")
        priority_options = [item.value for item in Priority]
        st.selectbox(
            "Priority *",
            priority_options,
            key="priority",
        )
        st.form_submit_button("Submit request", on_click=submit_request, args=(service,))

    if st.session_state.get("submission_error"):
        st.error(st.session_state["submission_error"])
    if st.session_state.get("submission_success"):
        st.success(st.session_state["submission_success"])

    st.subheader("Saved maintenance requests")
    st.button("Refresh saved requests")
    requests = service.list_requests()
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
                }
                for request in requests
            ]
        )

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

        st.selectbox(
            "New priority *",
            priority_options,
            key="manager_priority",
        )
        st.button("Update Priority", on_click=change_request_priority, args=(service,))
    else:
        st.info("Submit a request before changing its priority.")
