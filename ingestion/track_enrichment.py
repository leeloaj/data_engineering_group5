import json
from datetime import datetime, timezone

import requests
from psycopg.types.json import Jsonb

from .bronze import region_code, spotify_track_id
from .chart_csv import chart_track_ids
from .file_output_and_progress import atomic_output, report_stage
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
    with report_stage(f"Selecting tracks for {source}"):
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

    def save(track_id, status, payload):
        return connection.execute("""
            INSERT INTO bronze.track_enrichment
                (source, ingested_at, input_date, spotify_track_id, market, status, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            source, datetime.now(timezone.utc), snapshot_date, track_id, market, status,
            Jsonb(payload) if payload is not None else None,
        )).rowcount

    return save_results((track_id for (track_id,) in pending), source, market, token, save)


def save_results(track_ids, source, market, token, save):
    counts = {"found": 0, "missing": 0}

    def saved_detail(_elapsed):
        return f", results written: {sum(counts.values()):,}"

    with report_stage(f"Fetching and saving {source} results", detail=saved_detail):
        for track_id in track_ids:
            try:
                access_token = token() if callable(token) else token
                status, payload = fetch_track(source, track_id, access_token, market)
            except (ValueError, requests.RequestException) as error:
                raise ValueError(f"{source} failed for {track_id}: {error}") from error
            counts[status] += save(track_id, status, payload)
    return counts


def enrichment_sources(sources, market):
    market = region_code(market)
    if market == "GLOBAL":
        raise ValueError("Spotify market must be a country")
    token = spotify_token_provider() if "spotify_web_api" in sources else None
    for source in sources:
        source_market = market if source == "spotify_web_api" else ""
        source_token = token if source == "spotify_web_api" else None
        yield source, source_market, source_token


def enrich_tracks(connection, snapshot_date, market, sources=SOURCES, limit=None, new_only=False):
    for source, source_market, token in enrichment_sources(sources, market):
        counts = ingest_source(connection, source, snapshot_date, source_market, token, limit, new_only)
        print(f"{source}: {counts['found']} found, {counts['missing']} missing", flush=True)


def export_enrichment(csv_path, output_dir, snapshot_date, market, sources=SOURCES, limit=None,
                      *, fallback_date=None, fallback_region=None, weekly=False):
    with report_stage(f"Selecting tracks from {csv_path.name}"):
        track_ids = chart_track_ids(csv_path, fallback_date, fallback_region, weekly)[:limit]

    for source, source_market, token in enrichment_sources(sources, market):
        suffix = f"_{source_market}" if source_market else ""
        destination = output_dir / f"{csv_path.stem}_{source}_{snapshot_date}{suffix}.jsonl"
        with atomic_output(destination) as temporary, temporary.open("w", encoding="utf-8") as file:
            def save(track_id, status, payload):
                record = {
                    "source": source,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "input_date": snapshot_date.isoformat(),
                    "spotify_track_id": track_id,
                    "market": source_market,
                    "status": status,
                    "raw_json": payload,
                }
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
                return 1

            counts = save_results(track_ids, source, source_market, token, save)
        print(f"Saved {destination} ({counts['found']} found, {counts['missing']} missing)", flush=True)
