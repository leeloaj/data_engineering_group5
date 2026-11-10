import argparse
import csv
import hashlib
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from time import monotonic

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from .bronze import ensure_bronze, input_date, open_bronze, region_code
from .chart_csv import chart_csv_context, chart_rows
from .file_output_and_progress import atomic_output, report_stage
from .sources.get_charts_data import get_charts_data, get_charts_token, save_charts_to_csv
from .track_enrichment import SOURCES, enrich_tracks, export_enrichment


CHART_COLUMNS = """
    source, ingested_at, input_file, input_sha256, chart_date, region,
    chart_type, spotify_track_id, rank, streams, raw_row
"""


def ingest_charts(connection, csv_path, fallback_date=None, fallback_region=None, weekly=False, *, progress=False):
    """Load one UTF-8 CSV atomically and return (inserted rows, duplicate rows)."""
    path = Path(csv_path)
    context = chart_csv_context(path, fallback_date, fallback_region, weekly)

    with path.open("rb") as file:
        size_mib = os.fstat(file.fileno()).st_size / 1024**2
        with report_stage(f"Hashing {path.name} ({size_mib:,.1f} MiB)", progress):
            digest = hashlib.sha256()
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
            version = digest.hexdigest()
        file.seek(0)
        with io.TextIOWrapper(file, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, strict=True)
            ingested_at = datetime.now(timezone.utc)
            total = 0
            with (
                report_stage(f"Importing {path.name} into PostgreSQL", progress),
                connection.transaction(),
                connection.cursor() as cursor,
            ):
                cursor.execute("""
                    CREATE TEMP TABLE chart_import (
                        LIKE bronze.chart_entries, line_number integer NOT NULL
                    ) ON COMMIT DROP
                """)
                def copy_detail(elapsed):
                    return f", {total:,} rows sent ({total / max(elapsed, 0.001):,.0f} rows/s)"

                with report_stage("Validating and staging chart rows", progress, copy_detail):
                    with cursor.copy(f"COPY chart_import ({CHART_COLUMNS}, line_number) FROM STDIN") as copy:
                        rows = chart_rows(reader, *context)
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

    with report_stage("Resolving Kaggle archive (download, extraction, or cache)"):
        dataset = Path(kagglehub.dataset_download("dhruvildave/spotify-charts"))
    path = dataset / "charts.csv"
    if not path.is_file():
        raise ValueError(f"Kaggle download did not contain {path.name} in {dataset}")
    return path


def export_latest(region, weekly, output_dir):
    token = get_charts_token()
    if not token:
        raise ValueError("Set SPOTIFY_CHARTS_TOKEN (or BEARER_TOKEN) for Spotify Charts")
    region = region_code(region).lower()
    period = "weekly" if weekly else "daily"
    try:
        with report_stage(f"Fetching Spotify Charts ({region}, {period})"):
            chart = get_charts_data(token, date="latest", region=region, period=period)
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in {401, 403}:
            raise ValueError("Spotify Charts rejected the token. Replace SPOTIFY_CHARTS_TOKEN in .env or the environment.") from error
        raise

    try:
        display = chart["displayChart"]
        published_date = input_date(display["date"]).isoformat()
        expected_alias = f"REGIONAL_{region.upper()}_{period.upper()}"
        if display["chartMetadata"]["alias"] != expected_alias:
            raise ValueError(f"Spotify Charts response did not match {expected_alias}")
        with report_stage(f"Writing chart CSV for {published_date}"):
            return save_charts_to_csv(chart, published_date, region, output_dir, period)
    except (KeyError, TypeError) as error:
        raise ValueError("Unexpected Spotify Charts response format") from error


def ingest_latest(connection, region, weekly):
    with TemporaryDirectory() as temporary:
        csv_path = export_latest(region, weekly, temporary)
        return csv_path.name, *ingest_charts(connection, csv_path, progress=True)


def copy_chart_csv(csv_path, output_dir):
    destination = output_dir / csv_path.name
    with report_stage(f"Copying {csv_path.name} to {output_dir}"):
        if not csv_path.is_file():
            raise ValueError(f"Chart CSV does not exist: {csv_path}")
        if csv_path.resolve() != destination.resolve():
            with atomic_output(destination) as temporary:
                copyfile(csv_path, temporary)
    print(f"Chart CSV: {destination}", flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description="Export Spotify charts to CSV or load them into PostgreSQL bronze.")
    chart_inputs = parser.add_mutually_exclusive_group(required=True)
    chart_inputs.add_argument("csv", nargs="?", type=Path, help="Use a local chart CSV")
    chart_inputs.add_argument("--kaggle", action="store_true", help="Download the Kaggle chart archive")
    chart_inputs.add_argument("--latest", action="store_true", help="Fetch the latest published Spotify chart")
    parser.add_argument("--output-dir", type=Path, help="Save chart and enrichment files without PostgreSQL")
    parser.add_argument("--date", help="Fallback chart date (YYYY-MM-DD)")
    parser.add_argument("--region", help="Spotify Charts region (default: global), or CSV fallback region")
    parser.add_argument("--weekly", action="store_true", help="Use the weekly Spotify Charts series")
    parser.add_argument("--enrich", action="store_true", help="Fetch metadata and audio features for chart tracks")
    parser.add_argument("--enrichment-source", choices=SOURCES, help="Use one source with --enrich (default: both)")
    parser.add_argument("--market", default="EE", help="Spotify metadata catalog market (default: EE)")
    parser.add_argument("--enrichment-limit", type=int, help="Limit pending IDs per enrichment source")
    args = parser.parse_args()
    if args.date and not args.csv:
        parser.error("--date is only used with a local CSV")
    if args.kaggle and (args.weekly or args.region):
        parser.error("--kaggle loads all archive regions and contains daily charts")
    if args.enrichment_source and not args.enrich:
        parser.error("--enrichment-source requires --enrich")
    if args.enrichment_limit is not None and (not args.enrich or args.enrichment_limit <= 0):
        parser.error("--enrichment-limit requires --enrich and a positive value")

    sources = (args.enrichment_source,) if args.enrichment_source else SOURCES
    try:
        if args.output_dir is not None:
            load_dotenv()
            if args.latest:
                csv_path = export_latest(args.region or "global", args.weekly, args.output_dir)
            else:
                csv_path = download_kaggle_charts() if args.kaggle else args.csv
                csv_path = copy_chart_csv(csv_path, args.output_dir)
            if args.enrich:
                export_enrichment(
                    csv_path, args.output_dir, datetime.now(timezone.utc).date(), args.market,
                    sources, args.enrichment_limit, fallback_date=args.date,
                    fallback_region=args.region, weekly=args.weekly,
                )
            return

        started = monotonic()
        with report_stage("Connecting to PostgreSQL"):
            connection = open_bronze()
        with connection:
            with report_stage("Checking the bronze schema"):
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
                    sources, limit=args.enrichment_limit, new_only=True,
                )
    except (ValueError, OSError, csv.Error, psycopg.Error, requests.RequestException) as error:
        parser.exit(1, f"Chart ingestion failed: {error}\n")


if __name__ == "__main__":
    main()
