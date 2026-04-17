-- VACCINATION_PROCEDURE_CODE must be a valid SNOMED-CT code (numeric)
-- Per v5 spec: SNOMED-CT concept ID, Mandatory

SELECT
    _source_file,
    VACCINATION_PROCEDURE_CODE,
    'VACCINATION_PROCEDURE_CODE must be numeric SNOMED code' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE VACCINATION_PROCEDURE_CODE IS NOT NULL
  AND VACCINATION_PROCEDURE_CODE !~ '^[0-9]+$'