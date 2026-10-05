"""Page 3 — Méthodologie : source, définitions, nettoyage et limites."""

import pandas as pd
import streamlit as st

from dashboard import data
from retail import config
from retail import formatting as fmt

report = data.quality_report()
raw = report["brut"]
coverage = report["couverture_temporelle"]

st.title("Méthodologie")
st.markdown(
    "Cette page explique d'où viennent les chiffres, comment ils sont calculés et ce qu'ils "
    "ne permettent pas de conclure. Elle ne dépend pas des filtres."
)

st.header("Source des données", divider="gray")
st.markdown(
    f"""
- **Jeu de données :** [Online Retail]({config.SOURCE_PAGE_URL}), UCI Machine Learning Repository.
- **Citation :** {config.SOURCE_CITATION}
- **Licence :** [{config.SOURCE_LICENSE}]({config.SOURCE_LICENSE_URL}). Les données sont
  redistribuées ici sous forme préparée, avec attribution ; les modifications sont décrites
  ci-dessous.
- **Contenu :** toutes les transactions d'un détaillant en ligne britannique, sans magasin
  physique, qui vend principalement des articles cadeaux ; une grande partie de ses clients
  sont des grossistes.
- **Période réellement couverte :** du {fmt.date_fr(pd.Timestamp(coverage['premier_jour']))} au
  {fmt.date_fr(pd.Timestamp(coverage['dernier_jour']))}. Le mois de décembre 2011 est **incomplet**
  (9 jours) ; aucune donnée n'est présente entre le 24 décembre 2010 et le 3 janvier 2011.
- **Devise :** livre sterling (£, GBP), d'après la documentation de la source. Aucune
  conversion n'est appliquée.
- **Volume brut :** {fmt.number(raw['lignes'])} lignes de facture, {fmt.number(raw['factures_distinctes'])}
  factures, {fmt.number(raw['clients_distincts'])} identifiants client, {raw['pays_distincts']} pays.

Il s'agit de **données historiques** publiées à des fins de recherche : elles ne décrivent pas
la situation actuelle de l'entreprise.
"""
)

st.header("Définitions des indicateurs", divider="gray")
st.markdown(
    "Une **ligne** est un article d'une facture ; une **commande** est une facture de vente "
    "(un numéro de facture, qui peut contenir plusieurs lignes) ; un **client** est un "
    "identifiant client distinct. Tous les montants sont en livres sterling et portent sur "
    "les **produits** uniquement."
)
definitions = pd.DataFrame(
    [
        ("CA des ventes", "Σ quantité × prix unitaire des lignes de vente", "£",
         "Factures sans préfixe, quantité > 0, prix > 0, code article de produit."),
        ("Annulations et retours", "− Σ quantité × prix unitaire des lignes d'avoir", "£",
         "Factures « C ». Datées à la date de l'avoir ; non rattachées à la commande d'origine."),
        ("CA net", "CA des ventes − annulations et retours", "£",
         "Sur la même période et les mêmes filtres. Un avoir peut concerner une vente "
         "antérieure à la période choisie."),
        ("Commandes de vente", "Nombre de factures distinctes ayant au moins une ligne de vente",
         "commandes", "Une facture de 20 lignes compte pour une commande."),
        ("Panier moyen", "CA des ventes ÷ commandes de vente", "£ par commande",
         "Hors frais de port. Non calculé si aucune commande."),
        ("Clients identifiés", "Nombre d'identifiants client distincts ayant une commande de vente",
         "clients", "Les ventes sans identifiant sont exclues de cet indicateur seulement."),
        ("Clients récurrents",
         "Clients avec ≥ 2 commandes de vente ÷ clients identifiés", "%",
         "Dans la sélection courante ; dépend de la durée de la période."),
        ("Annulations / CA des ventes", "Annulations ÷ CA des ventes", "%",
         "Rapport de montants : ce n'est pas un taux de commandes retournées."),
    ],
    columns=["Indicateur", "Formule", "Unité", "Précisions"],
)
st.table(definitions.set_index("Indicateur"))
st.markdown(
    "Les **filtres** (dates, pays, produits) s'appliquent de la même façon à tous les "
    "indicateurs : ils sont définis une seule fois dans la requête SQL commune "
    "`sql/filtered_lines.sql`. Les variations affichées comparent la sélection à la période "
    "précédente de même durée, seulement si celle-ci est entièrement couverte par les données."
)

st.header("Préparation et nettoyage", divider="gray")
st.markdown(
    "Le script `scripts/prepare_data.py` télécharge le fichier de l'UCI, vérifie son empreinte, "
    "puis applique les règles ci-dessous. **Seuls les doublons exacts sont supprimés** : toutes "
    "les autres lignes sont conservées et classées, pour que chaque exclusion reste traçable. "
    "Les quantités négatives et les lignes sans client ne sont pas supprimées."
)
rules = pd.DataFrame(report["regles"])
rules = pd.DataFrame({
    "Règle": rules["code"] + " — " + rules["titre"],
    "Constat": rules["constat"],
    "Traitement": rules["traitement"],
    "Lignes": rules["lignes"].map(fmt.number),
    "Montant": rules["montant"].map(lambda v: fmt.money(v, 2) if pd.notna(v) else fmt.MISSING),
})
st.table(rules.set_index("Règle"))
st.caption("Les constats peuvent se recouvrir ; le tableau suivant, lui, classe chaque ligne une seule fois.")

st.subheader("Classement final des lignes")
line_types = pd.DataFrame(report["types_de_lignes"])
line_types = line_types[["libelle", "lignes", "montant", "lignes_sans_client", "inclus_dans_indicateurs"]]
line_types = line_types.rename(columns={
    "libelle": "Type de ligne", "lignes": "Lignes", "montant": "Montant (£)",
    "lignes_sans_client": "Dont sans client", "inclus_dans_indicateurs": "Dans les indicateurs",
})
st.dataframe(line_types, hide_index=True, width="stretch",
             column_config={"Montant (£)": st.column_config.NumberColumn(format="%.2f")})
check = report["controle_coherence"]
st.caption(
    f"Contrôle de cohérence : la somme des montants par type de ligne "
    f"({fmt.money(check['somme_par_type_de_ligne'], 2)}) est égale au montant total après "
    f"suppression des doublons ({fmt.money(check['montant_apres_doublons'], 2)})."
)

with st.expander("Ventes extrêmes exclues avec leur avoir"):
    st.markdown(
        f"{len(report['paires_extremes_exclues'])} ventes d'au moins "
        f"{fmt.money(config.OUTLIER_AMOUNT_THRESHOLD)} ont été annulées quelques minutes plus tard "
        "par un avoir du même client et du même montant. Elles sont exclues avec leur avoir : "
        "leur effet net est nul, mais elles gonfleraient à la fois les ventes et les annulations."
    )
    st.dataframe(pd.DataFrame(report["paires_extremes_exclues"]), hide_index=True, width="stretch")

with st.expander("Lignes hors produit (frais de port, commissions, remises…)"):
    st.markdown(
        "Ces lignes sont conservées dans les données mais exclues des indicateurs, qui portent "
        "sur les ventes de produits. Elles ne peuvent pas être rattachées à un produit et ne "
        "relèvent pas toutes d'une vente (commissions Amazon, frais bancaires)."
    )
    st.dataframe(pd.DataFrame(report["codes_hors_produit"]), hide_index=True, width="stretch",
                 column_config={"montant": st.column_config.NumberColumn(format="%.2f")})

with st.expander("Couverture par mois"):
    st.dataframe(pd.DataFrame(coverage["mois"]), hide_index=True, width="stretch")

st.header("Limites", divider="gray")
clients = report["clients"]
st.markdown(
    f"""
- **Clients non identifiés :** {fmt.percent(clients['part_ca_ventes_sans_client'])} du CA des
  ventes n'a pas d'identifiant client. Ces ventes comptent dans le CA et les commandes, mais pas
  dans les indicateurs clients.
- **Annulations non rattachées :** un avoir ne mentionne pas la facture d'origine. Le CA net
  d'une période déduit les avoirs *enregistrés* pendant cette période, même s'ils portent sur
  des ventes antérieures (y compris antérieures à décembre 2010).
- **Une seule année :** avec une seule fin d'année complète, on ne peut pas distinguer une
  saisonnalité récurrente d'une croissance ponctuelle. Décembre 2011 est incomplet.
- **Pas de coûts :** les données ne contiennent ni coûts d'achat, ni frais logistiques : aucune
  marge ni rentabilité n'est calculée.
- **Pays :** il s'agit du pays déclaré du client. {clients['clients_avec_plusieurs_pays']} clients
  sont associés à plusieurs pays et sont comptés dans chacun d'eux lorsqu'on filtre par pays.
- **Historique client tronqué :** un client « à 1 commande » a pu commander avant décembre
  2010 ; la part de clients ayant commandé plusieurs fois est donc une borne basse.
- **Doublons :** les lignes strictement identiques sont considérées comme des saisies répétées ;
  si certaines étaient des achats réels, le CA serait légèrement sous-estimé
  ({fmt.money(report['regles'][0]['montant'])} au total).
"""
)

st.header("Outils", divider="gray")
st.markdown(
    "Préparation en **Python / pandas**, calculs en **SQL** exécutés par **DuckDB**, interface "
    "**Streamlit**, graphiques **Plotly**. Le rapport de qualité complet est disponible dans le "
    "dépôt (`reports/data_quality.md`)."
)
