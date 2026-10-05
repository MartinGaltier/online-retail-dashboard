# Présentation du projet (2 minutes)

Texte de base à adapter à sa propre façon de parler (et à la première personne pour décrire
sa propre contribution).

## Le pitch

> **Le contexte.** Le projet part de vraies données de vente, pas d'un jeu « propre » de
> tutoriel : le jeu *Online Retail* de l'UCI, soit 541 909 lignes de facture d'un détaillant
> en ligne britannique, sur un an, de décembre 2010 à décembre 2011.
>
> **Le besoin.** Un responsable commercial veut savoir comment évoluent les ventes, quels produits
> et quels pays font le chiffre d'affaires, si les clients reviennent, et combien pèsent les
> annulations.
>
> **Le travail sur les données.** Le fichier contient des pièges : des quantités négatives, des
> lignes sans client, des frais de port mélangés aux produits, des doublons, et même une vente de
> 80 995 unités annulée douze minutes plus tard. La préparation, reproductible, ne supprime que
> les doublons exacts. Toutes les autres lignes sont classées, et chaque règle est
> chiffrée dans un rapport de qualité.
>
> **Les calculs.** Les indicateurs sont écrits en SQL et exécutés par DuckDB : CA des ventes,
> annulations, CA net, commandes, panier moyen, clients récurrents. Chaque définition est
> explicite ; par exemple, un ratio de montants n'est jamais présenté comme un taux de retour. Un seul
> fichier SQL applique les filtres, donc tous les graphiques restent cohérents.
>
> **La vérification.** 52 tests automatisés, plus un script qui recalcule les totaux depuis le fichier
> brut, par un autre chemin, et retrouve exactement les mêmes chiffres.
>
> **Le résultat.** Une application Streamlit en ligne, en trois pages. On y voit par exemple que
> septembre à novembre 2011 font 36 % du CA de l'année, que 65 % des clients identifiés ont commandé
> au moins deux fois, et que le Royaume-Uni pèse 85 % des ventes. Les recommandations qui en
> découlent sont prudentes et présentées comme des hypothèses à tester : une seule année de données ne permet pas de
> conclure à une saisonnalité.

## Les chiffres à connaître

| | Valeur (ensemble de la période) |
|---|---|
| Lignes brutes / préparées | 541 909 / 536 641 (5 268 doublons exacts retirés) |
| CA des ventes | 9,96 M£ |
| Annulations | 230 k£, soit 2,3 % du CA des ventes en valeur |
| CA net | 9,73 M£ |
| Commandes / panier moyen | 19 770 commandes, 504 £ |
| Clients identifiés / récurrents | 4 333, dont 65,3 % avec au moins 2 commandes |
| Ventes sans identifiant client | 15,2 % du CA des ventes |
| Royaume-Uni | 84,7 % du CA des ventes |

## Questions probables et éléments de réponse

**Pourquoi ne pas supprimer les quantités négatives ?**
Parce que ce sont des opérations réelles : des avoirs (factures commençant par « C ») ou des
ajustements de stock. Les supprimer surestimerait le CA net. Elles sont classées et comptées à part.

**Pourquoi garder les ventes sans client ?**
Elles représentent 15 % du CA. Les retirer fausserait le CA et le nombre de commandes. Elles sont
exclues seulement des indicateurs qui ont besoin d'un client, et la couverture est affichée.

**Comment rattachez-vous un retour à sa commande ?**
Ce n'est pas possible : les données ne contiennent pas la facture d'origine. Le CA net d'une période
déduit les avoirs enregistrés pendant cette période, et c'est écrit dans la méthodologie.

**Pourquoi DuckDB et pas seulement pandas ?**
Les définitions s'écrivent clairement en SQL, et DuckDB est une base embarquée très rapide, sans
serveur. La logique métier reste ainsi séparée de l'interface.

**Comment savez-vous que vos chiffres sont justes ?**
Par trois niveaux de contrôle : des tests sur un petit jeu dont les résultats se calculent à la main,
un recoupement SQL / pandas sur les vraies données, et un recalcul indépendant depuis l'Excel brut.

**Qu'avez-vous fait des valeurs aberrantes ?**
Elles sont examinées individuellement. Les trois ventes de plus de 10 000 £ ont toutes été annulées le jour
même par le même client, pour le même montant. Ce sont des erreurs de saisie corrigées, exclues
avec leur avoir par une règle générique et documentée.

**Quelle est la principale limite ?**
Une seule année de données : on ne peut pas dire si le pic de fin d'année est saisonnier. Il n'y a
pas non plus de coûts, donc aucune marge.

**Quelles suites possibles ?**
Ajouter les années suivantes (le jeu *Online Retail II* de l'UCI couvre 2009-2011) pour comparer d'une
année sur l'autre, puis une segmentation RFM des clients.

## Comprendre le code en 5 fichiers

1. `retail/prepare.py` : la fonction `prepare()` applique les règles R1 à R10 et construit le rapport.
2. `sql/filtered_lines.sql` : la macro de filtre commune à tous les indicateurs.
3. `sql/kpis.sql` : les indicateurs clés, avec leurs définitions en commentaire.
4. `retail/queries.py` : la fonction `run()` charge un fichier SQL et lui passe les paramètres.
5. `streamlit_app.py` : déclare les filtres dans la barre latérale et la navigation entre les pages.
