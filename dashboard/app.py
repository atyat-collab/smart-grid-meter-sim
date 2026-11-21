from datetime import datetime
from pathlib import Path
import numpy as np
from flask import Flask, jsonify, render_template, request

from config.simulation_config import CONFIG
from server.database import get_connection, seed_registered_meters
from simulator.meter_simulator import build_meter_registry
from simulator.profiles import compute_base_power_watts

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

_rng = np.random.default_rng(CONFIG.random_seed + 900)
_meter_profiles = {m["meter_id"]: m["params"] for m in build_meter_registry(_rng)}

EVENT_LABELS = {
    "COVER_OPEN": ("TAMPER_COVER", "Meter terminal cover opened"),
    "MAGNET_DETECTED": ("TAMPER_MAGNET", "Strong magnetic field detected near meter"),
    "BYPASS_50": ("BYPASS_ACTIVE", "Meter bypass simulated: recording 50% consumption only"),
    "POWER_OUTAGE": ("POWER_OUTAGE", "Power outage simulated: supply disconnected"),
    "NORMAL": ("NORMAL", "Meter restored to normal operating state"),
}


def get_latest_reading_for_meter(meter_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM meter_readings
        WHERE meter_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (meter_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_events_for_meter(meter_id: str, limit: int = 15) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, timestamp, meter_id, event_type, description
        FROM meter_events
        WHERE meter_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (meter_id, limit),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def generate_and_store_next_reading(meter_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT meter_id, meter_type, transformer_id, status FROM registered_meters WHERE meter_id = ?",
        (meter_id,),
    )
    meter_row = cursor.fetchone()
    if meter_row is None:
        conn.close()
        raise ValueError(f"Meter {meter_id} not found")

    meter_type = meter_row["meter_type"]
    transformer_id = meter_row["transformer_id"]
    status = meter_row["status"]

    prev = get_latest_reading_for_meter(meter_id)
    prev_cum = float(prev["cumulative_energy_kwh"]) if prev else 0.0

    now = datetime.now()
    ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
    hour = now.hour
    month = now.month

    params = _meter_profiles.get(
        meter_id,
        {
            "base_watts": 350.0,
            "morning_peak_watts": 900.0,
            "evening_peak_watts": 1400.0,
            "morning_center": 7.5,
            "evening_center": 19.5,
            "personal_scale": 1.0,
        },
    )

    base_power_w = compute_base_power_watts(
        meter_type=meter_type,
        hour=hour,
        month=month,
        profile_params=params,
        rng=_rng,
    )

    dt_hours = 5.0 / 3600.0

    if status == "POWER_OUTAGE":
        voltage_v = 0.0
        power_w = 0.0
        current_a = 0.0
        delta_kwh = 0.0
    else:
        voltage_v = max(
            195.0,
            float(_rng.normal(loc=CONFIG.nominal_voltage_v, scale=CONFIG.voltage_noise_std_v)),
        )
        power_w = base_power_w * 0.5 if status == "BYPASS_ACTIVE" else base_power_w
        current_a = power_w / voltage_v if voltage_v > 0 else 0.0
        delta_kwh = (power_w / 1000.0) * dt_hours

    new_cum_kwh = round(prev_cum + delta_kwh, 4)

    cursor.execute(
        """
        INSERT INTO meter_readings (
            timestamp,
            meter_id,
            meter_type,
            transformer_id,
            voltage_v,
            current_a,
            power_w,
            step_energy_kwh,
            cumulative_energy_kwh,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts_str,
            meter_id,
            meter_type,
            transformer_id,
            round(voltage_v, 2),
            round(current_a, 3),
            round(power_w, 2),
            round(delta_kwh, 6),
            new_cum_kwh,
            status,
        ),
    )
    conn.commit()
    conn.close()

    return get_latest_reading_for_meter(meter_id)


@app.route("/")
def index():
    seed_registered_meters()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT meter_id, meter_type, transformer_id, status FROM registered_meters ORDER BY meter_id ASC"
    )
    meters = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template("meter_ui.html", meters=meters)


@app.route("/api/ui/state")
def ui_state():
    meter_id = request.args.get("meter_id", "MTR-001").strip()
    tick = request.args.get("tick", "0").strip() == "1"

    if tick:
        latest = generate_and_store_next_reading(meter_id)
    else:
        latest = get_latest_reading_for_meter(meter_id) or generate_and_store_next_reading(meter_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT meter_id, meter_type, transformer_id, status FROM registered_meters WHERE meter_id = ?",
        (meter_id,),
    )
    meter_row = cursor.fetchone()
    conn.close()

    if meter_row is None:
        return jsonify({"error": f"Meter {meter_id} not found"}), 404

    meter_info = dict(meter_row)
    events = get_recent_events_for_meter(meter_id, limit=15)

    status = meter_info["status"]
    lights = {
        "connection": "ONLINE",
        "power_supply": "OFF" if status == "POWER_OUTAGE" else "ON",
        "tamper": "ALERT" if status in ("TAMPER_COVER", "TAMPER_MAGNET", "BYPASS_ACTIVE") else "CLEAR",
        "security": "COMPROMISED" if status in ("TAMPER_COVER", "TAMPER_MAGNET", "BYPASS_ACTIVE") else "SECURE",
    }

    return jsonify(
        {
            "meter": meter_info,
            "reading": latest,
            "lights": lights,
            "events": events,
        }
    )


@app.route("/api/ui/simulate", methods=["POST"])
def simulate_action():
    data = request.get_json(silent=True) or {}
    meter_id = str(data.get("meter_id", "MTR-001")).strip()
    action = str(data.get("action", "NORMAL")).strip()

    if action not in EVENT_LABELS:
        return jsonify({"error": "Invalid simulation action"}), 400

    new_status, description = EVENT_LABELS[action]
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE registered_meters SET status = ? WHERE meter_id = ?",
        (new_status, meter_id),
    )
    cursor.execute(
        """
        INSERT INTO meter_events (timestamp, meter_id, event_type, description)
        VALUES (?, ?, ?, ?)
        """,
        (ts_str, meter_id, new_status, description),
    )
    conn.commit()
    conn.close()

    latest = generate_and_store_next_reading(meter_id)
    events = get_recent_events_for_meter(meter_id, limit=15)

    return jsonify({"status": new_status, "reading": latest, "events": events}), 200


if __name__ == "__main__":
    seed_registered_meters()
    print(f"Templates folder: {TEMPLATES_DIR}")
    print("Starting Subscriber Meter UI on http://127.0.0.1:5050 ...")
    app.run(host="127.0.0.1", port=5050, debug=True)