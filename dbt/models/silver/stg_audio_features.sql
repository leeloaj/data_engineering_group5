-- ReccoBeats audio features, one row per track (latest snapshot wins).

with source as (

    select * from {{ source('bronze', 'track_enrichment') }}
    where source = 'reccobeats'
      and status = 'found'
      and raw_json is not null

),

features as (

    select
        source.spotify_track_id     as track_id,
        source.input_date           as snapshot_date,
        source.ingested_at,
        item.value                  as feature_json
    from source
    -- The response is {"content": [ ... ]}; ingestion has already checked
    -- that each item belongs to the requested track.
    cross join lateral jsonb_array_elements(source.raw_json -> 'content') as item (value)

),

latest as (

    select
        *,
        row_number() over (
            partition by track_id
            order by snapshot_date desc, ingested_at desc
        ) as row_num
    from features

)

select
    track_id,
    snapshot_date,
    cast(feature_json ->> 'danceability' as double precision)       as danceability,
    cast(feature_json ->> 'energy' as double precision)             as energy,
    cast(feature_json ->> 'valence' as double precision)            as valence,
    cast(feature_json ->> 'tempo' as double precision)              as tempo,
    cast(feature_json ->> 'loudness' as double precision)           as loudness,
    cast(feature_json ->> 'acousticness' as double precision)       as acousticness,
    cast(feature_json ->> 'instrumentalness' as double precision)   as instrumentalness,
    cast(feature_json ->> 'liveness' as double precision)           as liveness,
    cast(feature_json ->> 'speechiness' as double precision)        as speechiness,
    cast(feature_json ->> 'key' as integer)                         as musical_key,
    cast(feature_json ->> 'mode' as integer)                        as mode,
    feature_json ->> 'isrc'                                         as isrc
from latest
where row_num = 1
