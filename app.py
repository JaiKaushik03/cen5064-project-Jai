"""PropertyCare presentation: collect input, call the service, display saved requests."""

import os
from pathlib import Path

import streamlit as st

from src.data.maintenance_request_repository import MaintenanceRequestRepository
from src.domain.priority import Priority
from src.services.maintenance_request_service import MaintenanceRequestService


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
    with st.form("maintenance_request"):
        property_unit = st.text_input(
            "Property / Unit", placeholder="Oak Court / Unit 2B", key="property_unit"
        )
        title = st.text_input("Issue title", placeholder="Leaking kitchen sink", key="title")
        description = st.text_area("Description", key="description")
        priority = st.selectbox(
            "Priority", [item.value for item in Priority], index=1, key="priority"
        )
        submitted = st.form_submit_button("Submit request")

    if submitted:
        try:
            saved = service.submit(property_unit, title, description, priority)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(f"Request #{saved.id} saved successfully.")

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
