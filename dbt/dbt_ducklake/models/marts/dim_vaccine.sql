{{ config(materialized='table', schema='marts') }}

WITH deduped AS (
    SELECT * FROM {{ ref('int_vaccinations_deduplicated') }}
),

vaccines AS (
    SELECT DISTINCT
        vaccine_product_code,
        vaccine_product_term,
        vaccine_manufacturer,
        dose_unit_code,
        dose_unit_term
    FROM deduped
    WHERE vaccine_product_code IS NOT NULL
)

SELECT
    ROW_NUMBER() OVER (ORDER BY vaccine_product_code) AS vaccine_id,
    vaccine_product_code,
    vaccine_product_term,
    vaccine_manufacturer,
    dose_unit_code,
    dose_unit_term,
    CURRENT_TIMESTAMP AS _valid_from,
    TRUE AS _is_current
FROM vaccines