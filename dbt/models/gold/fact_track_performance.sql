-- Grain: one track x one region x one calendar date, from the daily Top 200
-- chart (weekly and Viral 50 charts are a different grain and are left out).
--
-- Incremental: each run processes rows ingested since the last run, plus rows
-- whose primary artist has changed (e.g. the track was enriched after its
-- chart rows were loaded). delete+insert on the grain key replaces existing
-- rows, so reruns do not create duplicates.

{{
    config(
        materialized='incremental',
        unique_key=['track_key', 'country_key', 'date_key'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}

with primary_artist as (

    select track_key, artist_key
    from {{ ref('bridge_track_artist') }}
    where is_primary

),

charts as (

    select
        {{ hash_key('track_id') }} as track_key,
        *
    from {{ ref('stg_chart_entries') }}
    where chart_type = 'top200'

),

{% if is_incremental() %}
stale_tracks as (

    -- Tracks whose stored artist_key no longer matches the current primary artist.
    select distinct existing.track_key
    from {{ this }} as existing
    left join primary_artist
        on primary_artist.track_key = existing.track_key
    where existing.artist_key
        <> coalesce(primary_artist.artist_key, {{ unknown_artist_key() }})

),
{% endif %}

to_load as (

    select * from charts
    {% if is_incremental() %}
    where ingested_at > (select coalesce(max(ingested_at), '-infinity') from {{ this }})
       or track_key in (select track_key from stale_tracks)
    {% endif %}

)

select
    to_load.track_key,
    coalesce(primary_artist.artist_key, {{ unknown_artist_key() }}) as artist_key,
    -- Left joins so an unknown region/date shows up as a NULL key and fails
    -- the not_null / relationships tests instead of being silently dropped.
    d.date_key,
    c.country_key,
    to_load.streams,
    to_load.chart_position,
    to_load.ingested_at
from to_load
left join primary_artist
    on primary_artist.track_key = to_load.track_key
left join {{ ref('dim_date') }} as d
    on d.full_date = to_load.chart_date
left join {{ ref('dim_country') }} as c
    on c.country_code = to_load.region_code
