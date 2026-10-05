# Creator Listening Analytics

Data Engineering Project 1, Group 5.

## Goal

Provide automated listening statistics and audio characteristic insights to creators (musicians/bands), enabling them to understand track performance over time and strategically curate music for target audiences.

## Data sources

- [Spotify Charts dataset](https://www.kaggle.com/datasets/dhruvildave/spotify-charts): historical chart positions and stream counts.
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/reference/get-track): track and artist metadata.
- [ReccoBeats API](https://reccobeats.com/docs/apis/get-audio-features): track audio features.

Datasets are linked using Spotify track IDs. Stream totals cover observations available in the selected charts.

## Design

The star schema contains `fact_track_performance` and four dimensions: `dim_track`, `dim_artist`, `dim_country`, and `dim_date`.

The fact-table grain is one track per country or region per calendar date.

Planned tools: Python and Airflow for ingestion, PostgreSQL for storage and transformation, Superset for reporting, and Docker for deployment.

## Files

- [Report.pdf](Report1.pdf): business brief, architecture, model, data dictionary, contributions, and AI disclosure, table definitions, pseudo SQL answering the five business questions.
