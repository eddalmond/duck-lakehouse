SELECT validation_rule, failure_count FROM (
    SELECT
        'NHS number not 10 digits' AS validation_rule,
        COUNT(*) AS failure_count
    FROM {{ ref('int_vaccinations_parsed') }}
    WHERE nhs_number IS NOT NULL AND LENGTH(nhs_number) != 10

    UNION ALL

    SELECT
        'DOB not YYYYMMDD (parse failed)' AS validation_rule,
        COUNT(*) AS failure_count
    FROM {{ ref('int_vaccinations_parsed') }}
    WHERE person_dob IS NULL

    UNION ALL

    SELECT
        'Invalid vaccine procedure code (not numeric)' AS validation_rule,
        COUNT(*) AS failure_count
    FROM {{ ref('int_vaccinations_parsed') }}
    WHERE vaccination_procedure_code IS NOT NULL
      AND vaccination_procedure_code !~ '^[0-9]+$'

    UNION ALL

    SELECT
        'Dose sequence out of range (1-9)' AS validation_rule,
        COUNT(*) AS failure_count
    FROM {{ ref('int_vaccinations_parsed') }}
    WHERE dose_sequence IS NOT NULL AND (dose_sequence < 1 OR dose_sequence > 9)

    UNION ALL

    SELECT
        'Site code empty for primary source' AS validation_rule,
        COUNT(*) AS failure_count
    FROM {{ ref('int_vaccinations_parsed') }}
    WHERE primary_source = TRUE AND (site_code IS NULL OR TRIM(site_code) = '')
) checks
WHERE failure_count > 0