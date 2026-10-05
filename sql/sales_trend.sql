-- Évolution des ventes, des annulations et du CA net par période.
--
-- Paramètre supplémentaire
--   grain : 'day', 'week' (semaines commençant le lundi) ou 'month'.
-- Les périodes sans aucune ligne dans la sélection n'apparaissent pas.
-- Montants en livres sterling (GBP).
SELECT
    date_trunc($grain, invoice_date)::DATE                                    AS period_start,
    COALESCE(SUM(amount) FILTER (WHERE line_type = 'vente'), 0)               AS gross_sales,
    COALESCE(-SUM(amount) FILTER (WHERE line_type = 'annulation'), 0)         AS cancellations_amount,
    SUM(amount)                                                               AS net_sales,
    COUNT(DISTINCT invoice_no) FILTER (WHERE line_type = 'vente')             AS orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE line_type = 'vente')            AS identified_customers
FROM filtered_lines($start_date, $end_date, $countries, $stock_codes)
GROUP BY period_start
ORDER BY period_start;
