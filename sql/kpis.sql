-- Indicateurs clés de la sélection courante.
--
-- Définitions (montants en livres sterling, GBP)
--   gross_sales           CA des ventes = somme de quantité × prix unitaire des lignes de vente.
--   cancellations_amount  Montant des annulations et retours enregistrés sur la période,
--                         en valeur positive (somme des lignes d'avoir, signe inversé).
--   net_sales             CA net = CA des ventes − annulations. Les avoirs sont datés à leur
--                         propre date : ils ne sont pas rattachés à la commande d'origine.
--   orders                Commandes de vente = factures distinctes ayant au moins une ligne de vente.
--   average_order_value   Panier moyen = CA des ventes ÷ commandes de vente.
--   identified_customers  Clients distincts ayant au moins une commande de vente (identifiant connu).
--   repeat_customer_rate  Part des clients identifiés ayant passé au moins 2 commandes distinctes
--                         dans la sélection.
-- Les ratios valent NULL lorsque leur dénominateur est nul (sélection vide).
WITH selection AS (
    SELECT * FROM filtered_lines($start_date, $end_date, $countries, $stock_codes)
),
sales AS (
    SELECT * FROM selection WHERE line_type = 'vente'
),
cancellations AS (
    SELECT * FROM selection WHERE line_type = 'annulation'
),
orders_per_customer AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS orders
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
totals AS (
    SELECT
        (SELECT COALESCE(SUM(amount), 0) FROM sales)                         AS gross_sales,
        (SELECT COALESCE(-SUM(amount), 0) FROM cancellations)                AS cancellations_amount,
        (SELECT COUNT(DISTINCT invoice_no) FROM sales)                       AS orders,
        (SELECT COUNT(*) FROM sales)                                         AS sales_lines,
        (SELECT COUNT(*) FROM cancellations)                                 AS cancellation_lines,
        (SELECT COUNT(DISTINCT invoice_no) FROM cancellations)               AS cancellation_documents,
        (SELECT COUNT(*) FROM orders_per_customer)                           AS identified_customers,
        (SELECT COUNT(*) FROM orders_per_customer WHERE orders >= 2)         AS repeat_customers,
        (SELECT COALESCE(SUM(amount), 0) FROM sales WHERE customer_id IS NOT NULL)
                                                                             AS identified_gross_sales,
        (SELECT COUNT(DISTINCT invoice_no) FROM sales WHERE customer_id IS NOT NULL)
                                                                             AS identified_orders
)
SELECT
    gross_sales,
    cancellations_amount,
    gross_sales - cancellations_amount                               AS net_sales,
    orders,
    gross_sales / NULLIF(orders, 0)                                  AS average_order_value,
    identified_customers,
    repeat_customers,
    repeat_customers::DOUBLE / NULLIF(identified_customers, 0)       AS repeat_customer_rate,
    cancellations_amount / NULLIF(gross_sales, 0)                    AS cancellations_to_sales_ratio,
    identified_gross_sales / NULLIF(gross_sales, 0)                  AS identified_sales_share,
    identified_orders::DOUBLE / NULLIF(orders, 0)                    AS identified_orders_share,
    sales_lines,
    cancellation_lines,
    cancellation_documents
FROM totals;
