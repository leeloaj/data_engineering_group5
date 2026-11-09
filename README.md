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

### Commands

Run from the repository root with Python 3.11+ and PostgreSQL.

```sh
python -m pip install -r requirements.txt

# Historical Kaggle backfill
python -m ingestion.ingest_charts --kaggle

# Latest global daily chart, with optional track enrichment
python -m ingestion.ingest_charts --latest
python -m ingestion.ingest_charts --latest --enrich

# Latest global weekly chart
python -m ingestion.ingest_charts --latest --weekly

# Local CSV
python -m ingestion.ingest_charts data/examples/charts_data_example.csv
python -m ingestion.ingest_charts path/to/single-day.csv --date 2026-10-20 --region EE

# Standalone enrichment after loading charts
python -m ingestion.ingest_track_enrichment --source spotify_web_api --market EE
python -m ingestion.ingest_track_enrichment --source reccobeats --new-only --limit 20
```

### Credentials

Set variables in your environment or a local `.env` based on [`.env.example`](.env.example).

| Where | What to set |
| --- | --- |
| All ingestion commands | `DATABASE_URL` for PostgreSQL. |
| Spotify Charts (`--latest`) | `SPOTIFY_CHARTS_TOKEN` or `BEARER_TOKEN`. Renew the Charts token when it expires. |
| Spotify track metadata (`--enrich` or `--source spotify_web_api`) | `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`, or `SPOTIFY_ACCESS_TOKEN`. These are Spotify Web API credentials. |
| Kaggle backfill (`--kaggle`) | Configure [KaggleHub credentials](https://github.com/Kaggle/kagglehub#authenticate) if Kaggle requires sign-in. |
| ReccoBeats (`--source reccobeats`) | No API key required. |
| Local CSV | No API key required unless you add `--enrich`. |

[Detailed ingestion guide](ingestion/README.md)

## Files

- [Report.pdf](docs/Report1.pdf): business brief, architecture, model, data dictionary, contributions, and AI disclosure, table definitions, pseudo SQL answering the five business questions.
