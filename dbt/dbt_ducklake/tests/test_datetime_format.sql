SELECT
    _source_file,
    date_and_time_raw,
    'DATE_AND_TIME must be YYYYMMDDThhmmsszz format' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE date_and_time_raw IS NOT NULL
  AND date_and_time_raw !~ '^[0-9]{4}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])T[0-9]{2}[0-9]{2}[0-9]{2}[0-9]{2}$'