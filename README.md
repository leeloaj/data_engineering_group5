# Creator Listening Analytics

Data Engineering Project 1, Group 5.

## Goal

Provide automated listening statistics and audio characteristic insights to creators (musicians/bands), enabling them to understand track performance over time and strategically curate music for target audiences.

## Data sources

- [Spotify Web API](https://developer.spotify.com/documentation/web-api/reference/get-track): track and artist metadata.
- [ReccoBeats API](https://reccobeats.com/docs/apis/get-audio-features): track audio features.
- [Spotify Charts dataset](https://www.kaggle.com/datasets/dhruvildave/spotify-charts): historical chart positions and stream counts.
- [Spotify Charts](https://charts.spotify.com): recent day/week csv download.

Datasets are linked using Spotify track IDs. Stream totals cover observations available in the selected charts.

## Design

The star schema contains `fact_track_performance` and four dimensions: `dim_track`, `dim_artist`, `dim_country`, and `dim_date`.

The fact-table grain is one track per country or region per calendar date.

Planned tools: Python and Airflow for ingestion, PostgreSQL for storage and transformation, Superset for reporting, and Docker for deployment.

## Bronze ingestion

### Essential setup and first run

Use Python 3.10+ and a running PostgreSQL database. Copy [`.env.example`](.env.example) to `.env` and set `DATABASE_URL` to your database. The database role needs permission to create the `bronze` schema and its tables.

From the repository root, with your virtual environment active, install dependencies and load the bundled sample:

```sh
python -m pip install -r requirements.txt
python -m ingestion.ingest_charts data/examples/charts_data_example.csv
```

The loader initializes `bronze` automatically and prints the inserted row count. The sample load needs no Spotify token.

### Optional commands by use case

#### Load live charts into PostgreSQL

Set `SPOTIFY_CHARTS_TOKEN` in `.env` before running either command.

```sh
# Global daily chart
python -m ingestion.ingest_charts --latest

# Global weekly chart
python -m ingestion.ingest_charts --latest --weekly
```

Use `--region EE` for Estonia.

#### Backfill history or load your own CSV

```sh
python -m ingestion.ingest_charts --kaggle
python -m ingestion.ingest_charts path/to/single-day.csv --date 2026-10-20 --region EE
```

#### Add track metadata or audio features

```sh
# Enrich tracks already loaded into PostgreSQL
python -m ingestion.ingest_track_enrichment --source spotify_web_api --market EE
python -m ingestion.ingest_track_enrichment --source reccobeats --new-only --limit 20
```

To load the latest chart and run both enrichment sources in PostgreSQL, use `python -m ingestion.ingest_charts --latest --enrich` with Spotify Web API credentials configured.

#### Export files without PostgreSQL

Set `SPOTIFY_CHARTS_TOKEN` for `--latest`. The chart export option also accepts `--kaggle` or a local chart CSV in place of `--latest`.

```sh
# Save the latest chart as a CSV
python -m ingestion.ingest_charts --latest --output-dir data/exports

# Save the latest chart and a small ReccoBeats sample
python -m ingestion.ingest_charts --latest --output-dir data/exports --enrich --enrichment-source reccobeats --enrichment-limit 5

# Enrich tracks from a CSV without PostgreSQL
python -m ingestion.ingest_track_enrichment --csv data/examples/charts_data_example.csv --output-dir data/exports --source reccobeats --limit 5
```

### Credentials

Set variables in your environment or a local `.env` based on [`.env.example`](.env.example).

| Where | What to set |
| --- | --- |
| Database loads and database-backed enrichment | `DATABASE_URL` for PostgreSQL. |
| Spotify Charts (`--latest`) | `SPOTIFY_CHARTS_TOKEN` or `BEARER_TOKEN`. Replace the token manually when it expires. |
| Spotify track metadata | `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`, or `SPOTIFY_ACCESS_TOKEN`. These are Spotify Web API credentials. |
| Kaggle backfill (`--kaggle`) | Configure [KaggleHub credentials](https://github.com/Kaggle/kagglehub#authenticate) if Kaggle requires sign-in. |
| ReccoBeats (`--source reccobeats`) | No API key required. |
| Local CSV | No API key required unless you request Spotify Web API enrichment. |

[Detailed ingestion guide](ingestion/README.md)

## Files

- [Report.pdf](docs/Report1.pdf): business brief, architecture, model, data dictionary, contributions, and AI disclosure, table definitions, pseudo SQL answering the five business questions.
