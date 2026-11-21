from pathlib import Path
import sqlite3
import numpy as np

from config.simulation_config import CONFIG
from simulator.meter_simulator import build_meter_registry


def get_db_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    db_dir = base_dir / "output"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "smart_grid.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Initializes SQLite tables for registered meters, accepted readings,
    rejected attempts, and meter event logs.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS registered_meters (
            meter_id TEXT PRIMARY KEY,
            meter_type TEXT NOT NULL,
            transformer_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NORMAL'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meter_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            meter_id TEXT NOT NULL,
            meter_type TEXT NOT NULL,
            transformer_id TEXT NOT NULL,
            voltage_v REAL NOT NULL,
            current_a REAL NOT NULL,
            power_w REAL NOT NULL,
            step_energy_kwh REAL NOT NULL,
            cumulative_energy_kwh REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'NORMAL',
            FOREIGN KEY (meter_id) REFERENCES registered_meters(meter_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rejected_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            meter_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meter_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            meter_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            FOREIGN KEY (meter_id) REFERENCES registered_meters(meter_id)
        )
        """
    )

    conn.commit()
    conn.close()


def seed_registered_meters() -> int:
    """
    Populates registered_meters with the 50 simulated meters if not already present.
    """
    init_db()
    rng = np.random.default_rng(CONFIG.random_seed)
    meters = build_meter_registry(rng)

    conn = get_connection()
    cursor = conn.cursor()

    for m in meters:
        cursor.execute(
            """
            INSERT OR IGNORE INTO registered_meters (meter_id, meter_type, transformer_id, status)
            VALUES (?, ?, ?, 'NORMAL')
            """,
            (m["meter_id"], m["meter_type"], m["transformer_id"]),
        )

    conn.commit()
    cursor.execute("SELECT COUNT(*) AS cnt FROM registered_meters")
    total = cursor.fetchone()["cnt"]
    conn.close()
    return int(total)


if __name__ == "__main__":
    count = seed_registered_meters()
    print(f"Database initialized. Registered meters count: {count}")