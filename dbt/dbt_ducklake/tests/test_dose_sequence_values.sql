SELECT
    _source_file,
    dose_sequence_raw,
    'DOSE_SEQUENCE must be 1-9' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE dose_sequence_raw IS NOT NULL
  AND dose_sequence_raw NOT IN ('1', '2', '3', '4', '5', '6', '7', '8', '9')