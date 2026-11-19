-- One row per artist credited on a charted track (SCD Type 1), plus an
-- "Unknown artist" row for tracks whose chart row has no artist name.
-- Artists of enriched tracks come from Spotify; the others come from the
-- chart files (artist_id 'chart:<name>', has_spotify_metadata = false).
--
-- artist_genres is NULL for now: genres come from Spotify's artist endpoint,
-- which the ingestion does not call yet.

with artists as (

    select distinct on (artist_id)
        artist_id,
        artist_name,
        has_spotify_metadata
    from {{ ref('stg_track_artists') }}
    order by artist_id, snapshot_date desc nulls last

)

select
    {{ hash_key('artist_id') }}     as artist_key,
    artist_id,
    artist_name,
    cast(null as varchar(500))      as artist_genres,
    has_spotify_metadata
from artists

union all

select
    {{ unknown_artist_key() }}      as artist_key,
    'unknown'                       as artist_id,
    'Unknown artist'                as artist_name,
    cast(null as varchar(500))      as artist_genres,
    false                           as has_spotify_metadata
