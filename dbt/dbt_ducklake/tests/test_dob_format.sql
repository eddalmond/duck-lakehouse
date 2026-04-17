SELECT
    _source_file,
    person_dob_raw,
    'PERSON_DOB must be YYYYMMDD format' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE person_dob_raw IS NOT NULL
  AND person_dob_raw !~ '^[0-9]{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'