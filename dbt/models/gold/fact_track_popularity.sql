-- Spotify popularity history for BQ2. Grain: one track x one snapshot date.
-- dim_track.popularity holds only the latest score (SCD Type 1); this table
-- keeps every score the enrichment runs have recorded.

select
    {{ hash_key('track_id') }}                              as track_key,
    cast(to_char(snapshot_date, 'YYYYMMDD') as integer)     as date_key,
    popularity
from {{ ref('stg_spotify_track_snapshots') }}
where popularity is not null
