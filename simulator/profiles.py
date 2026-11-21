import math
import numpy as np


def get_season_factor(month: int) -> float:
    """
    Returns seasonal consumption multiplier.
    Summer months (June, July, August) have the highest consumption.
    """
    if month in (6, 7, 8):
        return 1.35  # Peak summer
    if month in (12, 1, 2):
        return 1.12  # Winter heating/lighting
    if month in (3, 4, 5):
        return 1.00  # Spring
    return 0.95      # Autumn


def compute_base_power_watts(
    meter_type: str,
    hour: int,
    month: int,
    profile_params: dict,
    rng: np.random.Generator,
) -> float:
    """
    Computes instantaneous active power (in Watts) based on meter type,
    time of day, season, and unique per-meter characteristics.
    """
    season_factor = get_season_factor(month)

    if meter_type == "home":
        base_w = profile_params["base_watts"]
        morning_peak = profile_params["morning_peak_watts"]
        evening_peak = profile_params["evening_peak_watts"]
        morning_center = profile_params["morning_center"]
        evening_center = profile_params["evening_center"]
        personal_scale = profile_params["personal_scale"]

        # Smooth Gaussian-like daily peaks for morning and evening
        morning_wave = morning_peak * math.exp(-0.5 * ((hour - morning_center) / 1.8) ** 2)
        evening_wave = evening_peak * math.exp(-0.5 * ((hour - evening_center) / 2.2) ** 2)

        # Low overnight consumption
        night_factor = 0.55 if 0 <= hour < 6 else 1.0

        noise = rng.normal(loc=0.0, scale=90.0)
        raw_power = ((base_w + morning_wave + evening_wave) * night_factor + noise) * season_factor * personal_scale
        return max(120.0, raw_power)

    if meter_type == "shop":
        open_hour = profile_params["open_hour"]
        close_hour = profile_params["close_hour"]
        active_watts = profile_params["active_watts"]
        standby_watts = profile_params["standby_watts"]
        personal_scale = profile_params["personal_scale"]

        if open_hour <= hour <= close_hour:
            # Gradual ramp during business hours
            mid_day = (open_hour + close_hour) / 2.0
            day_curve = 0.85 + 0.20 * math.cos(math.pi * (hour - mid_day) / max(1.0, (close_hour - open_hour)))
            power = active_watts * day_curve
        else:
            power = standby_watts

        noise = rng.normal(loc=0.0, scale=140.0)
        return max(150.0, (power + noise) * season_factor * personal_scale)

    if meter_type == "factory":
        steady_watts = profile_params["steady_watts"]
        personal_scale = profile_params["personal_scale"]
        # Nearly steady high load with minor operational fluctuation
        fluctuation = rng.normal(loc=0.0, scale=steady_watts * 0.04)
        return max(5000.0, (steady_watts + fluctuation) * season_factor * personal_scale)

    raise ValueError(f"Unknown meter_type: {meter_type}")