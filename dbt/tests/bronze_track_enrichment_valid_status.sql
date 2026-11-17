SELECT
    source,
    input_date,
    market,
    spotify_track_id,
    status
FROM {{ source('bronze', 'track_enrichment') }}
WHERE spotify_track_id IS NULL
   OR TRIM(spotify_track_id) = ''
   OR status NOT IN ('found', 'missing')
