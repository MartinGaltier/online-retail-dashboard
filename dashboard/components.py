"""Éléments d'interface partagés : filtres, cartes d'indicateurs, exports et messages."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashboard import data
from retail import formatting as fmt
from retail.queries import Filters

UK = "United Kingdom"
ZONES = ["Tous les pays", "Royaume-Uni", "Hors Royaume-Uni", "Choisir des pays"]
FILTER_KEYS = ("f_period", "f_zone", "f_countries", "f_products")


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def sidebar_filters() -> Filters:
    """Affiche les filtres dans la barre latérale et renvoie la sélection courante."""
    first, last = data.coverage()
    options = data.filter_options()
    countries = options[options["dimension"] == "pays"]
    products = options[options["dimension"] == "produit"]
    country_labels = dict(zip(countries["value"], countries["label"], strict=True))
    product_labels = dict(zip(products["value"], products["label"], strict=True))

    sidebar = st.sidebar
    sidebar.header("Filtres")
    period = sidebar.date_input(
        "Période",
        value=(first, last),
        min_value=first,
        max_value=last,
        format="DD/MM/YYYY",
        key="f_period",
        help=f"Les données couvrent du {fmt.date_fr(first)} au {fmt.date_fr(last)}. "
             "La date retenue est celle de la facture ou de l'avoir.",
    )
    if isinstance(period, (tuple, list)) and len(period) == 2:
        start, end = period
    else:
        start = period[0] if isinstance(period, (tuple, list)) and period else first
        end = start
        sidebar.info("Une seule date est choisie : la période couvre ce seul jour.")

    zone = sidebar.radio("Marchés", ZONES, key="f_zone")
    if zone == "Royaume-Uni":
        selected_countries: tuple[str, ...] = (UK,)
    elif zone == "Hors Royaume-Uni":
        selected_countries = tuple(c for c in countries["value"] if c != UK)
    elif zone == "Choisir des pays":
        chosen = sidebar.multiselect(
            "Pays",
            options=countries["value"].tolist(),
            format_func=lambda c: country_labels.get(c, c),
            key="f_countries",
            placeholder="Choisissez un ou plusieurs pays",
        )
        if not chosen:
            sidebar.caption("Aucun pays choisi : tous les pays sont inclus.")
        selected_countries = tuple(sorted(chosen))
    else:
        selected_countries = ()

    chosen_products = sidebar.multiselect(
        "Produits",
        options=products["value"].tolist(),
        format_func=lambda code: f"{product_labels.get(code, code)} ({code})",
        key="f_products",
        placeholder="Tous les produits",
        help="Liste triée par CA des ventes sur toute la période. Tapez un nom ou un code "
             "pour rechercher. Sans sélection, tous les produits sont inclus.",
    )
    sidebar.button("Réinitialiser les filtres", on_click=_reset_filters, width="stretch")
    sidebar.divider()
    sidebar.caption(
        "Données historiques (décembre 2010 – décembre 2011) d'un détaillant en ligne "
        "britannique, publiées par l'UCI. Montants en livres sterling (£). "
        "Ces chiffres ne décrivent pas l'activité actuelle d'une entreprise."
    )
    return Filters(start, end, selected_countries, tuple(sorted(chosen_products)))


def describe_filters(filters: Filters) -> str:
    options = data.filter_options()
    total_countries = int((options["dimension"] == "pays").sum())
    first, last = data.coverage()
    period = f"du {fmt.date_fr(filters.start_date)} au {fmt.date_fr(filters.end_date)}"
    if (filters.start_date, filters.end_date) == (first, last):
        period += " (toute la période)"
    if not filters.countries:
        countries = f"tous les pays ({total_countries})"
    elif filters.countries == (UK,):
        countries = "Royaume-Uni"
    else:
        countries = f"{len(filters.countries)} pays"
    products = (
        "tous les produits" if not filters.stock_codes
        else f"{len(filters.stock_codes)} produit{'s' if len(filters.stock_codes) > 1 else ''}"
    )
    return f"**Sélection :** {period} · {countries} · {products}"


def selection_header(filters: Filters) -> None:
    st.markdown(describe_filters(filters))
    if filters.stock_codes:
        st.caption(
            "Filtre produit actif : les commandes, paniers et clients ne portent que sur les "
            "lignes des produits choisis (une commande compte si elle contient au moins un de "
            "ces produits)."
        )


def stop_if_empty(kpis: dict) -> None:
    """Message compréhensible lorsque la sélection ne contient aucune ligne."""
    if kpis["sales_lines"] == 0 and kpis["cancellation_lines"] == 0:
        st.warning(
            "Aucune vente ni annulation ne correspond à cette sélection. Élargissez la "
            "période, ou retirez des pays ou des produits dans les filtres à gauche.",
            icon=":material/filter_alt_off:",
        )
        st.stop()
    if kpis["sales_lines"] == 0:
        st.info(
            "Cette sélection ne contient que des annulations, aucune vente : les indicateurs "
            "de commandes, de panier et de clients ne sont pas calculables.",
            icon=":material/info:",
        )


def metric_card(label: str, value: str, help_text: str, delta: float | None = None,
                inverse: bool = False) -> None:
    st.metric(
        label,
        value,
        delta=None if delta is None else fmt.signed_percent(delta),
        delta_color="inverse" if inverse else "normal",
        help=help_text,
        border=True,
    )


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    """CSV lisible directement par Excel en français : « ; » et virgule décimale, UTF-8 avec BOM."""
    return frame.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def csv_download(frame: pd.DataFrame, file_name: str, label: str, key: str) -> None:
    st.download_button(
        label,
        data=to_csv_bytes(frame),
        file_name=file_name,
        mime="text/csv",
        icon=":material/download:",
        key=key,
        disabled=frame.empty,
    )


def with_filter_columns(frame: pd.DataFrame, filters: Filters) -> pd.DataFrame:
    """Ajoute la sélection à chaque ligne exportée, pour qu'un fichier reste interprétable seul."""
    return frame.assign(
        filtre_date_debut=filters.start_date.isoformat(),
        filtre_date_fin=filters.end_date.isoformat(),
        filtre_pays=", ".join(filters.countries) or "tous",
        filtre_codes_article=", ".join(filters.stock_codes) or "tous",
    )


def export_name(prefix: str, filters: Filters) -> str:
    def compact(day: date) -> str:
        return day.strftime("%Y%m%d")

    return f"{prefix}_{compact(filters.start_date)}_{compact(filters.end_date)}.csv"
