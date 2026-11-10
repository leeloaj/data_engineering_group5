-- Links each track to every credited artist, so collaborations count for all
-- artists involved. fact_track_performance.artist_key holds only the primary
-- artist; join through this table to attribute a track to all its artists.

select
    {{ hash_key('track_id') }}      as track_key,
    {{ hash_key('artist_id') }}     as artist_key,
    artist_order,
    artist_order = 1                as is_primary
from {{ ref('stg_spotify_track_artists') }}
