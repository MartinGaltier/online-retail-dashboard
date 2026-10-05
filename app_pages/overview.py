"""Page 1 — Vue d'ensemble : indicateurs clés et évolution des ventes."""

import pandas as pd
import streamlit as st

from dashboard import charts, components, data
from retail import formatting as fmt
from retail import insights
from retail.queries import GRAINS, previous_period

filters = st.session_state["filters"]

st.title("Vue d'ensemble des ventes")
st.markdown(
    "Ce tableau de bord résume l'activité d'un détaillant en ligne britannique (articles "
    "cadeaux, clientèle en grande partie professionnelle) entre décembre 2010 et décembre 2011. "
    "Les montants sont en livres sterling (£) et portent sur les **ventes de produits** : "
    "frais de port, commissions et ajustements comptables sont exclus "
    "(voir la page *Méthodologie*)."
)
components.selection_header(filters)

kpis = data.kpis(filters)
components.stop_if_empty(kpis)

first_available, _ = data.coverage()
previous = previous_period(filters, first_available)
before = data.kpis(previous) if previous else None


def change(key: str):
    return fmt.relative_change(kpis[key], before[key]) if before else None


st.subheader("Indicateurs clés")
row1 = st.columns(4)
with row1[0]:
    components.metric_card(
        "CA des ventes", fmt.compact_money(kpis["gross_sales"]),
        "Somme de quantité × prix unitaire des lignes de vente de produits.",
        change("gross_sales"),
    )
with row1[1]:
    components.metric_card(
        "Annulations et retours", fmt.compact_money(kpis["cancellations_amount"]),
        "Montant des avoirs (factures commençant par « C ») enregistrés sur la période, quelle "
        "que soit la date de la commande d'origine, que les données ne permettent pas de retrouver.",
        change("cancellations_amount"), inverse=True,
    )
with row1[2]:
    components.metric_card(
        "CA net", fmt.compact_money(kpis["net_sales"]),
        "CA des ventes moins annulations et retours enregistrés sur la même période.",
        change("net_sales"),
    )
with row1[3]:
    components.metric_card(
        "Commandes de vente", fmt.number(kpis["orders"]),
        "Nombre de factures distinctes comportant au moins une ligne de vente. Une commande "
        "de plusieurs lignes compte une seule fois.",
        change("orders"),
    )

row2 = st.columns(4)
with row2[0]:
    components.metric_card(
        "Panier moyen", fmt.money(kpis["average_order_value"]),
        "CA des ventes ÷ nombre de commandes de vente (hors frais de port).",
        change("average_order_value"),
    )
with row2[1]:
    components.metric_card(
        "Clients identifiés", fmt.number(kpis["identified_customers"]),
        "Clients distincts ayant au moins une commande de vente. Les ventes sans identifiant "
        "client ne sont pas comptées ici.",
        change("identified_customers"),
    )
with row2[2]:
    components.metric_card(
        "Clients récurrents", fmt.percent(kpis["repeat_customer_rate"]),
        "Part des clients identifiés ayant passé au moins 2 commandes distinctes dans la "
        "sélection. Dépend de la durée de la période choisie.",
        change("repeat_customer_rate"),
    )
with row2[3]:
    components.metric_card(
        "Annulations / CA des ventes", fmt.percent(kpis["cancellations_to_sales_ratio"]),
        "Montant des annulations rapporté au CA des ventes de la même période, en valeur. "
        "Ce n'est pas une part de commandes retournées.",
        change("cancellations_to_sales_ratio"), inverse=True,
    )

notes = []
if before:
    notes.append(
        f"Variations calculées par rapport à la période précédente de même durée "
        f"({fmt.date_fr(previous.start_date)} – {fmt.date_fr(previous.end_date)}), avec les mêmes "
        "pays et produits."
    )
else:
    notes.append(
        "Pas de variation affichée : la période précédente de même durée commencerait avant "
        f"le début des données ({fmt.date_fr(first_available)})."
    )
notes.append(
    f"Les indicateurs clients portent sur {fmt.percent(kpis['identified_sales_share'])} du CA des "
    f"ventes et {fmt.percent(kpis['identified_orders_share'])} des commandes, qui ont un "
    "identifiant client."
)
st.caption(" ".join(notes))

st.subheader("Évolution des ventes")
grain = st.segmented_control(
    "Regrouper par", options=list(GRAINS), format_func=GRAINS.get, default="month",
    key="grain", required=True,
)
grain = grain or "month"
trend = data.sales_trend(filters, grain)
if trend.empty:
    st.info("Aucune donnée à afficher pour cette période.")
else:
    st.plotly_chart(charts.sales_trend_figure(trend, grain), width="stretch",
                    config={"displaylogo": False})
    if trend["is_partial"].any():
        st.caption(
            "Les zones grisées marquent des périodes que la sélection ou les données ne "
            "couvrent qu'en partie (par exemple décembre 2011, qui s'arrête au 9) : ne les "
            "comparez pas directement aux autres."
        )
    st.plotly_chart(charts.cancellations_figure(trend, grain), width="stretch",
                    config={"displaylogo": False})

    export = trend.rename(columns={
        "period_start": "debut_periode",
        "gross_sales": "ca_ventes_gbp",
        "cancellations_amount": "annulations_gbp",
        "net_sales": "ca_net_gbp",
        "orders": "commandes_vente",
        "identified_customers": "clients_identifies",
        "is_partial": "periode_incomplete",
    })
    export["debut_periode"] = export["debut_periode"].dt.date
    export = export.round(2)
    with st.expander("Voir les données du graphique"):
        st.dataframe(export, hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        components.csv_download(
            components.with_filter_columns(export, filters),
            components.export_name(f"evolution_{grain}", filters),
            "Télécharger l'évolution (CSV)", key="dl_trend",
        )
    with right:
        kpi_export = {
            "ca_ventes_gbp": kpis["gross_sales"],
            "annulations_gbp": kpis["cancellations_amount"],
            "ca_net_gbp": kpis["net_sales"],
            "commandes_vente": kpis["orders"],
            "panier_moyen_gbp": kpis["average_order_value"],
            "clients_identifies": kpis["identified_customers"],
            "clients_plusieurs_commandes": kpis["repeat_customers"],
            "part_clients_plusieurs_commandes": kpis["repeat_customer_rate"],
            "annulations_sur_ca_ventes": kpis["cancellations_to_sales_ratio"],
            "part_ca_avec_client_identifie": kpis["identified_sales_share"],
        }
        components.csv_download(
            components.with_filter_columns(
                # Une colonne par indicateur : chaque valeur garde son type (entier ou décimal).
                pd.DataFrame([kpi_export]).round(
                    {k: (2 if k.endswith("_gbp") else 4) for k in kpi_export}
                ),
                filters,
            ),
            components.export_name("indicateurs", filters),
            "Télécharger les indicateurs (CSV)", key="dl_kpis",
        )

st.divider()
st.subheader("Ce que montrent les données sur l'ensemble de la période")
facts = data.global_facts()
st.caption(
    f"Analyse calculée sur toutes les données ({fmt.date_fr(facts['first_date'])} – "
    f"{fmt.date_fr(facts['last_date'])}), **indépendamment des filtres** choisis."
)
obs_col, rec_col = st.columns(2, gap="large")
with obs_col:
    st.markdown("##### Faits observés")
    for number, item in enumerate(insights.observations(facts), start=1):
        with st.container(border=True):
            st.markdown(f"**{number}. {item['titre']}**")
            st.markdown(item["fait"])
            st.caption(f"Limite : {item['limite']}")
with rec_col:
    st.markdown("##### Recommandations à tester")
    for number, item in enumerate(insights.recommendations(facts), start=1):
        with st.container(border=True):
            st.markdown(f"**{number}. {item['titre']}**")
            st.markdown(item["action"])
            st.caption(f"Hypothèse à vérifier : {item['hypothese']}")
