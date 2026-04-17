SELECT check_name, failure_count FROM (
    SELECT
        'NHS number length' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('stg_vaccinations') }}
    WHERE LENGTH(nhs_number) != 10 OR nhs_number !~ '^[0-9]{10}$'

    UNION ALL

    SELECT
        'Gender code values' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('stg_vaccinations') }}
    WHERE person_gender_code NOT IN ('0', '1', '2', '9')

    UNION ALL

    SELECT
        'Action flag values' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('stg_vaccinations') }}
    WHERE LOWER(action_flag) NOT IN ('new', 'update', 'delete')

    UNION ALL

    SELECT
        'Primary source values' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('stg_vaccinations') }}
    WHERE UPPER(primary_source_raw) NOT IN ('TRUE', 'FALSE')

    UNION ALL

    SELECT
        'Missing mandatory fields' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('stg_vaccinations') }}
    WHERE nhs_number IS NULL OR TRIM(nhs_number) = ''
       OR person_forename IS NULL OR TRIM(person_forename) = ''
       OR person_surname IS NULL OR TRIM(person_surname) = ''
       OR person_dob_raw IS NULL OR TRIM(person_dob_raw) = ''
       OR date_and_time_raw IS NULL OR TRIM(date_and_time_raw) = ''
       OR site_code IS NULL OR TRIM(site_code) = ''
       OR unique_id IS NULL OR TRIM(unique_id) = ''
       OR action_flag IS NULL OR TRIM(action_flag) = ''
) checks
WHERE failure_count > 0