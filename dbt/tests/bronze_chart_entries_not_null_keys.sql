SELECT
    source,
    input_file,
    spotify_track_id,
    region,
    chart_date
FROM {{ source('bronze', 'chart_entries') }}
WHERE spotify_track_id IS NULL
   OR TRIM(spotify_track_id) = ''
   OR chart_date IS NULL
   OR region IS NULL
   OR TRIM(region) = ''
