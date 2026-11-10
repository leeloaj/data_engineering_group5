-- Static calendar table (SCD Type 0). Range is set by the dim_date_start /
-- dim_date_end vars in dbt_project.yml.

with days as (

    select cast(d as date) as full_date
    from generate_series(
        cast('{{ var("dim_date_start") }}' as date),
        cast('{{ var("dim_date_end") }}' as date),
        interval '1 day'
    ) as d

)

select
    cast(to_char(full_date, 'YYYYMMDD') as integer)    as date_key,
    full_date,
    cast(extract(day from full_date) as integer)        as day,
    cast(extract(month from full_date) as integer)      as month,
    cast(extract(quarter from full_date) as integer)    as quarter,
    cast(extract(year from full_date) as integer)       as year,
    extract(isodow from full_date) in (6, 7)            as is_weekend
from days
