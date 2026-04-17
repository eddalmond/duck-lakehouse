-- ACTION_FLAG must be new, update, or delete (case-insensitive per spec)
-- Per v5 spec: ACTION_FLAG values are new/update/delete, Mandatory

SELECT
    _source_file,
    ACTION_FLAG,
    'ACTION_FLAG must be new, update, or delete' AS violation
FROM {{ ref('stg_vaccinations') }}
WHERE ACTION_FLAG IS NOT NULL
  AND LOWER(TRIM(ACTION_FLAG)) NOT IN ('new', 'update', 'delete')