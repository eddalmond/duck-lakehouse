{{ config(materialized='table', schema='marts') }}

WITH deduped AS (
    SELECT * FROM {{ ref('int_vaccinations_deduplicated') }}
),

sites AS (
    SELECT DISTINCT
        site_code,
        site_code_type_uri,
        location_code,
        location_code_type_uri
    FROM deduped
)

SELECT
    ROW_NUMBER() OVER (ORDER BY site_code) AS site_id,
    site_code,
    site_code_type_uri,
    location_code,
    location_code_type_uri,
    CURRENT_TIMESTAMP AS _valid_from,
    TRUE AS _is_current
FROM sites