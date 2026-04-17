{{ config(materialized='table', schema='marts') }}

WITH deduped AS (
    SELECT * FROM {{ ref('int_vaccinations_deduplicated') }}
),

by_site_date AS (
    SELECT
        site_code,
        site_code_type_uri,
        location_code,
        location_code_type_uri,
        CAST(vaccination_datetime AS DATE) AS vaccination_date,
        vaccination_procedure_code,
        dose_sequence,
        COUNT(*) AS event_count,
        COUNT(DISTINCT nhs_number) AS unique_patients
    FROM deduped
    WHERE validation_status = 'valid'
      AND action_flag != 'delete'
    GROUP BY
        site_code,
        site_code_type_uri,
        location_code,
        location_code_type_uri,
        CAST(vaccination_datetime AS DATE),
        vaccination_procedure_code,
        dose_sequence
),

by_type AS (
    SELECT
        vaccination_procedure_code,
        vaccination_procedure_term,
        vaccine_product_code,
        vaccine_product_term,
        vaccine_manufacturer,
        dose_sequence,
        CAST(vaccination_datetime AS DATE) AS vaccination_date,
        COUNT(*) AS event_count,
        COUNT(DISTINCT nhs_number) AS unique_patients,
        COUNT(DISTINCT site_code) AS unique_sites
    FROM deduped
    WHERE validation_status = 'valid'
      AND action_flag != 'delete'
    GROUP BY
        vaccination_procedure_code,
        vaccination_procedure_term,
        vaccine_product_code,
        vaccine_product_term,
        vaccine_manufacturer,
        dose_sequence,
        CAST(vaccination_datetime AS DATE)
),

final AS (
    SELECT
        'site_date' AS summary_type,
        site_code,
        site_code_type_uri,
        location_code,
        location_code_type_uri,
        vaccination_date,
        vaccination_procedure_code,
        NULL AS vaccine_product_code,
        NULL AS vaccine_manufacturer,
        dose_sequence,
        event_count,
        unique_patients,
        NULL AS unique_sites,
        CURRENT_TIMESTAMP AS _valid_from,
        TRUE AS _is_current
    FROM by_site_date

    UNION ALL

    SELECT
        'vaccine_type' AS summary_type,
        NULL AS site_code,
        NULL AS site_code_type_uri,
        NULL AS location_code,
        NULL AS location_code_type_uri,
        vaccination_date,
        vaccination_procedure_code,
        vaccine_product_code,
        vaccine_manufacturer,
        dose_sequence,
        event_count,
        unique_patients,
        unique_sites,
        CURRENT_TIMESTAMP AS _valid_from,
        TRUE AS _is_current
    FROM by_type
)

SELECT * FROM final