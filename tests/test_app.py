"""Exercise the real Streamlit screen with an isolated SQLite database."""

from pathlib import Path
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    path = tmp_path / "ui.db"
    monkeypatch.setenv("PROPERTYCARE_DB_PATH", str(path))
    return AppTest.from_file(str(APP_PATH), default_timeout=15).run(), path


def test_screen_submit_storage_and_new_session(app):
    screen, path = app
    assert not screen.exception
    assert screen.selectbox[0].options == ["Low", "Medium", "High", "Critical"]
    screen.text_input(key="property_unit").set_value("Oak Court / Unit 2B")
    screen.text_input(key="title").set_value("Leaking kitchen sink")
    screen.text_area(key="description").set_value("Water pools below the cabinet.")
    screen.selectbox(key="priority").set_value("Critical")
    screen.button[0].click().run()
    assert not screen.exception
    assert "saved successfully" in screen.success[0].value
    assert screen.text_input(key="property_unit").value == ""
    assert screen.text_input(key="title").value == ""
    assert screen.text_area(key="description").value == ""
    assert screen.selectbox(key="priority").value == "Medium"
    screen.button[1].click().run()
    assert not screen.exception
    assert "saved successfully" in screen.success[0].value
    assert len(screen.table[0].value) == 1
    assert screen.table[0].value.iloc[0]["Issue title"] == "Leaking kitchen sink"
    assert screen.table[0].value.iloc[0]["Priority"] == "Critical"
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT title, priority FROM maintenance_requests"
        ).fetchall() == [("Leaking kitchen sink", "Critical")]
    restarted = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not restarted.exception
    assert restarted.table[0].value.iloc[0]["Issue title"] == "Leaking kitchen sink"
    restarted.button[1].click().run()
    assert len(restarted.table[0].value) == 1


@pytest.mark.parametrize(
    ("property_unit", "title", "message"),
    [("", "Leak", "Property / Unit"), ("Unit 1", "   ", "Issue title")],
)
def test_screen_rejects_blank_required_fields(app, property_unit, title, message):
    screen, path = app
    screen.text_input(key="property_unit").set_value(property_unit)
    screen.text_input(key="title").set_value(title)
    screen.text_area(key="description").set_value("Keep these entered details.")
    screen.selectbox(key="priority").set_value("Critical")
    screen.button[0].click().run()
    assert not screen.exception
    assert message in screen.error[0].value
    assert screen.text_input(key="property_unit").value == property_unit
    assert screen.text_input(key="title").value == title
    assert screen.text_area(key="description").value == "Keep these entered details."
    assert screen.selectbox(key="priority").value == "Critical"
    assert not screen.success
    assert not screen.table
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM maintenance_requests").fetchone()[0] == 0


def test_screen_marks_required_fields_and_optional_description(app):
    screen, _ = app
    assert screen.text_input(key="property_unit").label == "Property / Unit *"
    assert screen.text_input(key="title").label == "Issue title *"
    assert screen.selectbox(key="priority").label == "Priority *"
    assert screen.text_area(key="description").label == "Description (optional)"
    assert screen.selectbox(key="priority").value == "Medium"


def test_screen_second_submission_uses_new_inputs_after_reset(app):
    screen, path = app
    screen.text_input(key="property_unit").set_value("Unit 1")
    screen.text_input(key="title").set_value("First leak")
    screen.text_area(key="description").set_value("First details")
    screen.selectbox(key="priority").set_value("Critical")
    screen.button[0].click().run()
    assert not screen.exception

    # Submitting the cleared form must not duplicate the saved request.
    screen.button[0].click().run()
    assert not screen.exception
    assert "Property / Unit" in screen.error[0].value
    assert not screen.success
    assert len(screen.table[0].value) == 1

    screen.text_input(key="property_unit").set_value("Unit 2")
    screen.text_input(key="title").set_value("Second leak")
    # Description is optional; priority uses the restored Medium default.
    screen.button[0].click().run()
    assert not screen.exception
    assert not screen.error
    assert screen.success[0].value == "Request #2 saved successfully."
    assert list(screen.table[0].value["Issue title"]) == ["Second leak", "First leak"]
    assert screen.text_input(key="property_unit").value == ""
    assert screen.text_input(key="title").value == ""
    assert screen.text_area(key="description").value == ""
    assert screen.selectbox(key="priority").value == "Medium"
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT title, description, priority FROM maintenance_requests ORDER BY id"
        ).fetchall() == [
            ("First leak", "First details", "Critical"),
            ("Second leak", "", "Medium"),
        ]


def seed_manager_request(path, status="Open"):
    from src.data.maintenance_request_repository import MaintenanceRequestRepository
    from src.domain.maintenance_request import MaintenanceRequest

    return MaintenanceRequestRepository(path).save(
        MaintenanceRequest(
            "Unit 3", "Manager test leak", "Keep these details", "Medium", status=status
        )
    )


def update_priority_button(screen):
    return next(button for button in screen.button if button.label == "Update Priority")


def test_screen_manager_changes_open_priority_and_reloads(app):
    screen, path = app
    saved = seed_manager_request(path)
    screen.run()
    assert screen.selectbox(key="manager_request_id").options == [
        f"#{saved.id}: Manager test leak (Unit 3)"
    ]
    screen.selectbox(key="manager_request_id").set_value(saved.id)
    screen.selectbox(key="manager_priority").set_value("High")
    update_priority_button(screen).click().run()
    assert not screen.exception
    assert not screen.error
    assert screen.success[0].value == f"Request #{saved.id} priority updated to High."
    assert screen.table[0].value.iloc[0]["Priority"] == "High"
    assert screen.table[0].value.iloc[0]["Status"] == "Open"
    assert screen.selectbox(key="manager_request_id").value == saved.id
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT id, property_unit, title, description, priority, created_at, status "
            "FROM maintenance_requests"
        ).fetchone()
    assert row == (
        saved.id, saved.property_unit, saved.title, saved.description,
        "High", saved.created_at, "Open",
    )
    restarted = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not restarted.exception
    assert restarted.table[0].value.iloc[0]["Priority"] == "High"


def test_screen_manager_rejects_completed_change_and_retains_selection(app):
    screen, path = app
    saved = seed_manager_request(path, status="Completed")
    screen.run()
    screen.selectbox(key="manager_request_id").set_value(saved.id)
    screen.selectbox(key="manager_priority").set_value("Critical")
    update_priority_button(screen).click().run()
    assert not screen.exception
    assert "Completed maintenance requests cannot" in screen.error[0].value
    assert not screen.success
    assert screen.selectbox(key="manager_request_id").value == saved.id
    assert screen.selectbox(key="manager_priority").value == "Critical"
    assert screen.table[0].value.iloc[0]["Priority"] == "Medium"
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT priority, status FROM maintenance_requests"
        ).fetchall() == [("Medium", "Completed")]


def test_screen_manager_handles_deleted_selection_and_clears_previous_success(app):
    from contextlib import closing

    screen, path = app
    seed_manager_request(path)
    screen.run()
    screen.selectbox(key="manager_priority").set_value("High")
    update_priority_button(screen).click().run()
    assert screen.success
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("DELETE FROM maintenance_requests")
    update_priority_button(screen).click().run()
    assert not screen.exception
    assert "was not found" in screen.error[0].value
    assert not screen.success
    assert not screen.table
    assert all(button.label != "Update Priority" for button in screen.button)
