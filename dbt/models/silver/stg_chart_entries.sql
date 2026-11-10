-- Cleaned chart observations from both chart sources.
--
-- Bronze already types and normalises the key columns. Here we pull track and
-- artist names out of raw_row (live CSVs and the Kaggle archive name them
-- differently) and pick one row per date x region x chart type x track when
-- the live feed and the Kaggle archive both cover the same chart.

with source as (

    select * from {{ source('bronze', 'chart_entries') }}

),

cleaned as (

    select
        chart_date,
        region                                                          as region_code,
        chart_type,
        spotify_track_id                                                as track_id,
        nullif(trim(coalesce(raw_row ->> 'track_name', raw_row ->> 'title')), '')      as track_name,
        nullif(trim(coalesce(raw_row ->> 'artist_names', raw_row ->> 'artist')), '')   as artist_names,
        rank                                                            as chart_position,
        streams,
        source                                                          as chart_source,
        input_file,
        ingested_at
    from source

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by chart_date, region_code, chart_type, track_id
            -- Live Spotify Charts data wins over the Kaggle archive.
            order by (chart_source = 'spotify_charts') desc, ingested_at desc
        ) as row_num
    from cleaned

)

select
    chart_date,
    region_code,
    chart_type,
    track_id,
    track_name,
    artist_names,
    chart_position,
    streams,
    chart_source,
    input_file,
    ingested_at
from deduplicated
where row_num = 1
