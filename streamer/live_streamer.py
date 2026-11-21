from datetime import datetime
from pathlib import Path
import time
import numpy as np
import pandas as pd
import requests

from config.simulation_config import CONFIG
from simulator.meter_simulator import build_meter_registry
from simulator.profiles import compute_base_power_watts

RECEIVER_URL = "http://127.0.0.1:5000/api/readings"


def stream_from_csv(csv_path: Path, limit_rows: int = 50, delay_seconds: float = 0.05) -> None:
    """
    Streams simulated readings from meter_readings_30d.csv to the receiver API.
    """
    df = pd.read_csv(csv_path).head(limit_rows)
    accepted_count = 0
    rejected_count = 0

    for _, row in df.iterrows():
        payload = {
            "timestamp": str(row["timestamp"]),
            "meter_id": str(row["meter_id"]),
            "meter_type": str(row["meter_type"]),
            "transformer_id": str(row["transformer_id"]),
            "voltage_v": float(row["voltage_v"]),
            "current_a": float(row["current_a"]),
            "power_w": float(row["power_w"]),
            "step_energy_kwh": float(row["step_energy_kwh"]),
            "cumulative_energy_kwh": float(row["cumulative_energy_kwh"]),
            "status": "NORMAL",
        }
        try:
            resp = requests.post(RECEIVER_URL, json=payload, timeout=5)
            if resp.status_code == 201:
                accepted_count += 1
            else:
                rejected_count += 1
        except requests.RequestException as exc:
            print(f"Connection error while sending {payload['meter_id']}: {exc}")
            break

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    print(f"CSV stream finished -> Accepted: {accepted_count}, Rejected: {rejected_count}")


def send_unregistered_meter_test() -> None:
    """
    Sends a reading from an unregistered meter (MTR-999) to verify that
    the receiver rejects unregistered meters before saving to the database.
    """
    fake_payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "meter_id": "MTR-999",
        "meter_type": "home",
        "transformer_id": "TR-01",
        "voltage_v": 221.0,
        "current_a": 4.5,
        "power_w": 994.5,
        "step_energy_kwh": 0.9945,
        "cumulative_energy_kwh": 120.5,
        "status": "NORMAL",
    }
    try:
        resp = requests.post(RECEIVER_URL, json=fake_payload, timeout=5)
        print(f"Unregistered meter test (MTR-999) -> Status {resp.status_code}: {resp.json()}")
    except requests.RequestException as exc:
        print(f"Unregistered meter test failed to connect: {exc}")


def stream_live_cycles(cycles: int = 5, interval_seconds: float = 2.0) -> None:
    """
    Generates and streams live readings across all 50 registered meters
    for a number of cycles (useful for live demos and Stage 3 UI updates).
    """
    rng = np.random.default_rng(CONFIG.random_seed + 500)
    meters = build_meter_registry(rng)
    dt_hours = interval_seconds / 3600.0

    for cycle in range(1, cycles + 1):
        now = datetime.now()
        ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
        hour = now.hour
        month = now.month

        sent_ok = 0
        for m in meters:
            power_w = compute_base_power_watts(
                meter_type=m["meter_type"],
                hour=hour,
                month=month,
                profile_params=m["params"],
                rng=rng,
            )
            voltage_v = max(
                195.0,
                float(rng.normal(loc=CONFIG.nominal_voltage_v, scale=CONFIG.voltage_noise_std_v)),
            )
            current_a = power_w / voltage_v
            delta_kwh = (power_w / 1000.0) * dt_hours
            m["cumulative_kwh"] += delta_kwh

            payload = {
                "timestamp": ts_str,
                "meter_id": m["meter_id"],
                "meter_type": m["meter_type"],
                "transformer_id": m["transformer_id"],
                "voltage_v": round(voltage_v, 2),
                "current_a": round(current_a, 3),
                "power_w": round(power_w, 2),
                "step_energy_kwh": round(delta_kwh, 6),
                "cumulative_energy_kwh": round(m["cumulative_kwh"], 4),
                "status": "NORMAL",
            }
            try:
                resp = requests.post(RECEIVER_URL, json=payload, timeout=5)
                if resp.status_code == 201:
                    sent_ok += 1
            except requests.RequestException as exc:
                print(f"Cycle {cycle} stopped due to connection error: {exc}")
                return

        print(f"[Cycle {cycle}/{cycles}] Streamed {sent_ok}/{len(meters)} meters at {ts_str}")
        if cycle < cycles:
            time.sleep(interval_seconds)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    csv_file = base_dir / "output" / "meter_readings_30d.csv"

    send_unregistered_meter_test()
    if csv_file.exists():
        stream_from_csv(csv_file, limit_rows=50, delay_seconds=0.02)
    stream_live_cycles(cycles=3, interval_seconds=2.0)