"""SQLite storage with CRUD for all tables (Scenario 7)."""
import sqlite3

from exceptions import DatabaseOperationError, RecordNotFoundError

# Whitelist of tables/columns. Table and column NAMES come only from here;
# all VALUES go through ? placeholders (parameterized queries).
TABLES = {
    "battery_cells": ["battery_id", "cell_id", "cell_type"],
    "sensor_readings": ["battery_id", "sensor_type", "value", "unit", "timestamp"],
    "cfd_results": ["case_name", "fluid", "reynolds_number", "inlet_temperature",
                    "nanoparticle_concentration", "pressure_drop",
                    "heat_transfer_coefficient", "max_temperature", "notes", "created_at"],
    "predictions": ["battery_id", "model_name", "predicted_temperature", "observed_temperature",
                    "abs_error", "pct_error", "created_at"],
    "maintenance_records": ["battery_id", "alert_type", "description", "timestamp", "status"],
}

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS battery_cells (
        id INTEGER PRIMARY KEY AUTOINCREMENT, battery_id TEXT NOT NULL,
        cell_id TEXT NOT NULL, cell_type TEXT, UNIQUE (battery_id, cell_id))""",
    """CREATE TABLE IF NOT EXISTS sensor_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, battery_id TEXT NOT NULL,
        sensor_type TEXT NOT NULL, value REAL NOT NULL, unit TEXT, timestamp TEXT)""",
    """CREATE TABLE IF NOT EXISTS cfd_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_name TEXT, fluid TEXT,
        reynolds_number REAL, inlet_temperature REAL, nanoparticle_concentration REAL,
        pressure_drop REAL, heat_transfer_coefficient REAL, max_temperature REAL,
        notes TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, battery_id TEXT NOT NULL, model_name TEXT,
        predicted_temperature REAL, observed_temperature REAL, abs_error REAL,
        pct_error REAL, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS maintenance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, battery_id TEXT NOT NULL,
        alert_type TEXT, description TEXT, timestamp TEXT, status TEXT)""",
]


class Database:
    def __init__(self, path="battery_tms.db"):
        try:
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            for stmt in SCHEMA:
                self._run(stmt)
        except sqlite3.Error as exc:
            raise DatabaseOperationError(f"Could not open database: {exc}") from exc

    # ---- helpers -------------------------------------------------------
    def _run(self, sql, params=(), fetch=None):
        """Run one statement with its own cursor (always closed). Commits on success,
        rolls back on failure. Returns (rows, lastrowid, rowcount)."""
        cur = None
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            rows = None
            if fetch == "one":
                rows = cur.fetchone()
            elif fetch == "all":
                rows = cur.fetchall()
            self.conn.commit()
            return rows, cur.lastrowid, cur.rowcount
        except sqlite3.Error as exc:
            self.conn.rollback()
            raise DatabaseOperationError(f"Database operation failed: {exc}") from exc
        finally:
            if cur is not None:
                cur.close()

    @staticmethod
    def _check(table, data=None):
        if table not in TABLES:
            raise DatabaseOperationError(f"Unknown table '{table}'.")
        if data is not None:
            bad = set(data) - set(TABLES[table])
            if bad or not data:
                raise DatabaseOperationError(f"Invalid columns for {table}: {bad or 'none given'}")

    # ---- CRUD ----------------------------------------------------------
    def create(self, table, data):
        """INSERT a row; returns the new id."""
        self._check(table, data)
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        _, rowid, _ = self._run(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
        return rowid

    def read(self, table, record_id):
        """SELECT one row by id; raises RecordNotFoundError if missing."""
        self._check(table)
        row, _, _ = self._run(f"SELECT * FROM {table} WHERE id = ?", (record_id,), fetch="one")
        if row is None:
            raise RecordNotFoundError(f"No record with id {record_id} in {table}.")
        return dict(row)

    def read_all(self, table, battery_id=None, sensor_type=None):
        """SELECT many rows (oldest first), optionally filtered by battery / sensor type."""
        self._check(table)
        clauses, params = [], []
        for column, value in (("battery_id", battery_id), ("sensor_type", sensor_type)):
            if value:
                if column not in TABLES[table]:
                    raise DatabaseOperationError(f"Table {table} has no column {column}.")
                clauses.append(f"{column} = ?")
                params.append(value)
        sql = f"SELECT * FROM {table}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows, _, _ = self._run(sql + " ORDER BY id", tuple(params), fetch="all")
        return [dict(r) for r in rows]

    def update(self, table, record_id, data):
        """UPDATE columns of one row; raises RecordNotFoundError if missing."""
        self._check(table, data)
        sets = ", ".join(f"{col} = ?" for col in data)
        _, _, count = self._run(f"UPDATE {table} SET {sets} WHERE id = ?",
                                tuple(data.values()) + (record_id,))
        if count == 0:
            raise RecordNotFoundError(f"No record with id {record_id} in {table}.")

    def delete(self, table, record_id):
        """DELETE one row; raises RecordNotFoundError if missing."""
        self._check(table)
        _, _, count = self._run(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        if count == 0:
            raise RecordNotFoundError(f"No record with id {record_id} in {table}.")

    # ---- convenience ---------------------------------------------------
    def ensure_battery(self, battery_id, cell_id="C01", cell_type="Li-ion"):
        """Register a battery cell the first time it is seen."""
        existing = [r for r in self.read_all("battery_cells", battery_id=battery_id)
                    if r["cell_id"] == cell_id]
        if not existing:
            self.create("battery_cells", {"battery_id": battery_id, "cell_id": cell_id,
                                          "cell_type": cell_type})

    def close(self):
        self.conn.close()
