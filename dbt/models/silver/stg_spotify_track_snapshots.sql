-- Spotify Web API track metadata, one row per track x snapshot date.
-- Every enrichment run is a new snapshot, which gives popularity history
-- (BQ2). If a date was fetched for several markets, the latest load wins.

with source as (

    select * from {{ source('bronze', 'track_enrichment') }}
    where source = 'spotify_web_api'
      and status = 'found'
      and raw_json is not null

),

parsed as (

    select
        spotify_track_id                                    as track_id,
        input_date                                          as snapshot_date,
        market,
        raw_json ->> 'name'                                 as track_title,
        cast(raw_json ->> 'duration_ms' as integer)         as duration_ms,
        cast(raw_json ->> 'explicit' as boolean)            as explicit,
        cast(raw_json ->> 'popularity' as integer)          as popularity,
        raw_json -> 'album' ->> 'id'                        as album_id,
        raw_json -> 'album' ->> 'name'                      as album_name,
        -- Spotify gives "2004", "2004-05" or "2004-05-17" depending on precision;
        -- year- and month-precision dates become the first day of that period.
        case raw_json -> 'album' ->> 'release_date_precision'
            when 'year'  then (raw_json -> 'album' ->> 'release_date') || '-01-01'
            when 'month' then (raw_json -> 'album' ->> 'release_date') || '-01'
            else raw_json -> 'album' ->> 'release_date'
        end                                                 as release_date_text,
        raw_json -> 'album' ->> 'release_date_precision'    as release_date_precision,
        raw_json -> 'artists'                               as artists,
        ingested_at
    from source

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by track_id, snapshot_date
            order by ingested_at desc
        ) as row_num
    from parsed

)

select
    track_id,
    snapshot_date,
    market,
    track_title,
    duration_ms,
    explicit,
    popularity,
    album_id,
    album_name,
    -- Some old tracks have placeholder dates such as "0000"; invalid or
    -- pre-1900 dates become NULL instead of failing the build.
    case
        when pg_input_is_valid(release_date_text, 'date')
         and left(release_date_text, 4) >= '1900'
        then cast(release_date_text as date)
    end                                                     as release_date,
    release_date_precision,
    artists,
    ingested_at,
    -- True for the newest snapshot of each track (used by the dimensions).
    snapshot_date = max(snapshot_date) over (partition by track_id) as is_latest
from deduplicated
where row_num = 1
