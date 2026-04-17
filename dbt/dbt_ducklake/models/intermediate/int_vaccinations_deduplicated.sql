{{ config(materialized='table', schema='intermediate') }}

WITH validated AS (
    SELECT * FROM {{ ref('int_vaccinations_validated') }}
),

deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY unique_id
            ORDER BY
                CASE action_flag
                    WHEN 'update' THEN 1
                    WHEN 'new' THEN 2
                    WHEN 'delete' THEN 3
                    ELSE 4
                END,
                COALESCE(vaccination_datetime, TIMESTAMP '1970-01-01') DESC,
                _loaded_at DESC
        ) AS _row_rank
    FROM validated
    WHERE validation_status = 'valid'
      AND action_flag != 'delete'
)

SELECT *
FROM deduplicated
WHERE _row_rank = 1