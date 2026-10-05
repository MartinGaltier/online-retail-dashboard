"""Vérification indépendante des totaux à partir du fichier Excel brut.

Ce script n'utilise ni `retail/prepare.py` ni les fichiers SQL : il relit le fichier source et
réapplique les définitions avec pandas, puis compare ses résultats à ceux de l'application
(SQL sur les données préparées). Il écrit `reports/verification.md`.

Usage : python scripts/verify_totals.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retail import config  # noqa: E402
from retail import queries as q  # noqa: E402

# Définitions réécrites ici volontairement, sans importer celles de la préparation.
NON_PRODUCT = {"POST", "DOT", "C2", "M", "D", "S", "AMAZONFEE", "BANK CHARGES", "CRUK", "B"}
# Paires vente / avoir exclues (règle R7), relevées lors de l'exploration du fichier brut.
EXCLUDED_PAIRS = {
    ("541431", "23166"), ("C541433", "23166"),
    ("556444", "22502"), ("C556445", "M"),
    ("581483", "23843"), ("C581484", "23843"),
}


def independent(raw: pd.DataFrame) -> dict:
    df = raw.drop_duplicates().copy()
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str).str.upper()
    df["amount"] = df["Quantity"] * df["UnitPrice"]
    df["month"] = df.groupby("InvoiceNo")["InvoiceDate"].transform("min").dt.to_period("M").astype(str)
    product = ~df["StockCode"].isin(NON_PRODUCT) & ~df["StockCode"].str.startswith("GIFT_")
    excluded = pd.Series(list(zip(df["InvoiceNo"], df["StockCode"], strict=True)), index=df.index).isin(EXCLUDED_PAIRS)
    regular = df["InvoiceNo"].str.fullmatch(r"\d+")
    sales = df[regular & product & ~excluded & (df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
    credits = df[df["InvoiceNo"].str.startswith("C") & product & ~excluded & (df["UnitPrice"] > 0)]
    per_customer = sales.dropna(subset=["CustomerID"]).groupby("CustomerID")["InvoiceNo"].nunique()
    return {
        "totals": {
            "gross_sales": sales["amount"].sum(),
            "cancellations_amount": -credits["amount"].sum(),
            "net_sales": sales["amount"].sum() + credits["amount"].sum(),
            "orders": sales["InvoiceNo"].nunique(),
            "identified_customers": len(per_customer),
            "repeat_customers": int((per_customer >= 2).sum()),
        },
        "by_month": sales.groupby("month")["amount"].sum(),
        "by_country": sales.groupby("Country")["amount"].sum(),
    }


def main() -> None:
    xlsx = config.RAW_DIR / config.RAW_XLSX_NAME
    if not xlsx.exists():
        sys.exit("Fichier brut absent : lancez d'abord `python scripts/prepare_data.py`.")
    raw = pd.read_excel(xlsx, dtype={"InvoiceNo": str, "StockCode": str})
    reference = independent(raw)

    con = q.connect()
    first, last = q.data_coverage(con)
    everything = q.Filters(first, last)
    app = q.kpis(con, everything)
    trend = q.sales_trend(con, everything, "month")
    app_month = trend.set_index(trend["period_start"].dt.to_period("M").astype(str))["gross_sales"]
    app_country = q.country_sales(con, everything).set_index("country")["gross_sales"]

    rows, failures = [], 0
    for key, expected in reference["totals"].items():
        actual = app[key]
        ok = abs(actual - expected) < 0.01
        failures += not ok
        rows.append(f"| {key} | {expected:,.2f} | {actual:,.2f} | {'OK' if ok else 'ÉCART'} |")
    month_gap = (reference["by_month"] - app_month.reindex(reference["by_month"].index)).abs().max()
    country_gap = (reference["by_country"] - app_country.reindex(reference["by_country"].index).fillna(0)).abs().max()
    failures += month_gap >= 0.01
    failures += country_gap >= 0.01

    report = "\n".join([
        "# Vérification indépendante des totaux",
        "",
        "Généré par `python scripts/verify_totals.py`. Le calcul de référence relit le fichier "
        "Excel brut avec pandas, sans utiliser la préparation ni le SQL de l'application.",
        "",
        "| Indicateur | Calcul indépendant | Application (SQL) | Résultat |",
        "|---|---:|---:|:---:|",
        *rows,
        "",
        f"- Écart maximal sur le CA des ventes mensuel ({len(reference['by_month'])} mois) : "
        f"{month_gap:.6f} £",
        f"- Écart maximal sur le CA des ventes par pays ({len(reference['by_country'])} pays) : "
        f"{country_gap:.6f} £",
        "",
        f"**Résultat : {'tous les contrôles concordent' if not failures else f'{failures} écart(s)'}.**",
        "",
    ])
    (config.REPORTS_DIR / "verification.md").write_text(report, encoding="utf-8")
    print(report)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
