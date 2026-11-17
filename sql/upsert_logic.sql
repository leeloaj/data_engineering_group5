-- ============================================================================
-- IDEMPOTENT INGESTION & SAFE RERUNS
-- Component: Bronze Layer Ingestion
-- Description: Duplicate-safe INSERT / ON CONFLICT DO NOTHING patterns for safe
--              pipeline reruns, preserving first-seen raw-source provenance.
-- ============================================================================

-- 1. Safe Rerun for bronze.chart_entries (First-seen provenance wins / skip duplicates)
INSERT INTO bronze.chart_entries (
    source,
    ingested_at,
    input_file,
    input_sha256,
    chart_date,
    region,
    chart_type,
    spotify_track_id,
    rank,
    streams,
    raw_row
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (source, chart_date, region, chart_type, spotify_track_id)
DO NOTHING;


-- 2. Safe Rerun for bronze.track_enrichment (Preserve first-seen snapshot provenance)
INSERT INTO bronze.track_enrichment (
    source,
    ingested_at,
    input_date,
    spotify_track_id,
    market,
    status,
    raw_json
)
VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (source, input_date, market, spotify_track_id)
DO NOTHING;
