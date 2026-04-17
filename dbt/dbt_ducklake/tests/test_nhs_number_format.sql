-- NHS number must be exactly 10 numeric digits
-- Per v5 spec: NHS_NUMBER is a String(10), Required, validated with no padding

SELECT
    _source_file,
    NHS_NUMBER,
    'NHS number must be 10 digits' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE NHS_NUMBER IS NOT NULL
  AND (
    LENGTH(TRIM(NHS_NUMBER)) != 10
    OR NHS_NUMBER !~ '^[0-9]{10}$'
  )