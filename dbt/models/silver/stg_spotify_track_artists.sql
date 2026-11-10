-- One row per track x credited artist, from each track's latest Spotify
-- snapshot. artist_order 1 is the primary (first-listed) artist.

select
    snapshots.track_id,
    artist.value ->> 'id'               as artist_id,
    artist.value ->> 'name'             as artist_name,
    cast(artist.ordinality as integer)  as artist_order,
    snapshots.snapshot_date
from {{ ref('stg_spotify_track_snapshots') }} as snapshots
cross join lateral jsonb_array_elements(snapshots.artists) with ordinality as artist (value, ordinality)
where snapshots.is_latest
  and artist.value ->> 'id' is not null
