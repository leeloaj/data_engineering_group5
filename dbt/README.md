# dbt: silver and gold models

Builds the star schema from the report out of the bronze tables loaded by the [ingestion package](../ingestion/README.md).

- **Silver** (views): `stg_chart_entries`, `stg_spotify_track_snapshots`, `stg_spotify_track_artists`, `stg_audio_features`
- **Gold** (tables): `dim_date`, `dim_country`, `dim_track`, `dim_artist`, `bridge_track_artist`, `fact_track_performance`, `fact_track_popularity`

## Run locally

Connection settings come from the `WAREHOUSE_DB_*` variables in `compose.yml` and `.env.example`, so dbt works in the Airflow containers and on your own machine without changes.

**In Docker** (after `docker compose up -d`, see `compose.yml`):

```sh
docker compose exec airflow-scheduler bash -c "cd /opt/airflow/dbt && dbt build"
```

**On your own machine** with Python 3.13 or older (newer dbt versions did not install on 3.13), from the repo root:

```sh
# 1. Python environment with ingestion and dbt
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt "dbt-core==1.10.23" "dbt-postgres==1.10.2"

# 2. Start only the warehouse database (port 5433)
cp .env.example .env
docker compose up -d warehouse-db

# 3. Load bronze (the loaders read DATABASE_URL from .env)
python -m ingestion.ingest_charts data/examples/charts_data_example.csv
python -m ingestion.ingest_track_enrichment --source reccobeats --limit 20

# without Spotify Web API credentials: load FAKE track metadata, for testing only
docker exec -i warehouse-db psql -U warehouse -d warehouse < dbt/dev/fake_spotify_enrichment.sql

# 4. Build all models and run all tests: expect "ERROR=0" on the last line
#    (WARN=1 just means the fake Spotify data is loaded)
cd dbt && dbt build --profiles-dir .
```

## Design choices

- **Fact grain:** one track × region × date, from the daily Top 200 chart only.
- **Keys:** `dim_track` and `dim_artist` use hashed keys (md5 of the Spotify ID) instead of the integer keys in the report, so keys stay the same when the dimensions are rebuilt.
- **Several artists:** the fact's `artist_key` is the first-listed artist. `bridge_track_artist` links all artists.
- **Tracks not yet enriched** get the "Unknown artist" key. The next run fills in the real artist.
- **Incremental fact:** only new rows are processed, and reruns do not create duplicates.
- **Popularity history (BQ2):** `fact_track_popularity` stores one score per track per enrichment run.
- `dim_country` includes Andorra and Russia, which appear only in the Kaggle history. Exclude `GLOBAL` when summing across countries.

## Status

Tested locally on the sample charts CSV, the full Kaggle backfill (26.2M bronze rows, 20.3M fact rows), a few ReccoBeats tracks and fake Spotify metadata. All tests pass. A rerun with no new data takes about 1 minute. Still open:

1. Run with real Spotify Web API data (needs credentials). Until tracks are enriched, their fact rows use "Unknown artist", so per-artist questions need enrichment first. The Kaggle history has about 218,000 distinct tracks.
2. `artist_genres` is empty until Spotify artist data is ingested.
