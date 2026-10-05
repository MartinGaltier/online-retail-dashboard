"""Point d'entrée de l'application : configuration, filtres communs et navigation."""

import streamlit as st

from dashboard import components, data

st.set_page_config(
    page_title="Tableau de bord des ventes – Online Retail",
    page_icon=":material/storefront:",
    layout="wide",
)

pages = [
    st.Page("app_pages/overview.py", title="Vue d'ensemble", icon=":material/monitoring:", default=True),
    st.Page("app_pages/breakdown.py", title="Produits, marchés et clients", icon=":material/leaderboard:"),
    st.Page("app_pages/methodology.py", title="Méthodologie", icon=":material/menu_book:"),
]
navigation = st.navigation(pages)

try:
    data.connection()
except FileNotFoundError:
    st.error(
        "Les données préparées sont introuvables. Exécutez `python scripts/prepare_data.py` "
        "pour les générer, puis relancez l'application.",
        icon=":material/error:",
    )
    st.stop()

# Les filtres sont déclarés ici pour être partagés et conservés d'une page à l'autre.
st.session_state["filters"] = components.sidebar_filters()

try:
    navigation.run()
except Exception:  # noqa: BLE001 - message lisible pour l'utilisateur, détail dans les journaux
    st.error(
        "Un problème inattendu empêche l'affichage de cette page. Essayez de réinitialiser les "
        "filtres ; si le problème persiste, rechargez la page.",
        icon=":material/error:",
    )
    raise
