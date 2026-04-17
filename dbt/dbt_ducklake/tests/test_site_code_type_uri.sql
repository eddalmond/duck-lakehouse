-- SITE_CODE_TYPE_URI must be the NHS ODS organization code URI
-- Per v5 spec: Mandatory, should be https://fhir.nhs.uk/Id/ods-organization-code

SELECT
    _source_file,
    SITE_CODE_TYPE_URI,
    'SITE_CODE_TYPE_URI should be NHS ODS URI' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE SITE_CODE_TYPE_URI IS NOT NULL
  AND SITE_CODE_TYPE_URI NOT LIKE 'https://fhir.nhs.uk/Id/ods-organization-code%'