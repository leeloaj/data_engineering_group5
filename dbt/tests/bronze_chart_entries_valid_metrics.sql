SELECT
    source,
    spotify_track_id,
    region,
    chart_type,
    chart_date,
    rank,
    streams
FROM {{ source('bronze', 'chart_entries') }}
WHERE streams < 0
   OR rank < 1
   OR rank > 200
