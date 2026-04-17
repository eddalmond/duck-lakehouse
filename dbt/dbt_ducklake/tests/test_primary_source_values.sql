SELECT
    _source_file,
    primary_source_raw,
    'PRIMARY_SOURCE must be TRUE or FALSE (case-sensitive)' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE primary_source_raw IS NOT NULL
  AND primary_source_raw NOT IN ('TRUE', 'FALSE')