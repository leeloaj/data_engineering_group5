-- Chart-based popularity for BQ2. Grain: one track x one calendar date.
-- Measured from daily Top 200 performance: global position and streams, how
-- many countries the track charts in, and chart points across those countries.
--
-- Incremental: each run recomputes only the track x date pairs that received
-- new fact rows since the last run. delete+insert on the grain key replaces
-- existing rows, so reruns do not create duplicates.

{{
    config(
        materialized='incremental',
        unique_key=['track_key', 'date_key'],
        incremental_strategy='delete+insert',
        on_schema_change='fail'
    )
}}

with performance as (

    select
        f.track_key,
        f.date_key,
        f.streams,
        f.chart_position,
        f.ingested_at,
        c.country_code = 'GLOBAL' as is_global
    from {{ ref('fact_track_performance') }} as f
    join {{ ref('dim_country') }} as c
        on c.country_key = f.country_key

),

{% if is_incremental() %}
changed as (

    select distinct track_key, date_key
    from performance
    where ingested_at > (select coalesce(max(ingested_at), '-infinity') from {{ this }})

),
{% endif %}

to_load as (

    select performance.*
    from performance
    {% if is_incremental() %}
    join changed using (track_key, date_key)
    {% endif %}

)

select
    track_key,
    date_key,
    -- Worldwide chart (NULL when the track is not on the global chart that day).
    min(chart_position) filter (where is_global)                as global_chart_position,
    sum(streams) filter (where is_global)                       as global_streams,
    -- Country charts (GLOBAL left out to avoid double counting).
    count(*) filter (where not is_global)                       as countries_charted,
    min(chart_position) filter (where not is_global)            as best_country_position,
    sum(streams) filter (where not is_global)                   as country_streams,
    -- 200 points for #1, 1 point for #200, summed over all country charts.
    -- Combines reach and position in one number for comparing tracks over time.
    coalesce(sum(201 - chart_position) filter (where not is_global), 0)
                                                                as chart_points,
    max(ingested_at)                                            as ingested_at
from to_load
group by track_key, date_key
