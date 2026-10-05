"""Règles de préparation appliquées à un petit fichier brut synthétique."""

from datetime import datetime

import pandas as pd
import pytest

from retail.prepare import prepare


def raw_frame(rows):
    return pd.DataFrame(
        rows,
        columns=["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
                 "UnitPrice", "CustomerID", "Country"],
    )


T = datetime(2011, 3, 1, 10, 0)
T_LATER = datetime(2011, 3, 1, 10, 1)
ROWS = [
    # Commande de deux lignes, dont un doublon exact de la première ligne.
    ("500001", "85123a", " WHITE HEART ", 2, T, 2.55, 17850.0, "United Kingdom"),
    ("500001", "85123a", " WHITE HEART ", 2, T, 2.55, 17850.0, "United Kingdom"),
    ("500001", "22423", "CAKESTAND", 1, T_LATER, 12.75, 17850.0, "United Kingdom"),
    # Vente sans identifiant client.
    ("500002", "22423", "CAKESTAND", 3, T, 12.75, None, "France"),
    # Annulation.
    ("C500003", "22423", "CAKESTAND", -1, T, 12.75, 17850.0, "United Kingdom"),
    # Ajustement de stock : quantité négative, prix nul, sans client.
    ("500004", "22423", "damaged", -5, T, 0.0, None, "United Kingdom"),
    # Ligne à prix nul.
    ("500005", "22423", None, 4, T, 0.0, None, "United Kingdom"),
    # Frais de port et commission.
    ("500006", "POST", "POSTAGE", 1, T, 18.0, 12345.0, "France"),
    ("C500007", "AMAZONFEE", "AMAZON FEE", -1, T, 500.0, None, "United Kingdom"),
    # Ajustement de créance.
    ("A500008", "B", "Adjust bad debt", 1, T, -100.0, None, "United Kingdom"),
    # Vente extrême annulée 10 minutes plus tard par le même client.
    ("500009", "23843", "PAPER CRAFT", 10000, T, 2.08, 16446.0, "United Kingdom"),
    ("C500010", "23843", "PAPER CRAFT", -10000, datetime(2011, 3, 1, 10, 10), 2.08, 16446.0,
     "United Kingdom"),
]


@pytest.fixture(scope="module")
def prepared():
    return prepare(raw_frame(ROWS))


def line(lines, invoice, code=None):
    selection = lines[lines["invoice_no"] == invoice]
    if code:
        selection = selection[selection["stock_code"] == code]
    assert len(selection) == 1
    return selection.iloc[0]


def test_exact_duplicates_removed(prepared):
    lines, report = prepared
    assert len(lines) == len(ROWS) - 1
    r1 = next(r for r in report["regles"] if r["code"] == "R1")
    assert r1["lignes"] == 1
    assert r1["montant"] == pytest.approx(5.10)


def test_line_types(prepared):
    lines, _ = prepared
    assert line(lines, "500001", "85123A")["line_type"] == "vente"
    assert line(lines, "500002")["line_type"] == "vente"
    assert line(lines, "C500003")["line_type"] == "annulation"
    assert line(lines, "500004")["line_type"] == "ajustement_stock"
    assert line(lines, "500005")["line_type"] == "vente_prix_nul"
    assert line(lines, "500006")["line_type"] == "hors_produit"
    assert line(lines, "C500007")["line_type"] == "hors_produit"
    assert line(lines, "A500008")["line_type"] == "ajustement_creance"
    assert line(lines, "500009")["line_type"] == "erreur_saisie_annulee"
    assert line(lines, "C500010")["line_type"] == "erreur_saisie_annulee"


def test_negative_quantities_are_kept(prepared):
    lines, _ = prepared
    assert (lines["quantity"] < 0).sum() == 4


def test_missing_customer_kept_as_sale(prepared):
    lines, _ = prepared
    sale = line(lines, "500002")
    assert pd.isna(sale["customer_id"])
    assert bool(sale["in_kpis"])


def test_normalisation(prepared):
    lines, _ = prepared
    assert "85123A" in set(lines["stock_code"])
    assert line(lines, "500001", "85123A")["description"] == "WHITE HEART"
    assert line(lines, "500002")["country_fr"] == "France"
    assert line(lines, "500005")["product_name"] == "CAKESTAND"


def test_invoice_uses_first_timestamp(prepared):
    lines, _ = prepared
    order = lines[lines["invoice_no"] == "500001"]
    assert order["invoice_datetime"].nunique() == 1
    assert order["invoice_datetime"].iloc[0] == pd.Timestamp(T)


def test_outlier_pair_reported(prepared):
    _, report = prepared
    assert len(report["paires_extremes_exclues"]) == 1
    pair = report["paires_extremes_exclues"][0]
    assert (pair["facture_vente"], pair["facture_avoir"]) == ("500009", "C500010")
    assert pair["delai_minutes"] == 10


def test_unmatched_large_sale_stays_a_sale():
    rows = [("600001", "23843", "PAPER CRAFT", 10000, T, 2.08, 16446.0, "United Kingdom")]
    lines, report = prepare(raw_frame(rows))
    assert lines.iloc[0]["line_type"] == "vente"
    assert report["paires_extremes_exclues"] == []


def test_reconciliation_has_no_gap(prepared):
    _, report = prepared
    assert report["controle_coherence"]["ecart"] == pytest.approx(0.0)


def test_missing_source_column_rejected():
    with pytest.raises(ValueError, match="Colonnes absentes"):
        prepare(raw_frame(ROWS).drop(columns=["Country"]))
