from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    total_meters: int = 50
    num_homes: int = 35
    num_shops: int = 10
    num_factories: int = 5

    num_transformers: int = 3
    days: int = 30
    interval_minutes: int = 60  # 1-hour step -> 24 readings/day -> 720 readings/meter for 30 days
    start_date: str = "2026-06-01 00:00:00"  # Summer start to showcase summer peak clearly

    nominal_voltage_v: float = 220.0
    voltage_noise_std_v: float = 2.5

    # Technical + non-technical loss range on transformer feeder: 3% to 5%
    min_loss_rate: float = 0.03
    max_loss_rate: float = 0.05

    random_seed: int = 42


CONFIG = SimulationConfig()