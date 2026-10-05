"""Indicateurs SQL sur le jeu synthétique : chaque valeur attendue est calculée à la main."""

from datetime import date

import pytest

from retail import queries as q
from tests.conftest import FULL, make_lines


def test_kpis_full_period(con):
    k = q.kpis(con, FULL)
    assert k["gross_sales"] == pytest.approx(115.0)  # 30 + 5 + 60 + 20
    assert k["cancellations_amount"] == pytest.approx(5.0)
    assert k["net_sales"] == pytest.approx(110.0)
    assert k["orders"] == 4  # 1001 compte une fois malgré ses 2 lignes
    assert k["sales_lines"] == 5
    assert k["average_order_value"] == pytest.approx(115.0 / 4)
    assert k["cancellation_lines"] == 1
    assert k["cancellation_documents"] == 1
    assert k["cancellations_to_sales_ratio"] == pytest.approx(5 / 115)


def test_multi_line_order_counts_once(con):
    k = q.kpis(con, q.Filters(date(2011, 1, 10), date(2011, 1, 10)))
    assert k["sales_lines"] == 2
    assert k["orders"] == 1
    assert k["average_order_value"] == pytest.approx(30.0)


def test_missing_customers_kept_in_sales_but_not_in_customer_kpis(con):
    k = q.kpis(con, FULL)
    # La vente 1004 sans client compte dans le CA et les commandes...
    assert k["gross_sales"] == pytest.approx(115.0)
    assert k["orders"] == 4
    # ... mais pas dans les clients identifiés (clients 1 et 2).
    assert k["identified_customers"] == 2
    assert k["identified_sales_share"] == pytest.approx(95 / 115)
    assert k["identified_orders_share"] == pytest.approx(3 / 4)


def test_repeat_customer_rate(con):
    k = q.kpis(con, FULL)
    assert k["repeat_customers"] == 1  # client 1 : commandes 1001 et 1002
    assert k["repeat_customer_rate"] == pytest.approx(0.5)


def test_cancellation_is_not_a_repeat_order(con):
    # Sur février, le client 1 n'a qu'un avoir : il n'est ni client identifié ni récurrent.
    k = q.kpis(con, q.Filters(date(2011, 2, 1), date(2011, 2, 28)))
    assert k["identified_customers"] == 1  # client 2 seulement
    assert k["repeat_customers"] == 0


def test_non_product_and_stock_adjustments_excluded(con):
    k = q.kpis(con, q.Filters(date(2011, 2, 20), date(2011, 2, 20)))
    assert k["sales_lines"] == 0
    assert k["cancellation_lines"] == 0
    assert k["gross_sales"] == 0


def test_empty_selection_returns_zeros_and_no_division_by_zero(con):
    k = q.kpis(con, q.Filters(date(2012, 1, 1), date(2012, 1, 31)))
    assert k["gross_sales"] == 0
    assert k["cancellations_amount"] == 0
    assert k["net_sales"] == 0
    assert k["orders"] == 0
    assert k["identified_customers"] == 0
    for ratio in ("average_order_value", "repeat_customer_rate", "cancellations_to_sales_ratio",
                  "identified_sales_share", "identified_orders_share"):
        assert k[ratio] is None


def test_selection_with_only_cancellations(con):
    k = q.kpis(con, q.Filters(date(2011, 2, 15), date(2011, 2, 15)))
    assert k["gross_sales"] == 0
    assert k["cancellations_amount"] == pytest.approx(5.0)
    assert k["net_sales"] == pytest.approx(-5.0)
    assert k["average_order_value"] is None
    assert k["cancellations_to_sales_ratio"] is None


def test_product_filter_applies_to_every_kpi(con):
    k = q.kpis(con, q.Filters(FULL.start_date, FULL.end_date, stock_codes=("B",)))
    assert k["gross_sales"] == pytest.approx(80.0)  # 20 + 60
    assert k["cancellations_amount"] == 0
    assert k["orders"] == 2
    assert k["average_order_value"] == pytest.approx(40.0)
    assert k["identified_customers"] == 2
    assert k["repeat_customer_rate"] == pytest.approx(0.0)


def test_country_filter(con):
    k = q.kpis(con, q.Filters(FULL.start_date, FULL.end_date, countries=("France",)))
    assert k["gross_sales"] == pytest.approx(60.0)
    assert k["orders"] == 1
    assert k["identified_customers"] == 1


def test_net_equals_sales_minus_cancellations_for_many_selections(con):
    selections = [
        FULL,
        q.Filters(date(2011, 1, 1), date(2011, 1, 31)),
        q.Filters(date(2011, 2, 1), date(2011, 2, 28)),
        q.Filters(FULL.start_date, FULL.end_date, countries=("United Kingdom",)),
        q.Filters(FULL.start_date, FULL.end_date, stock_codes=("A",)),
    ]
    for filters in selections:
        k = q.kpis(con, filters)
        assert k["net_sales"] == pytest.approx(k["gross_sales"] - k["cancellations_amount"])


def test_breakdowns_add_up_to_kpis(con):
    k = q.kpis(con, FULL)
    products = q.product_sales(con, FULL)
    countries = q.country_sales(con, FULL)
    trend = q.sales_trend(con, FULL, "month")
    for frame in (products, countries, trend):
        assert frame["gross_sales"].sum() == pytest.approx(k["gross_sales"])
        assert frame["cancellations_amount"].sum() == pytest.approx(k["cancellations_amount"])
        assert frame["net_sales"].sum() == pytest.approx(k["net_sales"])
    assert products["share_of_gross_sales"].sum() == pytest.approx(1.0)
    assert countries["share_of_gross_sales"].sum() == pytest.approx(1.0)


def test_sales_trend_by_month(con):
    trend = q.sales_trend(con, FULL, "month")
    assert trend["gross_sales"].tolist() == pytest.approx([35.0, 80.0])
    assert trend["cancellations_amount"].tolist() == pytest.approx([0.0, 5.0])
    assert trend["orders"].tolist() == [2, 2]


def test_product_sales_details(con):
    products = q.product_sales(con, FULL).set_index("stock_code")
    assert products.loc["A", "gross_sales"] == pytest.approx(35.0)  # 10 + 5 + 20
    assert products.loc["A", "quantity_sold"] == 7
    assert products.loc["A", "cancellations_amount"] == pytest.approx(5.0)
    assert products.loc["A", "quantity_cancelled"] == 1
    assert products.loc["A", "net_sales"] == pytest.approx(30.0)
    assert products.loc["B", "orders"] == 2
    assert "POST" not in products.index


def test_customer_frequency(con):
    freq = q.customer_frequency(con, FULL).set_index("frequency_band")
    assert freq.loc["1 commande", "customers"] == 1
    assert freq.loc["2 commandes", "customers"] == 1
    assert freq.loc["1 commande", "sales_share"] == pytest.approx(60 / 95)
    assert freq["customer_share"].sum() == pytest.approx(1.0)
    # Aucune colonne d'identifiant client n'est renvoyée.
    assert "customer_id" not in freq.reset_index().columns


def test_empty_breakdowns(con):
    empty = q.Filters(date(2012, 1, 1), date(2012, 1, 31))
    assert q.product_sales(con, empty).empty
    assert q.country_sales(con, empty).empty
    assert q.customer_frequency(con, empty).empty
    assert q.sales_trend(con, empty, "week").empty


def test_unknown_grain_rejected(con):
    with pytest.raises(ValueError):
        q.sales_trend(con, FULL, "year")


def test_data_coverage(con):
    assert q.data_coverage(con) == (date(2011, 1, 10), date(2011, 2, 15))


def test_previous_period():
    first = date(2010, 12, 1)
    previous = q.previous_period(q.Filters(date(2011, 3, 1), date(2011, 3, 31), ("France",)), first)
    assert previous == q.Filters(date(2011, 1, 29), date(2011, 2, 28), ("France",))
    assert q.previous_period(q.Filters(date(2010, 12, 1), date(2011, 12, 9)), first) is None


def test_partial_periods_flagged():
    con = q.connect_frame(make_lines())
    trend = q.sales_trend(con, FULL, "month")
    flagged = q.flag_partial_periods(trend, "month", FULL, (date(2010, 12, 1), date(2011, 2, 15)))
    assert flagged["is_partial"].tolist() == [False, True]  # février s'arrête au 15
    narrow = q.Filters(date(2011, 1, 15), date(2011, 2, 28))
    trend = q.sales_trend(con, narrow, "month")
    flagged = q.flag_partial_periods(trend, "month", narrow, (date(2010, 12, 1), date(2011, 12, 9)))
    assert flagged["is_partial"].tolist() == [True, False]  # janvier commence au 15
