-- UNIQUE_ID + UNIQUE_ID_URI combination must be unique per record
-- Per v5 spec: UNIQUE_ID must be globally unique when combined with UNIQUE_ID_URI

SELECT
    UNIQUE_ID,
    UNIQUE_ID_URI,
    COUNT(*) AS record_count
FROM {{ ref('stg_vaccinations') }}
WHERE UNIQUE_ID IS NOT NULL
  AND UNIQUE_ID_URI IS NOT NULL
GROUP BY UNIQUE_ID, UNIQUE_ID_URI
HAVING COUNT(*) > 1