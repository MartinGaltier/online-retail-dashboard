"""Préparation reproductible du jeu « Online Retail ».

Le traitement ne supprime que les doublons exacts. Toutes les autres lignes sont conservées
et reçoivent un type (`line_type`) qui indique si elles entrent dans les indicateurs.
Chaque règle est consignée avec le nombre de lignes et le montant concernés dans le
rapport de qualité (`reports/data_quality.json` et `.md`).
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from retail import config
from retail.countries import country_fr

SOURCE_COLUMNS = {
    "InvoiceNo": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "line_datetime",
    "UnitPrice": "unit_price",
    "CustomerID": "customer_id",
    "Country": "country",
}

# Codes article qui ne désignent pas une marchandise (relevés lors de l'exploration des données).
NON_PRODUCT_CODES = {
    "POST": "frais_port",
    "DOT": "frais_port",
    "C2": "frais_port",
    "M": "ajustement_manuel",
    "D": "remise",
    "S": "echantillon",
    "AMAZONFEE": "commission_frais",
    "BANK CHARGES": "commission_frais",
    "CRUK": "commission_frais",
    "B": "ajustement_creance",
}
GIFT_VOUCHER_PREFIX = "GIFT_"

STOCK_CATEGORY_LABELS = {
    "produit": "Produit (marchandise)",
    "frais_port": "Frais de port (POST, DOT, C2)",
    "ajustement_manuel": "Saisie manuelle (M)",
    "remise": "Remise (D)",
    "echantillon": "Échantillons (S)",
    "commission_frais": "Commissions et frais (AMAZONFEE, BANK CHARGES, CRUK)",
    "bon_cadeau": "Bons cadeaux (gift_0001_*)",
    "ajustement_creance": "Ajustement de créance douteuse (B)",
}

LINE_TYPE_LABELS = {
    "vente": "Vente de produit",
    "annulation": "Annulation / retour de produit",
    "hors_produit": "Ligne hors produit (port, frais, remises, saisies manuelles)",
    "vente_prix_nul": "Ligne à prix nul",
    "ajustement_stock": "Ajustement de stock (quantité négative, prix nul)",
    "erreur_saisie_annulee": "Vente extrême annulée le jour même et son avoir",
    "ajustement_creance": "Ajustement comptable de créance (facture « A »)",
    "autre": "Non classée",
}
LINE_TYPES_IN_KPIS = ("vente", "annulation")


# --------------------------------------------------------------------------------------
# Acquisition
# --------------------------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_raw(raw_dir: Path = config.RAW_DIR, force: bool = False) -> Path:
    """Télécharge l'archive UCI si nécessaire et vérifie l'empreinte du fichier Excel."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = raw_dir / config.RAW_XLSX_NAME
    if force or not xlsx_path.exists():
        print(f"Téléchargement de {config.RAW_ZIP_URL}")
        with urllib.request.urlopen(config.RAW_ZIP_URL, timeout=120) as response:
            payload = response.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extract(config.RAW_XLSX_NAME, raw_dir)
    checksum = file_sha256(xlsx_path)
    if checksum != config.RAW_XLSX_SHA256:
        raise ValueError(
            f"Empreinte inattendue pour {xlsx_path.name} : {checksum}. "
            "Le fichier source a peut-être changé ; vérifiez-le avant de poursuivre."
        )
    return xlsx_path


def load_raw(xlsx_path: Path) -> pd.DataFrame:
    """Lit le fichier Excel en conservant les identifiants sous forme de texte."""
    return pd.read_excel(
        xlsx_path,
        dtype={"InvoiceNo": str, "StockCode": str, "Description": str, "Country": str},
        engine="openpyxl",
    )


# --------------------------------------------------------------------------------------
# Préparation
# --------------------------------------------------------------------------------------


def _money(value: float) -> float:
    return round(float(value), 2)


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", "\u202f")


def _fmt_number(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\u202f").replace(".", ",")


def _fmt_money(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{_fmt_number(value, decimals)} £"


def _rule(code: str, title: str, finding: str, treatment: str, lines: int, amount: float | None):
    return {
        "code": code,
        "titre": title,
        "constat": finding,
        "traitement": treatment,
        "lignes": int(lines),
        "montant": None if amount is None else _money(amount),
    }


def classify_stock_code(code: str) -> str:
    if code in NON_PRODUCT_CODES:
        return NON_PRODUCT_CODES[code]
    if code.startswith(GIFT_VOUCHER_PREFIX):
        return "bon_cadeau"
    return "produit"


def invoice_kind(invoice_no: pd.Series) -> pd.Series:
    first = invoice_no.str[0]
    return pd.Series(
        np.select(
            [invoice_no.str.fullmatch(r"\d+"), first == "C", first == "A"],
            ["facture", "annulation", "ajustement_creance"],
            default="autre",
        ),
        index=invoice_no.index,
    )


def flag_cancelled_outliers(df: pd.DataFrame, threshold: float) -> tuple[pd.Series, list[dict]]:
    """Repère les ventes d'un montant >= seuil annulées le jour même par un avoir identique.

    Une paire est retenue si l'avoir a le même client, la même date, un montant exactement
    opposé et une heure postérieure ou égale à la vente. Le code article de l'avoir n'est pas
    exigé : certaines corrections sont saisies avec le code « M » (saisie manuelle).
    """
    flagged = pd.Series(False, index=df.index)
    pairs: list[dict] = []
    candidates = df[
        (df["invoice_kind"] == "facture")
        & (df["stock_category"] == "produit")
        & (df["quantity"] > 0)
        & (df["unit_price"] > 0)
        & (df["amount"] >= threshold)
    ]
    credits = df[(df["invoice_kind"] == "annulation") & df["customer_id"].notna()]
    for idx, sale in candidates.sort_values("line_datetime").iterrows():
        if pd.isna(sale["customer_id"]):
            continue
        match = credits[
            (credits["customer_id"] == sale["customer_id"])
            & (credits["line_datetime"].dt.date == sale["line_datetime"].date())
            & (credits["line_datetime"] >= sale["line_datetime"])
            & ((credits["amount"] + sale["amount"]).abs() < 0.005)
            & ~flagged.loc[credits.index]
        ].sort_values("line_datetime")
        if match.empty:
            continue
        credit_idx = match.index[0]
        flagged.loc[[idx, credit_idx]] = True
        delay = (match.loc[credit_idx, "line_datetime"] - sale["line_datetime"]).total_seconds() / 60
        pairs.append(
            {
                "facture_vente": sale["invoice_no"],
                "facture_avoir": match.loc[credit_idx, "invoice_no"],
                "code_article_vente": sale["stock_code"],
                "code_article_avoir": match.loc[credit_idx, "stock_code"],
                "quantite": int(sale["quantity"]),
                "montant": _money(sale["amount"]),
                "delai_minutes": int(round(delay)),
            }
        )
    return flagged, pairs


def canonical_product_names(df: pd.DataFrame) -> pd.Series:
    """Un libellé par code article : le plus fréquent sur les ventes, sinon sur toutes les lignes."""

    def most_frequent(frame: pd.DataFrame) -> pd.Series:
        named = frame.dropna(subset=["description"])
        counts = named.groupby(["stock_code", "description"]).size().reset_index(name="n")
        counts = counts.sort_values(["stock_code", "n", "description"], ascending=[True, False, True])
        return counts.drop_duplicates("stock_code").set_index("stock_code")["description"]

    from_sales = most_frequent(df[df["line_type"] == "vente"])
    from_all = most_frequent(df)
    names = df["stock_code"].map(from_sales).fillna(df["stock_code"].map(from_all))
    return names.fillna("Article " + df["stock_code"] + " (sans libellé)")


def prepare(raw: pd.DataFrame, outlier_threshold: float = config.OUTLIER_AMOUNT_THRESHOLD):
    """Transforme les lignes brutes en lignes typées et produit le rapport de qualité."""
    missing_columns = set(SOURCE_COLUMNS) - set(raw.columns)
    if missing_columns:
        raise ValueError(f"Colonnes absentes du fichier source : {sorted(missing_columns)}")

    df = raw[list(SOURCE_COLUMNS)].rename(columns=SOURCE_COLUMNS).copy()
    df["source_row"] = np.arange(len(df), dtype="int64")
    df["invoice_no"] = df["invoice_no"].astype(str).str.strip()
    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()
    df["line_datetime"] = pd.to_datetime(df["line_datetime"])
    df["amount"] = df["quantity"] * df["unit_price"]

    rules: list[dict] = []
    raw_summary = {
        "lignes": len(df),
        "colonnes": {source: str(raw[source].dtype) for source in SOURCE_COLUMNS},
        "valeurs_manquantes": {
            source: int(raw[source].isna().sum()) for source in SOURCE_COLUMNS
        },
        "premiere_date": df["line_datetime"].min().isoformat(sep=" "),
        "derniere_date": df["line_datetime"].max().isoformat(sep=" "),
        "factures_distinctes": int(df["invoice_no"].nunique()),
        "codes_article_distincts": int(df["stock_code"].nunique()),
        "clients_distincts": int(df["customer_id"].nunique()),
        "pays_distincts": int(df["country"].nunique()),
        "montant_total_brut": _money(df["amount"].sum()),
    }

    numeric_checks = {}
    for column in ("quantity", "unit_price"):
        values = df[column]
        numeric_checks[column] = {
            "min": float(values.min()),
            "p01": float(values.quantile(0.01)),
            "mediane": float(values.median()),
            "p99": float(values.quantile(0.99)),
            "max": float(values.max()),
            "negatifs": int((values < 0).sum()),
            "nuls": int((values == 0).sum()),
        }

    # R1 — Doublons exacts : toutes les colonnes identiques, y compris l'horodatage à la minute.
    duplicated = df.duplicated(subset=list(SOURCE_COLUMNS.values()), keep="first")
    rules.append(
        _rule(
            "R1",
            "Doublons exacts",
            "Lignes identiques sur les 8 colonnes (même facture, article, quantité, prix, "
            "minute, client et pays). Elles sont interprétées comme des saisies répétées.",
            "Une seule occurrence est conservée ; les copies sont supprimées.",
            duplicated.sum(),
            df.loc[duplicated, "amount"].sum(),
        )
    )
    df = df.loc[~duplicated].copy()

    # R2 — Normalisation des codes article et des libellés.
    upper_codes = df["stock_code"].str.upper()
    changed_codes = upper_codes != df["stock_code"]
    df["stock_code"] = upper_codes
    df["description"] = df["description"].astype("string").str.strip().replace("", pd.NA)
    rules.append(
        _rule(
            "R2",
            "Codes article en minuscules",
            "Certains codes existent en minuscules et en majuscules (ex. 85123a / 85123A).",
            "Codes convertis en majuscules ; espaces superflus retirés des libellés.",
            changed_codes.sum(),
            None,
        )
    )

    # R3 — Identifiant client : conservé même s'il manque.
    customer_values = df["customer_id"].dropna()
    if not (customer_values == customer_values.round()).all():
        raise ValueError("Identifiants client non entiers détectés.")
    df["customer_id"] = df["customer_id"].astype("Int64")
    missing_customer = df["customer_id"].isna()
    rules.append(
        _rule(
            "R3",
            "Identifiant client manquant",
            "Une partie des lignes n'a pas d'identifiant client.",
            "Lignes conservées pour les indicateurs de ventes ; exclues seulement des "
            "indicateurs par client (clients identifiés, achats répétés).",
            missing_customer.sum(),
            df.loc[missing_customer, "amount"].sum(),
        )
    )

    # R4 — Type de facture d'après le préfixe du numéro.
    df["invoice_kind"] = invoice_kind(df["invoice_no"])
    if (df["invoice_kind"] == "autre").any():
        raise ValueError("Numéros de facture au format inconnu : à examiner avant de poursuivre.")
    cancellations = df["invoice_kind"] == "annulation"
    positive_in_cancellations = cancellations & (df["quantity"] >= 0)
    if positive_in_cancellations.any():
        raise ValueError("Facture d'annulation avec une quantité positive : règle à revoir.")

    # R5 — Horodatage unique par facture (premier horodatage observé).
    first_time = df.groupby("invoice_no")["line_datetime"].transform("min")
    multi_time = df.groupby("invoice_no")["line_datetime"].transform("nunique") > 1
    spread = (
        df.groupby("invoice_no")["line_datetime"].agg(lambda s: s.max() - s.min()).max()
    )
    df["invoice_datetime"] = first_time
    df["invoice_date"] = df["invoice_datetime"].dt.normalize()
    rules.append(
        _rule(
            "R5",
            "Factures sur plusieurs horodatages",
            f"{int(df.loc[multi_time, 'invoice_no'].nunique())} factures ont des lignes "
            f"saisies à des minutes différentes (écart maximal : "
            f"{int(spread.total_seconds() // 60)} min).",
            "La date retenue pour toutes les lignes d'une facture est son premier "
            "horodatage, afin qu'un filtre de dates ne coupe jamais une commande.",
            multi_time.sum(),
            None,
        )
    )

    # R6 — Catégorie de code article.
    df["stock_category"] = df["stock_code"].map(classify_stock_code)
    non_product = df["stock_category"] != "produit"
    non_product_table = (
        df.loc[non_product]
        .groupby(["stock_category", "stock_code"])
        .agg(lignes=("amount", "size"), montant=("amount", "sum"))
        .reset_index()
        .sort_values(["stock_category", "lignes"], ascending=[True, False])
    )
    rules.append(
        _rule(
            "R6",
            "Codes hors produit",
            "Frais de port, commissions Amazon, frais bancaires, remises, échantillons, "
            "saisies manuelles, bons cadeaux et ajustements de créance utilisent des codes "
            "article spécifiques.",
            "Lignes conservées et signalées ; exclues des indicateurs, qui portent sur les "
            "ventes de produits. Leur total est indiqué séparément.",
            non_product.sum(),
            df.loc[non_product, "amount"].sum(),
        )
    )

    # R7 — Ventes extrêmes annulées le jour même.
    outlier_flag, outlier_pairs = flag_cancelled_outliers(df, outlier_threshold)
    large_sales = (
        (df["invoice_kind"] == "facture")
        & (df["stock_category"] == "produit")
        & (df["quantity"] > 0)
        & (df["unit_price"] > 0)
    )
    p99_sale_amount = df.loc[large_sales, "amount"].quantile(0.99)
    large_sales &= df["amount"] >= outlier_threshold
    rules.append(
        _rule(
            "R7",
            "Ventes extrêmes annulées le jour même",
            f"{int(large_sales.sum())} lignes de vente de produits atteignent au moins "
            f"{_fmt_money(outlier_threshold, 0)}, alors que 99 % des lignes de vente sont "
            f"inférieures à {_fmt_money(p99_sale_amount)}. {len(outlier_pairs)} d'entre elles "
            "sont annulées le jour même par un avoir du même client et du même montant.",
            "Chaque vente concernée et son avoir sont exclus ensemble des indicateurs "
            "(erreurs de saisie corrigées). Leur effet net est nul ; les garder gonflerait "
            "les ventes et les annulations du même montant.",
            outlier_flag.sum(),
            df.loc[outlier_flag & (df["amount"] > 0), "amount"].sum(),
        )
    )

    # R8 — Type de ligne, par ordre de priorité.
    is_invoice = df["invoice_kind"] == "facture"
    df["line_type"] = np.select(
        [
            df["invoice_kind"] == "ajustement_creance",
            outlier_flag,
            non_product,
            cancellations & (df["unit_price"] > 0),
            is_invoice & (df["quantity"] < 0),
            is_invoice & (df["unit_price"] == 0),
            is_invoice & (df["quantity"] > 0) & (df["unit_price"] > 0),
        ],
        [
            "ajustement_creance",
            "erreur_saisie_annulee",
            "hors_produit",
            "annulation",
            "ajustement_stock",
            "vente_prix_nul",
            "vente",
        ],
        default="autre",
    )
    unclassified = df["line_type"] == "autre"
    if unclassified.any():
        raise ValueError(f"{int(unclassified.sum())} lignes non classées : règle à compléter.")

    stock_adjustments = df["line_type"] == "ajustement_stock"
    rules.append(
        _rule(
            "R8",
            "Quantités négatives hors facture d'annulation",
            "Lignes à quantité négative et prix nul, sans client, souvent libellées "
            "« damaged », « check », « thrown away » : mouvements de stock internes.",
            "Conservées et signalées ; sans valeur monétaire, elles n'entrent pas dans les "
            "indicateurs de ventes ni d'annulations.",
            stock_adjustments.sum(),
            df.loc[stock_adjustments, "amount"].sum(),
        )
    )
    zero_price = df["line_type"] == "vente_prix_nul"
    rules.append(
        _rule(
            "R9",
            "Prix unitaires nuls",
            "Lignes de facture à prix nul (articles offerts, corrections, lignes sans "
            "libellé). Leur montant est nul.",
            "Conservées et signalées ; non comptées comme ventes (elles créeraient des "
            "commandes sans chiffre d'affaires).",
            zero_price.sum(),
            0.0,
        )
    )
    bad_debt = df["line_type"] == "ajustement_creance"
    rules.append(
        _rule(
            "R10",
            "Prix négatifs (ajustement de créance)",
            "Les seules valeurs de prix négatives proviennent des factures « A » "
            "libellées « Adjust bad debt ».",
            "Écritures comptables conservées et signalées ; exclues des indicateurs.",
            bad_debt.sum(),
            df.loc[bad_debt, "amount"].sum(),
        )
    )

    df["product_name"] = canonical_product_names(df)
    df["country_fr"] = df["country"].map(country_fr)
    df["in_kpis"] = df["line_type"].isin(LINE_TYPES_IN_KPIS)

    # Couverture temporelle par mois.
    first_day = df["invoice_date"].min()
    last_day = df["invoice_date"].max()
    months = []
    for month, frame in df.groupby(df["invoice_date"].dt.to_period("M")):
        month_start = month.start_time.normalize()
        month_end = month.end_time.normalize()
        complete = month_start >= first_day and month_end <= last_day
        months.append(
            {
                "mois": str(month),
                "premier_jour": frame["invoice_date"].min().date().isoformat(),
                "dernier_jour": frame["invoice_date"].max().date().isoformat(),
                "jours_avec_activite": int(frame["invoice_date"].nunique()),
                "lignes": len(frame),
                "statut": "complet" if complete else "partiel",
            }
        )

    line_types = (
        df.groupby("line_type")
        .agg(
            lignes=("amount", "size"),
            montant=("amount", "sum"),
            lignes_sans_client=("customer_id", lambda s: int(s.isna().sum())),
        )
        .reindex(list(LINE_TYPE_LABELS))
        .dropna(how="all")
        .reset_index()
    )
    line_types["libelle"] = line_types["line_type"].map(LINE_TYPE_LABELS)
    line_types["inclus_dans_indicateurs"] = line_types["line_type"].isin(LINE_TYPES_IN_KPIS)

    sales = df[df["line_type"] == "vente"]
    sales_without_customer = sales["customer_id"].isna()
    multi_country_customers = int((df.groupby("customer_id")["country"].nunique() > 1).sum())

    reconciliation_total = df["amount"].sum()
    reconciliation_by_type = line_types["montant"].sum()

    report = {
        "source": {
            "page": config.SOURCE_PAGE_URL,
            "archive": config.RAW_ZIP_URL,
            "fichier": config.RAW_XLSX_NAME,
            "sha256": config.RAW_XLSX_SHA256,
            "citation": config.SOURCE_CITATION,
            "licence": config.SOURCE_LICENSE,
            "devise": f"Livre sterling ({config.CURRENCY_CODE}), d'après la documentation de la source",
        },
        "brut": raw_summary,
        "controles_numeriques": numeric_checks,
        "regles": rules,
        "paires_extremes_exclues": outlier_pairs,
        "codes_hors_produit": [
            {
                "categorie": STOCK_CATEGORY_LABELS[row.stock_category],
                "code": row.stock_code,
                "lignes": int(row.lignes),
                "montant": _money(row.montant),
            }
            for row in non_product_table.itertuples()
        ],
        "types_de_lignes": [
            {
                "type": row.line_type,
                "libelle": row.libelle,
                "lignes": int(row.lignes),
                "montant": _money(row.montant),
                "lignes_sans_client": int(row.lignes_sans_client),
                "inclus_dans_indicateurs": bool(row.inclus_dans_indicateurs),
            }
            for row in line_types.itertuples()
        ],
        "couverture_temporelle": {
            "premier_jour": first_day.date().isoformat(),
            "dernier_jour": last_day.date().isoformat(),
            "mois": months,
        },
        "clients": {
            "lignes_de_vente_sans_client": int(sales_without_customer.sum()),
            "part_lignes_de_vente_sans_client": float(sales_without_customer.mean()),
            "part_ca_ventes_sans_client": float(
                sales.loc[sales_without_customer, "amount"].sum() / sales["amount"].sum()
            ),
            "clients_avec_plusieurs_pays": multi_country_customers,
        },
        "controle_coherence": {
            "montant_apres_doublons": _money(reconciliation_total),
            "somme_par_type_de_ligne": _money(reconciliation_by_type),
            "ecart": _money(reconciliation_total - reconciliation_by_type),
            "lignes_finales": len(df),
        },
    }

    columns = [
        "source_row",
        "invoice_no",
        "invoice_kind",
        "invoice_datetime",
        "invoice_date",
        "line_datetime",
        "stock_code",
        "stock_category",
        "description",
        "product_name",
        "quantity",
        "unit_price",
        "amount",
        "customer_id",
        "country",
        "country_fr",
        "line_type",
        "in_kpis",
    ]
    lines = df[columns].reset_index(drop=True)
    lines["invoice_date"] = lines["invoice_date"].dt.date
    for column in ("invoice_no", "invoice_kind", "stock_code", "stock_category", "product_name",
                   "country", "country_fr", "line_type"):
        lines[column] = lines[column].astype("string")
    return lines, report


# --------------------------------------------------------------------------------------
# Rapport de qualité
# --------------------------------------------------------------------------------------




def render_quality_markdown(report: dict) -> str:
    raw = report["brut"]
    lines = [
        "# Rapport de qualité des données",
        "",
        "Rapport généré par `python scripts/prepare_data.py` : ne pas modifier à la main.",
        "",
        "## Source",
        "",
        f"- Jeu de données : [Online Retail (UCI)]({report['source']['page']})",
        f"- Citation : {report['source']['citation']}",
        f"- Licence : {report['source']['licence']}",
        f"- Fichier : `{report['source']['fichier']}` (SHA-256 `{report['source']['sha256']}`)",
        f"- Devise : {report['source']['devise']}",
        "",
        "## Données brutes",
        "",
        f"- Lignes : {_fmt_int(raw['lignes'])}",
        f"- Période : du {raw['premiere_date']} au {raw['derniere_date']}",
        f"- Factures distinctes : {_fmt_int(raw['factures_distinctes'])} ; "
        f"codes article : {_fmt_int(raw['codes_article_distincts'])} ; "
        f"clients identifiés : {_fmt_int(raw['clients_distincts'])} ; "
        f"pays : {raw['pays_distincts']}",
        "",
        "| Colonne | Type lu | Valeurs manquantes |",
        "|---|---|---:|",
    ]
    for column, dtype in raw["colonnes"].items():
        lines.append(f"| {column} | {dtype} | {_fmt_int(raw['valeurs_manquantes'][column])} |")

    lines += ["", "## Contrôles numériques (avant traitement)", "",
              "| Variable | Min | 1er centile | Médiane | 99e centile | Max | Négatifs | Nuls |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, stats in report["controles_numeriques"].items():
        values = [_fmt_number(stats[key]) for key in ("min", "p01", "mediane", "p99", "max")]
        lines.append(
            f"| {name} | {' | '.join(values)} | {_fmt_int(stats['negatifs'])} | "
            f"{_fmt_int(stats['nuls'])} |"
        )

    lines += ["", "## Règles de traitement", "",
              "Les règles décrivent des constats qui peuvent se recouvrir (une ligne sans client "
              "peut aussi être une annulation). Le tableau « Types de lignes » plus bas est, lui, "
              "une partition : chaque ligne y figure une seule fois.", "",
              "| Règle | Constat | Traitement | Lignes | Montant |",
              "|---|---|---|---:|---:|"]
    for rule in report["regles"]:
        lines.append(
            f"| **{rule['code']} — {rule['titre']}** | {rule['constat']} | {rule['traitement']} | "
            f"{_fmt_int(rule['lignes'])} | {_fmt_money(rule['montant'])} |"
        )

    lines += ["", "### Ventes extrêmes exclues avec leur avoir (R7)", "",
              "| Facture | Avoir | Article (vente / avoir) | Quantité | Montant | Délai |",
              "|---|---|---|---:|---:|---:|"]
    for pair in report["paires_extremes_exclues"]:
        lines.append(
            f"| {pair['facture_vente']} | {pair['facture_avoir']} | "
            f"{pair['code_article_vente']} / {pair['code_article_avoir']} | "
            f"{_fmt_int(pair['quantite'])} | {_fmt_money(pair['montant'])} | "
            f"{pair['delai_minutes']} min |"
        )

    lines += ["", "### Codes hors produit (R6)", "",
              "| Catégorie | Code | Lignes | Montant |", "|---|---|---:|---:|"]
    for row in report["codes_hors_produit"]:
        lines.append(
            f"| {row['categorie']} | `{row['code']}` | {_fmt_int(row['lignes'])} | "
            f"{_fmt_money(row['montant'])} |"
        )

    lines += ["", "## Résultat : types de lignes", "",
              "| Type | Lignes | Montant | Lignes sans client | Dans les indicateurs |",
              "|---|---:|---:|---:|:---:|"]
    for row in report["types_de_lignes"]:
        lines.append(
            f"| {row['libelle']} | {_fmt_int(row['lignes'])} | {_fmt_money(row['montant'])} | "
            f"{_fmt_int(row['lignes_sans_client'])} | {'oui' if row['inclus_dans_indicateurs'] else 'non'} |"
        )
    check = report["controle_coherence"]
    lines += [
        "",
        f"Contrôle : montant total après suppression des doublons = {_fmt_money(check['montant_apres_doublons'])} ; "
        f"somme des types de lignes = {_fmt_money(check['somme_par_type_de_ligne'])} ; "
        f"écart = {_fmt_money(check['ecart'])}.",
        "",
        "## Clients",
        "",
        f"- Lignes de vente sans identifiant client : "
        f"{_fmt_int(report['clients']['lignes_de_vente_sans_client'])} "
        f"({_fmt_number(report['clients']['part_lignes_de_vente_sans_client'] * 100, 1)} % des lignes de vente).",
        f"- Part du chiffre d'affaires des ventes sans identifiant client : "
        f"{_fmt_number(report['clients']['part_ca_ventes_sans_client'] * 100, 1)} %.",
        f"- Clients associés à plusieurs pays : {report['clients']['clients_avec_plusieurs_pays']} "
        "(un tel client est compté dans chacun de ses pays lorsqu'on filtre par pays).",
        "",
        "## Couverture temporelle",
        "",
        "| Mois | Premier jour | Dernier jour | Jours avec activité | Lignes | Statut |",
        "|---|---|---|---:|---:|---|",
    ]
    for month in report["couverture_temporelle"]["mois"]:
        lines.append(
            f"| {month['mois']} | {month['premier_jour']} | {month['dernier_jour']} | "
            f"{month['jours_avec_activite']} | {_fmt_int(month['lignes'])} | {month['statut']} |"
        )
    lines += [
        "",
        "Un mois est « partiel » lorsque les données ne couvrent pas tous ses jours calendaires.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(lines: pd.DataFrame, report: dict) -> None:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines.to_parquet(config.PROCESSED_FILE, index=False, compression="zstd")
    config.QUALITY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config.QUALITY_MD.write_text(render_quality_markdown(report), encoding="utf-8")
