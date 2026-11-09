import argparse
from datetime import datetime, timezone

import psycopg
import requests
from psycopg.types.json import Jsonb

from .bronze import ensure_bronze, input_date, open_bronze, region_code, spotify_track_id
from .sources.get_track_info import get_audio_features, get_track_info, spotify_token_provider


SOURCES = ("spotify_web_api", "reccobeats")


def fetch_track(source, track_id, token, market):
    """Return a status and the source response JSON for one requested Spotify ID."""
    try:
        if source == "spotify_web_api":
            payload = get_track_info(token, track_id, market)
        else:
            payload = get_audio_features(track_id)
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 404:
            raise
        try:
            return "missing", error.response.json()
        except ValueError:
            return "missing", None

    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    if source == "spotify_web_api":
        linked_from = payload.get("linked_from")
        linked_id = linked_from.get("id") if isinstance(linked_from, dict) else None
        if payload.get("id") != track_id and linked_id != track_id:
            raise ValueError("Spotify returned a different track without a matching linked_from ID")
    else:
        items = payload.get("content")
        if not isinstance(items, list):
            raise ValueError("expected a ReccoBeats content array")
        if not items:
            return "missing", payload
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("href"), str):
                raise ValueError("ReccoBeats result has no Spotify href")
            if spotify_track_id(item["href"]) != track_id:
                raise ValueError("ReccoBeats returned a different Spotify track")
    return "found", payload


def ingest_source(connection, source, snapshot_date, market, token=None, limit=None, new_only=False):
    """Enrich distinct chart IDs, committing each result so interrupted runs can resume."""
    pending = connection.execute("""
        SELECT DISTINCT chart.spotify_track_id
        FROM bronze.chart_entries AS chart
        WHERE NOT EXISTS (
            SELECT 1 FROM bronze.track_enrichment AS existing
            WHERE existing.source = %s
              AND (%s OR existing.input_date = %s)
              AND existing.market = %s
              AND existing.spotify_track_id = chart.spotify_track_id
        )
        ORDER BY chart.spotify_track_id
        LIMIT %s
    """, (source, new_only, snapshot_date, market, limit))
    counts = {"found": 0, "missing": 0}
    for (track_id,) in pending:
        try:
            access_token = token() if callable(token) else token
            status, payload = fetch_track(source, track_id, access_token, market)
        except (ValueError, requests.RequestException) as error:
            raise ValueError(f"{source} failed for {track_id}: {error}") from error
        inserted = connection.execute("""
            INSERT INTO bronze.track_enrichment
                (source, ingested_at, input_date, spotify_track_id, market, status, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            source, datetime.now(timezone.utc), snapshot_date, track_id, market, status,
            Jsonb(payload) if payload is not None else None,
        )).rowcount
        counts[status] += inserted
    return counts


def enrich_tracks(connection, snapshot_date, market, sources=SOURCES, limit=None, new_only=False):
    market = region_code(market)
    if market == "GLOBAL":
        raise ValueError("Spotify market must be a country")
    token = spotify_token_provider() if "spotify_web_api" in sources else None
    for source in sources:
        source_market = market if source == "spotify_web_api" else ""
        source_token = token if source == "spotify_web_api" else None
        counts = ingest_source(
            connection, source, snapshot_date, source_market, source_token, limit, new_only
        )
        print(f"{source}: {counts['found']} found, {counts['missing']} missing")


def main():
    parser = argparse.ArgumentParser(description="Enrich bronze chart track IDs from Spotify and ReccoBeats.")
    parser.add_argument("--source", choices=SOURCES, help="Load a single source (default: both)")
    parser.add_argument("--input-date", default=datetime.now(timezone.utc).date().isoformat(),
                        help="Snapshot date (YYYY-MM-DD, default: today in UTC)")
    parser.add_argument("--market", default="EE", help="Spotify catalog market (default: EE)")
    parser.add_argument("--limit", type=int, help="Maximum number of pending track IDs per source")
    parser.add_argument("--new-only", action="store_true", help="Skip IDs already checked on any date")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    sources = (args.source,) if args.source else SOURCES
    try:
        snapshot_date = input_date(args.input_date)
        with open_bronze() as connection:
            ensure_bronze(connection)
            enrich_tracks(connection, snapshot_date, args.market, sources, args.limit, args.new_only)
    except (ValueError, OSError, psycopg.Error) as error:
        parser.exit(1, f"Track enrichment failed: {error}\n")


if __name__ == "__main__":
    main()
