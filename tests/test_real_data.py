"""Recoupement sur les données réelles : SQL (DuckDB) contre un calcul pandas indépendant.

Le calcul pandas ci-dessous n'utilise ni les fichiers SQL ni le module `queries` : il relit le
Parquet et réapplique les définitions directement. Si les deux chemins divergent, l'un des deux
est faux.
"""

from datetime import date

import pandas as pd
import pytest

from retail import config
from retail import queries as q

pytestmark = pytest.mark.skipif(
    not config.PROCESSED_FILE.exists(), reason="données préparées absentes"
)

SELECTIONS = [
    q.Filters(date(2010, 12, 1), date(2011, 12, 9)),
    q.Filters(date(2011, 9, 1), date(2011, 11, 30)),
    q.Filters(date(2010, 12, 1), date(2011, 12, 9), countries=("France", "Germany")),
    q.Filters(date(2011, 1, 1), date(2011, 6, 30), stock_codes=("22423", "85123A", "47566")),
    q.Filters(date(2011, 12, 1), date(2011, 12, 9), countries=("United Kingdom",)),
]


@pytest.fixture(scope="module")
def lines():
    return pd.read_parquet(config.PROCESSED_FILE)


@pytest.fixture(scope="module")
def con():
    return q.connect()


def pandas_kpis(lines: pd.DataFrame, filters: q.Filters) -> dict:
    day = pd.to_datetime(lines["invoice_date"])
    mask = day.between(pd.Timestamp(filters.start_date), pd.Timestamp(filters.end_date))
    if filters.countries:
        mask &= lines["country"].isin(filters.countries)
    if filters.stock_codes:
        mask &= lines["stock_code"].isin(filters.stock_codes)
    sales = lines[mask & (lines["line_type"] == "vente")]
    cancellations = lines[mask & (lines["line_type"] == "annulation")]
    per_customer = sales.dropna(subset=["customer_id"]).groupby("customer_id")["invoice_no"].nunique()
    return {
        "gross_sales": (sales["quantity"] * sales["unit_price"]).sum(),
        "cancellations_amount": -(cancellations["quantity"] * cancellations["unit_price"]).sum(),
        "orders": sales["invoice_no"].nunique(),
        "identified_customers": len(per_customer),
        "repeat_customers": int((per_customer >= 2).sum()),
    }


@pytest.mark.parametrize("filters", SELECTIONS, ids=lambda f: f"{f.start_date}-{f.end_date}")
def test_sql_matches_independent_pandas(con, lines, filters):
    sql = q.kpis(con, filters)
    expected = pandas_kpis(lines, filters)
    assert sql["gross_sales"] == pytest.approx(expected["gross_sales"], abs=0.01)
    assert sql["cancellations_amount"] == pytest.approx(expected["cancellations_amount"], abs=0.01)
    assert sql["net_sales"] == pytest.approx(
        expected["gross_sales"] - expected["cancellations_amount"], abs=0.01
    )
    assert sql["orders"] == expected["orders"]
    assert sql["identified_customers"] == expected["identified_customers"]
    assert sql["repeat_customers"] == expected["repeat_customers"]


def test_kpis_lines_are_products_with_valid_signs(lines):
    sales = lines[lines["line_type"] == "vente"]
    cancellations = lines[lines["line_type"] == "annulation"]
    assert (sales["quantity"] > 0).all() and (sales["unit_price"] > 0).all()
    assert (cancellations["quantity"] < 0).all()
    assert cancellations["invoice_no"].str.startswith("C").all()
    assert not sales["invoice_no"].str.startswith(("C", "A")).any()
    assert (lines.loc[lines["in_kpis"], "stock_category"] == "produit").all()


def test_one_date_country_customer_per_invoice(lines):
    per_invoice = lines.groupby("invoice_no").agg(
        dates=("invoice_date", "nunique"),
        countries=("country", "nunique"),
        customers=("customer_id", "nunique"),
    )
    assert (per_invoice["dates"] == 1).all()
    assert (per_invoice["countries"] == 1).all()
    assert (per_invoice["customers"] <= 1).all()


def test_monthly_trend_matches_kpis(con):
    filters = SELECTIONS[0]
    trend = q.sales_trend(con, filters, "month")
    kpis = q.kpis(con, filters)
    assert trend["gross_sales"].sum() == pytest.approx(kpis["gross_sales"], abs=0.01)
    assert trend["cancellations_amount"].sum() == pytest.approx(kpis["cancellations_amount"], abs=0.01)
