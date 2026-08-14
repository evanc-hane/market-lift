import argparse
import json
from pathlib import Path
from typing import Literal, cast

from marketlift.analysis import analyze_experiment
from marketlift.config import ProjectPaths, SimulationConfig
from marketlift.reporting import write_reports
from marketlift.simulation import simulate_marketplace
from marketlift.warehouse import build_warehouse

Scale = Literal["test", "demo", "full"]


def _common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--database", type=Path, default=Path("data/marketlift.duckdb"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    return parser


def run_pipeline(
    database: Path,
    reports: Path,
    scale: Scale = "demo",
    seed: int = 42,
) -> dict[str, object]:
    paths = ProjectPaths(database=database, report_directory=reports)
    paths.prepare()
    simulation_summary = simulate_marketplace(
        paths.database, SimulationConfig.for_scale(scale, seed)
    )
    warehouse_summary = build_warehouse(paths.database)
    results = analyze_experiment(paths.database)
    write_reports(results, paths.report_directory)
    return {
        "simulation": simulation_summary,
        "warehouse": warehouse_summary,
        "decision": results["decision"],
    }


def simulate_main() -> None:
    parser = _common_parser("Generate a semi-synthetic marketplace experiment.")
    parser.add_argument("--scale", choices=("test", "demo", "full"), default="demo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    config = SimulationConfig.for_scale(cast(Scale, args.scale), args.seed)
    print(json.dumps(simulate_marketplace(args.database, config), indent=2))


def build_main() -> None:
    parser = _common_parser("Build DuckDB analytical marts and run quality checks.")
    args = parser.parse_args()
    print(json.dumps(build_warehouse(args.database), indent=2))


def analyze_main() -> None:
    parser = _common_parser("Analyze the switchback experiment and write decision reports.")
    args = parser.parse_args()
    results = analyze_experiment(args.database)
    write_reports(results, args.reports)
    print(json.dumps(results["decision"], indent=2))


def run_main() -> None:
    parser = _common_parser("Run the complete MarketLift decision pipeline.")
    parser.add_argument("--scale", choices=("test", "demo", "full"), default="demo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = run_pipeline(
        args.database,
        args.reports,
        cast(Scale, args.scale),
        args.seed,
    )
    print(json.dumps(summary, indent=2))
