"""Mise en forme française, graphiques et export CSV."""

from datetime import date

import pandas as pd
import pytest

from dashboard import charts
from dashboard.components import to_csv_bytes
from retail import formatting as fmt
from retail import queries as q
from tests.conftest import FULL, make_lines

NNBSP = " "


def test_number_formats():
    assert fmt.number(1234567.891, 2) == f"1{NNBSP}234{NNBSP}567,89"
    assert fmt.money(503.92) == f"504{NNBSP}£"
    assert fmt.compact_money(9_962_596) == f"9,96{NNBSP}M£"
    assert fmt.compact_money(230_248) == f"230{NNBSP}k£"
    assert fmt.percent(0.6527) == f"65,3{NNBSP}%"
    assert fmt.signed_percent(0.1) == f"+10,0{NNBSP}%"


def test_missing_values_formatted_as_dash():
    for function in (fmt.number, fmt.money, fmt.compact_money, fmt.percent, fmt.signed_percent):
        assert function(None) == fmt.MISSING
        assert function(float("nan")) == fmt.MISSING


def test_relative_change_handles_zero():
    assert fmt.relative_change(110, 100) == pytest.approx(0.1)
    assert fmt.relative_change(10, 0) is None
    assert fmt.relative_change(None, 5) is None


def test_trend_figures_mark_partial_periods():
    con = q.connect_frame(make_lines())
    trend = q.flag_partial_periods(q.sales_trend(con, FULL, "month"), "month", FULL,
                                   (date(2011, 1, 1), date(2011, 2, 15)))
    sales = charts.sales_trend_figure(trend, "month")
    assert [trace.name for trace in sales.data] == ["CA des ventes", "CA net (après annulations)"]
    assert "(£)" in sales.layout.title.text
    assert len(sales.layout.shapes) == 1  # février est incomplet
    cancellations = charts.cancellations_figure(trend, "month")
    assert list(cancellations.data[0].y) == pytest.approx([0.0, 5.0])


def test_ranking_and_frequency_figures():
    con = q.connect_frame(make_lines())
    products = q.product_sales(con, FULL)
    figure = charts.ranking_figure(products, "product_name", "gross_sales", "Top", "money")
    assert list(figure.data[0].y) == ["Produit A", "Produit B"]  # le plus grand en haut
    frequency = charts.frequency_figure(q.customer_frequency(con, FULL))
    assert len(frequency.data) == 2


def test_csv_export_is_excel_friendly():
    frame = pd.DataFrame({"produit": ["Théière"], "ca_ventes_gbp": [1234.5]})
    content = to_csv_bytes(frame)
    assert content.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 pour Excel
    text = content.decode("utf-8-sig")
    assert text.splitlines() == ["produit;ca_ventes_gbp", "Théière;1234,5"]
