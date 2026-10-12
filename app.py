"""PropertyCare presentation: collect input, call the service, display saved requests."""

import os
from pathlib import Path

import streamlit as st

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.priority import Priority
from src.services.maintenance_request_service import MaintenanceRequestService


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


def main():
    st.set_page_config(page_title="PropertyCare", page_icon="🏠", layout="centered")
    st.title("PropertyCare")
    st.caption("Report a maintenance issue and view saved requests.")

    database_path = Path(
        os.environ.get(
            "PROPERTYCARE_DB_PATH",
            str(Path(__file__).resolve().parent / "data" / "propertycare.db"),
        )
    )
    service = MaintenanceRequestService(MaintenanceRequestRepository(database_path))

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
            index=priority_options.index(DEFAULT_PRIORITY.value),
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
                    "Submitted (UTC)": request.created_at,
                }
                for request in requests
            ]
        )


if __name__ == "__main__":
    main()
