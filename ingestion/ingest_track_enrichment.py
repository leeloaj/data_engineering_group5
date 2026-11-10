import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .bronze import ensure_bronze, input_date, open_bronze
from .file_output_and_progress import report_stage
from .track_enrichment import SOURCES, enrich_tracks, export_enrichment


def main():
    parser = argparse.ArgumentParser(description="Enrich chart track IDs from Spotify and ReccoBeats.")
    parser.add_argument("--source", choices=SOURCES, help="Load a single source (default: both)")
    parser.add_argument("--csv", type=Path, help="Read track IDs from a chart CSV instead of PostgreSQL")
    parser.add_argument("--output-dir", type=Path, help="Save enrichment for --csv as JSON Lines")
    parser.add_argument("--date", help="Fallback chart date for --csv (YYYY-MM-DD)")
    parser.add_argument("--region", help="Fallback chart region for --csv")
    parser.add_argument("--input-date", default=datetime.now(timezone.utc).date().isoformat(),
                        help="Snapshot date (YYYY-MM-DD, default: today in UTC)")
    parser.add_argument("--market", default="EE", help="Spotify catalog market (default: EE)")
    parser.add_argument("--limit", type=int, help="Maximum number of pending track IDs per source")
    parser.add_argument("--new-only", action="store_true", help="Skip IDs already checked on any date")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if (args.csv is None) != (args.output_dir is None):
        parser.error("--csv and --output-dir must be used together")
    if args.csv is None and (args.date or args.region):
        parser.error("--date and --region require --csv")
    if args.csv is not None and args.new_only:
        parser.error("--new-only requires PostgreSQL")

    sources = (args.source,) if args.source else SOURCES
    try:
        snapshot_date = input_date(args.input_date)
        if args.csv is not None:
            load_dotenv()
            export_enrichment(
                args.csv, args.output_dir, snapshot_date, args.market, sources, args.limit,
                fallback_date=args.date, fallback_region=args.region,
            )
            return
        with report_stage("Connecting to PostgreSQL"):
            connection = open_bronze()
        with connection:
            with report_stage("Checking the bronze schema"):
                ensure_bronze(connection)
            enrich_tracks(connection, snapshot_date, args.market, sources, args.limit, args.new_only)
    except (ValueError, OSError, csv.Error, psycopg.Error) as error:
        parser.exit(1, f"Track enrichment failed: {error}\n")


if __name__ == "__main__":
    main()
