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
    screen.button[0].click().run()
    assert not screen.exception
    assert message in screen.error[0].value
    assert not screen.success
    assert not screen.table
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM maintenance_requests").fetchone()[0] == 0
