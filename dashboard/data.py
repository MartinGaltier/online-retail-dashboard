"""Accès aux données depuis Streamlit, avec mise en cache.

- La base DuckDB (lecture du Parquet) est créée une seule fois par processus
  (`st.cache_resource`) et partagée par toutes les sessions.
- Les résultats des requêtes sont mis en cache par combinaison de filtres
  (`st.cache_data`) : revenir à une sélection déjà vue ne relance aucun calcul.
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd
import streamlit as st

from retail import config, insights
from retail import queries as q


def _filters_key(filters: q.Filters) -> tuple:
    return (filters.start_date, filters.end_date, filters.countries, filters.stock_codes)


_cache = st.cache_data(show_spinner=False, max_entries=200, hash_funcs={q.Filters: _filters_key})


@st.cache_resource(show_spinner="Chargement des données…")
def connection() -> duckdb.DuckDBPyConnection:
    return q.connect()


@st.cache_data(show_spinner=False)
def coverage():
    return q.data_coverage(connection())


@st.cache_data(show_spinner=False)
def filter_options() -> pd.DataFrame:
    return q.filter_options(connection())


@_cache
def kpis(filters: q.Filters) -> dict:
    return q.kpis(connection(), filters)


@_cache
def sales_trend(filters: q.Filters, grain: str) -> pd.DataFrame:
    trend = q.sales_trend(connection(), filters, grain)
    return q.flag_partial_periods(trend, grain, filters, coverage())


@_cache
def product_sales(filters: q.Filters) -> pd.DataFrame:
    return q.product_sales(connection(), filters)


@_cache
def country_sales(filters: q.Filters) -> pd.DataFrame:
    return q.country_sales(connection(), filters)


@_cache
def customer_frequency(filters: q.Filters) -> pd.DataFrame:
    return q.customer_frequency(connection(), filters)


@st.cache_data(show_spinner=False)
def global_facts() -> dict:
    return insights.global_facts(connection())


@st.cache_data(show_spinner=False)
def quality_report() -> dict:
    return json.loads(config.QUALITY_JSON.read_text(encoding="utf-8"))
