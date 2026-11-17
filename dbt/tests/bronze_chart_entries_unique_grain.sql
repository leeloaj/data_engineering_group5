SELECT
    source,
    spotify_track_id,
    region,
    chart_type,
    chart_date,
    COUNT(*) AS record_count
FROM {{ source('bronze', 'chart_entries') }}
GROUP BY source, spotify_track_id, region, chart_type, chart_date
HAVING COUNT(*) > 1
