"""Jeu de données synthétique dont tous les résultats attendus se calculent à la main."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retail import queries as q  # noqa: E402

COLUMNS = [
    "invoice_no", "invoice_date", "stock_code", "product_name", "quantity", "unit_price",
    "customer_id", "country", "line_type",
]

# Lignes au format du fichier préparé (seules les colonnes lues par le SQL sont utiles).
#  - 1001 : commande de 2 lignes (client 1)            -> 2×5 + 1×20 = 30 £
#  - 1002 : 2e commande du client 1                    -> 5 £
#  - 1003 : client 2 en France                         -> 3×20 = 60 £
#  - 1004 : vente sans identifiant client              -> 4×5 = 20 £
#  - C2001 : avoir du client 1                         -> -5 £
#  - 1005 : frais de port (hors produit)               -> exclu des indicateurs
#  - 1006 : ajustement de stock à prix nul             -> exclu des indicateurs
SYNTHETIC_ROWS = [
    ("1001", date(2011, 1, 10), "A", "Produit A", 2, 5.0, 1, "United Kingdom", "vente"),
    ("1001", date(2011, 1, 10), "B", "Produit B", 1, 20.0, 1, "United Kingdom", "vente"),
    ("1002", date(2011, 1, 20), "A", "Produit A", 1, 5.0, 1, "United Kingdom", "vente"),
    ("1003", date(2011, 2, 5), "B", "Produit B", 3, 20.0, 2, "France", "vente"),
    ("1004", date(2011, 2, 10), "A", "Produit A", 4, 5.0, None, "United Kingdom", "vente"),
    ("C2001", date(2011, 2, 15), "A", "Produit A", -1, 5.0, 1, "United Kingdom", "annulation"),
    ("1005", date(2011, 2, 20), "POST", "POSTAGE", 1, 15.0, 3, "France", "hors_produit"),
    ("1006", date(2011, 2, 20), "A", "Produit A", -10, 0.0, None, "United Kingdom", "ajustement_stock"),
]

FULL = q.Filters(date(2011, 1, 1), date(2011, 2, 28))


def make_lines(rows=SYNTHETIC_ROWS) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["customer_id"] = frame["customer_id"].astype("Int64")
    frame["amount"] = frame["quantity"] * frame["unit_price"]
    frame["country_fr"] = frame["country"].map({"United Kingdom": "Royaume-Uni", "France": "France"})
    return frame


@pytest.fixture
def con():
    connection = q.connect_frame(make_lines())
    yield connection
    connection.close()
