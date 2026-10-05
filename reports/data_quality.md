# Rapport de qualité des données

Rapport généré par `python scripts/prepare_data.py` : ne pas modifier à la main.

## Source

- Jeu de données : [Online Retail (UCI)](https://archive.ics.uci.edu/dataset/352/online+retail)
- Citation : Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33
- Licence : Creative Commons Attribution 4.0 International (CC BY 4.0)
- Fichier : `Online Retail.xlsx` (SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`)
- Devise : Livre sterling (GBP), d'après la documentation de la source

## Données brutes

- Lignes : 541 909
- Période : du 2010-12-01 08:26:00 au 2011-12-09 12:50:00
- Factures distinctes : 25 900 ; codes article : 4 070 ; clients identifiés : 4 372 ; pays : 38

| Colonne | Type lu | Valeurs manquantes |
|---|---|---:|
| InvoiceNo | str | 0 |
| StockCode | str | 0 |
| Description | str | 1 454 |
| Quantity | int64 | 0 |
| InvoiceDate | datetime64[us] | 0 |
| UnitPrice | float64 | 0 |
| CustomerID | float64 | 135 080 |
| Country | str | 0 |

## Contrôles numériques (avant traitement)

| Variable | Min | 1er centile | Médiane | 99e centile | Max | Négatifs | Nuls |
|---|---:|---:|---:|---:|---:|---:|---:|
| quantity | -80 995,00 | -2,00 | 3,00 | 100,00 | 80 995,00 | 10 624 | 0 |
| unit_price | -11 062,06 | 0,19 | 2,08 | 18,00 | 38 970,00 | 2 | 2 515 |

## Règles de traitement

Les règles décrivent des constats qui peuvent se recouvrir (une ligne sans client peut aussi être une annulation). Le tableau « Types de lignes » plus bas est, lui, une partition : chaque ligne y figure une seule fois.

| Règle | Constat | Traitement | Lignes | Montant |
|---|---|---|---:|---:|
| **R1 — Doublons exacts** | Lignes identiques sur les 8 colonnes (même facture, article, quantité, prix, minute, client et pays). Elles sont interprétées comme des saisies répétées. | Une seule occurrence est conservée ; les copies sont supprimées. | 5 268 | 21 740,98 £ |
| **R2 — Codes article en minuscules** | Certains codes existent en minuscules et en majuscules (ex. 85123a / 85123A). | Codes convertis en majuscules ; espaces superflus retirés des libellés. | 1 977 | — |
| **R3 — Identifiant client manquant** | Une partie des lignes n'a pas d'identifiant client. | Lignes conservées pour les indicateurs de ventes ; exclues seulement des indicateurs par client (clients identifiés, achats répétés). | 135 037 | 1 447 487,53 £ |
| **R5 — Factures sur plusieurs horodatages** | 43 factures ont des lignes saisies à des minutes différentes (écart maximal : 1 min). | La date retenue pour toutes les lignes d'une facture est son premier horodatage, afin qu'un filtre de dates ne coupe jamais une commande. | 3 320 | — |
| **R6 — Codes hors produit** | Frais de port, commissions Amazon, frais bancaires, remises, échantillons, saisies manuelles, bons cadeaux et ajustements de créance utilisent des codes article spécifiques. | Lignes conservées et signalées ; exclues des indicateurs, qui portent sur les ventes de produits. Leur total est indiqué séparément. | 2 940 | -45 311,21 £ |
| **R7 — Ventes extrêmes annulées le jour même** | 3 lignes de vente de produits atteignent au moins 10 000 £, alors que 99 % des lignes de vente sont inférieures à 179,00 £. 3 d'entre elles sont annulées le jour même par un avoir du même client et du même montant. | Chaque vente concernée et son avoir sont exclus ensemble des indicateurs (erreurs de saisie corrigées). Leur effet net est nul ; les garder gonflerait les ventes et les annulations du même montant. | 6 | 284 623,20 £ |
| **R8 — Quantités négatives hors facture d'annulation** | Lignes à quantité négative et prix nul, sans client, souvent libellées « damaged », « check », « thrown away » : mouvements de stock internes. | Conservées et signalées ; sans valeur monétaire, elles n'entrent pas dans les indicateurs de ventes ni d'annulations. | 1 336 | 0,00 £ |
| **R9 — Prix unitaires nuls** | Lignes de facture à prix nul (articles offerts, corrections, lignes sans libellé). Leur montant est nul. | Conservées et signalées ; non comptées comme ventes (elles créeraient des commandes sans chiffre d'affaires). | 1 157 | 0,00 £ |
| **R10 — Prix négatifs (ajustement de créance)** | Les seules valeurs de prix négatives proviennent des factures « A » libellées « Adjust bad debt ». | Écritures comptables conservées et signalées ; exclues des indicateurs. | 3 | -11 062,06 £ |

### Ventes extrêmes exclues avec leur avoir (R7)

| Facture | Avoir | Article (vente / avoir) | Quantité | Montant | Délai |
|---|---|---|---:|---:|---:|
| 541431 | C541433 | 23166 / 23166 | 74 215 | 77 183,60 £ | 16 min |
| 556444 | C556445 | 22502 / M | 60 | 38 970,00 £ | 3 min |
| 581483 | C581484 | 23843 / 23843 | 80 995 | 168 469,60 £ | 12 min |

### Codes hors produit (R6)

| Catégorie | Code | Lignes | Montant |
|---|---|---:|---:|
| Ajustement de créance douteuse (B) | `B` | 3 | -11 062,06 £ |
| Saisie manuelle (M) | `M` | 567 | -69 031,64 £ |
| Bons cadeaux (gift_0001_*) | `GIFT_0001_20` | 10 | 167,05 £ |
| Bons cadeaux (gift_0001_*) | `GIFT_0001_10` | 9 | 74,97 £ |
| Bons cadeaux (gift_0001_*) | `GIFT_0001_30` | 8 | 175,53 £ |
| Bons cadeaux (gift_0001_*) | `GIFT_0001_50` | 4 | 167,56 £ |
| Bons cadeaux (gift_0001_*) | `GIFT_0001_40` | 3 | 100,70 £ |
| Commissions et frais (AMAZONFEE, BANK CHARGES, CRUK) | `BANK CHARGES` | 37 | -7 175,64 £ |
| Commissions et frais (AMAZONFEE, BANK CHARGES, CRUK) | `AMAZONFEE` | 34 | -221 520,50 £ |
| Commissions et frais (AMAZONFEE, BANK CHARGES, CRUK) | `CRUK` | 16 | -7 933,43 £ |
| Échantillons (S) | `S` | 62 | -3 039,65 £ |
| Frais de port (POST, DOT, C2) | `POST` | 1 256 | 66 230,64 £ |
| Frais de port (POST, DOT, C2) | `DOT` | 710 | 206 245,48 £ |
| Frais de port (POST, DOT, C2) | `C2` | 144 | 6 986,00 £ |
| Remise (D) | `D` | 77 | -5 696,22 £ |

## Résultat : types de lignes

| Type | Lignes | Montant | Lignes sans client | Dans les indicateurs |
|---|---:|---:|---:|:---:|
| Vente de produit | 522 537 | 9 962 596,12 £ | 131 387 | oui |
| Annulation / retour de produit | 8 666 | -230 247,96 £ | 162 | oui |
| Ligne hors produit (port, frais, remises, saisies manuelles) | 2 936 | 4 720,85 £ | 1 026 | non |
| Ligne à prix nul | 1 157 | 0,00 £ | 1 123 | non |
| Ajustement de stock (quantité négative, prix nul) | 1 336 | 0,00 £ | 1 336 | non |
| Vente extrême annulée le jour même et son avoir | 6 | 0,00 £ | 0 | non |
| Ajustement comptable de créance (facture « A ») | 3 | -11 062,06 £ | 3 | non |

Contrôle : montant total après suppression des doublons = 9 726 006,95 £ ; somme des types de lignes = 9 726 006,95 £ ; écart = 0,00 £.

## Clients

- Lignes de vente sans identifiant client : 131 387 (25,1 % des lignes de vente).
- Part du chiffre d'affaires des ventes sans identifiant client : 15,2 %.
- Clients associés à plusieurs pays : 8 (un tel client est compté dans chacun de ses pays lorsqu'on filtre par pays).

## Couverture temporelle

| Mois | Premier jour | Dernier jour | Jours avec activité | Lignes | Statut |
|---|---|---|---:|---:|---|
| 2010-12 | 2010-12-01 | 2010-12-23 | 20 | 41 981 | complet |
| 2011-01 | 2011-01-04 | 2011-01-31 | 24 | 34 900 | complet |
| 2011-02 | 2011-02-01 | 2011-02-28 | 24 | 27 479 | complet |
| 2011-03 | 2011-03-01 | 2011-03-31 | 27 | 36 439 | complet |
| 2011-04 | 2011-04-01 | 2011-04-28 | 21 | 29 701 | complet |
| 2011-05 | 2011-05-01 | 2011-05-31 | 25 | 36 782 | complet |
| 2011-06 | 2011-06-01 | 2011-06-30 | 26 | 36 609 | complet |
| 2011-07 | 2011-07-01 | 2011-07-31 | 26 | 39 267 | complet |
| 2011-08 | 2011-08-01 | 2011-08-31 | 26 | 35 064 | complet |
| 2011-09 | 2011-09-01 | 2011-09-30 | 26 | 49 861 | complet |
| 2011-10 | 2011-10-02 | 2011-10-31 | 26 | 59 969 | complet |
| 2011-11 | 2011-11-01 | 2011-11-30 | 26 | 83 343 | complet |
| 2011-12 | 2011-12-01 | 2011-12-09 | 8 | 25 246 | partiel |

Un mois est « partiel » lorsque les données ne couvrent pas tous ses jours calendaires.
