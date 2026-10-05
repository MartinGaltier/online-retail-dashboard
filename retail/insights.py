"""Observations et recommandations sur l'ensemble du jeu de données (sans filtre).

Les chiffres cités sont recalculés à partir des requêtes SQL à chaque démarrage : le texte
ne contient aucun nombre saisi à la main.
"""

from __future__ import annotations

import duckdb

from retail import formatting as fmt
from retail import queries as q


def global_facts(con: duckdb.DuckDBPyConnection) -> dict:
    first, last = q.data_coverage(con)
    everything = q.Filters(first, last)
    kpis = q.kpis(con, everything)

    trend = q.flag_partial_periods(q.sales_trend(con, everything, "month"), "month", everything, (first, last))
    complete = trend[~trend["is_partial"]]
    top_months = complete.nlargest(3, "gross_sales").sort_values("period_start")
    median_month = complete["gross_sales"].median()
    peak = complete.loc[complete["gross_sales"].idxmax()]

    countries = q.country_sales(con, everything)
    domestic = countries[countries["country"] == "United Kingdom"].iloc[0]
    abroad = countries[countries["country"] != "United Kingdom"]
    top_abroad = abroad.head(4)

    frequency = q.customer_frequency(con, everything)
    most_loyal = frequency[frequency["band_order"] == frequency["band_order"].max()].iloc[0]
    single = frequency[frequency["band_order"] == 1].iloc[0]

    products = q.product_sales(con, everything)
    selling = products[products["gross_sales"] > 0]
    top_fifth = selling.head(max(1, round(len(selling) * 0.2)))

    return {
        "first_date": first,
        "last_date": last,
        "kpis": kpis,
        "partial_months": [fmt.month_fr(p) for p in trend.loc[trend["is_partial"], "period_start"]],
        "complete_months": len(complete),
        "top_months": [fmt.month_fr(p) for p in top_months["period_start"]],
        "top_months_share": top_months["gross_sales"].sum() / kpis["gross_sales"],
        "peak_month": fmt.month_fr(peak["period_start"]),
        "peak_month_sales": peak["gross_sales"],
        "median_month_sales": median_month,
        "peak_to_median": peak["gross_sales"] / median_month,
        "uk_share": domestic["share_of_gross_sales"],
        "abroad_countries": len(abroad[abroad["gross_sales"] > 0]),
        "top_abroad": [
            {
                "country": row.country_fr,
                "share": row.share_of_gross_sales,
                "customers": int(row.identified_customers),
            }
            for row in top_abroad.itertuples()
        ],
        "repeat_rate": kpis["repeat_customer_rate"],
        "identified_customers": kpis["identified_customers"],
        "loyal_band": most_loyal["frequency_band"],
        "loyal_customer_share": most_loyal["customer_share"],
        "loyal_sales_share": most_loyal["sales_share"],
        "single_order_customer_share": single["customer_share"],
        "unidentified_sales_share": 1 - kpis["identified_sales_share"],
        "products_selling": len(selling),
        "top_fifth_products_share": top_fifth["gross_sales"].sum() / selling["gross_sales"].sum(),
    }


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} et {items[-1]}"


def observations(facts: dict) -> list[dict]:
    """Trois faits observés, chacun accompagné de sa limite d'interprétation."""
    abroad = ", ".join(
        f"{item['country']} ({fmt.percent(item['share'])}, {item['customers']} clients identifiés)"
        for item in facts["top_abroad"]
    )
    return [
        {
            "titre": "Une fin d'année 2011 nettement plus forte",
            "fait": (
                f"Les trois meilleurs mois complets sont {_join(facts['top_months'])} : ils "
                f"représentent {fmt.percent(facts['top_months_share'])} du CA des ventes de la "
                f"période. Le pic, {facts['peak_month']}, atteint {fmt.money(facts['peak_month_sales'])}, "
                f"soit {fmt.number(facts['peak_to_median'], 1)} fois le mois médian "
                f"({fmt.money(facts['median_month_sales'])})."
            ),
            "limite": (
                "Les données ne couvrent qu'une seule période septembre-novembre : elles ne permettent pas "
                "de dire si ce pic est saisonnier et se répète, ou s'il traduit une croissance."
            ),
        },
        {
            "titre": "Un chiffre d'affaires porté par des clients récurrents",
            "fait": (
                f"{fmt.percent(facts['repeat_rate'])} des {fmt.number(facts['identified_customers'])} "
                f"clients identifiés ont passé au moins deux commandes. Les clients à "
                f"{facts['loyal_band']} représentent {fmt.percent(facts['loyal_customer_share'])} "
                f"des clients identifiés mais {fmt.percent(facts['loyal_sales_share'])} de leur CA "
                "des ventes."
            ),
            "limite": (
                f"{fmt.percent(facts['unidentified_sales_share'])} du CA des ventes n'a pas "
                "d'identifiant client et n'entre pas dans ce calcul. La période d'un an ne montre "
                "pas les achats antérieurs à décembre 2010."
            ),
        },
        {
            "titre": "Un marché très concentré sur le Royaume-Uni",
            "fait": (
                f"Le Royaume-Uni réalise {fmt.percent(facts['uk_share'])} du CA des ventes. "
                f"Les {facts['abroad_countries']} autres pays ou zones déclarés se partagent le reste ; "
                f"les quatre premiers sont : {abroad}."
            ),
            "limite": (
                "Le pays est celui du client déclaré dans la facture. Quelques clients étrangers "
                "importants suffisent à faire varier fortement le classement des pays."
            ),
        },
    ]


def recommendations(facts: dict) -> list[dict]:
    """Recommandations prudentes : chacune est une hypothèse à tester, pas une conclusion."""
    return [
        {
            "titre": "Préparer la fin d'année dès la fin de l'été",
            "action": (
                "Sécuriser les stocks et les capacités d'expédition des produits les plus vendus "
                "avant septembre, et planifier les actions commerciales sur cette période."
            ),
            "hypothese": (
                "Le pic observé en 2011 se reproduit chaque année. À vérifier avec l'historique "
                "des années précédentes avant d'engager des achats importants."
            ),
        },
        {
            "titre": "Suivre de près les clients les plus réguliers",
            "action": (
                f"Mettre en place un suivi des clients à {facts['loyal_band']} (alerte en cas "
                "de baisse de fréquence, interlocuteur dédié)."
            ),
            "hypothese": (
                "Une baisse d'activité de quelques clients réguliers pèserait fortement sur le CA. "
                "À tester en mesurant l'évolution de leur fréquence d'achat sur plusieurs mois."
            ),
        },
        {
            "titre": "Tester un développement ciblé hors Royaume-Uni",
            "action": (
                "Lancer une action de prospection limitée dans un pays européen déjà actif "
                "(par exemple l'un des quatre premiers marchés étrangers), avec un objectif "
                "mesurable et un groupe de comparaison."
            ),
            "hypothese": (
                "Ces marchés ont un potentiel au-delà des quelques clients actuels. Les données ne "
                "contiennent ni la taille des marchés ni les coûts logistiques : la rentabilité "
                "reste à évaluer."
            ),
        },
    ]
