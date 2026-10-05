# Décisions techniques

Ce document explique les choix principaux du projet et leurs alternatives.

## 1. Architecture en trois couches

```
scripts/prepare_data.py ──► data/processed/*.parquet ──► sql/*.sql (DuckDB) ──► Streamlit
   (pandas, une fois)           (6 Mo, versionné)          (à chaque filtre)       (affichage)
```

- **Préparation hors ligne** (`retail/prepare.py`) : l'Excel brut (23 Mo, 15 s de lecture) est traité
  une seule fois. L'application ne lit que le Parquet préparé : elle démarre vite et ne dépend pas
  d'un fichier présent uniquement sur un poste local.
- **Calculs en SQL** (`sql/`) : chaque indicateur est un fichier SQL lisible, commenté avec ses
  définitions. C'est la partie « métier » du projet, relisible par quelqu'un qui ne connaît pas Python.
- **Interface Streamlit** (`streamlit_app.py`, `app_pages/`, `dashboard/`) : elle n'effectue aucun
  calcul métier ; elle appelle `retail/queries.py`, met les résultats en cache et les affiche.

`retail/` ne dépend pas de Streamlit : les mêmes fonctions servent à l'application, aux tests et au
script de vérification.

## 2. DuckDB plutôt que pandas pour les indicateurs

- Le SQL exprime naturellement les définitions (`COUNT(DISTINCT invoice_no)`, `FILTER (WHERE …)`,
  `NULLIF` pour éviter les divisions par zéro).
- DuckDB est une base embarquée : pas de serveur, pas de compte, une simple dépendance Python. Les
  requêtes sur 531 000 lignes prennent environ 50 ms.
- La base est chargée **en mémoire** une seule fois par processus (`st.cache_resource`) ; chaque
  requête utilise son propre curseur, comme le recommande DuckDB lorsque plusieurs sessions partagent
  une connexion.

## 3. Un filtre défini une seule fois

Les filtres (dates, pays, produits) sont appliqués par une **macro SQL** unique,
`sql/filtered_lines.sql`. Tous les indicateurs lisent `filtered_lines($start_date, $end_date,
$countries, $stock_codes)` : il est impossible qu'un graphique applique un filtre différent des
cartes d'indicateurs. Une liste vide signifie « pas de filtre ». Les paramètres sont transmis par
DuckDB (requêtes préparées), jamais concaténés dans le texte SQL.

## 4. Périmètre : les ventes de produits

Les indicateurs portent sur les lignes de **produits**. Les frais de port, commissions Amazon, frais
bancaires, remises, saisies manuelles (code `M`) et bons cadeaux sont exclus et chiffrés dans le
rapport de qualité.

- *Pourquoi ?* Avec un filtre produit, ces lignes disparaîtraient de toute façon (elles ne sont pas
  rattachées à un produit). En les excluant partout, la somme des CA par produit est égale au CA total,
  quel que soit le filtre : les chiffres restent cohérents entre les vues.
- *Conséquence assumée :* le panier moyen est hors frais de port, et quelques avoirs saisis en code
  `M` ne sont pas déduits du CA net (ils sont listés dans le rapport).

## 5. Ne supprimer que les doublons exacts

Chaque ligne reçoit un `line_type` plutôt que d'être supprimée. Avantages : chaque exclusion est
traçable, le rapport de qualité indique le nombre de lignes et le montant concernés, et un contrôle
vérifie que la somme des montants par type est égale au total (écart nul).

- Les **quantités négatives** sont gardées : ce sont des avoirs (factures « C ») ou des ajustements
  de stock à prix nul.
- Les **ventes sans client** sont gardées dans les ventes, et exclues seulement des indicateurs
  clients, avec un taux de couverture affiché.
- Les **3 ventes extrêmes** annulées le jour même sont exclues avec leur avoir. La règle est générique
  (montant ≥ 10 000 £, avoir du même client, même jour, même montant), pas une liste écrite à la main.

## 6. Date d'une facture

43 factures ont des lignes saisies à une minute d'écart. Toutes les lignes d'une facture reçoivent
le **premier horodatage** de la facture, pour qu'un filtre de dates ne coupe jamais une commande en deux.

## 7. Annulations : pas de rattachement inventé

Un avoir ne contient pas la référence de la facture d'origine. Plutôt que de deviner un lien, le
projet date chaque annulation à la date de l'avoir et l'indique clairement : le CA net d'une période
est « ventes de la période − avoirs enregistrés pendant la période ». Le ratio affiché est un rapport
de **montants**, pas un taux de commandes retournées.

## 8. Comparaisons temporelles

Les variations comparent la sélection à la **période précédente de même durée**, avec les mêmes pays
et produits, et ne sont affichées que si cette période est entièrement couverte par les données. Les
périodes incomplètes (par exemple décembre 2011) sont grisées dans les graphiques.

## 9. Mise en cache

- `st.cache_resource` : la base DuckDB, partagée par toutes les sessions.
- `st.cache_data` : le résultat de chaque requête, par combinaison de filtres (200 entrées au plus).
  L'objet `Filters` est une dataclass figée, hachée via `hash_funcs`.

## 10. Observations sans chiffres écrits à la main

Les observations de la page d'accueil (`retail/insights.py`) sont des modèles de texte dont tous les
nombres sont recalculés à partir des requêtes. Si les données changent, le texte suit.

## 11. Vérification

- Tests unitaires sur un **jeu synthétique** dont chaque résultat se calcule à la main.
- Recoupement **SQL / pandas** sur les données réelles.
- **Recalcul indépendant depuis l'Excel brut** (`scripts/verify_totals.py`), sans réutiliser la
  préparation ni le SQL.
- Tests d'interface avec `streamlit.testing.v1.AppTest` (pages, filtres, sélection vide).

## 12. Dépendances et hébergement

- Versions figées dans `requirements.txt`, généré avec `uv pip compile` (toutes les dépendances,
  y compris indirectes) pour Python 3.12, la version par défaut de Streamlit Community Cloud.
- `openpyxl` et `pytest` ne servent qu'à la préparation et aux tests : ils sont dans
  `requirements-dev.txt` et ne sont pas installés sur l'hébergeur.
- Le Parquet (6 Mo) est versionné : il respecte largement les limites de GitHub (100 Mo par fichier)
  et sa redistribution est permise par la licence CC BY 4.0, avec attribution. L'Excel brut n'est pas
  versionné : le script le retélécharge et vérifie son empreinte.
- Aucun secret, aucune API externe, aucun compte utilisateur.

## 13. Accessibilité et lisibilité

- Interface en français, nombres au format français (espace fine, virgule décimale, symbole £).
- Deux couleurs seulement (bleu, orange), vérifiées pour le contraste et le daltonisme ; une légende
  ou un titre nomme chaque série ; les valeurs sont aussi disponibles en tableau et en CSV.
- Pas de graphique à deux axes : les annulations, d'un ordre de grandeur bien inférieur au CA, ont
  leur propre graphique.
- Exports CSV au format Excel français (séparateur `;`, virgule décimale, UTF-8 avec BOM) ; chaque
  ligne exportée rappelle les filtres appliqués.
