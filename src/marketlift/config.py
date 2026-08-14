from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 42
    city_count: int = 8
    zones_per_city: int = 4
    pre_period_days: int = 28
    experiment_days: int = 28
    mean_sessions_per_zone_hour: float = 20.0
    start_date: str = "2026-01-05"

    def __post_init__(self) -> None:
        if not 2 <= self.city_count <= 8:
            raise ValueError("city_count must be between 2 and 8")
        if self.zones_per_city < 2:
            raise ValueError("zones_per_city must be at least 2")
        if self.pre_period_days < 7 or self.experiment_days < 7:
            raise ValueError("pre-period and experiment windows must each be at least 7 days")
        if self.mean_sessions_per_zone_hour <= 0:
            raise ValueError("mean_sessions_per_zone_hour must be positive")

    @classmethod
    def for_scale(
        cls, scale: Literal["test", "demo", "full"], seed: int = 42
    ) -> "SimulationConfig":
        if scale == "test":
            return cls(
                seed=seed,
                city_count=2,
                zones_per_city=2,
                pre_period_days=7,
                experiment_days=7,
                mean_sessions_per_zone_hour=3,
            )
        if scale == "demo":
            return cls(seed=seed, mean_sessions_per_zone_hour=20)
        if scale == "full":
            return cls(seed=seed, mean_sessions_per_zone_hour=70)
        raise ValueError(f"Unknown scale: {scale}")


@dataclass(frozen=True)
class ProjectPaths:
    database: Path = Path("data/marketlift.duckdb")
    report_directory: Path = Path("reports")

    def prepare(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.report_directory.mkdir(parents=True, exist_ok=True)
