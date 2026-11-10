-- Warns if the local-testing fixture (dev/fake_spotify_enrichment.sql) has been
-- loaded, so fake Spotify data is never mistaken for real data.
-- Remove it with: delete from bronze.track_enrichment where raw_json ? '_fake';
{{ config(severity='warn') }}

select spotify_track_id, input_date
from {{ source('bronze', 'track_enrichment') }}
where raw_json ? '_fake'
