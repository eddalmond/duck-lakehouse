{{ config(materialized='table', schema='intermediate') }}

WITH staged AS (
    SELECT * FROM {{ ref('stg_vaccinations') }}
),

parsed AS (
    SELECT
        _source_file,
        _loaded_at,
        nhs_number,
        person_forename,
        person_surname,

        strptime(person_dob_raw, '%Y%m%d')::DATE AS person_dob,
        person_gender_code,
        person_postcode,

        CASE
            WHEN LENGTH(date_and_time_raw) >= 15
            THEN strptime(SUBSTR(date_and_time_raw, 1, 15), '%Y%m%dT%H%M%S')::TIMESTAMP
            ELSE strptime(date_and_time_raw, '%Y%m%d')::TIMESTAMP
        END AS vaccination_datetime,

        site_code,
        site_code_type_uri,
        unique_id,
        unique_id_uri,

        LOWER(action_flag) AS action_flag,

        performing_professional_forename,
        performing_professional_surname,

        strptime(recorded_date_raw, '%Y%m%d')::DATE AS recorded_date,

        UPPER(primary_source_raw) = 'TRUE' AS primary_source,

        vaccination_procedure_code,
        vaccination_procedure_term,
        TRY_CAST(dose_sequence_raw AS INTEGER) AS dose_sequence,
        vaccine_product_code,
        vaccine_product_term,
        vaccine_manufacturer,
        batch_number,

        strptime(expiry_date_raw, '%Y%m%d')::DATE AS expiry_date,

        site_of_vaccination_code,
        site_of_vaccination_term,
        route_of_vaccination_code,
        route_of_vaccination_term,

        TRY_CAST(dose_amount_raw AS DOUBLE) AS dose_amount,
        dose_unit_code,
        dose_unit_term,
        indication_code,
        location_code,
        location_code_type_uri
    FROM staged
)

SELECT * FROM parsed