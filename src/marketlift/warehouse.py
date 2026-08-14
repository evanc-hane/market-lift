from importlib.resources import files
from pathlib import Path

import duckdb

SQL_FILES = (
    "01_experiment_mart.sql",
    "02_pre_period.sql",
    "03_business_marts.sql",
)


def build_warehouse(database: str | Path) -> dict[str, int]:
    database_path = Path(database)
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    with duckdb.connect(str(database_path)) as connection:
        for sql_file in SQL_FILES:
            sql = files("marketlift.sql").joinpath(sql_file).read_text(encoding="utf-8")
            connection.execute(sql)
        checks = {
            "duplicate_assignments": """
                SELECT COUNT(*) FROM (
                    SELECT assignment_id FROM fct_experiment_assignments
                    GROUP BY assignment_id HAVING COUNT(*) > 1
                )
            """,
            "orphan_sessions": """
                SELECT COUNT(*) FROM fct_sessions s
                LEFT JOIN dim_zone z USING (zone_id)
                WHERE z.zone_id IS NULL
            """,
            "missing_experiment_units": """
                SELECT COUNT(*) FROM mart_experiment_cluster_hour WHERE sessions = 0
            """,
            "invalid_treatment": """
                SELECT COUNT(*) FROM fct_experiment_assignments
                WHERE treatment_assignment NOT IN (0, 1)
            """,
        }
        failures = {
            name: int(connection.execute(query).fetchone()[0]) for name, query in checks.items()
        }
        failed = {name: count for name, count in failures.items() if count > 0}
        if failed:
            raise ValueError(f"Warehouse quality checks failed: {failed}")
        tables = (
            "mart_experiment_cluster_hour",
            "mart_pre_experiment_covariates",
            "mart_customer_funnel_daily",
            "mart_city_unit_economics",
            "mart_experiment_guardrails",
        )
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
