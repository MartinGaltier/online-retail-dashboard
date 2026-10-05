"""Chemins, source des données et constantes partagées par la préparation et l'application."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SQL_DIR = ROOT_DIR / "sql"
REPORTS_DIR = ROOT_DIR / "reports"

# Source officielle (UCI Machine Learning Repository, licence CC BY 4.0).
SOURCE_PAGE_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"
RAW_ZIP_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
RAW_XLSX_NAME = "Online Retail.xlsx"
# Empreinte du fichier Excel publié par l'UCI : garantit que l'on traite bien la même version.
RAW_XLSX_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
SOURCE_CITATION = (
    "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. "
    "https://doi.org/10.24432/C5BW33"
)
SOURCE_LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
SOURCE_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

PROCESSED_FILE = PROCESSED_DIR / "online_retail_lines.parquet"
QUALITY_JSON = REPORTS_DIR / "data_quality.json"
QUALITY_MD = REPORTS_DIR / "data_quality.md"

# Les prix unitaires sont exprimés en livres sterling selon la documentation de la source.
CURRENCY_CODE = "GBP"
CURRENCY_SYMBOL = "£"

# Une vente dont le montant atteint ce seuil est examinée individuellement (voir prepare.py, règle R7).
OUTLIER_AMOUNT_THRESHOLD = 10_000.0
