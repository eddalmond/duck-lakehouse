-- PERSON_POSTCODE must follow UK postcode format (outward inward separated by space)
-- Per v5 spec: String(8), Mandatory, outward code space inward code

SELECT
    _source_file,
    PERSON_POSTCODE,
    'PERSON_POSTCODE must match UK postcode format' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE PERSON_POSTCODE IS NOT NULL
  AND PERSON_POSTCODE !~ '^[A-Z]{1,2}[0-9][0-9A-Z]? [0-9][A-Z]{2}$'