{{ config(materialized='table', schema='marts') }}

WITH deduped AS (
    SELECT * FROM {{ ref('int_vaccinations_deduplicated') }}
),

patients AS (
    SELECT
        nhs_number,
        person_forename,
        person_surname,
        person_dob,
        person_gender_code,
        person_postcode,
        _loaded_at
    FROM deduped
),

numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY nhs_number ORDER BY _loaded_at DESC) AS rn
    FROM patients
),

deduped_patients AS (
    SELECT * FROM numbered WHERE rn = 1
)

SELECT
    ROW_NUMBER() OVER (ORDER BY nhs_number) AS patient_id,
    nhs_number,
    person_forename,
    person_surname,
    person_dob,
    person_gender_code,
    person_postcode,
    CURRENT_TIMESTAMP AS _valid_from,
    TRUE AS _is_current
FROM deduped_patients