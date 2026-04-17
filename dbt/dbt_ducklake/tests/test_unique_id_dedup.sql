SELECT check_name, failure_count FROM (
    SELECT
        'Duplicate unique_id' AS check_name,
        COUNT(*) AS failure_count
    FROM (
        SELECT unique_id, COUNT(*) AS cnt
        FROM {{ ref('int_vaccinations_deduplicated') }}
        GROUP BY unique_id
        HAVING COUNT(*) > 1
    )

    UNION ALL

    SELECT
        'Multiple active records for same unique_id' AS check_name,
        COUNT(*) AS failure_count
    FROM {{ ref('fct_vaccination_events') }}
    WHERE vaccination_event_id IN (
        SELECT vaccination_event_id
        FROM {{ ref('fct_vaccination_events') }}
        WHERE _is_current = TRUE
        GROUP BY vaccination_event_id
        HAVING COUNT(*) > 1
    )
) checks
WHERE failure_count > 0