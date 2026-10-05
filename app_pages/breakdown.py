"""Page 2 — Produits, marchés et clients : classements, contributions et achats répétés."""

import streamlit as st

from dashboard import charts, components, data
from retail import formatting as fmt

filters = st.session_state["filters"]

st.title("Produits, marchés et clients")
st.markdown(
    "Quels produits et quels pays font le chiffre d'affaires, et dans quelle mesure les "
    "clients reviennent-ils acheter ? Tous les chiffres respectent les filtres choisis à gauche."
)
components.selection_header(filters)

kpis = data.kpis(filters)
components.stop_if_empty(kpis)

products_tab, countries_tab, customers_tab = st.tabs(
    [":material/inventory_2: Produits", ":material/public: Pays", ":material/group: Clients"]
)

# --------------------------------------------------------------------------------------
with products_tab:
    products = data.product_sales(filters)
    metrics = {
        "gross_sales": ("CA des ventes", "money"),
        "net_sales": ("CA net (après annulations)", "money"),
        "quantity_sold": ("Quantités vendues", "number"),
        "cancellations_amount": ("Annulations et retours", "money"),
    }
    left, right = st.columns([3, 1])
    with left:
        metric = st.selectbox("Classer les produits par", list(metrics),
                              format_func=lambda m: metrics[m][0], key="product_metric")
    with right:
        top_n = st.number_input("Nombre de produits", min_value=5, max_value=30, value=15,
                                step=5, key="product_top_n")
    label, kind = metrics[metric]
    ranked = products.sort_values([metric, "stock_code"], ascending=[False, True])
    ranked = ranked[ranked[metric] > 0].head(int(top_n))

    if ranked.empty:
        st.info(f"Aucun produit avec un montant positif pour « {label} » dans cette sélection.")
    else:
        unit = " (£)" if kind == "money" else " (unités)"
        st.plotly_chart(
            charts.ranking_figure(
                ranked, "product_name", metric, f"Top {len(ranked)} des produits – {label}{unit}",
                kind, detail_column="share_of_gross_sales" if metric == "gross_sales" else None,
                detail_label="Part du CA des ventes de la sélection",
            ),
            width="stretch", config={"displaylogo": False},
        )

    selling = products[products["gross_sales"] > 0].sort_values("gross_sales", ascending=False)
    if len(selling) >= 5:
        top_fifth = selling.head(max(1, round(len(selling) * 0.2)))
        share = top_fifth["gross_sales"].sum() / selling["gross_sales"].sum()
        st.markdown(
            f"**Concentration :** les {fmt.number(len(top_fifth))} produits les plus vendus "
            f"(20 % des {fmt.number(len(selling))} produits vendus dans la sélection) réalisent "
            f"**{fmt.percent(share)}** du CA des ventes."
        )

    table = products.rename(columns={
        "stock_code": "code_article",
        "product_name": "produit",
        "gross_sales": "ca_ventes_gbp",
        "quantity_sold": "quantite_vendue",
        "orders": "commandes",
        "cancellations_amount": "annulations_gbp",
        "quantity_cancelled": "quantite_annulee",
        "net_sales": "ca_net_gbp",
        "share_of_gross_sales": "part_ca_ventes",
    }).round({"ca_ventes_gbp": 2, "annulations_gbp": 2, "ca_net_gbp": 2, "part_ca_ventes": 5})
    with st.expander(f"Tableau complet des {fmt.number(len(table))} produits"):
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "ca_ventes_gbp": st.column_config.NumberColumn("CA des ventes (£)", format="%.2f"),
                "annulations_gbp": st.column_config.NumberColumn("Annulations (£)", format="%.2f"),
                "ca_net_gbp": st.column_config.NumberColumn("CA net (£)", format="%.2f"),
                "part_ca_ventes": st.column_config.NumberColumn("Part du CA", format="percent"),
            },
        )
    components.csv_download(
        components.with_filter_columns(table, filters),
        components.export_name("produits", filters),
        "Télécharger le classement des produits (CSV)", key="dl_products",
    )

# --------------------------------------------------------------------------------------
with countries_tab:
    countries = data.country_sales(filters)
    uk_present = (countries["country"] == components.UK).any() and len(countries) > 1
    exclude_uk = False
    if uk_present:
        exclude_uk = st.toggle(
            "Masquer le Royaume-Uni dans le graphique", key="hide_uk",
            help="Le Royaume-Uni pèse beaucoup plus que les autres pays : le masquer permet de "
                 "comparer les marchés étrangers entre eux. Les parts restent calculées sur "
                 "l'ensemble de la sélection.",
        )
        uk_share = countries.loc[countries["country"] == components.UK, "share_of_gross_sales"].iloc[0]
        st.markdown(f"Le Royaume-Uni représente **{fmt.percent(uk_share)}** du CA des ventes de la sélection.")
    shown = countries[countries["gross_sales"] > 0]
    if exclude_uk:
        shown = shown[shown["country"] != components.UK]
    shown = shown.head(15)
    if shown.empty:
        st.info("Aucun pays avec des ventes dans cette sélection.")
    else:
        st.plotly_chart(
            charts.ranking_figure(
                shown, "country_fr", "gross_sales",
                f"Top {len(shown)} des pays – CA des ventes (£)", "money",
                detail_column="share_of_gross_sales",
                detail_label="Part du CA des ventes de la sélection",
            ),
            width="stretch", config={"displaylogo": False},
        )
    st.caption(
        "Pays déclaré pour le client sur la facture. « Non précisé » et « Communauté européenne "
        "(non détaillé) » sont repris tels qu'ils figurent dans la source."
    )
    country_table = countries.rename(columns={
        "country": "pays_source",
        "country_fr": "pays",
        "gross_sales": "ca_ventes_gbp",
        "cancellations_amount": "annulations_gbp",
        "net_sales": "ca_net_gbp",
        "orders": "commandes",
        "identified_customers": "clients_identifies",
        "share_of_gross_sales": "part_ca_ventes",
    }).round({"ca_ventes_gbp": 2, "annulations_gbp": 2, "ca_net_gbp": 2, "part_ca_ventes": 5})
    with st.expander(f"Tableau des {len(country_table)} pays"):
        st.dataframe(
            country_table, hide_index=True, width="stretch",
            column_config={
                "ca_ventes_gbp": st.column_config.NumberColumn("CA des ventes (£)", format="%.2f"),
                "annulations_gbp": st.column_config.NumberColumn("Annulations (£)", format="%.2f"),
                "ca_net_gbp": st.column_config.NumberColumn("CA net (£)", format="%.2f"),
                "part_ca_ventes": st.column_config.NumberColumn("Part du CA", format="percent"),
            },
        )
    components.csv_download(
        components.with_filter_columns(country_table, filters),
        components.export_name("pays", filters),
        "Télécharger les résultats par pays (CSV)", key="dl_countries",
    )

# --------------------------------------------------------------------------------------
with customers_tab:
    st.markdown(
        "Un client « revient » s'il a passé **au moins deux commandes distinctes** dans la "
        "sélection. Seules les ventes avec un identifiant client sont prises en compte ; aucun "
        "client n'est affiché individuellement."
    )
    cols = st.columns(3)
    with cols[0]:
        components.metric_card("Clients identifiés", fmt.number(kpis["identified_customers"]),
                               "Clients distincts ayant au moins une commande de vente.")
    with cols[1]:
        components.metric_card("Clients récurrents",
                               fmt.percent(kpis["repeat_customer_rate"]),
                               "Part des clients identifiés ayant au moins 2 commandes de vente.")
    with cols[2]:
        components.metric_card("Part du CA avec client identifié",
                               fmt.percent(kpis["identified_sales_share"]),
                               "Part du CA des ventes rattachée à un identifiant client : c'est "
                               "la couverture des indicateurs de cette section.")

    frequency = data.customer_frequency(filters)
    if frequency.empty:
        st.info("Aucune vente avec un identifiant client dans cette sélection.")
    else:
        st.plotly_chart(charts.frequency_figure(frequency), width="stretch",
                        config={"displaylogo": False})
        repeat_sales = frequency.loc[frequency["band_order"] >= 2, "sales_share"].sum()
        st.markdown(
            f"Les clients ayant commandé au moins deux fois réalisent **{fmt.percent(repeat_sales)}** "
            "du CA des ventes des clients identifiés."
        )
        st.caption(
            "Plus la période choisie est courte, moins les clients ont l'occasion de commander "
            "plusieurs fois : comparez des périodes de même durée."
        )
        frequency_table = frequency.drop(columns="band_order").rename(columns={
            "frequency_band": "tranche_commandes",
            "customers": "clients",
            "gross_sales": "ca_ventes_gbp",
            "customer_share": "part_clients",
            "sales_share": "part_ca_ventes",
        }).round({"ca_ventes_gbp": 2, "part_clients": 5, "part_ca_ventes": 5})
        with st.expander("Voir le tableau par tranche"):
            st.dataframe(
                frequency_table, hide_index=True, width="stretch",
                column_config={
                    "ca_ventes_gbp": st.column_config.NumberColumn("CA des ventes (£)", format="%.2f"),
                    "part_clients": st.column_config.NumberColumn("Part des clients", format="percent"),
                    "part_ca_ventes": st.column_config.NumberColumn("Part du CA", format="percent"),
                },
            )
        components.csv_download(
            components.with_filter_columns(frequency_table, filters),
            components.export_name("frequence_clients", filters),
            "Télécharger la répartition des clients (CSV)", key="dl_frequency",
        )
