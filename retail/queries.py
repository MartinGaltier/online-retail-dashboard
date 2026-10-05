"""Exécution des fichiers SQL avec DuckDB.

Ce module ne dépend pas de Streamlit : il est utilisé tel quel par l'application, les tests
et le script de vérification. Les calculs métier sont dans le dossier `sql/` ; ce module se
contente de charger les données, de passer les filtres en paramètres et de typer les résultats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from retail import config

GRAINS = {"day": "Jour", "week": "Semaine", "month": "Mois"}
_PARAMETER = re.compile(r"\$([a-z_]+)")


@dataclass(frozen=True)
class Filters:
    """Sélection de l'utilisateur. Un tuple vide signifie « pas de filtre » sur la dimension."""

    start_date: date
    end_date: date
    countries: tuple[str, ...] = field(default_factory=tuple)
    stock_codes: tuple[str, ...] = field(default_factory=tuple)

    def as_params(self) -> dict:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "countries": list(self.countries),
            "stock_codes": list(self.stock_codes),
        }

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@lru_cache(maxsize=None)
def load_sql(name: str) -> str:
    return (config.SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")


def _setup(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    con.execute(load_sql("filtered_lines"))
    return con


def connect(parquet_path: Path = config.PROCESSED_FILE) -> duckdb.DuckDBPyConnection:
    """Charge le fichier préparé dans une base DuckDB en mémoire (quelques dizaines de Mo)."""
    if not Path(parquet_path).exists():
        raise FileNotFoundError(
            f"Fichier de données introuvable : {parquet_path}. "
            "Lancez `python scripts/prepare_data.py` pour le générer."
        )
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE lines AS SELECT * FROM read_parquet(?)", [str(parquet_path)])
    return _setup(con)


def connect_frame(lines: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    """Crée une base à partir d'un DataFrame de lignes (utilisé par les tests)."""
    con = duckdb.connect(":memory:")
    con.register("lines_frame", lines)
    con.execute("CREATE TABLE lines AS SELECT * FROM lines_frame")
    con.unregister("lines_frame")
    return _setup(con)


def run(
    con: duckdb.DuckDBPyConnection, name: str, filters: Filters | None = None, **extra
) -> pd.DataFrame:
    """Exécute `sql/<name>.sql` en ne transmettant que les paramètres qu'il utilise."""
    sql = load_sql(name)
    available = {**(filters.as_params() if filters else {}), **extra}
    wanted = set(_PARAMETER.findall(sql))
    missing = wanted - available.keys()
    if missing:
        raise ValueError(f"Paramètres manquants pour {name}.sql : {sorted(missing)}")
    params = {key: available[key] for key in wanted}
    # Un curseur par requête : DuckDB le recommande quand plusieurs fils d'exécution
    # (sessions Streamlit) partagent une même base.
    with con.cursor() as cursor:
        return cursor.execute(sql, params).df()


def _none_if_nan(value):
    return None if pd.isna(value) else value


def kpis(con: duckdb.DuckDBPyConnection, filters: Filters) -> dict:
    # to_dict("records") conserve le type de chaque colonne (entiers pour les comptes).
    row = run(con, "kpis", filters).to_dict("records")[0]
    return {key: _none_if_nan(value) for key, value in row.items()}


def sales_trend(con: duckdb.DuckDBPyConnection, filters: Filters, grain: str) -> pd.DataFrame:
    if grain not in GRAINS:
        raise ValueError(f"Granularité inconnue : {grain}")
    trend = run(con, "sales_trend", filters, grain=grain)
    trend["period_start"] = pd.to_datetime(trend["period_start"])
    return trend


def product_sales(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    return run(con, "product_sales", filters)


def country_sales(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    return run(con, "country_sales", filters)


def customer_frequency(con: duckdb.DuckDBPyConnection, filters: Filters) -> pd.DataFrame:
    return run(con, "customer_frequency", filters)


def filter_options(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return run(con, "filter_options")


def data_coverage(con: duckdb.DuckDBPyConnection) -> tuple[date, date]:
    row = run(con, "data_coverage").iloc[0]
    return pd.Timestamp(row["first_date"]).date(), pd.Timestamp(row["last_date"]).date()


# --------------------------------------------------------------------------------------
# Comparaisons temporelles
# --------------------------------------------------------------------------------------


def previous_period(filters: Filters, first_available: date) -> Filters | None:
    """Période de même durée juste avant la sélection, avec les mêmes autres filtres.

    Renvoie None si cette période commence avant le début des données : la comparaison
    porterait alors sur une période incomplète.
    """
    end = filters.start_date - timedelta(days=1)
    start = end - timedelta(days=filters.days - 1)
    if start < first_available:
        return None
    return Filters(start, end, filters.countries, filters.stock_codes)


def period_end(period_start: pd.Timestamp, grain: str) -> pd.Timestamp:
    if grain == "day":
        return period_start
    if grain == "week":
        return period_start + pd.Timedelta(days=6)
    return period_start + pd.offsets.MonthEnd(0)


def flag_partial_periods(
    trend: pd.DataFrame, grain: str, filters: Filters, coverage: tuple[date, date]
) -> pd.DataFrame:
    """Marque les périodes que la sélection ou les données ne couvrent pas entièrement."""
    lower = pd.Timestamp(max(filters.start_date, coverage[0]))
    upper = pd.Timestamp(min(filters.end_date, coverage[1]))
    trend = trend.copy()
    ends = trend["period_start"].map(lambda start: period_end(start, grain))
    trend["is_partial"] = (trend["period_start"] < lower) | (ends > upper)
    return trend
