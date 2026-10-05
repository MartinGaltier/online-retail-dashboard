-- Ventes et annulations par pays du client dans la sélection courante.
--
--   gross_sales           CA des ventes (GBP).
--   cancellations_amount  Annulations enregistrées (GBP, positif).
--   net_sales             CA des ventes − annulations (GBP).
--   orders                Commandes de vente.
--   identified_customers  Clients identifiés ayant au moins une commande de vente.
--   share_of_gross_sales  Part du pays dans le CA des ventes de la sélection.
WITH by_country AS (
    SELECT
        country,
        any_value(country_fr)                                               AS country_fr,
        COALESCE(SUM(amount) FILTER (WHERE line_type = 'vente'), 0)         AS gross_sales,
        COALESCE(-SUM(amount) FILTER (WHERE line_type = 'annulation'), 0)   AS cancellations_amount,
        SUM(amount)                                                         AS net_sales,
        COUNT(DISTINCT invoice_no) FILTER (WHERE line_type = 'vente')       AS orders,
        COUNT(DISTINCT customer_id) FILTER (WHERE line_type = 'vente')      AS identified_customers
    FROM filtered_lines($start_date, $end_date, $countries, $stock_codes)
    GROUP BY country
)
SELECT
    *,
    gross_sales / NULLIF(SUM(gross_sales) OVER (), 0) AS share_of_gross_sales
FROM by_country
ORDER BY gross_sales DESC, country;
