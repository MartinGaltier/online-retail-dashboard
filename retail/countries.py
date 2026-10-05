"""Libellés français des pays tels qu'ils apparaissent dans la source (en anglais)."""

COUNTRY_FR = {
    "Australia": "Australie",
    "Austria": "Autriche",
    "Bahrain": "Bahreïn",
    "Belgium": "Belgique",
    "Brazil": "Brésil",
    "Canada": "Canada",
    "Channel Islands": "Îles Anglo-Normandes",
    "Cyprus": "Chypre",
    "Czech Republic": "République tchèque",
    "Denmark": "Danemark",
    "EIRE": "Irlande",
    "European Community": "Communauté européenne (non détaillé)",
    "Finland": "Finlande",
    "France": "France",
    "Germany": "Allemagne",
    "Greece": "Grèce",
    "Hong Kong": "Hong Kong",
    "Iceland": "Islande",
    "Israel": "Israël",
    "Italy": "Italie",
    "Japan": "Japon",
    "Lebanon": "Liban",
    "Lithuania": "Lituanie",
    "Malta": "Malte",
    "Netherlands": "Pays-Bas",
    "Norway": "Norvège",
    "Poland": "Pologne",
    "Portugal": "Portugal",
    "RSA": "Afrique du Sud",
    "Saudi Arabia": "Arabie saoudite",
    "Singapore": "Singapour",
    "Spain": "Espagne",
    "Sweden": "Suède",
    "Switzerland": "Suisse",
    "USA": "États-Unis",
    "United Arab Emirates": "Émirats arabes unis",
    "United Kingdom": "Royaume-Uni",
    "Unspecified": "Non précisé",
}


def country_fr(name: str) -> str:
    """Retourne le libellé français, ou le nom d'origine si le pays n'est pas répertorié."""
    return COUNTRY_FR.get(name, name)
