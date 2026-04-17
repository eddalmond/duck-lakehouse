SELECT
    _source_file,
    nhs_number,
    person_forename,
    person_surname,
    person_dob_raw,
    person_gender_code,
    person_postcode,
    date_and_time_raw,
    site_code,
    unique_id,
    unique_id_uri,
    action_flag,
    recorded_date_raw,
    primary_source_raw,
    vaccination_procedure_code,
    location_code,
    location_code_type_uri
FROM {{ ref('stg_vaccinations') }}
WHERE TRIM(nhs_number) = ''
   OR TRIM(person_forename) = ''
   OR TRIM(person_surname) = ''
   OR TRIM(person_dob_raw) = ''
   OR TRIM(person_gender_code) = ''
   OR TRIM(person_postcode) = ''
   OR TRIM(date_and_time_raw) = ''
   OR TRIM(site_code) = ''
   OR TRIM(unique_id) = ''
   OR TRIM(unique_id_uri) = ''
   OR TRIM(action_flag) = ''
   OR TRIM(recorded_date_raw) = ''
   OR TRIM(primary_source_raw) = ''
   OR TRIM(vaccination_procedure_code) = ''
   OR TRIM(location_code) = ''
   OR TRIM(location_code_type_uri) = ''