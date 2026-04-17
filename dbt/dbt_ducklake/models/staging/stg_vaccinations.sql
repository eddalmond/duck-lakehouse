{{ config(materialized='table', schema='staging') }}

WITH source AS (
    SELECT * FROM {{ source('vaccination_lake', 'stg_vaccinations') }}
),

renamed AS (
    SELECT
        _source_file,
        _loaded_at,
        NHS_NUMBER AS nhs_number,
        PERSON_FORENAME AS person_forename,
        PERSON_SURNAME AS person_surname,
        PERSON_DOB AS person_dob_raw,
        PERSON_GENDER_CODE AS person_gender_code,
        PERSON_POSTCODE AS person_postcode,
        DATE_AND_TIME AS date_and_time_raw,
        SITE_CODE AS site_code,
        SITE_CODE_TYPE_URI AS site_code_type_uri,
        UNIQUE_ID AS unique_id,
        UNIQUE_ID_URI AS unique_id_uri,
        ACTION_FLAG AS action_flag,
        PERFORMING_PROFESSIONAL_FORENAME AS performing_professional_forename,
        PERFORMING_PROFESSIONAL_SURNAME AS performing_professional_surname,
        RECORDED_DATE AS recorded_date_raw,
        PRIMARY_SOURCE AS primary_source_raw,
        VACCINATION_PROCEDURE_CODE AS vaccination_procedure_code,
        VACCINATION_PROCEDURE_TERM AS vaccination_procedure_term,
        DOSE_SEQUENCE AS dose_sequence_raw,
        VACCINE_PRODUCT_CODE AS vaccine_product_code,
        VACCINE_PRODUCT_TERM AS vaccine_product_term,
        VACCINE_MANUFACTURER AS vaccine_manufacturer,
        BATCH_NUMBER AS batch_number,
        EXPIRY_DATE AS expiry_date_raw,
        SITE_OF_VACCINATION_CODE AS site_of_vaccination_code,
        SITE_OF_VACCINATION_TERM AS site_of_vaccination_term,
        ROUTE_OF_VACCINATION_CODE AS route_of_vaccination_code,
        ROUTE_OF_VACCINATION_TERM AS route_of_vaccination_term,
        DOSE_AMOUNT AS dose_amount_raw,
        DOSE_UNIT_CODE AS dose_unit_code,
        DOSE_UNIT_TERM AS dose_unit_term,
        INDICATION_CODE AS indication_code,
        LOCATION_CODE AS location_code,
        LOCATION_CODE_TYPE_URI AS location_code_type_uri
    FROM source
)

SELECT * FROM renamed