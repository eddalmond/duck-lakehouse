{% test v5_nhs_number_length(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE LENGTH({{ column_name }}) != 10
  OR {{ column_name }} !~ '^[0-9]{10}$'

{% endtest %}


{% test v5_date_format(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} !~ '^[0-9]{8}$'

{% endtest %}


{% test v5_datetime_format(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} !~ '^[0-9]{8}T[0-9]{6,8}$'

{% endtest %}


{% test v5_snomed_format(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} !~ '^[0-9]+$'

{% endtest %}


{% test v5_action_flag_values(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE LOWER({{ column_name }}) NOT IN ('new', 'update', 'delete')

{% endtest %}


{% test v5_primary_source_boolean(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE UPPER({{ column_name }}) NOT IN ('TRUE', 'FALSE')

{% endtest %}


{% test v5_gender_code_values(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} NOT IN ('0', '1', '2', '9')

{% endtest %}


{% test v5_postcode_format(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} !~ '^[A-Z]{1,2}[0-9][0-9A-Z]?[[:space:]][0-9][A-Z]{2}$'

{% endtest %}


{% test v5_no_pipe_in_fields(model) %}

SELECT *
FROM {{ model }}
WHERE {%- for col in adapter.get_columns_in_relation(model) -%}
    {{ col.name }} LIKE '%|%'
    {%- if not loop.last %} OR {% endif -%}
{%- endfor %}

{% endtest %}


{% test v5_no_null_mandatory(model) %}

WITH mandatory_fields AS (
    SELECT *
    FROM {{ model }}
    WHERE NHS_NUMBER IS NULL OR TRIM(NHS_NUMBER) = ''
       OR PERSON_FORENAME IS NULL OR TRIM(PERSON_FORENAME) = ''
       OR PERSON_SURNAME IS NULL OR TRIM(PERSON_SURNAME) = ''
       OR PERSON_DOB IS NULL OR TRIM(PERSON_DOB) = ''
       OR PERSON_GENDER_CODE IS NULL OR TRIM(PERSON_GENDER_CODE) = ''
       OR PERSON_POSTCODE IS NULL OR TRIM(PERSON_POSTCODE) = ''
       OR DATE_AND_TIME IS NULL OR TRIM(DATE_AND_TIME) = ''
       OR SITE_CODE IS NULL OR TRIM(SITE_CODE) = ''
       OR UNIQUE_ID IS NULL OR TRIM(UNIQUE_ID) = ''
       OR ACTION_FLAG IS NULL OR TRIM(ACTION_FLAG) = ''
       OR RECORDED_DATE IS NULL OR TRIM(RECORDED_DATE) = ''
       OR PRIMARY_SOURCE IS NULL OR TRIM(PRIMARY_SOURCE) = ''
       OR VACCINATION_PROCEDURE_CODE IS NULL OR TRIM(VACCINATION_PROCEDURE_CODE) = ''
       OR LOCATION_CODE IS NULL OR TRIM(LOCATION_CODE) = ''
)

SELECT COUNT(*) AS null_mandatory_count FROM mandatory_fields

{% endtest %}