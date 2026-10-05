-- Répartition des clients identifiés selon leur nombre de commandes dans la sélection.
--
-- Seules les lignes de vente avec un identifiant client sont prises en compte. Aucune donnée
-- individuelle n'est renvoyée : uniquement des effectifs et des montants par tranche.
--
--   frequency_band   Tranche de nombre de commandes de vente.
--   customers        Nombre de clients identifiés dans la tranche.
--   gross_sales      CA des ventes de ces clients (GBP).
--   customer_share   Part des clients identifiés.
--   sales_share      Part du CA des ventes des clients identifiés.
WITH orders_per_customer AS (
    SELECT
        customer_id,
        COUNT(DISTINCT invoice_no) AS orders,
        SUM(amount)                AS gross_sales
    FROM filtered_lines($start_date, $end_date, $countries, $stock_codes)
    WHERE line_type = 'vente'
      AND customer_id IS NOT NULL
    GROUP BY customer_id
),
banded AS (
    SELECT
        CASE
            WHEN orders = 1 THEN 1
            WHEN orders = 2 THEN 2
            WHEN orders = 3 THEN 3
            WHEN orders <= 5 THEN 4
            WHEN orders <= 10 THEN 5
            ELSE 6
        END AS band_order,
        gross_sales
    FROM orders_per_customer
)
SELECT
    band_order,
    CASE band_order
        WHEN 1 THEN '1 commande'
        WHEN 2 THEN '2 commandes'
        WHEN 3 THEN '3 commandes'
        WHEN 4 THEN '4 à 5 commandes'
        WHEN 5 THEN '6 à 10 commandes'
        ELSE '11 commandes ou plus'
    END                                                     AS frequency_band,
    COUNT(*)                                                AS customers,
    SUM(gross_sales)                                        AS gross_sales,
    COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER ()                AS customer_share,
    SUM(gross_sales) / NULLIF(SUM(SUM(gross_sales)) OVER (), 0) AS sales_share
FROM banded
GROUP BY band_order
ORDER BY band_order;
