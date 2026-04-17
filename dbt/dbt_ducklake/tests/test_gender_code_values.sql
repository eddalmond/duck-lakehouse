-- PERSON_GENDER_CODE must be one of 0, 1, 2, or 9
-- Per v5 spec: String with values 0 (not known), 1 (male), 2 (female), 9 (not applicable)

SELECT
    _source_file,
    PERSON_GENDER_CODE,
    'PERSON_GENDER_CODE must be 0, 1, 2, or 9' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE PERSON_GENDER_CODE IS NOT NULL
  AND PERSON_GENDER_CODE NOT IN ('0', '1', '2', '9')