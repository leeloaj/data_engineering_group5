-- One row per track x artist name, from the artist names in each track's most
-- recent chart row. Chart files list several artists as one comma-separated
-- string ("KAROL G, Judeline, rusowsky"); artist_order 1 is the first-listed.
-- Used for tracks without Spotify metadata, so per-artist questions also work
-- for the historical charts. A name that itself contains a comma is split.

with latest_chart_row as (

    select track_id, artist_names
    from {{ ref('stg_chart_tracks') }}
    where artist_names is not null

),

split as (

    select
        latest_chart_row.track_id,
        trim(artist.name)                   as artist_name,
        cast(artist.ordinality as integer)  as position_in_list
    from latest_chart_row
    cross join lateral regexp_split_to_table(latest_chart_row.artist_names, ',')
        with ordinality as artist (name, ordinality)

),

deduplicated as (

    -- Keep the first position if a name is listed twice for the same track.
    select distinct on (track_id, artist_name)
        track_id,
        artist_name,
        position_in_list
    from split
    where artist_name <> ''
    order by track_id, artist_name, position_in_list

)

select
    track_id,
    artist_name,
    cast(row_number() over (partition by track_id order by position_in_list) as integer)
        as artist_order
from deduplicated
