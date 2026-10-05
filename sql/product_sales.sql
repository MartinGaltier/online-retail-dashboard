-- Ventes et annulations par produit (code article) dans la sélection courante.
--
--   gross_sales           CA des ventes du produit (GBP).
--   quantity_sold         Unités vendues.
--   orders                Commandes de vente contenant le produit.
--   cancellations_amount  Montant des annulations enregistrées pour ce produit (GBP, positif).
--   net_sales             CA des ventes − annulations du produit (GBP).
--   share_of_gross_sales  Part du produit dans le CA des ventes de la sélection.
-- Un produit uniquement annulé dans la sélection apparaît avec un CA des ventes nul.
WITH by_product AS (
    SELECT
        stock_code,
        any_value(product_name)                                             AS product_name,
        COALESCE(SUM(amount) FILTER (WHERE line_type = 'vente'), 0)         AS gross_sales,
        COALESCE(SUM(quantity) FILTER (WHERE line_type = 'vente'), 0)       AS quantity_sold,
        COUNT(DISTINCT invoice_no) FILTER (WHERE line_type = 'vente')       AS orders,
        COALESCE(-SUM(amount) FILTER (WHERE line_type = 'annulation'), 0)   AS cancellations_amount,
        COALESCE(-SUM(quantity) FILTER (WHERE line_type = 'annulation'), 0) AS quantity_cancelled,
        SUM(amount)                                                         AS net_sales
    FROM filtered_lines($start_date, $end_date, $countries, $stock_codes)
    GROUP BY stock_code
)
SELECT
    *,
    gross_sales / NULLIF(SUM(gross_sales) OVER (), 0) AS share_of_gross_sales
FROM by_product
ORDER BY gross_sales DESC, stock_code;
