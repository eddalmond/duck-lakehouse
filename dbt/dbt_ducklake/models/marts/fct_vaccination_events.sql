{{ config(materialized='table', schema='marts') }}

WITH deduped AS (
    SELECT * FROM {{ ref('int_vaccinations_deduplicated') }}
),

final AS (
    SELECT
        unique_id AS vaccination_event_id,
        nhs_number,
        person_forename,
        person_surname,
        person_dob,
        person_gender_code,
        person_postcode,
        vaccination_datetime,
        site_code,
        site_code_type_uri,
        unique_id_uri,
        action_flag,
        performing_professional_forename,
        performing_professional_surname,
        recorded_date,
        primary_source,
        vaccination_procedure_code,
        vaccination_procedure_term,
        dose_sequence,
        vaccine_product_code,
        vaccine_product_term,
        vaccine_manufacturer,
        batch_number,
        expiry_date,
        site_of_vaccination_code,
        site_of_vaccination_term,
        route_of_vaccination_code,
        route_of_vaccination_term,
        dose_amount,
        dose_unit_code,
        dose_unit_term,
        indication_code,
        location_code,
        location_code_type_uri,
        CURRENT_TIMESTAMP AS _valid_from,
        TRUE AS _is_current,
        _loaded_at
    FROM deduped
)

SELECT * FROM final