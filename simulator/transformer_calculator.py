from pathlib import Path
import numpy as np
import pandas as pd

from config.simulation_config import CONFIG


def calculate_transformer_readings(
    df_meters: pd.DataFrame | None = None,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    """
    Aggregates meter consumption per transformer per timestamp and applies
    a realistic loss factor between 3% and 5% to simulate transformer feeder load.
    """
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = output_dir or (base_dir / "output")
    out_dir.mkdir(parents=True, exist_ok=True)

    if df_meters is None:
        meters_csv = out_dir / "meter_readings_30d.csv"
        df_meters = pd.read_csv(meters_csv)

    rng = np.random.default_rng(CONFIG.random_seed + 100)

    grouped = (
        df_meters.groupby(["timestamp", "transformer_id"], as_index=False)
        .agg(
            total_meters_power_w=("power_w", "sum"),
            total_meters_step_kwh=("step_energy_kwh", "sum"),
            total_meters_cumulative_kwh=("cumulative_energy_kwh", "sum"),
        )
        .sort_values(["timestamp", "transformer_id"])
        .reset_index(drop=True)
    )

    loss_rates = rng.uniform(
        low=CONFIG.min_loss_rate,
        high=CONFIG.max_loss_rate,
        size=len(grouped),
    )

    grouped["loss_rate"] = np.round(loss_rates, 4)
    # Supplied energy from transformer = metered sum / (1 - loss_rate) or metered sum * (1 + loss_rate)
    # Using supplied = metered_sum * (1 + loss_rate) so feeder output exceeds sum of customer meters by 3%-5%
    grouped["transformer_power_w"] = np.round(grouped["total_meters_power_w"] * (1.0 + grouped["loss_rate"]), 2)
    grouped["transformer_step_kwh"] = np.round(grouped["total_meters_step_kwh"] * (1.0 + grouped["loss_rate"]), 5)

    grouped["transformer_cumulative_kwh"] = (
        grouped.groupby("transformer_id")["transformer_step_kwh"].cumsum().round(4)
    )

    transformer_csv = out_dir / "transformer_readings_30d.csv"
    grouped.to_csv(transformer_csv, index=False)
    return grouped


if __name__ == "__main__":
    df_tr = calculate_transformer_readings()
    print(f"Generated {len(df_tr)} transformer records.")
    print(df_tr.head(6))