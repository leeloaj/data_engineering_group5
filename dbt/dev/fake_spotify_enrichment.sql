-- LOCAL TESTING ONLY. Fills bronze.track_enrichment with FAKE Spotify Web API
-- responses so the track/artist models can be tested without Spotify
-- credentials. Rows are marked with "_fake": true and can be removed with:
--   delete from bronze.track_enrichment where raw_json ? '_fake';
--
-- Shape follows GET /v1/tracks/{id}: name, duration_ms, explicit, popularity,
-- album {name, release_date, release_date_precision}, artists [{id, name}].
-- Artists are split from the chart's artist_names; their IDs are made up.
-- About 10% of tracks are left out to test the "not enriched yet" path, and
-- two snapshot dates are written to test popularity history.
--
-- Usage (from the repo root, after loading charts):
--   docker exec -i warehouse-db psql -U warehouse -d warehouse < dbt/dev/fake_spotify_enrichment.sql

delete from bronze.track_enrichment where raw_json ? '_fake';

with tracks as (

    select distinct on (spotify_track_id)
        spotify_track_id,
        raw_row ->> 'track_name'    as track_name,
        raw_row ->> 'artist_names'  as artist_names,
        ('x' || substr(md5(spotify_track_id), 1, 8))::bit(32)::int as seed
    from bronze.chart_entries
    order by spotify_track_id, chart_date desc

),

enriched as (

    select * from tracks where abs(seed) % 10 <> 0

),

snapshots as (

    select enriched.*, snapshot.input_date, snapshot.drift
    from enriched
    cross join (values (date '2026-11-01', 0), (date '2026-11-08', 3)) as snapshot (input_date, drift)

)

insert into bronze.track_enrichment
    (source, ingested_at, input_date, spotify_track_id, market, status, raw_json)
select
    'spotify_web_api',
    now(),
    input_date,
    spotify_track_id,
    'EE',
    'found',
    jsonb_build_object(
        '_fake', true,
        'id', spotify_track_id,
        'name', track_name,
        'duration_ms', 150000 + abs(seed) % 120000,
        'explicit', abs(seed) % 3 = 0,
        'popularity', least(100, 40 + abs(seed) % 55 + drift),
        'album', jsonb_build_object(
            'id', substr(md5('album' || spotify_track_id), 1, 22),
            'name', track_name,
            'release_date', case abs(seed) % 7
                when 0 then to_char(date '2015-01-01' + abs(seed) % 4000, 'YYYY')
                when 1 then to_char(date '2015-01-01' + abs(seed) % 4000, 'YYYY-MM')
                else to_char(date '2015-01-01' + abs(seed) % 4000, 'YYYY-MM-DD')
            end,
            'release_date_precision', case abs(seed) % 7
                when 0 then 'year' when 1 then 'month' else 'day' end
        ),
        'artists', (
            select jsonb_agg(
                jsonb_build_object('id', substr(md5(lower(trim(name))), 1, 22), 'name', trim(name))
                order by ord
            )
            from unnest(string_to_array(artist_names, ', ')) with ordinality as a (name, ord)
        )
    )
from snapshots;

select count(*) as fake_spotify_rows from bronze.track_enrichment where raw_json ? '_fake';
