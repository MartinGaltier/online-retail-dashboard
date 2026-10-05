# Vérification indépendante des totaux

Généré par `python scripts/verify_totals.py`. Le calcul de référence relit le fichier Excel brut avec pandas, sans utiliser la préparation ni le SQL de l'application.

| Indicateur | Calcul indépendant | Application (SQL) | Résultat |
|---|---:|---:|:---:|
| gross_sales | 9,962,596.12 | 9,962,596.12 | OK |
| cancellations_amount | 230,247.96 | 230,247.96 | OK |
| net_sales | 9,732,348.16 | 9,732,348.16 | OK |
| orders | 19,770.00 | 19,770.00 | OK |
| identified_customers | 4,333.00 | 4,333.00 | OK |
| repeat_customers | 2,828.00 | 2,828.00 | OK |

- Écart maximal sur le CA des ventes mensuel (13 mois) : 0.000000 £
- Écart maximal sur le CA des ventes par pays (38 pays) : 0.000002 £

**Résultat : tous les contrôles concordent.**
