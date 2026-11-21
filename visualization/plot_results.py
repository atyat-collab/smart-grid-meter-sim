from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd


def plot_single_day_profiles(df_meters: pd.DataFrame, charts_dir: Path) -> None:
    """
    Plots a full 24-hour day consumption profile (in kW) for one Home,
    one Shop, and one Factory from the first day of simulation.
    """
    df = df_meters.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    first_day = df["timestamp"].dt.date.min()
    day_df = df[df["timestamp"].dt.date == first_day]

    sample_home = day_df[day_df["meter_type"] == "home"]["meter_id"].iloc[0]
    sample_shop = day_df[day_df["meter_type"] == "shop"]["meter_id"].iloc[0]
    sample_factory = day_df[day_df["meter_type"] == "factory"]["meter_id"].iloc[0]

    samples = [
        (sample_home, "Home"),
        (sample_shop, "Shop"),
        (sample_factory, "Factory"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    fig.suptitle(f"24-Hour Power Consumption Profile ({first_day})", fontsize=14, fontweight="bold")

    for ax, (meter_id, label) in zip(axes, samples):
        m_df = day_df[day_df["meter_id"] == meter_id].sort_values("timestamp")
        hours = m_df["timestamp"].dt.strftime("%H:%M")
        power_kw = m_df["power_w"] / 1000.0

        ax.plot(hours, power_kw, marker="o", linewidth=2, markersize=4)
        ax.set_title(f"{label} Meter ({meter_id})", fontsize=11, fontweight="bold")
        ax.set_ylabel("Power (kW)")
        ax.grid(True, linestyle="--", alpha=0.5)

    axes[-1].set_xlabel("Hour of Day")
    plt.xticks(rotation=45)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    out_file = charts_dir / "day_profile_home_shop_factory.png"
    plt.savefig(out_file, dpi=300)
    plt.close(fig)


def plot_transformer_vs_meters(df_transformers: pd.DataFrame, charts_dir: Path) -> None:
    """
    Compares each transformer's power/energy against the sum of its connected meters
    over the 30-day simulation period.
    """
    df = df_transformers.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    transformers = sorted(df["transformer_id"].unique())
    fig, axes = plt.subplots(len(transformers), 1, figsize=(12, 10), sharex=True)
    fig.suptitle("Transformer Feeder Load vs. Sum of Connected Meters (30 Days)", fontsize=14, fontweight="bold")

    if len(transformers) == 1:
        axes = [axes]

    for ax, tr_id in zip(axes, transformers):
        tr_df = df[df["transformer_id"] == tr_id].sort_values("timestamp")

        ax.plot(
            tr_df["timestamp"],
            tr_df["transformer_power_w"] / 1000.0,
            label=f"{tr_id} Output (with 3%-5% loss)",
            linewidth=2,
        )
        ax.plot(
            tr_df["timestamp"],
            tr_df["total_meters_power_w"] / 1000.0,
            label=f"{tr_id} Sum of Connected Meters",
            linewidth=1.5,
            linestyle="--",
        )

        ax.set_title(f"Transformer {tr_id}", fontsize=11, fontweight="bold")
        ax.set_ylabel("Power (kW)")
        ax.legend(loc="upper right")
        ax.grid(True, linestyle="--", alpha=0.5)

    axes[-1].set_xlabel("Date")
    plt.xticks(rotation=30)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    out_file = charts_dir / "transformer_vs_meters_30d.png"
    plt.savefig(out_file, dpi=300)
    plt.close(fig)


def generate_all_plots(output_dir: Path | None = None) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = output_dir or (base_dir / "output")
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    df_meters = pd.read_csv(out_dir / "meter_readings_30d.csv")
    df_transformers = pd.read_csv(out_dir / "transformer_readings_30d.csv")

    plot_single_day_profiles(df_meters, charts_dir)
    plot_transformer_vs_meters(df_transformers, charts_dir)
    print(f"Charts saved successfully to: {charts_dir}")


if __name__ == "__main__":
    generate_all_plots()
