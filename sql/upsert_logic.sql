-- ============================================================================
-- IDEMPOTENT INGESTION & SAFE RERUNS
-- Component: Bronze Layer Ingestion (Step 5)
-- Author: Johannes
-- Description: Duplicate-safe INSERT / ON CONFLICT patterns for safe pipeline reruns
--              matching the exact schema in sql/bronze.sql.
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


-- 2. Safe Rerun for bronze.track_enrichment (Update payload if rerun on same snapshot date)
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
DO UPDATE SET
    ingested_at = EXCLUDED.ingested_at,
    status = EXCLUDED.status,
    raw_json = EXCLUDED.raw_json;
