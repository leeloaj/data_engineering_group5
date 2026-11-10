-- One row per Spotify track that has appeared on any chart (SCD Type 1:
-- rebuilt on every run, so attributes show the latest known values).
--
-- Tracks that have not been enriched yet still get a row, titled from the
-- chart data, so every fact row has a track. Their Spotify-only attributes
-- are NULL until enrichment runs (has_spotify_metadata = false).

with chart_tracks as (

    select distinct on (track_id)
        track_id,
        track_name
    from {{ ref('stg_chart_entries') }}
    order by track_id, chart_date desc, ingested_at desc

),

spotify as (

    select * from {{ ref('stg_spotify_track_snapshots') }}
    where is_latest

),

audio as (

    select * from {{ ref('stg_audio_features') }}

)

select
    {{ hash_key('chart_tracks.track_id') }}            as track_key,
    chart_tracks.track_id,
    coalesce(spotify.track_title, chart_tracks.track_name, 'Unknown track') as track_title,
    spotify.album_name,
    spotify.release_date,
    spotify.release_date_precision,
    spotify.duration_ms,
    spotify.explicit,
    spotify.popularity,
    spotify.snapshot_date                               as popularity_snapshot_date,
    case when audio.track_id is not null then
        jsonb_build_object(
            'danceability',     audio.danceability,
            'energy',           audio.energy,
            'valence',          audio.valence,
            'tempo',            audio.tempo,
            'loudness',         audio.loudness,
            'acousticness',     audio.acousticness,
            'instrumentalness', audio.instrumentalness,
            'liveness',         audio.liveness,
            'speechiness',      audio.speechiness,
            'key',              audio.musical_key,
            'mode',             audio.mode
        )
    end                                                 as audio_features,
    spotify.track_id is not null                        as has_spotify_metadata
from chart_tracks
left join spotify
    on spotify.track_id = chart_tracks.track_id
left join audio
    on audio.track_id = chart_tracks.track_id
