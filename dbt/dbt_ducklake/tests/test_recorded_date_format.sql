SELECT
    _source_file,
    recorded_date_raw,
    'RECORDED_DATE must be YYYYMMDD format' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE recorded_date_raw IS NOT NULL
  AND recorded_date_raw !~ '^[0-9]{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'