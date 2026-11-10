-- One row per Spotify artist credited on an enriched track (SCD Type 1),
-- plus an "Unknown artist" row for tracks without Spotify metadata yet.
--
-- artist_genres is NULL for now: genres come from Spotify's artist endpoint,
-- which the ingestion does not call yet.

with artists as (

    select distinct on (artist_id)
        artist_id,
        artist_name
    from {{ ref('stg_spotify_track_artists') }}
    order by artist_id, snapshot_date desc

)

select
    {{ hash_key('artist_id') }}     as artist_key,
    artist_id,
    artist_name,
    cast(null as varchar(500))      as artist_genres
from artists

union all

select
    {{ unknown_artist_key() }}      as artist_key,
    'unknown'                       as artist_id,
    'Unknown artist'                as artist_name,
    cast(null as varchar(500))      as artist_genres
