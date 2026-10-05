-- Lignes retenues pour les indicateurs, après application des filtres de l'utilisateur.
--
-- Tous les fichiers SQL d'indicateurs lisent cette macro : un même filtre s'applique donc
-- de façon identique à chaque indicateur, tableau et graphique.
--
-- Paramètres
--   start_date, end_date : bornes incluses, appliquées à la date de la facture
--                          (date de l'avoir pour une annulation).
--   countries            : liste de pays (noms de la source) ; liste vide = tous les pays.
--   stock_codes          : liste de codes article ; liste vide = tous les produits.
--
-- Seules les lignes de type 'vente' et 'annulation' (produits) entrent dans les indicateurs.
-- Les autres types (frais de port, ajustements, lignes à prix nul…) sont décrits dans
-- reports/data_quality.md.
CREATE OR REPLACE MACRO filtered_lines(start_date, end_date, countries, stock_codes) AS TABLE
SELECT
    invoice_no,
    invoice_date,
    stock_code,
    product_name,
    quantity,
    unit_price,
    amount,
    customer_id,
    country,
    country_fr,
    line_type
FROM lines
WHERE line_type IN ('vente', 'annulation')
  AND invoice_date BETWEEN start_date AND end_date
  AND (len(countries::VARCHAR[]) = 0 OR list_contains(countries::VARCHAR[], country))
  AND (len(stock_codes::VARCHAR[]) = 0 OR list_contains(stock_codes::VARCHAR[], stock_code));
