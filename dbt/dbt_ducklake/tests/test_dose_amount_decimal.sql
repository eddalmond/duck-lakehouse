SELECT
    _source_file,
    dose_amount_raw,
    'DOSE_AMOUNT must be a valid decimal number' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE dose_amount_raw IS NOT NULL
  AND TRIM(dose_amount_raw) != ''
  AND TRY_CAST(dose_amount_raw AS DOUBLE) IS NULL