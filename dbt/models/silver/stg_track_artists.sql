-- One row per track x credited artist, used by dim_artist and
-- bridge_track_artist. Spotify artists are used when the track has Spotify
-- metadata; otherwise the artist names from the chart files are used, with
-- artist_id 'chart:<name>' because the charts carry no Spotify artist ID.
-- When a track is enriched later, its Spotify artists replace the chart names.

with spotify as (

    select
        track_id,
        artist_id,
        artist_name,
        artist_order,
        true as has_spotify_metadata,
        snapshot_date
    from {{ ref('stg_spotify_track_artists') }}

),

chart as (

    select
        chart_artists.track_id,
        'chart:' || chart_artists.artist_name   as artist_id,
        chart_artists.artist_name,
        chart_artists.artist_order,
        false                                   as has_spotify_metadata,
        cast(null as date)                      as snapshot_date
    from {{ ref('stg_chart_track_artists') }} as chart_artists
    where not exists (
        select 1 from spotify where spotify.track_id = chart_artists.track_id
    )

)

select * from spotify
union all
select * from chart
