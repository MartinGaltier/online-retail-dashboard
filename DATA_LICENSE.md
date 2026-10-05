# Licence des données

Les données de ce dépôt proviennent du jeu **Online Retail** :

> Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository.
> https://doi.org/10.24432/C5BW33

Page source : https://archive.ics.uci.edu/dataset/352/online+retail

Elles sont publiées sous licence **Creative Commons Attribution 4.0 International (CC BY 4.0)** :
https://creativecommons.org/licenses/by/4.0/

Le fichier `data/processed/online_retail_lines.parquet` est une **version modifiée** des données
d'origine : 5 268 doublons exacts ont été retirés, les codes article sont mis en majuscules, et des
colonnes ont été ajoutées (type de ligne, catégorie de code, libellé de produit, pays en français,
date de facture unifiée). Toutes les transformations sont décrites dans `reports/data_quality.md` et
reproductibles avec `scripts/prepare_data.py`.

La licence MIT du dépôt (fichier `LICENSE`) s'applique au code uniquement, pas aux données.
