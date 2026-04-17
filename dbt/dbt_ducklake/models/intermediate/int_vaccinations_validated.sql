{{ config(materialized='table', schema='intermediate') }}

WITH parsed AS (
    SELECT * FROM {{ ref('int_vaccinations_parsed') }}
),

validated AS (
    SELECT
        *,
        CASE
            WHEN nhs_number IS NULL OR TRIM(nhs_number) = '' THEN 'missing_mandatory'
            WHEN LENGTH(nhs_number) != 10 THEN 'invalid_nhs_number_length'
            WHEN person_forename IS NULL OR TRIM(person_forename) = '' THEN 'missing_mandatory'
            WHEN person_surname IS NULL OR TRIM(person_surname) = '' THEN 'missing_mandatory'
            WHEN person_dob IS NULL THEN 'invalid_dob'
            WHEN person_gender_code NOT IN ('0', '1', '2', '9') THEN 'invalid_gender_code'
            WHEN person_postcode IS NULL OR TRIM(person_postcode) = '' THEN 'missing_mandatory'
            WHEN vaccination_datetime IS NULL THEN 'invalid_datetime'
            WHEN site_code IS NULL OR TRIM(site_code) = '' THEN 'missing_mandatory'
            WHEN unique_id IS NULL OR TRIM(unique_id) = '' THEN 'missing_mandatory'
            WHEN action_flag NOT IN ('new', 'update', 'delete') THEN 'invalid_action_flag'
            WHEN primary_source IS NULL THEN 'invalid_primary_source'
            WHEN vaccination_procedure_code IS NULL OR TRIM(vaccination_procedure_code) = '' THEN 'missing_mandatory'
            WHEN dose_sequence IS NULL THEN 'invalid_dose_sequence'
            WHEN location_code IS NULL OR TRIM(location_code) = '' THEN 'missing_mandatory'
            ELSE 'valid'
        END AS validation_status
    FROM parsed
)

SELECT * FROM validated