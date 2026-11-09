import argparse
import csv
import hashlib
import io
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic

import psycopg
import requests
from psycopg.types.json import Jsonb

from .bronze import ensure_bronze, input_date, open_bronze, region_code, spotify_track_id
from .ingest_track_enrichment import enrich_tracks
from .sources.get_charts_data import get_charts_data, save_charts_to_csv


CHART_COLUMNS = """
    source, ingested_at, input_file, input_sha256, chart_date, region,
    chart_type, spotify_track_id, rank, streams, raw_row
"""
PROGRESS_INTERVAL = 30


@contextmanager
def report_stage(name, enabled, detail=lambda elapsed: ""):
    """Report elapsed time even while a download or database call blocks."""
    if not enabled:
        yield
        return

    started = monotonic()
    finished = Event()

    def report(status):
        elapsed = monotonic() - started
        print(f"{name}: {status} ({elapsed:,.1f}s){detail(elapsed)}", flush=True)

    def heartbeat():
        while not finished.wait(PROGRESS_INTERVAL):
            report("running")

    print(f"{name}: starting", flush=True)
    worker = Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        finished.set()
        worker.join()
    report("done")


def chart_rows(reader, fallback_date, fallback_region, weekly=False):
    headers = reader.fieldnames or []
    historical = "chart" in headers
    if historical and weekly:
        raise ValueError("the Kaggle archive contains daily charts")
    id_column = next((name for name in ("id", "uri", "url") if name in headers), None)
    required = {"rank", "streams"}
    if not fallback_date:
        required.add("date")
    if not fallback_region:
        required.add("region")
    if len(headers) != len(set(headers)):
        raise ValueError("duplicate CSV headers")
    if required.difference(headers) or not id_column:
        raise ValueError("expected rank, streams, id/uri/url, and a chart date and region")

    source = "kaggle_spotify_charts" if historical else "spotify_charts"
    for row in reader:
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("column count differs from the header")
            chart_date = input_date(row.get("date", "").strip() or fallback_date or "")
            region = region_code(row.get("region", "").strip() or fallback_region or "")
            track_id = spotify_track_id(row[id_column])
            chart_type = row["chart"].strip().lower() if historical else "top200"
            if chart_type not in {"top200", "viral50"}:
                raise ValueError(f"unknown chart type: {chart_type!r}")
            if weekly:
                chart_type = "top200_weekly"
            rank = int(row["rank"])
            streams = int(row["streams"]) if row["streams"].strip() else None
            if not 0 < rank < 2**31 or (streams is not None and not 0 <= streams < 2**63):
                raise ValueError("rank must be positive and streams must be nonnegative")
        except ValueError as error:
            raise ValueError(f"CSV line {reader.line_num}: {error}") from error
        yield source, chart_date, region, chart_type, track_id, rank, streams, row


def ingest_charts(connection, csv_path, fallback_date=None, fallback_region=None, weekly=False, *, progress=False):
    """Load one UTF-8 CSV atomically and return (inserted rows, duplicate rows)."""
    path = Path(csv_path)
    filename_context = re.fullmatch(
        r"charts_data_(\d{4}-\d{2}-\d{2})_([a-zA-Z]+)(_weekly)?\.csv", path.name
    )
    if filename_context:
        fallback_date = fallback_date or filename_context[1]
        fallback_region = fallback_region or filename_context[2]
        weekly = weekly or bool(filename_context[3])
    if fallback_date:
        fallback_date = input_date(fallback_date).isoformat()
    if fallback_region:
        fallback_region = region_code(fallback_region)

    with path.open("rb") as file:
        size_mib = os.fstat(file.fileno()).st_size / 1024**2
        with report_stage(f"Hashing {path.name} ({size_mib:,.1f} MiB)", progress):
            version = hashlib.file_digest(file, "sha256").hexdigest()
        file.seek(0)
        with io.TextIOWrapper(file, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, strict=True)
            ingested_at = datetime.now(timezone.utc)
            total = 0
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TEMP TABLE chart_import (
                        LIKE bronze.chart_entries, line_number integer NOT NULL
                    ) ON COMMIT DROP
                """)
                def copy_detail(elapsed):
                    return f", {total:,} rows sent ({total / max(elapsed, 0.001):,.0f} rows/s)"

                with report_stage("Validating and staging chart rows", progress, copy_detail):
                    with cursor.copy(f"COPY chart_import ({CHART_COLUMNS}, line_number) FROM STDIN") as copy:
                        rows = chart_rows(reader, fallback_date, fallback_region, weekly)
                        for source, *values, raw_row in rows:
                            copy.write_row((
                                source, ingested_at, path.name, version, *values,
                                Jsonb(raw_row), reader.line_num,
                            ))
                            total += 1
                if not total:
                    raise ValueError("CSV contains no chart rows")
                with report_stage("Merging staged rows into bronze", progress):
                    cursor.execute(f"""
                        INSERT INTO bronze.chart_entries ({CHART_COLUMNS})
                        SELECT {CHART_COLUMNS} FROM chart_import
                        ORDER BY source, chart_date, region, chart_type, spotify_track_id, line_number
                        ON CONFLICT DO NOTHING
                    """)
                    inserted = cursor.rowcount
    return inserted, total - inserted


def download_kaggle_charts():
    import kagglehub

    with report_stage("Resolving Kaggle archive (download, extraction, or cache)", True):
        dataset = Path(kagglehub.dataset_download("dhruvildave/spotify-charts"))
    path = dataset / "charts.csv"
    if not path.is_file():
        raise ValueError(f"Kaggle download did not contain {path.name} in {dataset}")
    return path


def ingest_latest(connection, region, weekly):
    token = os.getenv("SPOTIFY_CHARTS_TOKEN") or os.getenv("BEARER_TOKEN")
    if not token:
        raise ValueError("Set SPOTIFY_CHARTS_TOKEN (or BEARER_TOKEN) for Spotify Charts")
    region = region_code(region).lower()
    period = "weekly" if weekly else "daily"
    try:
        chart = get_charts_data(token, date="latest", region=region, period=period)
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in {401, 403}:
            raise ValueError("Spotify Charts rejected the Charts token. Renew SPOTIFY_CHARTS_TOKEN.") from error
        raise

    try:
        display = chart["displayChart"]
        published_date = input_date(display["date"]).isoformat()
        expected_alias = f"REGIONAL_{region.upper()}_{period.upper()}"
        if display["chartMetadata"]["alias"] != expected_alias:
            raise ValueError(f"Spotify Charts response did not match {expected_alias}")
        with TemporaryDirectory() as temporary:
            csv_path = save_charts_to_csv(chart, published_date, region, temporary, period)
            return csv_path.name, *ingest_charts(connection, csv_path)
    except (KeyError, TypeError) as error:
        raise ValueError("Unexpected Spotify Charts response format") from error


def main():
    parser = argparse.ArgumentParser(description="Fetch or load Spotify charts into PostgreSQL bronze.")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("csv", nargs="?", type=Path, help="Load a local CSV")
    sources.add_argument("--kaggle", action="store_true", help="Download and load the Kaggle archive")
    sources.add_argument("--latest", action="store_true", help="Fetch the latest published Spotify chart")
    parser.add_argument("--date", help="Fallback chart date (YYYY-MM-DD)")
    parser.add_argument("--region", help="Spotify Charts region (default: global), or CSV fallback region")
    parser.add_argument("--weekly", action="store_true", help="Use the weekly Spotify Charts series")
    parser.add_argument("--enrich", action="store_true", help="Fetch metadata and audio for unchecked IDs")
    parser.add_argument("--market", default="EE", help="Spotify metadata catalog market (default: EE)")
    parser.add_argument("--enrichment-limit", type=int, help="Limit pending IDs per enrichment source")
    args = parser.parse_args()
    if args.date and not args.csv:
        parser.error("--date is only used with a local CSV")
    if args.kaggle and (args.weekly or args.region):
        parser.error("--kaggle loads all archive regions and contains daily charts")
    if args.enrichment_limit is not None and (not args.enrich or args.enrichment_limit <= 0):
        parser.error("--enrichment-limit requires --enrich and a positive value")

    try:
        started = monotonic()
        with open_bronze() as connection:
            ensure_bronze(connection)
            if args.latest:
                name, inserted, duplicates = ingest_latest(connection, args.region or "global", args.weekly)
            else:
                csv_path = download_kaggle_charts() if args.kaggle else args.csv
                name = csv_path.name
                inserted, duplicates = ingest_charts(
                    connection, csv_path, args.date, args.region, args.weekly, progress=True,
                )
            print(
                f"{name}: {inserted:,} inserted, {duplicates:,} duplicates skipped "
                f"in {monotonic() - started:,.1f}s",
                flush=True,
            )
            if args.enrich:
                enrich_tracks(
                    connection, datetime.now(timezone.utc).date(), args.market,
                    limit=args.enrichment_limit, new_only=True,
                )
    except (ValueError, OSError, csv.Error, psycopg.Error, requests.RequestException) as error:
        parser.exit(1, f"Chart ingestion failed: {error}\n")


if __name__ == "__main__":
    main()
