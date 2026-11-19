-- One row per track seen on any chart, with the track and artist names from
-- its most recent chart row. Stored as a table so the large chart history is
-- scanned once per run; dim_track and stg_chart_track_artists read from here.

{{ config(materialized='table') }}

select distinct on (track_id)
    track_id,
    track_name,
    artist_names,
    chart_date as last_chart_date
from {{ ref('stg_chart_entries') }}
order by track_id, chart_date desc, ingested_at desc
