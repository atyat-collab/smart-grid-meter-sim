from datetime import datetime, timezone
import json
from flask import Flask, jsonify, request

from server.database import get_connection, seed_registered_meters

app = Flask(__name__)

REQUIRED_FIELDS = [
    "timestamp",
    "meter_id",
    "meter_type",
    "transformer_id",
    "voltage_v",
    "current_a",
    "power_w",
    "step_energy_kwh",
    "cumulative_energy_kwh",
]


def is_meter_registered(meter_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM registered_meters WHERE meter_id = ?",
        (meter_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def log_rejected_reading(meter_id: str, reason: str, payload: dict) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    received_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO rejected_readings (received_at, meter_id, reason, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (received_at, meter_id or "UNKNOWN", reason, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "smart-grid-receiver"}), 200


@app.route("/api/meters", methods=["GET"])
def list_meters():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT meter_id, meter_type, transformer_id, status
        FROM registered_meters
        ORDER BY meter_id ASC
        """
    )
    meters = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"count": len(meters), "meters": meters}), 200


@app.route("/api/readings", methods=["POST"])
def receive_reading():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        log_rejected_reading("UNKNOWN", "Invalid JSON payload", {})
        return jsonify({"accepted": False, "error": "Invalid JSON payload"}), 400

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        meter_id = str(payload.get("meter_id", "UNKNOWN"))
        reason = f"Missing required fields: {', '.join(missing)}"
        log_rejected_reading(meter_id, reason, payload)
        return jsonify({"accepted": False, "error": reason}), 400

    meter_id = str(payload["meter_id"]).strip()

    # Verify meter registration before saving to database
    if not is_meter_registered(meter_id):
        reason = f"Unregistered meter '{meter_id}' rejected before database insert"
        log_rejected_reading(meter_id, reason, payload)
        return jsonify({"accepted": False, "error": reason}), 403

    status = str(payload.get("status", "NORMAL")).strip() or "NORMAL"

    conn = get_connection()
    cursor = conn.cursor()
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
            str(payload["timestamp"]),
            meter_id,
            str(payload["meter_type"]),
            str(payload["transformer_id"]),
            float(payload["voltage_v"]),
            float(payload["current_a"]),
            float(payload["power_w"]),
            float(payload["step_energy_kwh"]),
            float(payload["cumulative_energy_kwh"]),
            status,
        ),
    )
    inserted_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return (
        jsonify(
            {
                "accepted": True,
                "reading_id": inserted_id,
                "meter_id": meter_id,
                "status": status,
            }
        ),
        201,
    )


@app.route("/api/readings/latest", methods=["GET"])
def latest_reading():
    meter_id = request.args.get("meter_id", "").strip()
    if not meter_id:
        return jsonify({"error": "meter_id query parameter is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.*, m.status AS meter_connection_status
        FROM meter_readings r
        LEFT JOIN registered_meters m ON r.meter_id = m.meter_id
        WHERE r.meter_id = ?
        ORDER BY r.id DESC
        LIMIT 1
        """,
        (meter_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"meter_id": meter_id, "reading": None}), 404

    return jsonify({"meter_id": meter_id, "reading": dict(row)}), 200


if __name__ == "__main__":
    seed_registered_meters()
    print("Starting Smart Grid Receiver API on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=False)