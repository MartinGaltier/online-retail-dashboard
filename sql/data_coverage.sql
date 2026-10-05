-- Première et dernière dates présentes dans les lignes utilisées par les indicateurs.
SELECT
    MIN(invoice_date) AS first_date,
    MAX(invoice_date) AS last_date
FROM lines
WHERE line_type IN ('vente', 'annulation');
