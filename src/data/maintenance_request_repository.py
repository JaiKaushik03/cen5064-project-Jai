"""SQLite storage for validated maintenance requests."""

from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3

from src.domain.maintenance_request import MaintenanceRequest


class MaintenanceRequestRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            # Serialize schema inspection/migration and commit it atomically.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS maintenance_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_unit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Open'
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(maintenance_requests)")
            }
            if "status" not in columns:
                connection.execute(
                    "ALTER TABLE maintenance_requests "
                    "ADD COLUMN status TEXT NOT NULL DEFAULT 'Open'"
                )

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, request: MaintenanceRequest) -> MaintenanceRequest:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO maintenance_requests
                    (property_unit, title, description, priority, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request.property_unit,
                    request.title,
                    request.description,
                    request.priority.value,
                    request.created_at,
                    request.status.value,
                ),
            )
            return replace(request, id=cursor.lastrowid)

    def list_all(self) -> list[MaintenanceRequest]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM maintenance_requests ORDER BY id DESC"
            ).fetchall()
        return [MaintenanceRequest(**dict(row)) for row in rows]

    def get_by_id(self, request_id: int) -> MaintenanceRequest | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM maintenance_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return MaintenanceRequest(**dict(row)) if row is not None else None

    def update_priority(self, request: MaintenanceRequest) -> MaintenanceRequest:
        """Persist only priority, provided the loaded record's status is still current."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE maintenance_requests SET priority = ? WHERE id = ? AND status = ?",
                (request.priority.value, request.id, request.status.value),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    "Request no longer exists or its status changed. Refresh and try again."
                )
        return request
