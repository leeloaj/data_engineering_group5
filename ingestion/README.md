# Bronze ingestion details

See the [project README](../README.md#commands) for command examples. The [bronze schema](../sql/bronze.sql) defines the tables described below.

## Setup and credentials

Use Python 3.11+ and a running PostgreSQL database. From the repository root, install dependencies with `python -m pip install -r requirements.txt`. Set `DATABASE_URL` in your environment or in a local `.env` based on [`.env.example`](../.env.example). The loaders create the `bronze` schema and tables on first run, so the database user needs permission to create the schema.

- **Spotify Charts** uses `SPOTIFY_CHARTS_TOKEN` or the existing `BEARER_TOKEN` for daily and weekly chart downloads. Renew this token when it expires.
- **Spotify Web API** uses `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` to obtain and renew track metadata access tokens. You can supply `SPOTIFY_ACCESS_TOKEN` directly instead. These credentials are separate from the Charts token. Development Mode app owners need Spotify Premium. [Spotify client credentials](https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow), [Spotify quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).
- **KaggleHub** uses its standard credential configuration if Kaggle requires sign-in for the backfill. [KaggleHub authentication](https://github.com/Kaggle/kagglehub#authenticate).
- **ReccoBeats** and local CSV ingestion require no API token on their own. Adding `--enrich` to a chart command also runs Spotify metadata enrichment and requires Web API credentials.

## Charts

`--kaggle` downloads and caches the historical archive through KaggleHub and loads its `charts.csv`. During long stages it prints elapsed time every 30 seconds. The stages cover download or cache resolution, file hashing, PostgreSQL staging, and the final merge. Staging reports rows sent and average rows per second. The final line reports committed inserts, duplicates skipped, and elapsed time.

`--latest` uses Spotify's published chart date. It reads the authenticated feed behind the daily or weekly chart page. Weekly observations use `chart_type = 'top200_weekly'`. [Kaggle archive](https://www.kaggle.com/datasets/dhruvildave/spotify-charts), [Spotify daily charts](https://charts.spotify.com/charts/view/regional-global-daily/latest), [Spotify weekly charts](https://charts.spotify.com/charts/view/regional-global-weekly/latest).

The latest chart defaults to global. Use `--region EE` for Estonia or specify another region. Schedule recurring runs after Spotify publishes the chart. With `--enrich`, use `--enrichment-limit 100` to cap requests per source on a run, for example after a historical backfill.

The CSV loader accepts the repository's daily exports, single-day Spotify Charts CSVs, and the extracted Kaggle `charts.csv`. It accepts bare Spotify track IDs, track URIs, and track URLs. It reads dates and regions from CSV columns and fills missing values from command-line defaults or the downloader's `charts_data_YYYY-MM-DD_region.csv` filename. Regions normalize to country codes or `GLOBAL`. Top 200 and Viral 50 observations are stored separately, and blank stream counts become SQL `NULL`.

`bronze.chart_entries` stores the source, UTC ingestion time, chart date, input filename and SHA-256, and all original CSV fields in `raw_row`. Each file loads in one transaction. A malformed row rolls back the file and reports its line number when available. The first stored row for a given source, chart date, region, chart type, and Spotify ID wins. Reruns and overlapping files from the same source skip that key and preserve the original provenance.

## Track metadata and audio features

The loader reads distinct Spotify IDs from the bronze chart table. Spotify uses the selected catalog market, which defaults to `EE`. ReccoBeats results are matched by the Spotify ID in their `href`. [ReccoBeats audio features](https://reccobeats.com/docs/apis/get-audio-features).

`bronze.track_enrichment` stores one row per source, snapshot date, market, and Spotify ID. The market is empty for ReccoBeats. Rows record UTC ingestion time, status, and the complete response JSON in `raw_json` when available. An empty ReccoBeats result or HTTP 404 is recorded as `missing`. Authentication failures, throttling, and other request errors stop the run with an error.

`--enrich` on the chart loader and `--new-only` on the standalone enrichment loader skip IDs with an existing result for that source and market. For a refresh or to retry missing tracks, run standalone enrichment on a new snapshot date without `--new-only`.

Load charts before standalone enrichment. Rerun with the same `--input-date` to resume at unprocessed IDs. The date defaults to today in UTC.

## Ingestion files

The ingestion package contains the loaders and shared validation code. API clients live in [`sources/`](sources/), and the sample CSV and Spotify Charts JSON response live in [`data/examples/`](../data/examples/).
