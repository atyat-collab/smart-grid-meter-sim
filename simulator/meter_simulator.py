from pathlib import Path
import numpy as np
import pandas as pd

from config.simulation_config import CONFIG
from simulator.profiles import compute_base_power_watts


def build_meter_registry(rng: np.random.Generator) -> list[dict]:
    """
    Creates 50 smart meters:
      - 35 homes ('home')
      - 10 shops ('shop')
      - 5 factories ('factory')
    Assigned across 3 transformers ('TR-01', 'TR-02', 'TR-03'),
    each with unique consumption parameters so no two meters are identical.
    """
    transformers = [f"TR-{i:02d}" for i in range(1, CONFIG.num_transformers + 1)]
    meters: list[dict] = []

    meter_specs = (
        [("home", CONFIG.num_homes)]
        + [("shop", CONFIG.num_shops)]
        + [("factory", CONFIG.num_factories)]
    )

    meter_counter = 1
    for meter_type, count in meter_specs:
        for _ in range(count):
            meter_id = f"MTR-{meter_counter:03d}"
            # Distribute meters across transformers in a balanced round-robin with slight jitter
            transformer_id = transformers[(meter_counter - 1) % len(transformers)]

            if meter_type == "home":
                params = {
                    "base_watts": float(rng.uniform(220.0, 480.0)),
                    "morning_peak_watts": float(rng.uniform(650.0, 1450.0)),
                    "evening_peak_watts": float(rng.uniform(1100.0, 2400.0)),
                    "morning_center": float(rng.uniform(6.5, 8.5)),
                    "evening_center": float(rng.uniform(18.0, 21.5)),
                    "personal_scale": float(rng.uniform(0.75, 1.35)),
                }
            elif meter_type == "shop":
                params = {
                    "open_hour": int(rng.integers(8, 11)),
                    "close_hour": int(rng.integers(20, 23)),
                    "active_watts": float(rng.uniform(1800.0, 4200.0)),
                    "standby_watts": float(rng.uniform(220.0, 550.0)),
                    "personal_scale": float(rng.uniform(0.80, 1.30)),
                }
            elif meter_type == "factory":
                params = {
                    "steady_watts": float(rng.uniform(14000.0, 28000.0)),
                    "personal_scale": float(rng.uniform(0.85, 1.25)),
                }
            else:
                raise ValueError(f"Unsupported meter type: {meter_type}")

            meters.append(
                {
                    "meter_id": meter_id,
                    "meter_type": meter_type,
                    "transformer_id": transformer_id,
                    "params": params,
                    "cumulative_kwh": 0.0,
                }
            )
            meter_counter += 1

    return meters


def simulate_30_days(output_dir: Path | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """
    Runs the 30-day smart meter simulation and saves readings to CSV.
    """
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = output_dir or (base_dir / "output")
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(CONFIG.random_seed)
    meters = build_meter_registry(rng)

    total_steps = int((CONFIG.days * 24 * 60) / CONFIG.interval_minutes)
    dt_hours = CONFIG.interval_minutes / 60.0

    timestamps = pd.date_range(
        start=CONFIG.start_date,
        periods=total_steps,
        freq=f"{CONFIG.interval_minutes}min",
    )

    records: list[dict] = []

    for ts in timestamps:
        hour = int(ts.hour)
        month = int(ts.month)
        timestamp_str = ts.strftime("%Y-%m-%d %H:%M:%S")

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

            records.append(
                {
                    "timestamp": timestamp_str,
                    "meter_id": m["meter_id"],
                    "meter_type": m["meter_type"],
                    "transformer_id": m["transformer_id"],
                    "voltage_v": round(voltage_v, 2),
                    "current_a": round(current_a, 3),
                    "power_w": round(power_w, 2),
                    "step_energy_kwh": round(delta_kwh, 5),
                    "cumulative_energy_kwh": round(m["cumulative_kwh"], 4),
                }
            )

    df_readings = pd.DataFrame(records)
    csv_path = out_dir / "meter_readings_30d.csv"
    df_readings.to_csv(csv_path, index=False)

    return df_readings, meters


if __name__ == "__main__":
    df, meter_list = simulate_30_days()
    print(f"Generated {len(df)} readings across {len(meter_list)} meters.")
    print(df.head(5))