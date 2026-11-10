-- Static country table (SCD Type 0) built from the spotify_regions seed.
-- country_key is fixed in the seed so keys never shift when rows are added.

select
    cast(country_key as integer)        as country_key,
    cast(country_code as varchar(10))   as country_code,
    cast(country_name as varchar(100))  as country_name,
    cast(region as varchar(100))        as region
from {{ ref('spotify_regions') }}
