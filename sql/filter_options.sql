-- Valeurs proposées dans les filtres : produits et pays présents dans les indicateurs,
-- classés par CA des ventes sur l'ensemble de la période (sans filtre).
SELECT
    'produit'                                                       AS dimension,
    stock_code                                                      AS value,
    any_value(product_name)                                         AS label,
    COALESCE(SUM(amount) FILTER (WHERE line_type = 'vente'), 0)     AS gross_sales
FROM lines
WHERE line_type IN ('vente', 'annulation')
GROUP BY stock_code
UNION ALL
SELECT
    'pays',
    country,
    any_value(country_fr),
    COALESCE(SUM(amount) FILTER (WHERE line_type = 'vente'), 0)
FROM lines
WHERE line_type IN ('vente', 'annulation')
GROUP BY country
ORDER BY dimension, gross_sales DESC, value;
