"""SQLite storage for validated maintenance requests."""

from contextlib import closing
from dataclasses import replace, fields
from pathlib import Path
import sqlite3

from src.domain.accounts import normalize_account_key
from src.domain.maintenance_request import MaintenanceRequest, ConcurrentRequestError
from src.services.maintenance_ports import RequestPage


class MaintenanceRequestRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            # Serialize schema inspection/migration and commit it atomically.
            connection.execute("BEGIN IMMEDIATE")
            tables = {row[0].casefold() for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if tables & {"tenant_accounts", "owner_accounts", "contractor_accounts"}:
                raise ValueError("Authentication and maintenance databases must be separate.")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS maintenance_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_unit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Open',
                    tenant_key TEXT
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

            if "tenant_key" not in columns:
                connection.execute("ALTER TABLE maintenance_requests ADD COLUMN tenant_key TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS maintenance_requests_tenant_key "
                               "ON maintenance_requests(tenant_key, id)")

            connection.execute("CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT NOT NULL, UNIQUE(name, address))")
            connection.execute("CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY AUTOINCREMENT, property_id INTEGER NOT NULL REFERENCES properties(id), number TEXT NOT NULL, UNIQUE(property_id, number))")
            additions = {
                "tenant_name": "TEXT", "tenant_email": "TEXT", "tenant_phone": "TEXT",
                "tenant_address": "TEXT", "tenant_unit": "TEXT", "completed_at": "TEXT",
                "assigned_contractor_key": "TEXT", "assigned_contractor_name": "TEXT", "assigned_at": "TEXT", "work_started_at": "TEXT", "scheduled_for": "TEXT",
                "estimated_cost_cents": "INTEGER", "actual_cost_cents": "INTEGER",
                "completion_notes": "TEXT NOT NULL DEFAULT ''", "registered_unit_id": "INTEGER", "photo": "BLOB",
                "revision": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE maintenance_requests ADD COLUMN {name} {declaration}")
            for name, indexed in (("contractor", "assigned_contractor_key, status, id"),
                                   ("status", "status, id"), ("unit", "registered_unit_id, id")):
                connection.execute(f"CREATE INDEX IF NOT EXISTS maintenance_requests_{name} ON maintenance_requests({indexed})")

    @staticmethod
    def _hydrate(row):
        return MaintenanceRequest(**dict(row), _legacy=True)

    @staticmethod
    def _summary_columns():
        names = [item.name for item in fields(MaintenanceRequest)
                 if item.name not in {"photo", "has_photo"} and not item.name.startswith("_")]
        return ', '.join(names) + ', NULL AS photo, photo IS NOT NULL AS has_photo'


    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def save(self, request: MaintenanceRequest) -> MaintenanceRequest:
        names = [item.name for item in fields(request)
                 if item.name not in {"id", "has_photo"} and not item.name.startswith("_")]
        values = [getattr(request, name) for name in names]
        values = [value.value if hasattr(value, "value") else value for value in values]
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                f"INSERT INTO maintenance_requests ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})",
                values,
            )
            return replace(request, id=cursor.lastrowid)

    def transact_update(self, request_id, transform):
        """Serialize read/decision/write; the service supplies the Domain decision."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM maintenance_requests WHERE id = ?", (request_id,)).fetchone()
            if row is None:
                raise ValueError("Maintenance request was not found.")
            request = self._hydrate(row)
            # Only unassigned Open Critical work can block assignment; avoid
            # loading every historical row and every photo into this transaction.
            rows = connection.execute(
                "SELECT " + self._summary_columns() + " FROM maintenance_requests "
                "WHERE status = 'Open' AND priority = 'Critical' AND assigned_contractor_key IS NULL AND id != ?",
                (request_id,),
            ).fetchall()
            requests = [request, *(self._hydrate(item) for item in rows)]
            updated = transform(request, requests)
            names = ("status", "completed_at", "assigned_contractor_key", "assigned_contractor_name", "assigned_at",
                     "estimated_cost_cents", "actual_cost_cents", "completion_notes", "work_started_at", "scheduled_for")
            values = [getattr(updated, name) for name in names]
            values = [value.value if hasattr(value, "value") else value for value in values]
            connection.execute("UPDATE maintenance_requests SET " + ', '.join(name + ' = ?' for name in names)
                               + ", revision = revision + 1 WHERE id = ?", (*values, request_id))
        return replace(updated, revision=request.revision + 1)

    def list_all(self) -> list[MaintenanceRequest]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM maintenance_requests ORDER BY id DESC"
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    def get_by_id(self, request_id: int) -> MaintenanceRequest | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM maintenance_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return self._hydrate(row) if row is not None else None

    def list_for_tenant(self, tenant_key: str) -> list[MaintenanceRequest]:
        tenant_key = normalize_account_key(tenant_key)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM maintenance_requests WHERE tenant_key = ? ORDER BY id DESC",
                (tenant_key,),
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    def get_for_tenant(self, request_id: int, tenant_key: str) -> MaintenanceRequest | None:
        tenant_key = normalize_account_key(tenant_key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM maintenance_requests WHERE id = ? AND tenant_key = ?",
                (request_id, tenant_key),
            ).fetchone()
        return self._hydrate(row) if row is not None else None

    def update_priority(self, request: MaintenanceRequest) -> MaintenanceRequest:
        """Persist only priority, provided the loaded record's status is still current."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE maintenance_requests SET priority = ?, revision = revision + 1 "
                "WHERE id = ? AND status = ? AND revision = ?",
                (request.priority.value, request.id, request.status.value, request.revision),
            )
            if cursor.rowcount != 1:
                raise ConcurrentRequestError(
                    "Request no longer exists or its status changed. Another person may have edited it; reload the selected request and review it."
                )
        return replace(request, revision=request.revision + 1)


    def register_property(self, item):
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute("INSERT INTO properties (name, address) VALUES (?, ?)", (item.name, item.address))
            return replace(item, id=cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("This property is already registered.") from error

    def register_unit(self, item):
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute("INSERT INTO units (property_id, number) VALUES (?, ?)", (item.property_id, item.number))
            return replace(item, id=cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("Choose an existing property and a unit number not already registered there.") from error

    def list_properties(self):
        with closing(self._connect()) as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM properties ORDER BY name, id")]

    def list_units(self):
        with closing(self._connect()) as connection:
            return [dict(row) for row in connection.execute("SELECT u.id, u.property_id, u.number, p.name, p.address FROM units u JOIN properties p ON p.id=u.property_id ORDER BY p.name, u.number")]

    def get_unit(self, unit_id):
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT u.id, u.property_id, u.number, p.name, p.address FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id = ?", (unit_id,)).fetchone()
        return dict(row) if row else None


    def list_for_contractor(self, account_key):
        key = normalize_account_key(account_key)
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM maintenance_requests WHERE assigned_contractor_key = ? ORDER BY id DESC", (key,)).fetchall()
        return [self._hydrate(row) for row in rows]

    def get_for_contractor(self, request_id, account_key):
        key = normalize_account_key(account_key)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM maintenance_requests WHERE id = ? AND assigned_contractor_key = ?",
                                     (request_id, key)).fetchone()
        return self._hydrate(row) if row else None

    def list_page(self, *, limit=25, offset=0, tenant_key=None, contractor_key=None,
                  status=None, unit_id=None, unassigned=False):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError("Choose a valid history page (1–100 requests at a time).")
        clauses, values = [], []
        for name, value in (("tenant_key", tenant_key), ("assigned_contractor_key", contractor_key),
                            ("status", status), ("registered_unit_id", unit_id)):
            if value is not None:
                if name.endswith("_key"):
                    value = normalize_account_key(value)
                clauses.append(name + " = ?")
                values.append(value.value if hasattr(value, 'value') else value)
        if unassigned:
            clauses.append("assigned_contractor_key IS NULL")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            total = connection.execute("SELECT COUNT(*) FROM maintenance_requests" + where, values).fetchone()[0]
            order = "CASE WHEN priority = 'Critical' THEN 0 ELSE 1 END, id DESC" if unassigned else "id DESC"
            rows = connection.execute("SELECT " + self._summary_columns() + " FROM maintenance_requests" + where
                                      + " ORDER BY " + order + " LIMIT ? OFFSET ?", (*values, limit, offset)).fetchall()
        return RequestPage([self._hydrate(row) for row in rows], total)

    def totals(self, *, contractor_key=None, unit_id=None):
        clauses, values = [], []
        if contractor_key is not None:
            clauses.append("assigned_contractor_key = ?")
            values.append(normalize_account_key(contractor_key))
        if unit_id is not None:
            clauses.append("registered_unit_id = ?")
            values.append(unit_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            return dict(connection.execute("SELECT COUNT(*) AS total, "
                "COALESCE(SUM(estimated_cost_cents), 0) AS estimated, "
                "COALESCE(SUM(CASE WHEN status = 'Completed' THEN actual_cost_cents ELSE 0 END), 0) AS actual "
                "FROM maintenance_requests" + where, values).fetchone())
